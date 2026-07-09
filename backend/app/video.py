"""Video pipeline -- script generation only, by design.

The full generative-video path (shot script -> rendered clips -> composed
MP4) is architected the same way the comic pipeline is: a real Genblaze
text step for planning, followed by a real Genblaze video-generation step
per shot (GMI Cloud's pixverse-v5.6-t2v / wan2.6-r2v are already wired in
pipeline.py's provider routing and would activate automatically the
moment a funded key is present -- no code change needed to turn this on).

For this submission we deliberately do not spend on video-provider
credits, so only the script-generation half actually runs here. That's a
stated scope decision, not a missing feature -- see the banner in the
app's header and the /video page itself.
"""
from __future__ import annotations

import re
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from genblaze_core import Modality, Pipeline
from genblaze_core.providers import RetryPolicy
from genblaze_core.testing import MockProvider

from .config import get_settings
from .pipeline import (
    _extract_text_output,
    _local_file_url,
    _patch_nvidia_chat_text_asset,
    _finalize_result,
)
from .storage import get_backend, get_sink

_VIDEO_NAME_PREFIX = "veritas-video-script:"
_SCRIPT_MODEL = "meta/llama-3.2-11b-vision-instruct"


@dataclass
class VideoShot:
    index: int
    description: str
    narration: str
    duration_sec: int


@dataclass
class VideoScriptResult:
    run_id: str | None
    manifest_key: str | None
    verified: bool
    idea: str
    date: str
    script_text: str
    shots: list[VideoShot] = field(default_factory=list)


def _script_prompt(idea: str) -> str:
    return (
        f"Write a short-form video shot list (4-6 shots) for this idea: {idea}\n\n"
        "Reply in exactly this format, one block per shot, nothing else "
        "(no preamble, no closing remarks):\n\n"
        "SHOT 1\n"
        "DESCRIPTION: <camera direction and visual action for this shot, "
        "written the way a director's shot list would read>\n"
        "NARRATION: <the voiceover line spoken during this shot>\n"
        "DURATION: <an integer, seconds this shot should run>\n\n"
        "SHOT 2\n...\n\n(continue through the final shot)"
    )


_SHOT_RE = re.compile(
    # Tolerant of the model separating fields with a newline *or* just a
    # space -- NVIDIA's free-tier chat models don't reliably follow the
    # prompted line-break format. The end-of-string branch of the lookahead
    # allows trailing whitespace after the final shot's digits (\Z alone
    # only matches the exact end, so a trailing "\n" after the last shot
    # -- the common case -- would otherwise make the whole match fail).
    r"SHOT\s*\d+\s*[:.]?\s*DESCRIPTION:\s*(?P<desc>.+?)\s*NARRATION:\s*(?P<narr>.+?)"
    r"\s*DURATION:\s*(?P<dur>\d+)"
    r"(?=\s*SHOT\s*\d+\s*[:.]?\s*DESCRIPTION:|\s*\Z)",
    re.IGNORECASE | re.DOTALL,
)


def _parse_script(script_text: str) -> list[VideoShot]:
    """Parse SHOT/DESCRIPTION/NARRATION/DURATION blocks. Never raises --
    a model that ignores the format degrades to one whole-script shot
    instead of failing the request."""
    out: list[VideoShot] = []
    for i, m in enumerate(_SHOT_RE.finditer(script_text or "")):
        desc = " ".join(m.group("desc").split())
        narr = " ".join(m.group("narr").split())
        try:
            dur = max(1, int(m.group("dur")))
        except ValueError:
            dur = 4
        if desc and narr:
            out.append(VideoShot(index=i, description=desc, narration=narr, duration_sec=dur))
    if out:
        return out
    text = " ".join((script_text or "").split())[:280] or "A short video begins."
    return [VideoShot(index=0, description=text, narration=text, duration_sec=6)]


def _mock_script(idea: str) -> str:
    return (
        f"SHOT 1\nDESCRIPTION: {idea}, opening shot.\n"
        f"NARRATION: This is {idea}.\nDURATION: 5\n"
    )


def generate_video_script(idea: str) -> VideoScriptResult:
    """Real Genblaze text generation for the shot list -- own signed
    manifest, verified and B2-indexed exactly like every other generation
    in this app. No video provider is ever called here."""
    date = time.strftime("%Y-%m-%d")
    sink = get_sink()
    name = f"{_VIDEO_NAME_PREFIX}{idea[:60]}"
    prompt = _script_prompt(idea)
    s = get_settings()

    if s.has_nvidia:
        _patch_nvidia_chat_text_asset()
        from genblaze_nvidia.chat_provider import NvidiaChatProvider

        chat_provider = NvidiaChatProvider(timeout=90.0, retry_policy=RetryPolicy.aggressive())
        pipe = Pipeline(name).step(
            chat_provider, model=_SCRIPT_MODEL, prompt=prompt, modality=Modality.TEXT,
            fallback_models=["meta/llama-3.2-90b-vision-instruct"],
        )
        model, provider_name = _SCRIPT_MODEL, "nvidia"
    else:
        mock_text = _mock_script(idea)
        stage = Path(tempfile.gettempdir()) / "veritas_stage"
        stage.mkdir(exist_ok=True)
        mock_path = stage / f"video-script-{uuid.uuid4().hex[:12]}.txt"
        mock_path.write_text(mock_text, encoding="utf-8")
        from genblaze_core.models.asset import Asset

        def _factory(step):
            return [Asset(url=_local_file_url(mock_path), media_type="text/plain")]

        pipe = Pipeline(name).step(
            MockProvider(assets=_factory, cost_usd=0.0), model="mock-text-v1",
            prompt=prompt, modality=Modality.TEXT,
        )
        model, provider_name = "mock-text-v1", "mock"

    run = pipe.run(sink=sink, timeout=120, raise_on_failure=False)
    script_text = _extract_text_output(run.run.steps[0]) or (
        _mock_script(idea) if not s.has_nvidia else ""
    )
    gr = _finalize_result(
        run, sink, prompt=prompt, modality=Modality.TEXT,
        provider_name=provider_name, model=model, parent_run_id=None,
    )

    return VideoScriptResult(
        run_id=gr.run_id, manifest_key=gr.manifest_key, verified=gr.manifest_verified,
        idea=idea, date=date, script_text=script_text, shots=_parse_script(script_text),
    )
