"""Offline stand-ins for the OpenAI API and the Google Maps web services (no keys, no network)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

from mapagent.llm import LLMClient
from mapagent.map_tools import MapsClient
from mapagent.usage import UsageTracker

PLACES = {
    "dubai mall": {"lat": 25.1972, "lng": 55.2796},
    "rydges wellington": {"lat": -41.2799, "lng": 174.7781},
    "kelburn park": {"lat": -41.2853, "lng": 174.7699},
    "victoria university of wellington": {"lat": -41.2901, "lng": 174.7682},
}


def _coords(name: str) -> Dict[str, float]:
    key = name.strip().lower()
    if key in PLACES:
        return PLACES[key]
    seed = sum(ord(c) for c in key)
    return {"lat": 10 + (seed % 100) / 1000.0, "lng": 20 + (seed % 37) / 1000.0}


class FakeGoogleMaps:
    """Mimics the subset of ``googlemaps.Client`` used by the MapTools."""

    def __init__(self) -> None:
        self.calls: List[str] = []

    def geocode(self, address: str):
        self.calls.append("geocode")
        if "nowhere" in address.lower() or "unknown place" in address.lower():
            return []
        return [{"geometry": {"location": _coords(address)}, "formatted_address": address}]

    def places(self, query: str = None, location=None, radius=None, type=None, **_: Any):  # noqa: A002
        self.calls.append("places")
        if query and "unknown place" in query.lower():
            return {"results": []}
        if location is None:
            return {"results": [{"place_id": f"pid:{query}", "name": query, "geometry": {"location": _coords(query)}}]}
        results = []
        for index, distance in enumerate((0.3, 0.9, 30.0)):
            results.append(
                {
                    "place_id": f"pid:{query}:{index}",
                    "name": f"{query.title()} {index + 1}",
                    "rating": 4.0 + index / 10,
                    "user_ratings_total": 100 * (index + 1),
                    "geometry": {"location": {"lat": location["lat"] + distance / 111.0, "lng": location["lng"]}},
                }
            )
        return {"results": results}

    def place(self, place_id: str, **_: Any):
        self.calls.append("place")
        name = place_id.split(":", 1)[1]
        return {
            "result": {
                "name": name,
                "formatted_address": f"1 Main Street, {name}",
                "rating": 4.4,
                "types": ["point_of_interest", "establishment"],
                "user_ratings_total": 321,
                "price_level": 2,
                "serves_lunch": True,
                "opening_hours": {"open_now": True, "weekday_text": [f"{d}: 9:00 AM - 5:00 PM" for d in ("Monday", "Tuesday")]},
                "reviews": [{"rating": 5, "relative_time_description": "a month ago", "text": "Great place."}],
            }
        }

    def directions(self, origin: str, destination: str, mode: str = None, waypoints=None, alternatives=None, departure_time=None, **_: Any):
        self.calls.append("directions")
        if "nowhere" in (origin + destination).lower():
            return []
        stops = [origin, *(waypoints or []), destination]
        legs = []
        for a, b in zip(stops, stops[1:]):
            minutes = 3 + (sum(ord(c) for c in a + b) % 7)
            legs.append(
                {
                    "start_address": a,
                    "end_address": b,
                    "distance": {"text": f"{minutes / 2:.1f} km", "value": minutes * 500},
                    "duration": {"text": f"{minutes} mins", "value": minutes * 60},
                    "steps": [
                        {"html_instructions": f"Head <b>north</b> on Main St<div>toward {b}</div>",
                         "distance": {"text": "0.5 km"}, "duration": {"text": "1 min"}, "travel_mode": "DRIVING"},
                        {"html_instructions": f"Turn <b>left</b> onto {b} Rd",
                         "distance": {"text": "1.0 km"}, "duration": {"text": "2 mins"}, "travel_mode": "DRIVING"},
                    ],
                }
            )
        routes = [{"summary": "Main St", "legs": legs}]
        if alternatives and not waypoints:
            routes.append({"summary": "Second Ave", "legs": legs})
        return routes


def fake_maps(usage: Optional[UsageTracker] = None) -> MapsClient:
    return MapsClient(usage=usage, gmaps_client=FakeGoogleMaps())


def _tool_call(call_id: str, name: str, arguments: Dict[str, Any]):
    return SimpleNamespace(id=call_id, type="function", function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


def _completion(content: str = "", tool_calls=None, finish_reason: str = "stop"):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or None)
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)], usage=usage)


class FakeLLM(LLMClient):
    """An ``LLMClient`` whose backend answers from simple rules on the prompt.

    ``answer`` decides the option letter (or the open-ended answer) of the Solution Generator.
    """

    def __init__(self, usage: Optional[UsageTracker] = None, answer: Callable[[str], str] = lambda prompt: "B") -> None:
        self.provider = "fake"
        self.usage = usage or UsageTracker()
        self._unsupported = {}
        self.answer = answer
        self.requests: List[Dict[str, Any]] = []

    def _create(self, kwargs: Dict[str, Any]):
        self.requests.append(kwargs)
        messages = kwargs["messages"]
        last = messages[-1]
        content = last.get("content")
        text = content if isinstance(content, str) else " ".join(p.get("text", "") for p in content or [] if isinstance(p, dict))

        if kwargs.get("tools"):  # Map-Tool Agent
            if last["role"] == "tool":
                return _completion("The retrieval is complete.")
            question = text.lower()
            if "trip" in question or "journey" in question or "visit" in question:
                return _completion(tool_calls=[_tool_call("call_1", "trip", {
                    "current_location": "Rydges Wellington",
                    "visiting_places": ["Kelburn Park", "Victoria University of Wellington", "Rydges Wellington"],
                    "travel_mode": "driving"})])
            return _completion(tool_calls=[
                _tool_call("call_1", "nearby", {"query": "restaurant", "location": "Dubai Mall", "type": "restaurant", "radius": 2}),
                _tool_call("call_2", "place_info", {"location_address": "Dubai Mall"}),
                _tool_call("call_3", "route", {"origin": "Dubai Mall", "destination": "Kelburn Park", "mode": "car"}),
                _tool_call("call_4", "nearby", {"query": "restaurant", "location": "Dubai Mall", "type": "restaurant", "radius": 2}),
            ])
        if "act as a policy model" in text:
            if '"has_image": true' in text.split("Question:")[-1]:
                return _completion('["visual_place_recognizer", "map_service", "solution_generator", "answer_generator"]')
            return _completion('Modules: ["google_maps", "sequencer", "Solution_Generator", "Answer_Generator"]')
        if text.startswith("I will provide you with an image"):
            return _completion("Radmansgatan 46, 113 57 Stockholm, Sweden 600 meters")
        if text.startswith("Your primary task is to comprehensively organize"):
            return _completion("I. Organized information\n" + text.split("Information gathered by the previous modules:")[-1][:500])
        if "Answer Generator" in text:
            verdict = self.answer(text)
            return _completion(f"Based on the response from the solution generator, this seems logical and correct. The answer is {verdict}.")
        if text.startswith("Given the question"):
            return _completion(f"Step 1: read the context. Step 2: compare.\nTherefore, the answer is {self.answer(text)}.")
        return _completion("")
