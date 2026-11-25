import pytest

from mapagent.modules import parse_place_and_radius
from mapagent.solver import canonical_module, default_pipeline, finalize_modules, parse_module_list


@pytest.mark.parametrize(
    "text, expected",
    [
        ('["map_service", "sequencer", "solution_generator", "answer_generator"]',
         ["map_service", "sequencer", "solution_generator", "answer_generator"]),
        ("Modules: ['google_maps', 'Solution_Generator', 'Answer_Generator']",
         ["google_maps", "Solution_Generator", "Answer_Generator"]),
        ("I would use the Map Service, then the Solution Generator and the Answer Generator.",
         ["map_service", "solution_generator", "answer_generator"]),
        ("no idea", None),
        ("", None),
    ],
)
def test_parse_module_list(text, expected):
    parsed = parse_module_list(text)
    if expected is None:
        assert parsed is None
    else:
        assert [canonical_module(x) for x in parsed] == [canonical_module(x) for x in expected]


def test_canonical_module_aliases():
    assert canonical_module("google_maps") == "map_service"
    assert canonical_module("Image_Search") == "visual_place_recognizer"
    assert canonical_module("Visual Place Recognizer module") == "visual_place_recognizer"
    assert canonical_module("bing_search") is None
    assert canonical_module("__import__('os')") is None


def test_finalize_modules():
    assert finalize_modules(["sequencer", "map_service"], has_image=False) == [
        "map_service", "sequencer", "solution_generator", "answer_generator"]
    assert finalize_modules(["visual_place_recognizer", "map_service"], has_image=False) == [
        "map_service", "solution_generator", "answer_generator"]
    assert finalize_modules(["map_service", "visual_place_recognizer"], has_image=True)[:2] == [
        "visual_place_recognizer", "map_service"]
    assert finalize_modules([], has_image=False) == ["solution_generator", "answer_generator"]
    assert default_pipeline(True)[0] == "visual_place_recognizer"


@pytest.mark.parametrize(
    "text, place, radius_km",
    [
        ("Radmansgatan 46, 113 57 Stockholm, Sweden 600 meters", "Radmansgatan 46, 113 57 Stockholm, Sweden", 0.6),
        ("Howth, Ireland 2 km", "Howth, Ireland", 2.0),
        ("Cole Street Guesthouse, 5 Cole St, Freetown, Sierra Leone, radius: 0.5 kilometers",
         "Cole Street Guesthouse, 5 Cole St, Freetown, Sierra Leone", 0.5),
        ("Dubai Mall, Dubai 800", "Dubai Mall, Dubai", 0.8),
        ("Times Square, New York", "Times Square, New York", None),
    ],
)
def test_parse_place_and_radius(text, place, radius_km):
    parsed_place, parsed_radius = parse_place_and_radius(text)
    assert parsed_place == place
    assert parsed_radius == (pytest.approx(radius_km) if radius_km is not None else None)
