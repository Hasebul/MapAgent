"""Answer extraction, scoring and result aggregation.

Scoring
-------
* Multiple-choice questions (MapEval-API/Textual/Visual): the prediction is correct iff the selected option
  (or "Unanswerable") is exactly the gold option, after whitespace/case normalisation.
* Open-ended questions (MapQA): correct iff the extracted answer equals the gold answer after normalisation,
  contains it as a whole phrase, or - when the gold answer is a quantity such as "21694.66 meters" - is within
  a relative tolerance of it (5% by default) after unit conversion.

``legacy_fuzzy=True`` reproduces the scorer of the original release (fuzzy string similarity >= 30%). That scorer
accepts about half of the *wrong* MapEval options as correct, so use it only to compare with older numbers.
"""

from __future__ import annotations

import re
import unicodedata
from collections import OrderedDict
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

OPTION_LETTERS = "ABCDEFGH"
UNANSWERABLE = "Unanswerable"
LEGACY_FALLBACK_PREDICTION = "Not able to answer the question"
LEGACY_FUZZY_THRESHOLD = 30
DEFAULT_NUMERIC_TOLERANCE = 0.05

# ----------------------------------------------------------------------------- formatting
def format_options(choices: Sequence[str]) -> str:
    return " ".join(f"({OPTION_LETTERS[i]}) {choice}" for i, choice in enumerate(choices))


def letter_to_choice(letter: Optional[str], choices: Sequence[str]) -> Optional[str]:
    """Map "A"/"B"/... (or "Unanswerable") to the corresponding answer text."""
    if letter is None:
        return None
    if letter == UNANSWERABLE:
        return UNANSWERABLE
    index = OPTION_LETTERS.find(letter)
    return choices[index] if 0 <= index < len(choices) else None


# ----------------------------------------------------------------------------- extraction
_PREFIX = (
    r"(?i:\banswer\b)\s*(?:(?i:is|should\s+be|would\s+be|will\s+be|:|=)\s*)?"
    r"(?:(?i:option|choice)\s*)?[:\-]?\s*[*_`'\"\s]*"
)
_ANSWER_LETTER = re.compile(_PREFIX + r"[(\[]?\s*([A-H])\s*[)\]]?(?![A-Za-z0-9])")
_ANSWER_UNANSWERABLE = re.compile(_PREFIX + r"(?i:un-?answerable)")
_UNANSWERABLE_PHRASE = re.compile(
    r"(?i)\b(?:un-?answerable|cannot\s+be\s+answered|can\s*not\s+be\s+determined|is\s+not\s+answerable)\b"
)
_PAREN_LETTER = re.compile(r"[(\[]([A-H])[)\]]")
_OPEN_ANSWER = re.compile(r"(?i:\b(?:final\s+)?answer\s*(?:is\s*:?|:)\s*)(.+)")
_EDGE_NOISE = re.compile(r"^[\s*_`\"'“”‘’]+|[\s*_`\"'“”‘’.]+$")


def extract_choice(text: Optional[str], num_choices: int, *, strict: bool = False) -> Optional[str]:
    """Extract the selected option letter (or ``UNANSWERABLE``) from a model response.

    The last explicit statement ("the answer is B", "Answer: (B)", "the answer is Unanswerable") wins.
    With ``strict=False`` a few weaker cues are also used (an "unanswerable" statement, a trailing "(B)",
    or a single option text mentioned at the end of the response).
    """
    if not text:
        return None
    candidates: List[Tuple[int, str]] = []
    for match in _ANSWER_LETTER.finditer(text):
        if OPTION_LETTERS.index(match.group(1)) < num_choices:
            candidates.append((match.start(), match.group(1)))
    for match in _ANSWER_UNANSWERABLE.finditer(text):
        candidates.append((match.start(), UNANSWERABLE))
    if candidates:
        return max(candidates)[1]
    if strict:
        return None
    if _UNANSWERABLE_PHRASE.search(text):
        return UNANSWERABLE
    tail = text[-300:]
    letters = [m.group(1) for m in _PAREN_LETTER.finditer(tail) if OPTION_LETTERS.index(m.group(1)) < num_choices]
    if letters:
        return letters[-1]
    return None


def extract_choice_by_text(text: Optional[str], choices: Sequence[str]) -> Optional[str]:
    """Fallback: the letter of the only option whose text appears at the end of ``text``."""
    if not text:
        return None
    tail = normalize_text(text[-400:])
    hits = [OPTION_LETTERS[i] for i, c in enumerate(choices) if len(c.strip()) >= 3 and normalize_text(c) in tail]
    return hits[0] if len(hits) == 1 else None


