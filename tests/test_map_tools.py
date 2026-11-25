import json
from types import SimpleNamespace

import pytest

from mapagent.map_tools import MapsAuthError, MapsClient, MapToolAgent, run_map_tool
from mapagent.map_tools.tools import (
    TOOL_SCHEMAS,
    format_duration,
    haversine_km,
    nearby,
    normalize_travel_mode,
    place_info,
    route,
    trip,
)
from mapagent.usage import UsageTracker
from tests.fakes import FakeGoogleMaps, FakeLLM, fake_maps


def test_tool_schemas_follow_the_paper():
    names = [schema["function"]["name"] for schema in TOOL_SCHEMAS]
    assert names == ["trip", "route", "nearby", "place_info"]
    nearby_params = TOOL_SCHEMAS[2]["function"]["parameters"]["properties"]
    assert set(nearby_params) == {"query", "location", "type", "radius"}
    assert "california" not in json.dumps(TOOL_SCHEMAS).lower()


def test_helpers():
    assert normalize_travel_mode("car") == "driving"
    assert normalize_travel_mode("public transport") == "transit"
    assert normalize_travel_mode(None) == "driving"
    assert format_duration(30) == "1 min"
    assert format_duration(3900) == "1 hour 5 mins"
    assert haversine_km({"lat": 0, "lng": 0}, {"lat": 0, "lng": 1}) == pytest.approx(111.19, rel=1e-3)


def test_trip_pairs_and_api_calls():
    maps = fake_maps()
    text = trip(maps, "Rydges Wellington", ["Kelburn Park", "Victoria University of Wellington", "rydges wellington"])
    # the duplicate of the start location is removed: 3 places -> 3 x (search + details) + 6 ordered pairs
    assert maps.usage.snapshot().map_api_calls == 3 * 2 + 6
    assert text.startswith("All Location Info:")
    assert text.count("The travel time(distance) from") == 6
    assert "from Kelburn Park to Rydges Wellington is" in text


def test_trip_unknown_place_does_not_crash():
    text = trip(fake_maps(), "Unknown Place 123", ["Kelburn Park"])
    assert "No information found for this location" in text


def test_route_multi_leg_and_alternatives():
    maps = fake_maps()
    text = route(maps, "Seabird Water Taxi", "Sierra Leone Grammar School", mode="drive", waypoints=["Cole Street Guesthouse"])
    assert "with waypoint(s) Cole Street Guesthouse" in text
    assert "Leg 1:" in text and "Leg 2:" in text
    assert "Head north on Main St toward" in text  # HTML instructions converted to text
    text = route(maps, "A Street", "B Street")
    assert "There are total 2 routes" in text
    assert "No driving route" in route(maps, "nowhere", "B Street")


def test_nearby_filters_by_radius():
    maps = fake_maps()
    small = nearby(maps, "restaurant", "Dubai Mall", "restaurant", radius=2)
    assert "within 2 kilometers" in small
    assert small.count("( distance:") == 2  # the place 30 km away is filtered out
    assert nearby(maps, "restaurant", "Dubai Mall", "restaurant", radius=50).count("( distance:") == 3
    assert nearby(maps, "restaurant", "Dubai Mall").count("( distance:") == 2  # default radius 20 km
    assert "Could not find the location" in nearby(maps, "cafe", "Unknown Place XYZ")


def test_place_info_details():
    text = place_info(fake_maps(), "Multiplan Center")
    assert "Name: Multiplan Center" in text
    assert "Serves Lunch: Yes" in text and "Serves Dinner" not in text  # absent attributes are not reported as "No"
    assert "Reviews:" in text
    assert "No place information" in place_info(fake_maps(), "Unknown Place")


def test_run_map_tool_dispatch():
    maps = fake_maps()
    assert "Route 1" in run_map_tool(maps, "directions", {"origin": "A", "destination": "B", "travel_mode": "walking"})
    assert "Name:" in run_map_tool(maps, "get_place_info", {"location": "Kelburn Park"})
    assert "missing required argument" in run_map_tool(maps, "trip", {"current_location": "A"})
    assert "unknown map tool" in run_map_tool(maps, "weather", {})
    assert maps.usage.snapshot().map_tool_calls == 2


class _DeniedMaps(FakeGoogleMaps):
    def geocode(self, address):
        raise RuntimeError("REQUEST_DENIED (The provided API key is invalid.)")


def test_fatal_maps_errors_propagate():
    maps = MapsClient(gmaps_client=_DeniedMaps())
    with pytest.raises(MapsAuthError):
        run_map_tool(maps, "nearby", {"query": "cafe", "location": "Dubai Mall"})


def test_missing_key_is_reported(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_MAP_API_KEY", raising=False)
    with pytest.raises(MapsAuthError):
        MapsClient()


def test_map_tool_agent_parallel_dedup_and_rounds():
    usage = UsageTracker()
    llm = FakeLLM(usage=usage)
    agent = MapToolAgent(llm, "fake-model", fake_maps(usage), max_rounds=3)
    result = agent.run("Which restaurant near Dubai Mall has the highest rating?", visual_context="center: Dubai Mall")
    assert result.rounds == 2  # one round of tool calls, then the agent stops
    assert [call["tool"] for call in result.calls] == ["nearby", "place_info", "route", "nearby"]
    assert result.information.count("There are some restaurant") == 1  # the duplicated call is executed once
    assert usage.snapshot().map_tool_calls == 3
    assert usage.snapshot().llm_calls == 2
    request = llm.requests[0]
    assert request["tools"] and "center: Dubai Mall" in request["messages"][1]["content"]
    tool_messages = [m for m in llm.requests[1]["messages"] if m["role"] == "tool"]
    assert len(tool_messages) == 4  # every tool_call_id gets an answer


def test_map_tool_agent_bad_arguments():
    class BadArgsLLM(FakeLLM):
        def _create(self, kwargs):
            self.requests.append(kwargs)
            if kwargs["messages"][-1]["role"] == "tool":
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="done", tool_calls=None), finish_reason="stop")], usage=None)
            call = SimpleNamespace(id="c1", type="function", function=SimpleNamespace(name="trip", arguments="{not json"))
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[call]), finish_reason="tool_calls")], usage=None)

    result = MapToolAgent(BadArgsLLM(), "fake", fake_maps()).run("plan a trip")
    assert "could not parse the arguments" in result.information
