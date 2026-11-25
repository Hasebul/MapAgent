from pathlib import Path

import pytest

from mapagent.data import BENCHMARKS, benchmark_task_dirs, load_task
from mapagent.scoring import UNANSWERABLE

EXPECTED = {"mapeval_api": (300, 0), "mapeval_textual": (300, 0), "mapeval_visual": (400, 0), "mapqa": (2196, 10)}


def _load(benchmark):
    spec = BENCHMARKS[benchmark]
    examples, skipped = [], []
    for task_dir in benchmark_task_dirs(benchmark):
        loaded, missing = load_task(task_dir, use_context=spec.use_context, use_image=spec.use_image,
                                    open_ended=spec.open_ended or None)
        examples += loaded
        skipped += missing
    return examples, skipped


@pytest.mark.parametrize("benchmark", sorted(EXPECTED))
def test_benchmark_sizes(benchmark):
    examples, skipped = _load(benchmark)
    assert (len(examples), len(skipped)) == EXPECTED[benchmark]


@pytest.mark.parametrize("benchmark", ["mapeval_api", "mapeval_visual"])
def test_mcq_gold_answers_are_options(benchmark):
    examples, _ = _load(benchmark)
    for example in examples:
        assert example.answer == UNANSWERABLE or example.answer in example.choices, example.pid
        assert all(choice.strip() for choice in example.choices)
        if example.task == "unanswerable":
            assert example.answer == UNANSWERABLE


def test_context_and_images():
    api, _ = _load("mapeval_api")
    textual, _ = _load("mapeval_textual")
    visual, _ = _load("mapeval_visual")
    assert not any(e.context for e in api)
    assert all(e.context for e in textual)
    assert all(e.image_path and Path(e.image_path).is_file() for e in visual)


def test_mapqa_is_open_ended_without_answer_leak():
    examples, skipped = _load("mapqa")
    assert all(e.open_ended and e.choices == [] for e in examples)
    assert {reason for _, reason in skipped} == {"missing gold answer"}


def test_split_selection():
    task = benchmark_task_dirs("mapeval_api", tasks=["poi"])[0]
    assert len(load_task(task, split="minitest")[0]) == 63
    assert len(load_task(task, split="all")[0]) == 64
    assert len(load_task(task, limit=5)[0]) == 5
    with pytest.raises(KeyError):
        load_task(task, split="train")