def extract_open_answer(text: Optional[str]) -> Optional[str]:
    """Extract a short free-form answer ("the answer is X")."""
    if not text:
        return None
    matches = list(_OPEN_ANSWER.finditer(text))
    if matches:
        candidate = matches[-1].group(1)
    else:
        lines = [line for line in text.splitlines() if line.strip()]
        candidate = lines[-1] if lines else ""
    candidate = _EDGE_NOISE.sub("", candidate).strip()
    if re.fullmatch(r"(?i)un-?answerable", candidate):
        return UNANSWERABLE
    return candidate or None


def has_explicit_answer(text: Optional[str], *, open_ended: bool, num_choices: int) -> bool:
    """True if ``text`` states its final answer explicitly ("the answer is ...")."""
    if not text:
        return False
    if open_ended:
        return _OPEN_ANSWER.search(text) is not None
    return extract_choice(text, num_choices, strict=True) is not None


# ----------------------------------------------------------------------------- scoring
def normalize_text(text: Any) -> str:
    text = unicodedata.normalize("NFKC", str(text)).lower()
    return re.sub(r"\s+", " ", text).strip()


def _normalize_open(text: Any) -> str:
    text = unicodedata.normalize("NFKC", str(text)).lower()
    text = re.sub(r"[’‘`´]", "'", text)
    text = re.sub(r"[^\w\s'.]", " ", text.replace("_", " "))
    return re.sub(r"\s+", " ", text).strip(" .'")


_UNIT_FACTORS = {
    "m": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0, "metres": 1.0,
    "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0, "kilometre": 1000.0, "kilometres": 1000.0,
    "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
}
_QUANTITY = re.compile(
    r"(-?\d[\d,]*(?:\.\d+)?)\s*(kilometers?|kilometres?|km|meters?|metres?|miles?|mi|feet|foot|ft|m)?\b",
    re.IGNORECASE,
)


def _parse_quantity(text: str, full: bool = False) -> Optional[Tuple[float, Optional[float]]]:
    """Return ``(number, factor)``; ``factor`` converts the number to meters (``None`` without a unit)."""
    value = str(text).strip().lower().rstrip(".")
    match = _QUANTITY.fullmatch(value) if full else _QUANTITY.search(value)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    unit = match.group(2)
    return number, (_UNIT_FACTORS[unit] if unit else None)


def _score_open(prediction: str, gold: str, tolerance: float) -> bool:
    gold_quantity = _parse_quantity(gold, full=True)
    if gold_quantity is not None:
        predicted = _parse_quantity(prediction)
        if predicted is None:
            return False
        (gold_number, gold_factor), (number, factor) = gold_quantity, predicted
        if gold_factor and factor:
            gold_value, value = gold_number * gold_factor, number * factor
        else:  # a side without a unit is read in the unit of the other side
            gold_value, value = gold_number, number
        return abs(value - gold_value) <= tolerance * max(abs(gold_value), 1e-9)
    gold_norm, pred_norm = _normalize_open(gold), _normalize_open(prediction)
    if not gold_norm or not pred_norm:
        return False
    if gold_norm == pred_norm:
        return True
    return re.search(rf"(?<!\w){re.escape(gold_norm)}(?!\w)", pred_norm) is not None


def legacy_fuzzy_equal(prediction: Optional[str], gold: Any, threshold: int = LEGACY_FUZZY_THRESHOLD) -> bool:
    """The original release's ``safe_equal`` for strings (``fuzz.ratio >= 30``)."""
    pred = LEGACY_FALLBACK_PREDICTION if prediction is None else str(prediction)
    p, g = pred.strip().lower(), str(gold).strip().lower()
    if p == g:
        return True
    if not p or not g:
        return False
    return int(round(100 * SequenceMatcher(None, p, g).ratio())) >= threshold


def score_prediction(
    prediction: Optional[str],
    gold: Any,
    *,
    open_ended: bool,
    legacy_fuzzy: bool = False,
    numeric_tolerance: float = DEFAULT_NUMERIC_TOLERANCE,
) -> bool:
    if gold is None:
        return False
    if legacy_fuzzy:
        return legacy_fuzzy_equal(prediction, gold)
    if prediction is None:
        return False
    if open_ended:
        return _score_open(str(prediction), str(gold), numeric_tolerance)
    return normalize_text(prediction) == normalize_text(gold)


