"""Unit tests for the comic script parser -- no network, no B2.

The regex had a real bug caught during manual testing: NVIDIA's free-tier
chat model sometimes writes "PAGE 1 IMAGE: ..." on one line (space, not a
newline) instead of the prompted line-break format. These tests pin both
shapes so a future "tidy up the regex" pass can't silently regress it.
"""
from __future__ import annotations

from app.comics import _parse_script


def test_parse_script_with_newline_separated_fields() -> None:
    text = (
        "PAGE 1\n"
        "IMAGE: a lighthouse at dusk\n"
        "NARRATION: a keeper waits for the tide.\n\n"
        "PAGE 2\n"
        "IMAGE: a shooting star falls\n"
        "NARRATION: something wonderful arrives.\n"
    )
    panels = _parse_script(text, pages=2, style="comic")
    assert len(panels) == 2
    assert panels[0][0].startswith("a lighthouse at dusk")
    assert panels[0][1] == "a keeper waits for the tide."
    assert panels[1][1] == "something wonderful arrives."


def test_parse_script_with_space_separated_fields() -> None:
    # The real-world failure mode: no newline between "PAGE 1" and "IMAGE:".
    text = (
        "PAGE 1 IMAGE: a lighthouse at dusk "
        "NARRATION: a keeper waits for the tide.\n\n"
        "PAGE 2 IMAGE: a shooting star falls "
        "NARRATION: something wonderful arrives."
    )
    panels = _parse_script(text, pages=2, style="comic")
    assert len(panels) == 2
    assert panels[0][1] == "a keeper waits for the tide."
    assert panels[1][1] == "something wonderful arrives."
    # image_prompt must not leak the "PAGE n IMAGE:" scaffolding into the
    # actual prompt sent to the image provider.
    assert "PAGE" not in panels[0][0]
    assert "IMAGE:" not in panels[0][0]


def test_parse_script_applies_style_suffix() -> None:
    # Two pages, trailing newline after the last one -- exercises the real
    # regex path (not the single-page fallback, which would also happen to
    # contain the style suffix and could mask a regression).
    text = "PAGE 1\nIMAGE: a robot\nNARRATION: it dreams.\n\nPAGE 2\nIMAGE: a fox\nNARRATION: it runs.\n"
    comic_panels = _parse_script(text, pages=2, style="comic")
    anime_panels = _parse_script(text, pages=2, style="anime")
    assert len(comic_panels) == 2
    assert len(anime_panels) == 2
    assert "comic book" in comic_panels[0][0]
    assert "anime" in anime_panels[0][0]


def test_parse_script_handles_trailing_newline_after_last_page() -> None:
    # Regression guard: the lookahead's end-of-string branch must tolerate
    # trailing whitespace after the final page, or the last page silently
    # drops out of the match and the whole comic falls back to one page.
    text = "PAGE 1\nIMAGE: a robot\nNARRATION: it dreams.\n\nPAGE 2\nIMAGE: a fox\nNARRATION: it runs.\n"
    panels = _parse_script(text, pages=2, style="comic")
    assert len(panels) == 2
    assert panels[1][1] == "it runs."


def test_parse_script_truncates_to_requested_page_count() -> None:
    text = "\n\n".join(
        f"PAGE {i}\nIMAGE: scene {i}\nNARRATION: beat {i}." for i in range(1, 5)
    )
    panels = _parse_script(text, pages=2, style="comic")
    assert len(panels) == 2


def test_parse_script_falls_back_on_unparseable_text() -> None:
    # A model that ignores the format entirely should degrade to a single
    # page instead of raising or returning an empty list.
    panels = _parse_script("the model just wrote a paragraph instead", pages=3, style="comic")
    assert len(panels) == 1
    assert panels[0][1]  # narration is non-empty
