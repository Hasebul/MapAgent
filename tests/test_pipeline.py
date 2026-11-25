"""End-to-end runs of run.py / evaluate.py with the fake LLM and the fake Google Maps client."""

import json

import pytest

import evaluate
import run
from mapagent.data import load_task, benchmark_task_dirs
from mapagent.llm import LLMClient
from mapagent.solver import MapAgent, SolverConfig
from tests.fakes import FakeLLM, fake_maps


def _run(tmp_path, *args, answer=lambda prompt: "B"):
    llm = FakeLLM(answer=answer)
    argv = list(args) + ["--output_dir", str(tmp_path)]
    return run.main(argv, llm=llm, maps=fake_maps(llm.usage)), llm


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize(
    "benchmark, task",
    [("mapeval_api", "trip"), ("mapeval_textual", "nearby"), ("mapeval_visual", "counting"), ("mapqa", "task_1")],
)
def test_every_benchmark_runs_end_to_end(tmp_path, benchmark, task):
    summary, llm = _run(tmp_path, "--benchmark", benchmark, "--tasks", task, "--limit", "2",
                        answer=lambda prompt: "Plan Check" if "Hayama" in prompt else "B")
    run_dir = next((tmp_path / benchmark).iterdir())
    records = _records(run_dir / f"{task}.jsonl")
    assert len(records) == 2 and summary["n"] == 2
    for record in records:
        assert record["error"] is None
        assert record["modules"][-2:] == ["solution_generator", "answer_generator"]
        assert "map_service" in record["modules"]
        assert record["usage"]["llm_calls"] >= 5
        assert record["usage"]["map_api_calls"] > 0
        json.dumps(record)  # serialisable
    assert (run_dir / "summary.json").exists() and (run_dir / "config.json").exists()
    if benchmark == "mapeval_visual":
        assert records[0]["modules"][0] == "visual_place_recognizer"
        assert records[0]["trace"]["visual_place_recognizer"]["radius_km"] == pytest.approx(0.6)
        # the solution generator and the planner receive the image
        image_requests = [r for r in llm.requests if not isinstance(r["messages"][-1]["content"], str)]
        assert len(image_requests) == 2 * 3  # planner, VPR, solution generator for 2 questions
    if benchmark == "mapeval_textual":
        assert "Context:" in records[0]["trace"]["solution_generator"]["input"]
    if benchmark == "mapqa":
        assert records[0]["open_ended"] and records[0]["choices"] == []
        assert records[0]["prediction"] == "Plan Check" and records[0]["correct"]
        assert "Options:" not in records[0]["trace"]["solution_generator"]["input"]


def test_resume_and_rerun(tmp_path):
    _run(tmp_path, "--benchmark", "mapeval_api", "--tasks", "poi", "--limit", "3")
    summary, llm = _run(tmp_path, "--benchmark", "mapeval_api", "--tasks", "poi", "--limit", "3")
    assert llm.requests == []  # everything was already done
    assert summary["n"] == 3
    summary, llm = _run(tmp_path, "--benchmark", "mapeval_api", "--tasks", "poi", "--limit", "3", "--overwrite")
    assert llm.requests and summary["n"] == 3


def test_base_mode_uses_no_tools(tmp_path):
    summary, llm = _run(tmp_path, "--benchmark", "mapeval_textual", "--tasks", "trip", "--limit", "2", "--mode", "base")
    records = _records(next((tmp_path / "mapeval_textual").iterdir()) / "trip.jsonl")
    assert all(r["modules"] == ["solution_generator", "answer_generator"] for r in records)
    assert all(r["usage"]["map_api_calls"] == 0 and r["usage"]["llm_calls"] == 2 for r in records)
    assert not any(r.get("tools") for r in llm.requests)


def test_fixed_modules_and_rule_answer_generator(tmp_path):
    _, llm = _run(tmp_path, "--benchmark", "mapeval_api", "--tasks", "routing", "--limit", "1",
                  "--modules", "google_maps", "solution_generator", "answer_generator", "--answer_generator", "rule")
    record = _records(next((tmp_path / "mapeval_api").iterdir()) / "routing.jsonl")[0]
    assert record["modules"] == ["map_service", "solution_generator", "answer_generator"]
    assert record["usage"]["llm_calls"] == 3  # map agent (2 rounds) + solution generator; no planner, no verifier
    assert record["prediction_letter"] == "B"


def test_unknown_module_is_rejected(tmp_path):
    with pytest.raises(SystemExit):
        _run(tmp_path, "--benchmark", "mapeval_api", "--modules", "bing_search")


