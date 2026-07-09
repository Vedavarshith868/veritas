"""Comic generation: theme -> Genblaze-scripted story -> Genblaze-generated
panel images -> Pillow-composed strip -> edge-tts narration per page.

Provenance boundary, stated plainly (the same honesty as the official
Genblaze reference sample's own "ffmpeg is our one non-Genblaze adapter"
framing): the script and every panel image are real Genblaze Pipeline
runs, each with its own signed manifest, verified the exact same way
every other generation in this app is verified. Compositing the panels
into one strip and synthesizing narration audio are NOT Genblaze
capabilities -- there is no Genblaze image-compositing or local-TTS
provider -- so those two steps use Pillow and edge-tts (free, no API key,
the same engine this project's own demo-video narration uses) directly.
Both derived files still get uploaded to B2, hashed, and registered in
the same sha-256 verify-index as every Genblaze-generated asset, so
/verify recognizes them too.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
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
    GenerationResult,
    _build_pipeline,
    _extract_text_output,
    _local_file_url,
    _patch_nvidia_chat_text_asset,
    _finalize_result,
)
from .storage import get_backend, get_sink, read_bytes

_COMIC_NAME_PREFIX = "veritas-comic:"
_COMIC_SCRIPT_NAME_PREFIX = "veritas-comic-script:"
_SCRIPT_MODEL = "meta/llama-3.2-11b-vision-instruct"
_NARRATION_VOICE = "en-US-ChristopherNeural"
_STYLE_SUFFIXES = {
    "comic": ", bold comic book panel art, ink outlines, halftone shading, dynamic composition",
    "anime": ", anime key art, cel shading, vibrant colors, expressive character art",
}


@dataclass
class ComicPage:
    index: int
    image_prompt: str
    narration_text: str
    image_run_id: str | None = None
    image_manifest_key: str | None = None
    image_asset_key: str | None = None
    image_sha256: str | None = None
    image_verified: bool = False
    narration_asset_key: str | None = None
    narration_sha256: str | None = None


@dataclass
class ComicResult:
    comic_id: str
    theme: str
    style: str
    date: str
    script_run_id: str | None
    script_manifest_key: str | None
    script_verified: bool
    script_text: str
    pages: list[ComicPage] = field(default_factory=list)
    composed_asset_key: str | None = None
    composed_sha256: str | None = None


def _comic_json_key(comic_id: str, date: str) -> str:
    return f"{get_settings().prefix}/comics/{date}/{comic_id}/comic.json"


def _script_prompt(theme: str, pages: int, style: str) -> str:
    return (
        f"Write a {pages}-page {style} story about: {theme}\n\n"
        "Reply in exactly this format, one block per page, nothing else "
        "(no preamble, no closing remarks):\n\n"
        "PAGE 1\n"
        "IMAGE: <a single vivid visual description of this page's key scene, "
        "written as a direct image-generation prompt -- concrete subjects, "
        "setting, action, no meta-commentary>\n"
        "NARRATION: <one or two short sentences a narrator would read aloud "
        "for this page>\n\n"
        f"PAGE 2\n...\n\n(continue through PAGE {pages})"
    )


_PAGE_RE = re.compile(
    # Tolerant of the model separating PAGE/IMAGE/NARRATION with a newline
    # *or* just a space -- NVIDIA's free-tier chat models don't reliably
    # follow the prompted line-break format. The trailing \s* before \Z
    # tolerates trailing whitespace after the final page (see the
    # equivalent, more visibly broken case in video.py's _SHOT_RE).
    r"PAGE\s*\d+\s*[:.]?\s*IMAGE:\s*(?P<image>.+?)\s*NARRATION:\s*(?P<narration>.+?)"
    r"(?=\s*PAGE\s*\d+\s*[:.]?\s*IMAGE:|\s*\Z)",
    re.IGNORECASE | re.DOTALL,
)


def _parse_script(script_text: str, pages: int, style: str) -> list[tuple[str, str]]:
    """Parse the model's PAGE/IMAGE/NARRATION blocks. Never raises -- a
    model that doesn't follow the format degrades to a single-page
    fallback instead of failing the whole comic."""
    suffix = _STYLE_SUFFIXES.get(style, _STYLE_SUFFIXES["comic"])
    out: list[tuple[str, str]] = []
    for m in _PAGE_RE.finditer(script_text or ""):
        image = " ".join(m.group("image").split())
        narration = " ".join(m.group("narration").split())
        if image and narration:
            out.append((image + suffix, narration))
    if out:
        return out[:pages]
    narration = " ".join((script_text or "").split())[:280] or "A story begins."
    return [(f"{narration}{suffix}", narration)]


def _mock_script(theme: str, pages: int) -> str:
    """Zero-cost fallback when no NVIDIA key is configured -- mirrors
    pipeline.py's mock-image philosophy: the loop still runs for real,
    just without paid inference."""
    blocks = []
    for i in range(1, pages + 1):
        blocks.append(
            f"PAGE {i}\nIMAGE: {theme}, panel {i} of {pages}\n"
            f"NARRATION: Page {i} of {theme}.\n"
        )
    return "\n".join(blocks)


def _synthesize_narration(text: str) -> bytes:
    """Free, local, no-API-key narration via Microsoft's edge-tts -- the
    same engine this project's own demo-video narration uses."""
    import edge_tts

    async def _run() -> bytes:
        path = Path(tempfile.gettempdir()) / f"veritas-narration-{uuid.uuid4().hex[:12]}.mp3"
        communicate = edge_tts.Communicate(text, _NARRATION_VOICE, rate="+2%")
        await communicate.save(str(path))
        try:
            return path.read_bytes()
        finally:
            path.unlink(missing_ok=True)

    return asyncio.run(_run())


