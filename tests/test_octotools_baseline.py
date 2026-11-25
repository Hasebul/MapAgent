"""The OctoTools baseline runs offline with a fake OpenAI client and the fake Google Maps client."""

import json
import types
from pathlib import Path

import pytest

pytest.importorskip("pydantic")
pytest.importorskip("tenacity")

BASELINE = Path(__file__).resolve().parent.parent / "baselines" / "octotools"


def _response(content=None, parsed=None):
    message = types.SimpleNamespace(content=content, parsed=parsed, tool_calls=None)
    usage = types.SimpleNamespace(prompt_tokens=50, completion_tokens=10)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message, finish_reason="stop")], usage=usage)


class _Completions:
    def create(self, **kwargs):
        content = kwargs["messages"][-1]["content"]
        text = content if isinstance(content, str) else json.dumps(content)
        return _response("Therefore, the answer is B." if "concise output" in text else "ok")

    def parse(self, model, messages, response_format, **kwargs):
        name = response_format.__name__
        values = {
            "QueryAnalysis": dict(concise_summary="s", required_skills="r", relevant_tools="Trip_Tool", additional_considerations="-"),
            "NextStep": dict(justification="j", context="c", sub_goal="trip info", tool_name="Trip Tool"),
            "ToolCommand": dict(analysis="a", explanation="e", command='execution = tool.execute(current_location="Rydges Wellington", visiting_places=["Kelburn Park"])'),
            "MemoryVerification": dict(analysis="ok", stop_signal=True),
        }[name]
        return _response(parsed=response_format(**values))


def test_octotools_baseline_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.syspath_prepend(str(BASELINE))
    import octotools.engine.openai as engine
    from octotools.tools import _maps

    from mapagent.map_tools import MapsClient
    from tests.fakes import FakeGoogleMaps

    monkeypatch.setattr(engine, "_make_client", lambda: types.SimpleNamespace(chat=types.SimpleNamespace(completions=_Completions())))
    monkeypatch.setattr(_maps, "_client", MapsClient(usage=_maps.USAGE, gmaps_client=FakeGoogleMaps()))
    import solve

    solve.main(["--benchmark", "mapeval_api", "--tasks", "trip", "--limit", "2", "--model", "gpt-4o-mini",
                "--output_dir", str(tmp_path)])
    records = [json.loads(line) for line in (tmp_path / "mapeval_api" / "octotools_gpt-4o-mini" / "trip.jsonl").read_text().splitlines()]
    assert len(records) == 2
    first = records[0]
    assert first["error"] is None and first["prediction_letter"] == "B"
    assert first["trace"]["memory"]["Action Step 1"]["tool_name"] == "Trip_Tool"
    assert "All Location Info" in json.dumps(first["trace"]["memory"])
    assert first["usage"]["llm_calls"] == 5 and first["usage"]["map_api_calls"] == 6
