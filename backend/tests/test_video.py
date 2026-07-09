"""Unit tests for the video shot-list parser -- no network, no B2."""
from __future__ import annotations

from app.video import _parse_script


def test_parse_script_with_newline_separated_fields() -> None:
    text = (
        "SHOT 1\n"
        "DESCRIPTION: a hiker crests a ridge at sunrise\n"
        "NARRATION: power your adventures.\n"
        "DURATION: 5\n\n"
        "SHOT 2\n"
        "DESCRIPTION: close-up on solar panels charging\n"
        "NARRATION: harness the sun.\n"
        "DURATION: 3\n"
    )
    shots = _parse_script(text)
    assert len(shots) == 2
    assert shots[0].description == "a hiker crests a ridge at sunrise"
    assert shots[0].narration == "power your adventures."
    assert shots[0].duration_sec == 5
    assert shots[1].duration_sec == 3


def test_parse_script_with_space_separated_fields() -> None:
    # Same real-world failure mode as the comic parser: no newline between
    # "SHOT 1" and "DESCRIPTION:".
    text = (
        "SHOT 1 DESCRIPTION: a hiker crests a ridge "
        "NARRATION: power your adventures. DURATION: 5\n\n"
        "SHOT 2 DESCRIPTION: solar panels charging "
        "NARRATION: harness the sun. DURATION: 3"
    )
    shots = _parse_script(text)
    assert len(shots) == 2
    assert shots[0].narration == "power your adventures."
    assert shots[1].duration_sec == 3
    assert "SHOT" not in shots[0].description
    assert "DESCRIPTION:" not in shots[0].description


def test_parse_script_falls_back_on_unparseable_text() -> None:
    shots = _parse_script("the model just wrote a paragraph instead")
    assert len(shots) == 1
    assert shots[0].narration
    assert shots[0].duration_sec > 0


def test_parse_script_handles_non_numeric_duration_gracefully() -> None:
    # DURATION requires at least one digit by construction, so a model that
    # writes a non-numeric duration fails the whole-shot regex match and
    # degrades to the single-shot fallback -- never raises.
    text = "SHOT 1\nDESCRIPTION: a scene\nNARRATION: a line\nDURATION: not-a-number\n"
    shots = _parse_script(text)
    assert len(shots) == 1
    assert shots[0].duration_sec > 0
