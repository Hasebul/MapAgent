#!/usr/bin/env python
"""Score MapAgent result files: overall and per-category accuracy, and average cost per query.

Examples
--------
    python evaluate.py results/mapeval_api/mapagent_gpt-3.5-turbo
    python evaluate.py results/mapqa/mapagent_gpt-3.5-turbo --numeric_tolerance 0.01
    python evaluate.py results/mapeval_api/mapagent_gpt-3.5-turbo/trip.jsonl --output trip_summary.json

Predictions are re-scored from the saved records, so the scoring options can be changed without re-running.
``--legacy_fuzzy`` reproduces the original release's lenient scorer (fuzzy similarity >= 30%), which accepts
many wrong options; use it only to compare with old numbers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mapagent.data import TASK_DISPLAY_NAMES  # noqa: E402
from mapagent.scoring import DEFAULT_NUMERIC_TOLERANCE, format_summary, load_records, summarize  # noqa: E402


def _collect(path: Path):
    """Return ``(files, task_order, title)`` for a run directory or a single JSONL file."""
    if path.is_dir():
        files = sorted(path.glob("*.jsonl"))
        task_order: List[str] = []
        config = path / "config.json"
        if config.exists():
            task_order = json.loads(config.read_text(encoding="utf-8")).get("tasks", [])
        return files, task_order, str(path)
    return [path], [], str(path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help="Run directories (containing <task>.jsonl files) or JSONL files.")
    parser.add_argument("--numeric_tolerance", type=float, default=DEFAULT_NUMERIC_TOLERANCE,
                        help="Relative tolerance for numeric open-ended answers (MapQA).")
    parser.add_argument("--legacy_fuzzy", action="store_true",
                        help="Use the original release's fuzzy scorer (similarity >= 30%%).")
    parser.add_argument("--output", help="Write the summaries to this JSON file.")
    args = parser.parse_args(argv)

    summaries = {}
    for raw in args.paths:
        path = Path(raw)
        if not path.exists():
            print(f"[error] {path} does not exist")
            return 1
        files, task_order, title = _collect(path)
        if not files:
            print(f"[error] no .jsonl result files in {path}")
            return 1
        summary = summarize(
            load_records(files),
            task_order=task_order,
            display_names=TASK_DISPLAY_NAMES,
            legacy_fuzzy=args.legacy_fuzzy,
            numeric_tolerance=args.numeric_tolerance,
        )
        summaries[title] = summary
        print(f"\n## {title}\n\n{format_summary(summary)}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(summaries, handle, indent=2, ensure_ascii=False)
        print(f"\nSaved to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
