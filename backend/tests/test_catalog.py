"""Unit tests for catalog helpers — pure logic, no B2 calls."""
from __future__ import annotations

from app.catalog import _extract_caption, sha256_of


def test_sha256_of_is_deterministic() -> None:
    a = sha256_of(b"hello world")
    b = sha256_of(b"hello world")
    assert a == b
    assert len(a) == 64
    assert all(c in "0123456789abcdef" for c in a)


def test_sha256_of_differs_by_one_bit() -> None:
    a = sha256_of(b"hello world")
    b = sha256_of(b"hello worle")  # single character diff
    assert a != b


def test_extract_caption_missing_step_returns_none() -> None:
    # Only one step — no caption step at all
    caption, model = _extract_caption([{"step_id": "s0", "assets": []}])
    assert caption is None
    assert model is None


def test_extract_caption_empty_steps_returns_none() -> None:
    caption, model = _extract_caption([])
    assert caption is None
    assert model is None


def test_extract_caption_from_step_text_field() -> None:
    steps = [
        {"step_id": "s0"},
        {"step_id": "s1", "model": "meta/llama-3.2-11b-vision-instruct",
         "text": "A red apple on a wooden table."},
    ]
    caption, model = _extract_caption(steps)
    assert caption == "A red apple on a wooden table."
    assert model == "meta/llama-3.2-11b-vision-instruct"


def test_extract_caption_from_step_output_text_field() -> None:
    # Genblaze also exposes text via 'output_text' on some providers
    steps = [
        {},
        {"model": "vlm", "output_text": "  a caption with padding  "},
    ]
    caption, model = _extract_caption(steps)
    assert caption == "a caption with padding"
    assert model == "vlm"


def test_extract_caption_from_text_asset() -> None:
    # Fallback: pull from a text/* asset attached to the step
    steps = [
        {},
        {"model": "vlm",
         "assets": [{"media_type": "text/plain", "text": "asset caption"}]},
    ]
    caption, model = _extract_caption(steps)
    assert caption == "asset caption"
    assert model == "vlm"


def test_extract_caption_from_asset_metadata_text() -> None:
    # NvidiaChatProvider stashes the real caption in metadata['text'] — its
    # asset.url/text fields are placeholders (see _patch_nvidia_chat_text_asset
    # in pipeline.py). This is the shape actually persisted in live manifests.
    steps = [
        {},
        {"model": "vlm",
         "assets": [{"media_type": "text/plain", "metadata": {"text": "metadata caption"}}]},
    ]
    caption, model = _extract_caption(steps)
    assert caption == "metadata caption"
    assert model == "vlm"


def test_extract_caption_ignores_non_text_asset() -> None:
    # A step with only an image asset should not produce a caption
    steps = [
        {},
        {"model": "vlm",
         "assets": [{"media_type": "image/png", "url": "b2://foo.png"}]},
    ]
    caption, model = _extract_caption(steps)
    assert caption is None
    assert model == "vlm"


def test_extract_caption_returns_model_even_on_failure() -> None:
    # If step 1 exists but produced no usable text, we still want to
    # know which model was attempted — useful for debugging.
    steps = [{}, {"model": "some-vlm", "status": "failed"}]
    caption, model = _extract_caption(steps)
    assert caption is None
    assert model == "some-vlm"
