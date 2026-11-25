import pytest

from mapagent.scoring import (
    UNANSWERABLE,
    extract_choice,
    extract_choice_by_text,
    extract_open_answer,
    has_explicit_answer,
    legacy_fuzzy_equal,
    letter_to_choice,
    score_prediction,
    summarize,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Step 1 ... Therefore, the answer is B.", "B"),
        ("the answer is (C)", "C"),
        ("Answer: **(B) Al Ihsan Jame Mosque**", "B"),
        ("Thus, the correct answer is: **(D) Three**", "D"),
        ("The answer is: D. Seabird Water Taxi -> ...", "D"),
        ("The answer is A. Howth Castle.", "A"),
        ("Final Answer: C", "C"),
        ('the answer is "A"', "A"),
        ("the answer is option B", "B"),
        ("First I thought the answer is A, but after checking, the answer is C.", "C"),
        ("The answer is Unanswerable.", UNANSWERABLE),
        ("The answer is B. Wait, none fits: the answer is Unanswerable", UNANSWERABLE),
    ],
)
def test_extract_choice(text, expected):
    assert extract_choice(text, 4) == expected


@pytest.mark.parametrize(
    "text",
    ["The answer is Amsterdam.", "the answer is a bit unclear", "Answer Generator output", "", None],
)
def test_extract_choice_rejects_non_letters(text):
    assert extract_choice(text, 4, strict=True) is None


def test_extract_choice_out_of_range_and_fallbacks():
    assert extract_choice("the answer is E", 4, strict=True) is None
    assert extract_choice("This question is unanswerable with the given data.", 4) == UNANSWERABLE
    assert extract_choice("This question is unanswerable with the given data.", 4, strict=True) is None
    assert extract_choice("I would pick (B) here.", 4) == "B"
    assert extract_choice_by_text("Overall, Kelburn Park is the best choice.", ["Rydges", "Kelburn Park", "Te Papa"]) == "B"
    assert extract_choice_by_text("Kelburn Park or Te Papa", ["Rydges", "Kelburn Park", "Te Papa"]) is None


def test_has_explicit_answer():
    assert has_explicit_answer("so the answer is B.", open_ended=False, num_choices=4)
    assert not has_explicit_answer("maybe (B)", open_ended=False, num_choices=4)
    assert has_explicit_answer("Thus, the answer is Plan Check.", open_ended=True, num_choices=0)


def test_letter_to_choice():
    choices = ["One", "Two", "Three"]
    assert letter_to_choice("B", choices) == "Two"
    assert letter_to_choice("D", choices) is None
    assert letter_to_choice(UNANSWERABLE, choices) == UNANSWERABLE
    assert letter_to_choice(None, choices) is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Reasoning...\nThus, the answer is **Plan Check**.", "Plan Check"),
        ("the final answer is: 21.7 km", "21.7 km"),
        ("Scout Coffee Co.", "Scout Coffee Co"),
        ("So the answer is Unanswerable.", UNANSWERABLE),
    ],
)
def test_extract_open_answer(text, expected):
    assert extract_open_answer(text) == expected


def test_strict_mcq_scoring_rejects_similar_wrong_options():
    assert score_prediction("Three", "Three", open_ended=False)
    assert score_prediction("  three ", "Three", open_ended=False)
    assert not score_prediction("Seven", "Ten", open_ended=False)
    assert not score_prediction("Mary Castle", "Howth Castle", open_ended=False)
    assert not score_prediction(None, "Three", open_ended=False)
    # The first release's scorer accepted these wrong answers (real MapEval-Visual options):
    assert legacy_fuzzy_equal("Seven", "Ten")
    assert score_prediction("Mary Castle", "Howth Castle", open_ended=False, legacy_fuzzy=True)


def test_legacy_fuzzy_matches_original_fallback():
    # The original answer generator predicted this string when no option was found.
    assert legacy_fuzzy_equal(None, "Not able to answer the question")
    assert not legacy_fuzzy_equal("Saqsaywaman", "xyz")


@pytest.mark.parametrize(
    "prediction, gold, expected",
    [
        ("Plan Check", "Plan Check", True),
        ("Plan Check restaurant", "Plan Check", True),
        ("Check", "Plan Check", False),
        ("21.69 km", "21694.66 meters", True),
        ("about 21700 m", "21694.66 meters", True),
        ("25 km", "21694.66 meters", False),
        ("21694", "21694.66 meters", True),
        ("7 Eleven", "7-Eleven", True),
        ("No amenities found", "No amenities found", True),
        ("Unanswerable", "Plan Check", False),
    ],
)
def test_open_ended_scoring(prediction, gold, expected):
    assert score_prediction(prediction, gold, open_ended=True) is expected


def test_summarize():
    records = [
        {"task": "poi", "prediction": "A", "gold": "A", "usage": {"llm_calls": 5, "total_tokens": 1000}, "time_sec": 2},
        {"task": "poi", "prediction": "B", "gold": "A", "usage": {"llm_calls": 7, "total_tokens": 3000}, "time_sec": 4},
        {"task": "trip", "prediction": "C", "gold": "C", "error": None},
        {"task": "trip", "prediction": None, "gold": "C", "error": "TimeoutError"},
    ]
    summary = summarize(records, task_order=["trip", "poi"], display_names={"poi": "Place Info"})
    assert list(summary["tasks"]) == ["trip", "poi"]
    assert summary["tasks"]["poi"]["name"] == "Place Info"
    assert summary["n"] == 4 and summary["correct"] == 2 and summary["errors"] == 1
    assert summary["overall_accuracy"] == pytest.approx(50.0)
    assert summary["macro_accuracy"] == pytest.approx(50.0)
    assert summary["cost"]["avg_llm_calls"] == pytest.approx(3.0)
