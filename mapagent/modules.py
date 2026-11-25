"""The module inventory of MapAgent (Section 3.3, Table 10).

=========================  ==========================================================================
Module                     Role
=========================  ==========================================================================
visual_place_recognizer    VLM: central place of the map image and its approximate radius.
map_service                Fetches geospatial data through the Map-Tool Agent (inner layer).
sequencer                  LLM: organizes the information gathered by the preceding modules.
solution_generator         LLM/VLM: step-by-step solution from the question and gathered information.
answer_generator           Verifies the solution and extracts the predicted answer.
=========================  ==========================================================================

Every module reads and updates a :class:`QueryState`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from .data import Example
from .prompts import (
    ANSWER_GENERATOR_MCQ_PROMPT,
    ANSWER_GENERATOR_OPEN_PROMPT,
    SEQUENCER_PROMPT,
    SOLUTION_GENERATOR_MCQ_PROMPT,
    SOLUTION_GENERATOR_OPEN_PROMPT,
    VISUAL_PLACE_RECOGNIZER_PROMPT,
)
from .scoring import (
    extract_choice,
    extract_choice_by_text,
    extract_open_answer,
    format_options,
    has_explicit_answer,
    letter_to_choice,
)

if TYPE_CHECKING:  # pragma: no cover
    from .solver import MapAgent


@dataclass
class QueryState:
    example: Example
    question_text: str  # question (+ context) + options: input of the planner and the Solution Generator
    map_query: str  # question + options: input of the Map-Tool Agent, the Sequencer and the Answer Generator
    info: List[Tuple[str, str]] = field(default_factory=list)  # (label, text) gathered by the modules
    visual_context: Optional[Dict[str, Any]] = None
    solution: Optional[str] = None
    prediction: Optional[str] = None  # option text, "Unanswerable", or a free-form answer (MapQA)
    prediction_letter: Optional[str] = None
    trace: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_example(cls, example: Example) -> "QueryState":
        options = f"Options: {format_options(example.choices)}" if (example.choices and not example.open_ended) else ""
        question_parts = [example.question]
        if example.context:
            question_parts.append(f"Context: {example.context}")
        if options:
            question_parts.append(options)
        map_query = example.question + (f"\n\n{options}" if options else "")
        return cls(example=example, question_text="\n\n".join(question_parts), map_query=map_query)

    def render_info(self) -> str:
        return "\n\n".join(f"{label}:\n{text}" for label, text in self.info)


# --------------------------------------------------------------------------- helpers
_RADIUS_AT_END = re.compile(
    r"[\s,;:(\-]*(?:(?:with\s+a\s+)?radius\s*(?:of|is|:|=)?\s*)?(?:approximately|approx\.?|about|around|~)?\s*"
    r"(\d+(?:\.\d+)?)\s*(kilometers?|kilometres?|km|meters?|metres?|m|miles?|mi)?\s*\)?\.?\s*$",
    re.IGNORECASE,
)


def parse_place_and_radius(text: str) -> Tuple[str, Optional[float]]:
    """Split the Visual Place Recognizer output "<address> <radius>" into ``(address, radius_km)``."""
    cleaned = " ".join((text or "").replace("**", "").split()).strip(" \"'")
    match = _RADIUS_AT_END.search(cleaned)
    if not match or match.start() == 0:
        return cleaned, None
    value, unit = float(match.group(1)), (match.group(2) or "").lower()
    if unit.startswith("k"):
        radius_km = value
    elif unit.startswith("mi"):
        radius_km = value * 1.609344
    elif unit.startswith("m"):
        radius_km = value / 1000.0
    else:  # no unit: large values are meters
        radius_km = value / 1000.0 if value > 50 else value
    place = cleaned[: match.start()].strip(" ,;:-")
    return place or cleaned, min(max(radius_km, 0.05), 50.0)


def _format_km(value: float) -> str:
    return f"{value * 1000:.0f} meters" if value < 1 else f"{value:g} kilometers"


def _generate(agent: "MapAgent", component: str, prompt: str, *, image_path: Optional[str] = None, temperature=None):
    config = agent.config
    return agent.llm.generate(
        config.model_for(component),
        prompt,
        image_path=image_path,
        temperature=config.temperature if temperature is None else temperature,
        max_tokens=config.max_tokens.get(component),
    )


# --------------------------------------------------------------------------- modules
def visual_place_recognizer(agent: "MapAgent", state: QueryState) -> None:
    image = state.example.image_path
    if not image:
        state.trace["visual_place_recognizer"] = {"skipped": "the question has no image"}
        return
    response = _generate(agent, "visual_place_recognizer", VISUAL_PLACE_RECOGNIZER_PROMPT, image_path=image)
    place, radius_km = parse_place_and_radius(response.content)
    state.visual_context = {"place": place, "radius_km": radius_km}
    description = f"The central point of this image indicates the location of {place}."
    if radius_km:
        description += f" The radius from this central point to the image's edge is about {_format_km(radius_km)}."
    state.info.append(("Visual Place Recognizer output", description))
    state.trace["visual_place_recognizer"] = {"output": response.content, "place": place, "radius_km": radius_km}


def map_service(agent: "MapAgent", state: QueryState) -> None:
    if agent.map_agent is None:
        raise RuntimeError("The map_service module needs a Google Maps API key (set GOOGLE_MAPS_API_KEY).")
    visual = None
    if state.visual_context and state.visual_context.get("place"):
        place, radius_km = state.visual_context["place"], state.visual_context.get("radius_km")
        visual = f'Visual context from the Visual Place Recognizer: the map image is centered at "{place}"'
        if radius_km:
            visual += f" and covers a radius of about {radius_km:g} km around it"
        visual += (
            ". When the question refers to the map or does not name a reference location, use this place as the "
            "location (and this radius) in your tool calls."
        )
    result = agent.map_agent.run(state.map_query, visual_context=visual)
    state.info.append(("Google Maps response", result.information or "No information was retrieved from Google Maps."))
    state.trace["map_service"] = {
        "tool_calls": [{key: call[key] for key in ("round", "tool", "arguments")} for call in result.calls],
        "rounds": result.rounds,
        "information": result.information,
        "agent_message": result.final_message,
    }


def sequencer(agent: "MapAgent", state: QueryState) -> None:
    if not state.info:
        state.trace["sequencer"] = {"skipped": "no information to organize"}
        return
    prompt = (
        f"{SEQUENCER_PROMPT}\n\nQuestion: {state.map_query}\n\n"
        f"Information gathered by the previous modules:\n{state.render_info()}\n\nOrganized information:"
    )
    response = _generate(agent, "sequencer", prompt)
    if not response.content or response.finish_reason == "length":
        # Never pass on a truncated summary: keep the original information instead.
        state.trace["sequencer"] = {"output": response.content, "kept_original": True}
        return
    state.info = [("Organized geospatial information", response.content)]
    state.trace["sequencer"] = {"output": response.content}


def solution_generator(agent: "MapAgent", state: QueryState) -> None:
    example, config = state.example, agent.config
    instructions = SOLUTION_GENERATOR_OPEN_PROMPT if example.open_ended else SOLUTION_GENERATOR_MCQ_PROMPT
    test_prompt = f"Question: {state.question_text}\n\n"
    if example.skill:
        test_prompt += f"Metadata: {json.dumps({'skill': example.skill}, ensure_ascii=False)}\n\n"
    if state.info:
        test_prompt += f"{state.render_info()}\n\n"
    test_prompt += "Solution: "
    image = example.image_path if config.image_to_solution_generator else None

    solution, attempts = "", 0
    for attempts in range(1, max(1, config.sg_patience) + 1):
        # Retry with a slightly higher temperature when no explicit answer was given (original behaviour).
        temperature = config.temperature
        if attempts > 1 and config.temperature < 0.1:
            temperature = min(config.temperature + 0.1, 1.0)
        response = _generate(
            agent, "solution_generator", f"{instructions}\n\n{test_prompt}", image_path=image, temperature=temperature
        )
        solution = response.content
        if has_explicit_answer(solution, open_ended=example.open_ended, num_choices=len(example.choices)):
            break
    state.solution = solution
    state.trace["solution_generator"] = {"input": test_prompt, "output": solution, "attempts": attempts}


def _extract(text: Optional[str], example: Example, *, strict: bool = False) -> Optional[str]:
    if example.open_ended:
        return extract_open_answer(text) if (not strict or has_explicit_answer(text, open_ended=True, num_choices=0)) else None
    letter = extract_choice(text, len(example.choices), strict=strict)
    if letter is None and not strict:
        letter = extract_choice_by_text(text, example.choices)
    return letter


def answer_generator(agent: "MapAgent", state: QueryState) -> None:
    example, config = state.example, agent.config
    solution = state.solution or ""
    final, source, verifier_output = _extract(solution, example), "solution", None

    if config.answer_generator == "llm" and solution:
        instructions = ANSWER_GENERATOR_OPEN_PROMPT if example.open_ended else ANSWER_GENERATOR_MCQ_PROMPT
        prompt = f"{instructions}\n\nQuestion: {state.map_query}\nSolution: {solution}\nOutput:"
        verifier_output = _generate(agent, "answer_generator", prompt).content
        verified = _extract(verifier_output, example, strict=True)
        if verified is not None:
            final, source = verified, "verifier"

    if example.open_ended:
        state.prediction, state.prediction_letter = final, None
    else:
        state.prediction_letter = final
        state.prediction = letter_to_choice(final, example.choices)
    state.trace["answer_generator"] = {
        "mode": config.answer_generator,
        "verifier_output": verifier_output,
        "source": source if final is not None else None,
        "prediction": state.prediction,
    }


MODULES: Dict[str, Callable[["MapAgent", QueryState], None]] = {
    "visual_place_recognizer": visual_place_recognizer,
    "map_service": map_service,
    "sequencer": sequencer,
    "solution_generator": solution_generator,
    "answer_generator": answer_generator,
}
