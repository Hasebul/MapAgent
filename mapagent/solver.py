"""MapAgent: Planner Agent (outer layer) and module execution (Section 3).

The planner receives the query (and the map image for visual questions) together with the module inventory
and returns the sequence of modules to run. ``map_service`` delegates to the Map-Tool Agent (inner layer);
the other modules run directly without additional agent overhead.
"""

from __future__ import annotations

import ast
import json
import re
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .data import Example
from .llm import LLMClient, is_fatal_llm_error
from .map_tools import MapsClient, MapToolAgent, is_fatal_maps_error
from .modules import MODULES, QueryState
from .prompts import PLANNER_PROMPT
from .scoring import score_prediction

MODULE_ORDER = ("visual_place_recognizer", "map_service", "sequencer", "solution_generator", "answer_generator")
MODULE_ALIASES = {
    "google_maps": "map_service",
    "googlemaps": "map_service",
    "google_map": "map_service",
    "map": "map_service",
    "maps": "map_service",
    "map_services": "map_service",
    "image_search": "visual_place_recognizer",
    "visual_place_recognition": "visual_place_recognizer",
    "vpr": "visual_place_recognizer",
    "solution_generation": "solution_generator",
    "answer_generation": "answer_generator",
}
# Names searched for when the planner does not answer with a list (generic aliases such as "map" are excluded).
_SCAN_NAMES = MODULE_ORDER + ("google_maps", "googlemaps", "image_search", "visual_place_recognition")
COMPONENTS = ("planner", "visual_place_recognizer", "map_agent", "sequencer", "solution_generator", "answer_generator")
DEFAULT_MAX_TOKENS = {
    "planner": 128,
    "visual_place_recognizer": 256,
    "map_agent": 1024,
    "sequencer": 2048,
    "solution_generator": 1024,
    "answer_generator": 256,
}


def canonical_module(name: Any) -> Optional[str]:
    key = re.sub(r"[\s\-]+", "_", str(name).strip().strip("'\"").lower())
    key = re.sub(r"_module$", "", key)
    key = MODULE_ALIASES.get(key, key)
    return key if key in MODULE_ORDER else None


def parse_module_list(text: Optional[str]) -> Optional[List[str]]:
    """Parse the planner output (a JSON / Python list of module names) without ``eval``."""
    if not text:
        return None
    match = re.search(r"\[[^\[\]]*\]", text, re.S)
    if match:
        for loader in (json.loads, ast.literal_eval):
            try:
                value = loader(match.group(0))
            except (ValueError, SyntaxError):
                continue
            if isinstance(value, (list, tuple)):
                return [str(item) for item in value]
    hits = []  # fall back to module names mentioned in the text, in order of appearance
    for name in _SCAN_NAMES:
        pattern = re.escape(name).replace("_", "[ _-]?")
        hits.extend((m.start(), canonical_module(name)) for m in re.finditer(pattern, text, re.IGNORECASE))
    names = list(dict.fromkeys(name for _, name in sorted(hits)))
    return names or None


def default_pipeline(has_image: bool) -> List[str]:
    modules = ["map_service", "sequencer", "solution_generator", "answer_generator"]
    return (["visual_place_recognizer"] if has_image else []) + modules


def finalize_modules(names: Sequence[str], has_image: bool) -> List[str]:
    """Keep known modules, drop the image module for text-only questions and end with SG -> AG."""
    selected = {canonical_module(name) for name in names} - {None}
    if not has_image:
        selected.discard("visual_place_recognizer")
    selected |= {"solution_generator", "answer_generator"}
    return [module for module in MODULE_ORDER if module in selected]


@dataclass
class SolverConfig:
    mode: str = "mapagent"  # "mapagent" (planner + modules) or "base" (solution + answer generators only)
    model: str = "gpt-3.5-turbo"
    module_models: Dict[str, str] = field(default_factory=dict)  # per-component overrides (see COMPONENTS)
    temperature: float = 0.0
    max_tokens: Dict[str, int] = field(default_factory=lambda: dict(DEFAULT_MAX_TOKENS))
    sg_patience: int = 3
    answer_generator: str = "llm"  # "llm" (verify + extract, as in the paper) or "rule" (regex only)
    map_max_rounds: int = 3
    map_max_workers: int = 5
    fixed_modules: Optional[List[str]] = None
    image_to_planner: bool = True
    image_to_solution_generator: bool = True
    verbose: bool = False

    def model_for(self, component: str) -> str:
        return self.module_models.get(component) or self.model