def _compose_strip(panel_images: list[bytes]) -> bytes:
    """Stack every panel into one vertical strip -- a real comic page, not
    just a gallery. The only non-Genblaze *visual* step, exactly like the
    reference sample's own ffmpeg composition stage."""
    from PIL import Image

    ACCENT = (250, 204, 21)
    GUTTER = 16
    TARGET_W = 900

    frames: list[Image.Image] = []
    for data in panel_images:
        im = Image.open(io.BytesIO(data)).convert("RGB")
        ratio = TARGET_W / im.width
        frames.append(im.resize((TARGET_W, max(1, int(im.height * ratio)))))
    if not frames:
        raise RuntimeError("no panel images to compose")

    total_h = sum(f.height for f in frames) + GUTTER * (len(frames) + 1)
    canvas = Image.new("RGB", (TARGET_W + GUTTER * 2, total_h), (8, 8, 9))
    y = GUTTER
    for f in frames:
        bordered = Image.new("RGB", (f.width + 6, f.height + 6), ACCENT)
        bordered.paste(f, (3, 3))
        canvas.paste(bordered, (GUTTER - 3, y - 3))
        y += f.height + GUTTER

    out = io.BytesIO()
    canvas.save(out, "PNG")
    return out.getvalue()


def _upload_derived_asset(
    *, comic_id: str, date: str, filename: str, data: bytes, media_type: str,
    provider: str, prompt: str,
) -> tuple[str, str]:
    """Upload a non-Genblaze-generated file (composited strip, narration
    audio) and register it in the same sha-256 verify-index every
    Genblaze-generated asset uses, via a synthetic GenerationResult --
    reuses the existing indexer unchanged rather than inventing a second
    index schema. manifest_verified is honestly False here: this file
    never passed through Genblaze's Manifest.verify(), it's app-level
    post-processing, not an AI generation."""
    from . import indexer

    key = f"{get_settings().prefix}/comics/{date}/{comic_id}/{filename}"
    sha256 = hashlib.sha256(data).hexdigest()
    get_backend().put(key, data, content_type=media_type)

    fake_gr = GenerationResult(
        run_id=comic_id,
        parent_run_id=None,
        prompt=prompt,
        modality="image" if media_type.startswith("image") else "audio",
        provider=provider,
        model="pillow" if media_type.startswith("image") else "edge-tts",
        asset_url=key,
        asset_key=key,
        sha256=sha256,
        size_bytes=len(data),
        media_type=media_type,
        manifest_verified=False,
        manifest_key=None,
    )
    indexer.write_verify_index(fake_gr)
    return key, sha256


