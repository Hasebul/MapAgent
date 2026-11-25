#!/usr/bin/env python
"""Build ``problems.json`` / ``pid_splits.json`` of a MapQA task folder from its ``data.json``.

This is how ``datasets_dir/map_qa_data/task_*/problems.json`` were produced:

    python scripts/prepare_mapqa.py datasets_dir/map_qa_data/task_9 --overwrite

The question is extended with an instruction and the geo-entity context. MapQA is open-ended: ``choices``
stores only the gold answer (for compatibility with the MapEval format) and is never shown to the model;
``mapagent.data.load_task`` detects such tasks automatically.

Note: the released ``pid_splits.json`` files contain extra splits ("test", "problems") that this script does not
recreate; it writes a single "minitest" split with every question.
"""

import argparse
import json
from pathlib import Path


def build(task_dir: Path, overwrite: bool) -> None:
    targets = [task_dir / "problems.json", task_dir / "pid_splits.json"]
    if not overwrite and any(path.exists() for path in targets):
        raise SystemExit(f"{task_dir}: problems.json / pid_splits.json exist; pass --overwrite to replace them")
    with open(task_dir / "data.json", encoding="utf-8") as handle:
        data = json.load(handle)

    problems, pids = {}, []
    for number, row in enumerate(data, 1):
        item = dict(row)
        item["question"] = (
            f"{row['question']} All the location are inside California. In final answer pick only one location. "
            f"Context: {row['context']}"
        )
        item["choices"] = [row["answer"]]
        item["hint"] = ""
        item["skill"] = "Fetch context from corresponding google map api and based on the context answer the question "
        item["solution"] = "To find the answer, You have to choose one option from the MCQ"
        item["split"] = "test"
        item["classification"] = row["type"]
        problems[str(number)] = item
        pids.append(str(number))

    with open(targets[0], "w", encoding="utf-8") as handle:
        json.dump(problems, handle, ensure_ascii=False, indent=4)
    with open(targets[1], "w", encoding="utf-8") as handle:
        json.dump({"minitest": pids}, handle, ensure_ascii=False, indent=4)
    print(f"{task_dir}: wrote {len(problems)} problems")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task_dirs", nargs="+", type=Path, help="MapQA task folders containing data.json")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    for folder in args.task_dirs:
        build(folder, args.overwrite)