class MapAgent:
    def __init__(self, config: SolverConfig, llm: LLMClient, maps: Optional[MapsClient] = None) -> None:
        if config.mode not in ("mapagent", "base"):
            raise ValueError(f"Unknown mode {config.mode!r}")
        if config.answer_generator not in ("llm", "rule"):
            raise ValueError(f"Unknown answer generator mode {config.answer_generator!r}")
        self.config = config
        self.llm = llm
        self.maps = maps
        self.usage = llm.usage
        if maps is not None:
            maps.usage = self.usage  # one set of counters per query
        self.map_agent = (
            MapToolAgent(
                llm,
                config.model_for("map_agent"),
                maps,
                max_rounds=config.map_max_rounds,
                max_workers=config.map_max_workers,
                temperature=config.temperature,
                max_tokens=config.max_tokens.get("map_agent", 1024),
                verbose=config.verbose,
            )
            if maps is not None
            else None
        )

    # ------------------------------------------------------------------ planner
    def select_modules(self, state: QueryState) -> List[str]:
        example = state.example
        if self.config.mode == "base":
            return ["solution_generator", "answer_generator"]
        if self.config.fixed_modules:
            modules = finalize_modules(self.config.fixed_modules, example.has_image)
            state.trace["planner"] = {"fixed_modules": modules}
            return modules

        metadata = json.dumps({"has_image": example.has_image})
        prompt = f"{PLANNER_PROMPT}\n\nQuestion: {state.question_text}\n\nMetadata: {metadata}\n\nModules: "
        response = self.llm.generate(
            self.config.model_for("planner"),
            prompt,
            image_path=example.image_path if self.config.image_to_planner else None,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens.get("planner"),
        )
        names = parse_module_list(response.content)
        fallback = not names or not any(canonical_module(name) for name in names)
        modules = finalize_modules(default_pipeline(example.has_image) if fallback else names, example.has_image)
        state.trace["planner"] = {"output": response.content, "modules": modules, "fallback": fallback}
        return modules

    # ------------------------------------------------------------------ solve one example
    def solve(self, example: Example) -> Dict[str, Any]:
        state = QueryState.from_example(example)
        self.usage.reset()
        start = time.time()
        errors: List[str] = []

        def failed(step: str, exc: Exception) -> None:
            # Configuration errors (bad key, unknown model, ...) abort the run; anything else is recorded and
            # the remaining modules still run, so one failing call does not void the whole question.
            if is_fatal_llm_error(exc) or is_fatal_maps_error(exc):
                raise exc
            errors.append(f"{step}: {type(exc).__name__}: {exc}")
            if self.config.verbose:
                traceback.print_exc()

        try:
            modules = self.select_modules(state)
        except Exception as exc:  # noqa: BLE001
            failed("planner", exc)
            modules = finalize_modules(default_pipeline(example.has_image), example.has_image)
        for name in modules:
            if self.config.verbose:
                print(f"  -> {name}")
            try:
                MODULES[name](self, state)
            except Exception as exc:  # noqa: BLE001
                failed(name, exc)
        error = "; ".join(errors) or None

        image = Path(example.image_path) if example.image_path else None
        return {
            "pid": example.pid,
            "task": example.task,
            "category": example.category,
            "question": example.question,
            "choices": example.choices,
            "gold": example.answer,
            "open_ended": example.open_ended,
            "context_used": bool(example.context),
            "image": f"{image.parent.name}/{image.name}" if image else None,
            "modules": modules,
            "prediction": state.prediction,
            "prediction_letter": state.prediction_letter,
            "correct": score_prediction(
                state.prediction, example.answer, open_ended=example.open_ended, choices=example.choices
            ),
            "solution": state.solution,
            "trace": state.trace,
            "usage": self.usage.snapshot().to_dict(),
            "time_sec": round(time.time() - start, 3),
            "error": error,
        }
