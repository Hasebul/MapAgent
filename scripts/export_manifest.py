#!/usr/bin/env python
"""Write (or check) the question manifests in ``datasets_dir/manifests/``.

One CSV per data folder; one row per question with: task, pid, category, gold answer, number of options shown to
the model, the splits of ``pid_splits.json`` that contain it, whether ``run.py`` evaluates it (``--split all``) and
why not, and a short SHA-1 of the question text so that two copies of the data can be compared.

    python scripts/export_manifest.py           # (re)write datasets_dir/manifests/*.csv
    python scripts/export_manifest.py --check   # exit with status 1 if the data no longer matches the manifests
"""

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mapagent.data import BENCHMARKS, DEFAULT_DATASETS_ROOT, load_task  # noqa: E402

FOLDERS = {  # data folder -> (preset that defines its tasks, presets that use it)
    "txt_data": ("mapeval_api", "mapeval_api, mapeval_textual"),
    "img_data": ("mapeval_visual", "mapeval_visual"),
    "map_qa_data": ("mapqa", "mapqa"),
}
COLUMNS = ["task", "pid", "category", "answer", "num_options", "splits", "evaluated", "note", "question_sha1"]


def build(folder: str, datasets_root: Path) -> str:
    spec = BENCHMARKS[FOLDERS[folder][0]]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for task in spec.tasks:
        task_dir = datasets_root / folder / task
        problems = json.loads((task_dir / "problems.json").read_text(encoding="utf-8"))
        splits = json.loads((task_dir / "pid_splits.json").read_text(encoding="utf-8"))
        examples, skipped = load_task(task_dir, open_ended=spec.open_ended or None)
        evaluated = {ex.pid: ex for ex in examples}
        reasons = dict(skipped)
        for pid in sorted(problems, key=lambda p: (0, int(p)) if p.isdigit() else (1, p)):
            item = problems[pid]
            example = evaluated.get(pid)
            writer.writerow([
                task,
                pid,
                item.get("classification") or item.get("category") or task,
                example.answer if example else item.get("answer"),
                len(example.choices) if example else "",
                "|".join(name for name, ids in splits.items() if pid in map(str, ids)),
                "yes" if example else "no",
                reasons.get(pid, ""),
                hashlib.sha1(str(item.get("question", "")).encode("utf-8")).hexdigest()[:12],
            ])
    return out.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datasets_root", type=Path, default=DEFAULT_DATASETS_ROOT)
    parser.add_argument("--check", action="store_true", help="Compare with the existing manifests instead of writing.")
    args = parser.parse_args()
    target = args.datasets_root / "manifests"
    status = 0
    for folder, (_, presets) in FOLDERS.items():
        content = build(folder, args.datasets_root)
        path = target / f"{folder}.csv"
        rows = content.count("\n") - 1
        if args.check:
            same = path.exists() and path.read_text(encoding="utf-8") == content
            print(f"{path}: {'OK' if same else 'DIFFERENT'} ({rows} questions; {presets})")
            status |= 0 if same else 1
        else:
            target.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path} ({rows} questions; {presets})")
    return status


if __name__ == "__main__":
    sys.exit(main())
