#!/usr/bin/env python
"""Run MapAgent on a benchmark (or on one task folder) and save one JSON record per question.

Examples
--------
    # MapEval-API with GPT-3.5-Turbo (paper setting)
    python run.py --benchmark mapeval_api --model gpt-3.5-turbo

    # MapEval-Visual with GPT-4o, only the counting task, first 10 questions
    python run.py --benchmark mapeval_visual --model gpt-4o --tasks counting --limit 10

    # Qwen-2.5-72B through OpenRouter (any OpenAI-compatible endpoint works the same way)
    python run.py --benchmark mapqa --model qwen/qwen-2.5-72b-instruct --base_url https://openrouter.ai/api/v1

    # A single task folder
    python run.py --data_root datasets_dir/txt_data/trip --model gpt-4o-mini

Results are written to ``<output_dir>/<benchmark>/<label>/<task>.jsonl`` (one record per question) together
with ``config.json`` and ``summary.json``. Interrupted runs resume where they stopped.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mapagent import __version__  # noqa: E402
from mapagent.data import (  # noqa: E402
    BENCHMARKS,
    DEFAULT_DATASETS_ROOT,
    TASK_DISPLAY_NAMES,
    benchmark_task_dirs,
    load_task,
)
from mapagent.llm import PROVIDERS, LLMClient, is_fatal_llm_error  # noqa: E402
from mapagent.map_tools import MapsAuthError, MapsClient, is_fatal_maps_error  # noqa: E402
from mapagent.scoring import format_summary, load_records, summarize  # noqa: E402
from mapagent.solver import (  # noqa: E402
    COMPONENTS,
    DEFAULT_MAX_TOKENS,
    MapAgent,
    SolverConfig,
    canonical_module,
    finalize_modules,
)
from mapagent.usage import UsageTracker  # noqa: E402

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **_):  # type: ignore
        return iterable

_MODEL_FLAGS = {
    "planner": ("--planner_model", "--policy_engine"),
    "visual_place_recognizer": ("--vpr_model",),
    "map_agent": ("--map_agent_model",),
    "sequencer": ("--sequencer_model",),
    "solution_generator": ("--sg_model", "--sg_engine"),
    "answer_generator": ("--ag_model",),
}
_MAX_TOKEN_FLAGS = {
    "planner": ("--planner_max_tokens", "--policy_max_tokens"),
    "visual_place_recognizer": ("--vpr_max_tokens",),
    "map_agent": ("--map_agent_max_tokens",),
    "sequencer": ("--sequencer_max_tokens",),
    "solution_generator": ("--sg_max_tokens",),
    "answer_generator": ("--ag_max_tokens",),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run MapAgent on MapEval-API / MapEval-Textual / MapEval-Visual / MapQA.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    data = parser.add_argument_group("data")
    data.add_argument("--benchmark", choices=sorted(BENCHMARKS), help="Benchmark preset.")
    data.add_argument("--tasks", nargs="+", help="Subset of the preset's tasks (default: all of them).")
    data.add_argument("--data_root", help="Run one task folder (containing problems.json) instead of a preset.")
    data.add_argument("--datasets_root", default=str(DEFAULT_DATASETS_ROOT), help="Location of datasets_dir.")
    data.add_argument("--split", "--test_split", default="all", help="'all' or a split of pid_splits.json (e.g. minitest).")
    data.add_argument("--limit", "--test_number", type=int, default=-1, help="Questions per task (-1: all).")
    data.add_argument("--use_context", action=argparse.BooleanOptionalAction, default=None,
                      help="Give the textual map context to the model (default: from the preset).")
    data.add_argument("--use_image", action=argparse.BooleanOptionalAction, default=None,
                      help="Give the map image to the model (default: from the preset / auto-detected).")
    data.add_argument("--open_ended", action=argparse.BooleanOptionalAction, default=None,
                      help="Treat questions as open-ended (default: from the preset / auto-detected).")

    method = parser.add_argument_group("method")
    method.add_argument("--mode", choices=["mapagent", "base"], default="mapagent",
                        help="'mapagent': planner + modules; 'base': the backbone model alone (solution + answer generators).")
    method.add_argument("--modules", nargs="+", help="Fixed module sequence (skips the planner), e.g. map_service solution_generator answer_generator.")
    method.add_argument("--answer_generator", choices=["llm", "rule"], default="llm",
                        help="'llm': verify the solution and extract the answer with the LLM (paper); 'rule': regex extraction only.")
    method.add_argument("--sg_patience", type=int, default=3, help="Solution Generator attempts until it states an answer.")
    method.add_argument("--map_max_rounds", type=int, default=3, help="Maximum tool-calling rounds of the Map-Tool Agent.")
    method.add_argument("--map_max_workers", type=int, default=5, help="Parallel tool calls of the Map-Tool Agent.")
    method.add_argument("--image_to_planner", action=argparse.BooleanOptionalAction, default=True,
                        help="Show the map image to the planner (visual questions).")
    method.add_argument("--image_to_solution_generator", action=argparse.BooleanOptionalAction, default=True,
                        help="Show the map image to the Solution Generator (visual questions).")

    llm = parser.add_argument_group("LLM backend")
    llm.add_argument("--model", "--llm", help="Model (or Azure deployment) used by every module; default: the preset's paper setting.")
    for component, flags in _MODEL_FLAGS.items():
        llm.add_argument(*flags, dest=f"{component}_model", help=f"Override the model of the {component}.")
    llm.add_argument("--temperature", type=float, default=0.0)
    for component, flags in _MAX_TOKEN_FLAGS.items():
        llm.add_argument(*flags, dest=f"{component}_max_tokens", type=int, default=DEFAULT_MAX_TOKENS[component])
    llm.add_argument("--provider", choices=PROVIDERS, default=os.getenv("MAPAGENT_LLM_PROVIDER", "openai"))
    llm.add_argument("--base_url", help="OpenAI-compatible endpoint (OpenRouter, vLLM, ...) or the Azure endpoint.")
    llm.add_argument("--api_version", help="Azure OpenAI API version.")
    llm.add_argument("--max_retries", type=int, default=5, help="Retries of transient API errors.")
    llm.add_argument("--timeout", type=float, default=120.0, help="Timeout of one LLM request (seconds).")

    output = parser.add_argument_group("output")
    output.add_argument("--output_dir", "--output_root", default="results")
    output.add_argument("--label", help="Run name (default: <mode>_<model>).")
    output.add_argument("--overwrite", action="store_true", help="Start from scratch instead of resuming.")
    output.add_argument("--rerun_errors", action="store_true", help="Re-run questions whose previous attempt failed.")
    output.add_argument("--verbose", "-v", action="store_true", help="Print module outputs for every question.")
    return parser


@dataclass
class TaskRun:
    name: str
    path: Path
    use_context: bool
    use_image: bool
    open_ended: Optional[bool]


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "run"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        return
    load_dotenv(ROOT / ".env")
    load_dotenv()


def resolve_tasks(args: argparse.Namespace):
    """Return ``(run_name, default_model, [TaskRun, ...])``."""
    if bool(args.benchmark) == bool(args.data_root):
        raise SystemExit("error: pass exactly one of --benchmark or --data_root")
    if args.benchmark:
        spec = BENCHMARKS[args.benchmark]
        use_context = spec.use_context if args.use_context is None else args.use_context
        use_image = spec.use_image if args.use_image is None else args.use_image
        open_ended = (spec.open_ended or None) if args.open_ended is None else args.open_ended
        tasks = [
            TaskRun(path.name, path, use_context, use_image, open_ended)
            for path in benchmark_task_dirs(args.benchmark, args.datasets_root, args.tasks)
        ]
        return spec.name, spec.default_model, tasks

    path = Path(args.data_root)
    with open(path / "problems.json", encoding="utf-8") as handle:
        first = next(iter(json.load(handle).values()), {})
    use_image = ("image_path" in first) if args.use_image is None else args.use_image
    task = TaskRun(path.name, path, bool(args.use_context), use_image, args.open_ended)
    return "custom", ("gpt-4o" if use_image else "gpt-3.5-turbo"), [task]


def _read_done(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    return {str(record.get("pid")): record for record in load_records([path])}


def main(argv: Optional[List[str]] = None, *, llm: Any = None, maps: Any = None) -> Dict[str, Any]:
    """Entry point. ``llm`` / ``maps`` can be injected (used by the offline tests)."""
    _load_dotenv()  # before building the parser: MAPAGENT_LLM_PROVIDER may come from .env
    args = build_parser().parse_args(argv)
    if args.model in ("chameleon", "cot"):  # flag values of the original release
        print(f"Note: '--model {args.model}' is deprecated; use '--mode {'mapagent' if args.model == 'chameleon' else 'base'}' "
              "and pass the LLM name with --model.")
        args.mode, args.model = ("mapagent" if args.model == "chameleon" else "base"), None
    run_name, default_model, tasks = resolve_tasks(args)
    model = args.model or default_model

    config = SolverConfig(
        mode=args.mode,
        model=model,
        module_models={c: getattr(args, f"{c}_model") for c in COMPONENTS if getattr(args, f"{c}_model", None)},
        temperature=args.temperature,
        max_tokens={c: getattr(args, f"{c}_max_tokens") for c in COMPONENTS},
        sg_patience=args.sg_patience,
        answer_generator=args.answer_generator,
        map_max_rounds=args.map_max_rounds,
        map_max_workers=args.map_max_workers,
        fixed_modules=args.modules,
        image_to_planner=args.image_to_planner,
        image_to_solution_generator=args.image_to_solution_generator,
        verbose=args.verbose,
    )
    unknown = [m for m in args.modules or [] if canonical_module(m) is None]
    if unknown:
        raise SystemExit(f"error: unknown module(s) in --modules: {unknown}")

    usage = UsageTracker()
    try:
        if llm is None:
            llm = LLMClient(
                provider=args.provider,
                base_url=args.base_url,
                api_version=args.api_version,
                max_retries=args.max_retries,
                timeout=args.timeout,
                usage=usage,
            )
        needs_maps = args.mode == "mapagent" and (
            not args.modules or "map_service" in finalize_modules(args.modules, True)
        )
        if maps is None and needs_maps:
            maps = MapsClient(usage=llm.usage)
    except (ValueError, MapsAuthError) as exc:
        raise SystemExit(f"Configuration error: {exc}")

    agent = MapAgent(config, llm, maps if needs_maps else None)
    label = args.label or _slug(f"{args.mode}_{model}")
    run_dir = Path(args.output_dir) / run_name / label
    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "config.json", "w", encoding="utf-8") as handle:
        json.dump(
            {
                "version": __version__,
                "benchmark": run_name,
                "tasks": [t.name for t in tasks],
                "models": {c: config.model_for(c) for c in COMPONENTS},
                "arguments": vars(args),
                "started": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            handle,
            indent=2,
            ensure_ascii=False,
        )
    print(f"Run directory: {run_dir}")
    print(f"Mode: {args.mode} | model: {model} | provider: {args.provider}")

    for task in tasks:
        examples, skipped = load_task(
            task.path,
            split=args.split,
            use_context=task.use_context,
            use_image=task.use_image,
            open_ended=task.open_ended,
            limit=args.limit,
        )
        for pid, reason in skipped:
            print(f"[{task.name}] skipping pid {pid}: {reason}")
        out_file = run_dir / f"{task.name}.jsonl"
        if args.overwrite and out_file.exists():
            out_file.unlink()
        done = _read_done(out_file)
        todo = [
            ex for ex in examples
            if ex.pid not in done or (args.rerun_errors and done[ex.pid].get("error"))
        ]
        print(f"\n[{task.name}] {len(examples)} questions, {len(examples) - len(todo)} already done, {len(todo)} to run")

        with open(out_file, "a", encoding="utf-8") as handle:
            for example in tqdm(todo, desc=TASK_DISPLAY_NAMES.get(task.name, task.name)):
                try:
                    record = agent.solve(example)
                except Exception as exc:  # noqa: BLE001
                    if is_fatal_llm_error(exc) or is_fatal_maps_error(exc):
                        raise SystemExit(f"\nAborting: {type(exc).__name__}: {exc}\nCheck your API keys / model names.")
                    raise
                handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                handle.flush()
                done[example.pid] = record
                if args.verbose:
                    print(
                        f"  pid={record['pid']} modules={record['modules']} prediction={record['prediction']!r} "
                        f"gold={record['gold']!r} correct={record['correct']} error={record['error']}"
                    )
        task_records = [done[ex.pid] for ex in examples if ex.pid in done]
        correct = sum(bool(r.get("correct")) for r in task_records)
        print(f"[{task.name}] accuracy: {100.0 * correct / max(len(task_records), 1):.2f}% ({correct}/{len(task_records)})")

    records = load_records(sorted(run_dir.glob("*.jsonl")))
    summary = summarize(records, task_order=[t.name for t in tasks], display_names=TASK_DISPLAY_NAMES)
    with open(run_dir / "summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)
    print(f"\n{run_name} | {label}\n{format_summary(summary)}")
    return summary


if __name__ == "__main__":
    main()