# ----------------------------------------------------------------------------- result files
def load_records(paths: Iterable[Any]) -> List[Dict[str, Any]]:
    """Read JSONL result files. If a question appears several times (e.g. after ``--rerun_errors``),
    the last record wins. Malformed lines are skipped with a warning."""
    import json
    from pathlib import Path

    records: "OrderedDict[Tuple[str, str], Dict[str, Any]]" = OrderedDict()
    for path in paths:
        path = Path(path)
        with open(path, encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    print(f"[warning] {path}:{number}: skipping a malformed line")
                    continue
                key = (str(record.get("task") or path.stem), str(record.get("pid")))
                records.pop(key, None)
                records[key] = record
    return list(records.values())


# ----------------------------------------------------------------------------- aggregation
_COST_FIELDS = ("llm_calls", "total_tokens", "map_tool_calls", "map_api_calls")


def summarize(
    records: Iterable[Dict[str, Any]],
    *,
    task_order: Optional[Sequence[str]] = None,
    display_names: Optional[Dict[str, str]] = None,
    legacy_fuzzy: bool = False,
    numeric_tolerance: float = DEFAULT_NUMERIC_TOLERANCE,
) -> Dict[str, Any]:
    """Accuracy per task, overall (micro) and macro accuracy, and average cost per query."""
    display_names = display_names or {}
    buckets: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for record in records:
        task = record.get("task") or "all"
        bucket = buckets.setdefault(task, {"n": 0, "correct": 0, "errors": 0, "time_sec": 0.0, **{f: 0 for f in _COST_FIELDS}})
        bucket["n"] += 1
        bucket["correct"] += int(
            score_prediction(
                record.get("prediction"),
                record.get("gold"),
                open_ended=bool(record.get("open_ended")),
                legacy_fuzzy=legacy_fuzzy,
                numeric_tolerance=numeric_tolerance,
            )
        )
        bucket["errors"] += int(bool(record.get("error")))
        bucket["time_sec"] += float(record.get("time_sec") or 0.0)
        usage = record.get("usage") or {}
        for field_name in _COST_FIELDS:
            bucket[field_name] += int(usage.get(field_name) or 0)

    order = [t for t in (task_order or []) if t in buckets] + sorted(t for t in buckets if t not in (task_order or []))
    tasks = OrderedDict()
    for task in order:
        bucket = buckets[task]
        n = bucket["n"]
        tasks[task] = {
            "name": display_names.get(task, task),
            "n": n,
            "correct": bucket["correct"],
            "accuracy": 100.0 * bucket["correct"] / n if n else 0.0,
            "errors": bucket["errors"],
        }
    total = sum(b["n"] for b in buckets.values())
    correct = sum(b["correct"] for b in buckets.values())
    cost = {
        f"avg_{name}": (sum(b[name] for b in buckets.values()) / total if total else 0.0)
        for name in (*_COST_FIELDS, "time_sec")
    }
    return {
        "tasks": tasks,
        "n": total,
        "correct": correct,
        "overall_accuracy": 100.0 * correct / total if total else 0.0,
        "macro_accuracy": (sum(t["accuracy"] for t in tasks.values()) / len(tasks)) if tasks else 0.0,
        "errors": sum(b["errors"] for b in buckets.values()),
        "cost": cost,
        "scoring": "legacy_fuzzy" if legacy_fuzzy else "strict",
    }


def format_summary(summary: Dict[str, Any]) -> str:
    """Markdown table in the layout of the paper's result tables."""
    tasks = summary["tasks"]
    header = ["Overall"] + [t["name"] for t in tasks.values()]
    values = [f"{summary['overall_accuracy']:.2f}"] + [f"{t['accuracy']:.2f}" for t in tasks.values()]
    counts = [f"{summary['correct']}/{summary['n']}"] + [f"{t['correct']}/{t['n']}" for t in tasks.values()]
    lines = [
        "| " + " | ".join(["Metric"] + header) + " |",
        "|" + "---|" * (len(header) + 1),
        "| " + " | ".join(["Accuracy (%)"] + values) + " |",
        "| " + " | ".join(["Correct / N"] + counts) + " |",
        "",
        f"Macro accuracy: {summary['macro_accuracy']:.2f}%  |  scoring: {summary['scoring']}  |  "
        f"examples with errors: {summary['errors']}",
    ]
    cost = summary["cost"]
    lines.append(
        "Average cost per query: "
        f"{cost['avg_llm_calls']:.2f} LLM calls, {cost['avg_total_tokens'] / 1000:.2f}K tokens, "
        f"{cost['avg_map_tool_calls']:.2f} MapTool calls, {cost['avg_map_api_calls']:.2f} Google Maps API calls, "
        f"{cost['avg_time_sec']:.1f} s"
    )
    return "\n".join(lines)