def generate_comic(theme: str, pages: int = 4, style: str = "comic") -> ComicResult:
    """Full multi-step comic pipeline.

    Real Genblaze provenance for the two AI-generated parts (script text,
    panel images) -- each is its own signed, verified Pipeline run, grouped
    under one comic_id via Genblaze's own project_id, exactly the
    mechanism campaigns already use for grouping variants. Compositing and
    narration are app-level post-processing (see module docstring) but
    still land in B2, hashed and indexed like everything else.
    """
    if not (1 <= pages <= 8):
        raise ValueError("pages must be between 1 and 8")
    style = style if style in _STYLE_SUFFIXES else "comic"
    comic_id = str(uuid.uuid4())
    date = time.strftime("%Y-%m-%d")
    sink = get_sink()
    name = f"{_COMIC_NAME_PREFIX}{theme[:60]}"
    # Distinct name prefix from the panel-image runs above, so the frontend
    # can reliably filter the text-only script run out of image galleries
    # (it has no image to show) while still finding it via project_id.
    script_name = f"{_COMIC_SCRIPT_NAME_PREFIX}{theme[:50]}"

    # --- Step 1: the script, as a real single-step Genblaze run -----------
    s = get_settings()
    prompt = _script_prompt(theme, pages, style)
    if s.has_nvidia:
        _patch_nvidia_chat_text_asset()
        from genblaze_nvidia.chat_provider import NvidiaChatProvider

        chat_provider = NvidiaChatProvider(timeout=90.0, retry_policy=RetryPolicy.aggressive())
        script_pipe = Pipeline(script_name, project_id=comic_id).step(
            chat_provider, model=_SCRIPT_MODEL, prompt=prompt, modality=Modality.TEXT,
            fallback_models=["meta/llama-3.2-90b-vision-instruct"],
        )
        script_model = _SCRIPT_MODEL
        script_provider_name = "nvidia"
    else:
        # Zero-cost path: a real local text file through the exact same
        # MockProvider/Pipeline/manifest loop pipeline.py uses for mock
        # images, so the comic feature never hard-fails without a key.
        mock_text = _mock_script(theme, pages)
        stage = Path(tempfile.gettempdir()) / "veritas_stage"
        stage.mkdir(exist_ok=True)
        mock_path = stage / f"comic-script-{uuid.uuid4().hex[:12]}.txt"
        mock_path.write_text(mock_text, encoding="utf-8")
        from genblaze_core.models.asset import Asset

        def _factory(step):
            return [Asset(url=_local_file_url(mock_path), media_type="text/plain")]

        script_pipe = Pipeline(script_name, project_id=comic_id).step(
            MockProvider(assets=_factory, cost_usd=0.0), model="mock-text-v1",
            prompt=prompt, modality=Modality.TEXT,
        )
        script_model = "mock-text-v1"
        script_provider_name = "mock"

    script_run = script_pipe.run(sink=sink, timeout=120, raise_on_failure=False)
    script_text = _extract_text_output(script_run.run.steps[0]) or (
        _mock_script(theme, pages) if not s.has_nvidia else ""
    )
    script_gr = _finalize_result(
        script_run, sink, prompt=prompt, modality=Modality.TEXT,
        provider_name=script_provider_name, model=script_model, parent_run_id=None,
    )

    panels = _parse_script(script_text, pages, style)

    # --- Step 2: every panel's image, one real Genblaze batch_run --------
    image_prompts = [p[0] for p in panels]
    img_pipe, img_provider, img_model = _build_pipeline(
        image_prompts[0], Modality.IMAGE, project_id=comic_id, name=name,
    )
    image_results = img_pipe.batch_run(
        prompts=image_prompts, sink=sink, fail_fast=False,
        raise_on_failure=False, max_concurrency=3,
    )

    pages_out: list[ComicPage] = []
    panel_bytes: list[bytes] = []
    for i, ((image_prompt, narration), result) in enumerate(zip(panels, image_results)):
        try:
            gr = _finalize_result(
                result, sink, prompt=image_prompt, modality=Modality.IMAGE,
                provider_name=img_provider, model=img_model, parent_run_id=None,
            )
        except Exception:
            continue
        page = ComicPage(
            index=i, image_prompt=image_prompt, narration_text=narration,
            image_run_id=gr.run_id, image_manifest_key=gr.manifest_key,
            image_asset_key=gr.asset_key, image_sha256=gr.sha256,
            image_verified=gr.manifest_verified,
        )
        try:
            data = read_bytes(gr.asset_key)
            panel_bytes.append(data)
        except Exception:
            data = None
        # --- Step 3: narration for this page, uploaded + indexed --------
        try:
            audio = _synthesize_narration(narration)
            n_key, n_sha = _upload_derived_asset(
                comic_id=comic_id, date=date, filename=f"narration/page_{i}.mp3",
                data=audio, media_type="audio/mpeg", provider="veritas-tts",
                prompt=narration,
            )
            page.narration_asset_key = n_key
            page.narration_sha256 = n_sha
        except Exception:
            pass
        pages_out.append(page)

    # --- Step 4: composite every generated panel into one strip ----------
    composed_key = composed_sha = None
    if panel_bytes:
        try:
            composed = _compose_strip(panel_bytes)
            composed_key, composed_sha = _upload_derived_asset(
                comic_id=comic_id, date=date, filename="composed.png",
                data=composed, media_type="image/png", provider="veritas-composer",
                prompt=f"composed strip for: {theme}",
            )
        except Exception:
            pass

    result = ComicResult(
        comic_id=comic_id, theme=theme, style=style, date=date,
        script_run_id=script_gr.run_id, script_manifest_key=script_gr.manifest_key,
        script_verified=script_gr.manifest_verified, script_text=script_text,
        pages=pages_out, composed_asset_key=composed_key, composed_sha256=composed_sha,
    )
    _write_comic_record(result)
    return result


def _write_comic_record(r: ComicResult) -> None:
    body = asdict(r)
    get_backend().put(
        _comic_json_key(r.comic_id, r.date),
        json.dumps(body, ensure_ascii=False, default=str).encode("utf-8"),
        content_type="application/json",
    )


def list_comics(limit: int = 30) -> list[dict[str, Any]]:
    """Newest-first comic records, straight from B2 -- same 'no separate
    database' story as everything else in this app."""
    from .storage import list_keys, read_json

    keys = [
        k for k in list_keys(f"{get_settings().prefix}/comics/")
        if k.endswith("comic.json")
    ]
    keys.sort(reverse=True)
    out: list[dict[str, Any]] = []
    for key in keys[:limit]:
        try:
            out.append(read_json(key))
        except Exception:
            continue
    return out
