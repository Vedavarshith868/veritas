"""Unit tests for pipeline pure helpers — no network, no B2."""
from __future__ import annotations

import os

from app.pipeline import _extract_text_output, _local_file_url


class _FakeStep:
    """Duck-typed stand-in for a genblaze step object."""

    def __init__(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeAsset:
    def __init__(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


def test_local_file_url_uses_forward_slashes() -> None:
    from pathlib import Path

    p = Path.cwd() / "sample.png"
    url = _local_file_url(p)
    assert url.startswith("file:")
    # Windows drive-letter colon is preserved; separators are all forward
    assert "\\" not in url


def test_local_file_url_is_absolute() -> None:
    from pathlib import Path

    url = _local_file_url(Path("relative.png"))
    # resolve() makes it absolute; on Windows this includes a drive letter,
    # on POSIX a leading /
    tail = url[len("file:") :]
    assert tail.startswith("/") or (len(tail) > 2 and tail[1] == ":")


def test_extract_text_from_step_text_attr() -> None:
    step = _FakeStep(text="a photo of a cat")
    assert _extract_text_output(step) == "a photo of a cat"


def test_extract_text_from_step_output_text_attr() -> None:
    step = _FakeStep(text=None, output_text="fallback field")
    assert _extract_text_output(step) == "fallback field"


def test_extract_text_ignores_whitespace_only() -> None:
    step = _FakeStep(text="   \n  ", output_text=None, assets=[])
    assert _extract_text_output(step) is None


def test_extract_text_from_text_asset() -> None:
    step = _FakeStep(
        text=None,
        output_text=None,
        assets=[_FakeAsset(media_type="text/plain", text="asset text")],
    )
    assert _extract_text_output(step) == "asset text"


def test_extract_text_ignores_image_asset() -> None:
    step = _FakeStep(
        text=None,
        output_text=None,
        assets=[_FakeAsset(media_type="image/png", url="b2://foo.png")],
    )
    assert _extract_text_output(step) is None


def test_extract_text_decodes_data_url() -> None:
    # Some providers return text as a data: URL; helper should decode.
    import base64

    payload = base64.b64encode(b"decoded caption").decode()
    step = _FakeStep(
        text=None,
        output_text=None,
        assets=[
            _FakeAsset(
                media_type="text/plain",
                text=None,
                url=f"data:text/plain;base64,{payload}",
            )
        ],
    )
    assert _extract_text_output(step) == "decoded caption"