def test_evaluate_cli(tmp_path, capsys):
    _run(tmp_path, "--benchmark", "mapeval_api", "--tasks", "trip", "unanswerable", "--limit", "2")
    run_dir = next((tmp_path / "mapeval_api").iterdir())
    out = tmp_path / "summary.json"
    assert evaluate.main([str(run_dir), "--output", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "| Metric | Overall | Trip | Unanswerable |" in printed
    data = json.loads(out.read_text())
    assert data[str(run_dir)]["n"] == 4
    assert evaluate.main([str(run_dir), "--legacy_fuzzy"]) == 0


def test_errors_are_recorded_not_raised():
    class FailingSequencer(FakeLLM):
        def _create(self, kwargs):
            text = kwargs["messages"][-1]["content"]
            if isinstance(text, str) and text.startswith("Your primary task is to comprehensively organize"):
                raise TimeoutError("simulated timeout")
            return super()._create(kwargs)

    llm = FailingSequencer()
    agent = MapAgent(SolverConfig(), llm, fake_maps(llm.usage))
    example = load_task(benchmark_task_dirs("mapeval_api", tasks=["nearby"])[0], limit=1)[0][0]
    record = agent.solve(example)
    assert record["error"] == "sequencer: TimeoutError: simulated timeout"
    # the remaining modules still ran and produced an answer from the raw map information
    assert record["modules"][-1] == "answer_generator" and record["prediction_letter"] == "B"
    assert "Google Maps response" in record["trace"]["solution_generator"]["input"]


def test_llm_client_adapts_to_rejected_parameters():
    import openai

    class Client(LLMClient):
        def __init__(self):
            super().__init__(provider="openai", api_key="test")
            self.seen = []

    client = Client()

    def create(**kwargs):
        client.seen.append(dict(kwargs))
        if "max_tokens" in kwargs:
            error = openai.BadRequestError.__new__(openai.BadRequestError)
            Exception.__init__(error, "Unsupported parameter: 'max_tokens'. Use 'max_completion_tokens' instead.")
            raise error
        message = type("M", (), {"content": " ok ", "tool_calls": None})()
        choice = type("C", (), {"message": message, "finish_reason": "stop"})()
        return type("R", (), {"choices": [choice], "usage": None})()

    client._client = type("X", (), {})()
    client._client.chat = type("Y", (), {})()
    client._client.chat.completions = type("Z", (), {"create": staticmethod(create)})()
    response = client.generate("o-model", "hi", max_tokens=10)
    assert response.content == "ok"
    assert "max_completion_tokens" in client.seen[-1] and "max_tokens" not in client.seen[-1]
    client.generate("o-model", "again", max_tokens=10)
    assert "max_tokens" not in client.seen[-1]  # remembered for this model


def test_fatal_errors_abort_the_run(tmp_path):
    import openai

    from tests.fakes import FakeGoogleMaps
    from mapagent.map_tools import MapsClient

    class Unauthorized(FakeLLM):
        def _create(self, kwargs):
            error = openai.AuthenticationError.__new__(openai.AuthenticationError)
            Exception.__init__(error, "Incorrect API key provided")
            raise error

    llm = Unauthorized()
    with pytest.raises(SystemExit, match="Aborting"):
        run.main(["--benchmark", "mapeval_api", "--tasks", "poi", "--limit", "1", "--output_dir", str(tmp_path)],
                 llm=llm, maps=fake_maps(llm.usage))

    class DeniedMaps(FakeGoogleMaps):
        def geocode(self, address):
            raise RuntimeError("REQUEST_DENIED (The provided API key is invalid.)")

        def places(self, *args, **kwargs):
            raise RuntimeError("REQUEST_DENIED (The provided API key is invalid.)")

        def directions(self, *args, **kwargs):
            raise RuntimeError("REQUEST_DENIED (The provided API key is invalid.)")

    llm = FakeLLM()
    with pytest.raises(SystemExit, match="Aborting"):
        run.main(["--benchmark", "mapeval_api", "--tasks", "nearby", "--limit", "1", "--output_dir", str(tmp_path)],
                 llm=llm, maps=MapsClient(usage=llm.usage, gmaps_client=DeniedMaps()))


def test_run_provenance_manifest_and_missing_questions(tmp_path, capsys):
    _run(tmp_path, "--benchmark", "mapeval_api", "--tasks", "poi", "--limit", "3")
    run_dir = next((tmp_path / "mapeval_api").iterdir())
    config = json.loads((run_dir / "config.json").read_text())
    assert set(config["models"]) == {"planner", "visual_place_recognizer", "map_agent", "sequencer",
                                     "solution_generator", "answer_generator"}
    assert "git_revision" in config and config["endpoint"] and config["provider"] == "openai"
    assert not str(config["arguments"]["datasets_root"]).startswith("/")  # no user paths in shared files
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["questions"]["poi"] == ["1", "2", "3"]
    assert manifest["selection"]["poi"]["split"] == "all"

    # drop one result: evaluate.py still divides by the 3 questions of the manifest
    results = run_dir / "poi.jsonl"
    lines = results.read_text().splitlines()
    results.write_text("\n".join(lines[:2]) + "\n")
    out = tmp_path / "eval.json"
    assert evaluate.main([str(run_dir), "--output", str(out)]) == 0
    summary = json.loads(out.read_text())[str(run_dir)]
    assert summary["n"] == 3 and summary["missing"] == 1
    assert evaluate.main([str(run_dir), "--ignore_missing", "--output", str(out)]) == 0
    assert json.loads(out.read_text())[str(run_dir)]["n"] == 2
