#!/usr/bin/env python
"""OctoTools baseline (Lu et al., 2025) on the MapAgent benchmarks.

OctoTools is a flat (single-layer) planner-executor agent: at every step it selects one tool, writes the
tool command, executes it, and verifies whether it can stop. Here it is given the same four map tools as
MapAgent (Trip, Directions/Route, Nearby, POI/PlaceInfo, implemented by ``mapagent.map_tools``) plus the
generalist solution generator, and it uses MapAgent's data loader and answer format. Results are written in
the format of ``run.py`` and can be scored with ``python evaluate.py <run directory>``.

Example:
    python baselines/octotools/solve.py --benchmark mapeval_api --model gpt-4o-mini --limit 5

Note: OctoTools executes the Python tool commands written by the LLM (``exec``); run it in an isolated
environment.
"""

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
for _path in (str(REPO), str(HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import openai  # noqa: E402

from mapagent.data import BENCHMARKS, DEFAULT_DATASETS_ROOT, TASK_DISPLAY_NAMES, load_task  # noqa: E402
from mapagent.map_tools import is_fatal_maps_error  # noqa: E402
from mapagent.scoring import (  # noqa: E402
    extract_choice,
    extract_open_answer,
    format_options,
    format_summary,
    letter_to_choice,
    load_records,
    score_prediction,
    summarize,
)
from octotools.engine.openai import USAGE  # noqa: E402
from octotools.models.executor import Executor  # noqa: E402
from octotools.models.initializer import Initializer  # noqa: E402
from octotools.models.memory import Memory  # noqa: E402
from octotools.models.planner import Planner  # noqa: E402
from octotools.models.utils import make_json_serializable_truncated  # noqa: E402
from octotools.tools import _maps  # noqa: E402
from run import _slug, resolve_tasks  # noqa: E402

MAP_TOOLS = ["Trip_Tool", "Nearby_Tool", "Directions_Tool", "POI_Tool", "Generalist_Solution_Generator_Tool"]


def build_query(example) -> str:
    parts = [example.question]
    if example.context:
        parts.append(f"Context: {example.context}")
    if example.open_ended:
        parts.append('Give a short final answer and conclude with "the answer is <answer>".')
    else:
        parts.append(f"Options: {format_options(example.choices)}")
        parts.append(
            'Conclude with "the answer is X", where X is the option letter, or "the answer is Unanswerable" '
            "if none of the options is correct."
        )
    return "\n\n".join(parts)


def solve_one(planner: Planner, executor: Executor, example, args, cache_dir: Path) -> dict:
    memory = Memory()  # a fresh memory for every question
    executor.set_query_cache_dir(str(cache_dir / f"{example.task}_{example.pid}"))
    USAGE.reset()
    _maps.USAGE.reset()
    start = time.time()
    question, image = build_query(example), example.image_path

    query_analysis = planner.analyze_query(question, image)
    steps, map_tool_calls = 0, 0
    while steps < args.max_steps and (time.time() - start) < args.max_time:
        steps += 1
        next_step = planner.generate_next_step(question, image, query_analysis, memory, steps, args.max_steps)
        context, sub_goal, tool_name = planner.extract_context_subgoal_and_tool(next_step)
        if tool_name is None or tool_name not in planner.available_tools:
            command, result = "No command was generated.", f"Tool {tool_name!r} is not available."
        else:
            tool_command = executor.generate_tool_command(
                question, image, context, sub_goal, tool_name, planner.toolbox_metadata[tool_name]
            )
            _, command = executor.extract_explanation_and_command(tool_command)
            result = make_json_serializable_truncated(executor.execute_tool_command(tool_name, command))
            if tool_name in MAP_TOOLS[:4]:
                map_tool_calls += max(1, command.count("tool.execute("))
        memory.add_action(steps, tool_name, sub_goal, command, result)
        verification = planner.verificate_context(question, image, query_analysis, memory)
        if planner.extract_conclusion(verification) == "STOP":
            break

    output = planner.generate_direct_output(question, image, memory)
    output_text = output if isinstance(output, str) else json.dumps(output, default=str)
    if example.open_ended:
        letter, prediction = None, extract_open_answer(output_text)
    else:
        letter = extract_choice(output_text, len(example.choices))
        prediction = letter_to_choice(letter, example.choices)
    usage = {
        "llm_calls": USAGE.llm_calls,
        "prompt_tokens": USAGE.prompt_tokens,
        "completion_tokens": USAGE.completion_tokens,
        "total_tokens": USAGE.prompt_tokens + USAGE.completion_tokens,
        "map_tool_calls": map_tool_calls,
        "map_api_calls": _maps.USAGE.snapshot().map_api_calls,
    }
    return {
        "pid": example.pid,
        "task": example.task,
        "category": example.category,
        "question": example.question,
        "choices": example.choices,
        "gold": example.answer,
        "open_ended": example.open_ended,
        "prediction": prediction,
        "prediction_letter": letter,
        "correct": score_prediction(prediction, example.answer, open_ended=example.open_ended),
        "solution": output_text,
        "trace": {"query_analysis": str(query_analysis), "memory": memory.get_actions(), "steps": steps},
        "usage": usage,
        "time_sec": round(time.time() - start, 3),
        "error": None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="OctoTools baseline on the MapAgent benchmarks.")
    parser.add_argument("--benchmark", choices=sorted(BENCHMARKS))
    parser.add_argument("--tasks", nargs="+")
    parser.add_argument("--data_root", help="A single task folder instead of a preset.")
    parser.add_argument("--datasets_root", default=str(DEFAULT_DATASETS_ROOT))
    parser.add_argument("--split", default="all")
    parser.add_argument("--limit", type=int, default=-1)
    parser.add_argument("--use_context", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--use_image", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--open_ended", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--model", "--llm_engine_name", dest="model", help="LLM (default: the preset's paper setting).")
    parser.add_argument("--enabled_tools", help="Comma-separated tool classes (default: the map tools + generalist).")
    parser.add_argument("--max_steps", type=int, default=10)
    parser.add_argument("--max_time", type=int, default=300, help="Seconds per question.")
    parser.add_argument("--output_dir", default="results")
    parser.add_argument("--label", help="Run name (default: octotools_<model>).")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--rerun_errors", action="store_true")
    args = parser.parse_args(argv)

    run_name, default_model, tasks = resolve_tasks(args)
    model = args.model or default_model
    tools = args.enabled_tools.split(",") if args.enabled_tools else list(MAP_TOOLS)
    if not args.enabled_tools and any(task.use_image for task in tasks):
        tools.append("Image_Captioner_Tool")

    initializer = Initializer(enabled_tools=tools, model_string=model)
    planner = Planner(model, toolbox_metadata=initializer.toolbox_metadata, available_tools=initializer.available_tools)
    run_dir = Path(args.output_dir) / run_name / (args.label or _slug(f"octotools_{model}"))
    run_dir.mkdir(parents=True, exist_ok=True)
    executor = Executor(model, root_cache_dir=str(run_dir / "cache"))
    with open(run_dir / "config.json", "w", encoding="utf-8") as handle:
        json.dump({"benchmark": run_name, "tasks": [t.name for t in tasks], "method": "octotools", "model": model,
                   "tools": initializer.available_tools, "arguments": vars(args)}, handle, indent=2)

    for task in tasks:
        examples, skipped = load_task(task.path, split=args.split, use_context=task.use_context,
                                      use_image=task.use_image, open_ended=task.open_ended, limit=args.limit)
        out_file = run_dir / f"{task.name}.jsonl"
        if args.overwrite and out_file.exists():
            out_file.unlink()
        done = {str(r.get("pid")): r for r in load_records([out_file])} if out_file.exists() else {}
        todo = [ex for ex in examples if ex.pid not in done or (args.rerun_errors and done[ex.pid].get("error"))]
        print(f"\n[{task.name}] {len(examples)} questions ({len(skipped)} skipped), {len(todo)} to run")
        with open(out_file, "a", encoding="utf-8") as handle:
            for example in todo:
                try:
                    record = solve_one(planner, executor, example, args, run_dir / "cache")
                except (openai.AuthenticationError, openai.PermissionDeniedError, openai.NotFoundError) as exc:
                    raise SystemExit(f"Aborting: {type(exc).__name__}: {exc}")
                except Exception as exc:  # noqa: BLE001
                    if is_fatal_maps_error(exc):
                        raise SystemExit(f"Aborting: {exc}")
                    record = {"pid": example.pid, "task": example.task, "gold": example.answer,
                              "open_ended": example.open_ended, "prediction": None, "correct": False,
                              "error": f"{type(exc).__name__}: {exc}"}
                handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                handle.flush()
                print(f"  pid={example.pid} prediction={record['prediction']!r} gold={example.answer!r} correct={record['correct']}")

    summary = summarize(load_records(sorted(run_dir.glob("*.jsonl"))), task_order=[t.name for t in tasks],
                        display_names=TASK_DISPLAY_NAMES)
    with open(run_dir / "summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print(f"\n{run_name} | OctoTools ({model})\n{format_summary(summary)}")


if __name__ == "__main__":
    main()
