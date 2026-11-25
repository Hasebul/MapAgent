"""Benchmark loading (Section 4.1, Table 4).

``datasets_dir`` layout::

    txt_data/{poi,nearby,routing,trip,unanswerable}/       MapEval-API and MapEval-Textual (300 questions)
    img_data/{poi,nearby,routing,counting,unanswerable}/   MapEval-Visual (400 questions, images in img_data/VData)
    map_qa_data/task_{1..9}/                               MapQA (open-ended)

Every task folder contains ``problems.json`` (``{pid: problem}``) and ``pid_splits.json``
(``{split_name: [pid, ...]}``). MapEval-API and MapEval-Textual share the same questions: the Textual
setting additionally gives the model the textual ``context`` of each question.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .scoring import UNANSWERABLE

DEFAULT_DATASETS_ROOT = Path(__file__).resolve().parent.parent / "datasets_dir"

TASK_DISPLAY_NAMES: Dict[str, str] = {
    "poi": "Place Info",
    "nearby": "Nearby",
    "routing": "Routing",
    "trip": "Trip",
    "counting": "Counting",
    "unanswerable": "Unanswerable",
    **{f"task_{i}": f"Type {i}" for i in range(1, 10)},
}


@dataclass(frozen=True)
class BenchmarkSpec:
    name: str
    data_dir: str
    tasks: Tuple[str, ...]
    use_context: bool = False
    use_image: bool = False
    open_ended: bool = False
    default_model: str = "gpt-3.5-turbo"
    description: str = ""


BENCHMARKS: Dict[str, BenchmarkSpec] = {
    "mapeval_api": BenchmarkSpec(
        name="mapeval_api",
        data_dir="txt_data",
        tasks=("poi", "nearby", "routing", "trip", "unanswerable"),
        description="MapEval-API: answer with Google Maps tools only (no context).",
    ),
    "mapeval_textual": BenchmarkSpec(
        name="mapeval_textual",
        data_dir="txt_data",
        tasks=("poi", "nearby", "routing", "trip", "unanswerable"),
        use_context=True,
        description="MapEval-Textual: the long textual map context is given with each question.",
    ),
    "mapeval_visual": BenchmarkSpec(
        name="mapeval_visual",
        data_dir="img_data",
        tasks=("poi", "nearby", "routing", "counting", "unanswerable"),
        use_image=True,
        default_model="gpt-4o",
        description="MapEval-Visual: a digital map snapshot is given with each question.",
    ),
    "mapqa": BenchmarkSpec(
        name="mapqa",
        data_dir="map_qa_data",
        tasks=tuple(f"task_{i}" for i in range(1, 10)),
        open_ended=True,
        description="MapQA: open-ended questions over OpenStreetMap geo-entities.",
    ),
}


@dataclass
class Example:
    pid: str
    task: str
    question: str
    choices: List[str]
    answer: str
    category: str = ""
    context: str = ""
    image_path: Optional[str] = None
    open_ended: bool = False
    skill: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_image(self) -> bool:
        return bool(self.image_path)


def _pid_key(pid: str):
    return (0, int(pid)) if str(pid).isdigit() else (1, str(pid))


def _resolve_path(base: Path, relative: str) -> Optional[Path]:
    """Resolve ``relative`` under ``base``; path components are matched case-insensitively.

    The problem files refer to ``Vdata/ID_1.PNG`` while the folder is ``VData``; this only works on
    case-insensitive file systems without this lookup.
    """
    direct = base / relative
    if direct.exists():
        return direct
    current = base
    for part in Path(relative).parts:
        if not current.is_dir():
            return None
        matches = [entry for entry in os.listdir(current) if entry.lower() == part.lower()]
        if not matches:
            return None
        current = current / matches[0]
    return current if current.exists() else None


def _valid_answer(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    return str(value).strip() != ""


def load_task(
    task_dir: os.PathLike,
    *,
    split: str = "all",
    use_context: bool = False,
    use_image: bool = False,
    open_ended: Optional[bool] = None,
    limit: int = -1,
) -> Tuple[List[Example], List[Tuple[str, str]]]:
    """Load one task folder. Returns ``(examples, skipped)`` where ``skipped`` lists ``(pid, reason)``."""
    task_dir = Path(task_dir)
    problems_file = task_dir / "problems.json"
    if not problems_file.exists():
        raise FileNotFoundError(f"{problems_file} does not exist")
    with open(problems_file, encoding="utf-8") as handle:
        problems: Dict[str, Dict[str, Any]] = json.load(handle)

    if split == "all":
        pids = sorted(problems, key=_pid_key)
    else:
        with open(task_dir / "pid_splits.json", encoding="utf-8") as handle:
            splits = json.load(handle)
        if split not in splits:
            raise KeyError(f"Split {split!r} not found in {task_dir / 'pid_splits.json'}; available: {sorted(splits)} or 'all'")
        pids = list(dict.fromkeys(str(pid) for pid in splits[split] if str(pid) in problems))

    if open_ended is None:  # MapQA-style problems carry the gold answer as their only "choice"
        open_ended = all(len([c for c in (p.get("choices") or []) if str(c).strip()]) <= 1 for p in problems.values())

    task = task_dir.name
    examples: List[Example] = []
    skipped: List[Tuple[str, str]] = []
    for pid in pids:
        item = problems[pid]
        if not _valid_answer(item.get("answer")):
            skipped.append((pid, "missing gold answer"))
            continue
        answer = str(item["answer"]).strip()
        choices: List[str] = []
        if not open_ended:  # empty placeholder options ("") are not shown to the model
            choices = [str(c).strip() for c in item.get("choices") or [] if isinstance(c, str) and c.strip()]
            if answer != UNANSWERABLE and answer not in choices:
                skipped.append((pid, "gold answer is not one of the options"))
                continue

        context_parts = [str(item.get("hint") or "").strip()]
        if use_context:
            context_parts.append(str(item.get("context") or "").strip())
        context = "\n\n".join(part for part in context_parts if part)

        image_path = None
        if use_image:
            relative = item.get("image_path") or item.get("image")
            resolved = _resolve_path(task_dir.parent, relative) if relative else None
            if resolved is None:
                resolved = _resolve_path(task_dir, relative) if relative else None
            if resolved is None:
                skipped.append((pid, f"image not found: {relative}"))
                continue
            image_path = str(resolved)

        examples.append(
            Example(
                pid=str(pid),
                task=task,
                question=str(item.get("question") or "").strip(),
                choices=choices,
                answer=answer,
                category=str(item.get("classification") or item.get("category") or task),
                context=context,
                image_path=image_path,
                open_ended=bool(open_ended),
                skill=str(item.get("skill") or "").strip(),
                extra={key: item[key] for key in ("type", "concepts", "id") if key in item},
            )
        )
        if 0 < limit <= len(examples):
            break
    return examples, skipped


def benchmark_task_dirs(benchmark: str, datasets_root: os.PathLike = DEFAULT_DATASETS_ROOT, tasks: Optional[Sequence[str]] = None) -> List[Path]:
    spec = BENCHMARKS[benchmark]
    selected = list(tasks) if tasks else list(spec.tasks)
    unknown = [t for t in selected if t not in spec.tasks]
    if unknown:
        raise ValueError(f"Unknown task(s) {unknown} for {benchmark}; available: {list(spec.tasks)}")
    return [Path(datasets_root) / spec.data_dir / task for task in selected]
