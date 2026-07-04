"""Veritas provenance pipeline.

Core idea: every generated asset flows through a Genblaze Pipeline that
(1) generates media, (2) uploads it to Backblaze B2 via the storage sink,
and (3) produces a cryptographically verifiable provenance manifest that is
persisted alongside the asset.

Two provider modes:
  * "mock"  — MockProvider returning a real, locally-rendered PNG. Lets the
              full generate->store->manifest->verify loop run with zero API
              cost (used until real provider keys are added).
  * "gmi"   — GMICloud provider (video/image) when GMI_API_KEY is set.

The rest of the app only calls generate_media(); provider selection is here.
"""
from __future__ import annotations

import os
import tempfile
import textwrap
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from genblaze_core import Modality, Pipeline
from genblaze_core.models.asset import Asset
from genblaze_core.models.step import Step
from genblaze_core.testing import MockProvider

from .config import get_settings
from .storage import get_sink

# Directory where mock/staged source bytes live before upload.
_STAGE_DIR = Path(tempfile.gettempdir()) / "veritas_stage"
_STAGE_DIR.mkdir(exist_ok=True)


@dataclass
class GenerationResult:
    run_id: str
    parent_run_id: str | None
    prompt: str
    modality: str
    provider: str
    model: str
    asset_url: str          # durable/back-end URL on B2
    asset_key: str          # B2 object key
    sha256: str
    size_bytes: int | None
    media_type: str
    manifest_verified: bool
    manifest_key: str | None
    manifest: dict[str, Any] = field(default_factory=dict)


def _render_placeholder_png(prompt: str) -> Path:
    """Render a real PNG containing the prompt text (mock-mode 'generation')."""
    from PIL import Image, ImageDraw

    W, H = 1024, 576
    img = Image.new("RGB", (W, H), (18, 20, 28))
    d = ImageDraw.Draw(img)
    # Simple gradient bar for a touch of polish.
    for x in range(W):
        d.line([(x, 0), (x, 8)], fill=(80 + x % 120, 40, 160 - x % 120))
    d.text((40, 60), "VERITAS · provenance-first generative media",
           fill=(235, 235, 245))
    wrapped = textwrap.fill(prompt, width=52)
    d.multiline_text((40, 140), wrapped, fill=(180, 200, 255), spacing=10)
    d.text((40, H - 60), f"mock render · {time.strftime('%Y-%m-%d %H:%M:%S')}",
           fill=(120, 130, 150))
    out = _STAGE_DIR / f"mock_{int(time.time()*1000)}.png"
    img.save(out, "PNG")
    return out


def _patch_nvidia_windows_file_uri() -> None:
    """Work around a Windows bug in genblaze_nvidia's file:// URI builder.

    ``save_bytes_to_output_dir`` returns ``path.resolve().as_uri()``, which
    on Windows yields ``file:///C:/...``. Genblaze's own transfer layer then
    does ``Path(urlparse(url).path)``, and for that scheme the path
    component (``/C:/...``) mangles into a drive-relative path
    (``C:Users\\...``) that fails its allowlist check. Same root cause as
    the fix in ``_local_file_url`` below, applied to third-party code we
    don't own. No-op on non-Windows or if the upstream signature changes.
    """
    if os.name != "nt":
        return
    try:
        from genblaze_nvidia import image as _nvidia_image
    except ImportError:
        return

    original = _nvidia_image.save_bytes_to_output_dir

    def _patched(payload: bytes, output_dir, *, extension: str, prefix: str = "nvidia") -> str:
        import uuid

        base = Path(output_dir) if output_dir is not None else Path.cwd()
        base.mkdir(parents=True, exist_ok=True)
        filename = f"{prefix}-{uuid.uuid4().hex[:12]}.{extension.lstrip('.')}"
        p = base / filename
        p.write_bytes(payload)
        return _local_file_url(p)

    if getattr(original, "__module__", "") != __name__:
        _nvidia_image.save_bytes_to_output_dir = _patched


def _local_file_url(path: Path) -> str:
    """Cross-platform file: URL that Genblaze's transfer parser resolves correctly.

    Genblaze does ``Path(urlparse(url).path)``. On Windows, ``Path.as_uri()``
    yields ``file:///C:/...`` whose path (``/C:/...``) mangles to a
    drive-relative path. Using ``file:`` + forward-slashed absolute path keeps
    ``parsed.path`` a valid absolute path on both Windows and POSIX.
    """
    return "file:" + str(path.resolve()).replace(os.sep, "/")


def _mock_asset_factory(prompt: str):
    """Build a MockProvider assets factory that points at a real local PNG."""
    path = _render_placeholder_png(prompt)
    url = _local_file_url(path)  # file: URL the sink can read

    def factory(step: Step) -> list[Asset]:
        return [Asset(url=url, media_type="image/png")]

    return factory


def _build_pipeline(
    prompt: str,
    modality: Modality,
    *,
    project_id: str | None = None,
    name: str = "veritas-generate",
) -> tuple[Pipeline, str, str]:
    """Return (pipeline, provider_name, model) for the given request.

    Real providers activate per-modality when their key is present and
    VERITAS_PROVIDER != "mock": GMICloud for image/video, ElevenLabs for
    audio. Falls back to MockProvider (real local PNG, zero cost) otherwise.

    ``project_id`` groups related runs (e.g. campaign fan-outs) — it's
    persisted on the Run and readable back from the manifest.
    """
    s = get_settings()

    # Image: NVIDIA first — confirmed working on this account's free tier.
    # GMI's image path is fully wired but its account has 0 credits right
    # now; it stays as the second choice for whenever that clears.
    if s.has_nvidia and modality == Modality.IMAGE:
        # Probed LIVE on this account: flux.1-dev works; SDXL/flux-schnell
        # were not enabled on this account key, so they're not used as
        # fallbacks here (a bad fallback is worse than none).
        from genblaze_nvidia.image import NvidiaImageProvider

        _patch_nvidia_windows_file_uri()
        # output_dir must be under the OS temp dir — the sink's file://
        # allowlist rejects paths elsewhere (e.g. the provider's CWD default).
        provider = NvidiaImageProvider(output_dir=_STAGE_DIR)
        model = "black-forest-labs/flux.1-dev"
        pipe = Pipeline(name, project_id=project_id).step(
            provider, model=model, prompt=prompt, modality=Modality.IMAGE,
        )
        return pipe, "nvidia", model

    if s.has_gmi and modality == Modality.IMAGE:
        # Real image generation with a genuine fallback chain (probed LIVE
        # on this account: seedream 4.0 -> 3.0).
        from genblaze_gmicloud import GMICloudImageProvider

        provider = GMICloudImageProvider()
        model = "seedream-4-0-250828"
        pipe = Pipeline(name, project_id=project_id).step(
            provider, model=model, prompt=prompt, modality=Modality.IMAGE,
            fallback_models=["seedream-3-0-t2i-250415"],
        )
        return pipe, "gmicloud", model

    if s.has_gmi and modality == Modality.VIDEO:
        from genblaze_gmicloud import GMICloudVideoProvider

        provider = GMICloudVideoProvider()
        model = "pixverse-v5.6-t2v"  # probed LIVE; wan2.6-r2v as fallback
        pipe = Pipeline(name, project_id=project_id).step(
            provider, model=model, prompt=prompt, modality=Modality.VIDEO,
            fallback_models=["wan2.6-r2v"],
        )
        return pipe, "gmicloud", model

    if s.has_elevenlabs and modality == Modality.AUDIO:
        from genblaze_elevenlabs import ElevenLabsTTSProvider

        provider = ElevenLabsTTSProvider()
        model = "eleven_flash_v2_5"  # cheapest/fastest; turbo_v2_5 as fallback
        pipe = Pipeline(name, project_id=project_id).step(
            provider, model=model, prompt=prompt, modality=Modality.AUDIO,
            fallback_models=["eleven_turbo_v2_5"],
        )
        return pipe, "elevenlabs", model

    # Mock path — real local PNG, real B2 upload, real manifest.
    provider = MockProvider(assets=_mock_asset_factory(prompt), cost_usd=0.0)
    model = "mock-image-v1"
    pipe = Pipeline(name, project_id=project_id).step(
        provider, model=model, prompt=prompt, modality=Modality.IMAGE,
    )
    return pipe, "mock", model


def _finalize_result(
    result: Any,
    sink: Any,
    *,
    prompt: str,
    modality: Modality,
    provider_name: str,
    model: str,
    parent_run_id: str | None,
) -> GenerationResult:
    """Shared post-processing for a single completed PipelineResult.

    Extracts the output asset + manifest, then applies the B2 hardening
    (verify-index, metadata stamp, WORM lock). Used by both a single
    generate_media() run and each item of a generate_campaign() batch.
    """
    run = result.run
    step = run.steps[0]
    if not step.assets:
        detail = getattr(step, "error", None) or getattr(step, "status", "unknown")
        raise RuntimeError(f"generation step produced no assets: {detail}")
    asset = step.assets[0]

    manifest = result.manifest
    verified = bool(manifest.verify()) if manifest is not None else False

    manifest_key = None
    manifest_dict: dict[str, Any] = {}
    if manifest is not None:
        try:
            manifest_key = sink.manifest_key_for(run)
        except Exception:
            manifest_key = None
        try:
            manifest_dict = manifest.model_dump(mode="json")
        except Exception:
            manifest_dict = {}

    asset_key = asset.url.split(f"{get_settings().b2_bucket}/", 1)[-1]

    gr = GenerationResult(
        run_id=str(getattr(run, "run_id", getattr(run, "id", ""))),
        parent_run_id=getattr(run, "parent_run_id", None) or parent_run_id,
        prompt=prompt,
        modality=modality.value,
        provider=provider_name,
        model=model,
        asset_url=asset.url,
        asset_key=asset_key,
        sha256=asset.sha256 or "",
        size_bytes=asset.size_bytes,
        media_type=asset.media_type,
        manifest_verified=verified,
        manifest_key=manifest_key,
        manifest=manifest_dict,
    )

    # B2 hardening (best-effort): O(1) verify index + self-describing asset
    # metadata + WORM compliance copy. Failures degrade gracefully.
    from . import compliance, indexer

    indexer.write_verify_index(gr)
    indexer.stamp_asset_metadata(gr)
    if manifest_dict:
        locked_key = compliance.write_locked_manifest(gr.run_id, manifest_dict)
        if locked_key:
            gr.manifest["locked_copy"] = locked_key
    return gr


def generate_media(
    prompt: str, modality: str = "image", parent_run_id: str | None = None
) -> GenerationResult:
    """Run the provenance pipeline end-to-end and return a structured result.

    ``parent_run_id`` links this run to a previous iteration (Genblaze
    lineage): the manifest records the pointer, so "regenerate" chains are
    auditable end-to-end.
    """
    mod = Modality(modality)
    sink = get_sink()  # fresh sink per run (sink is spent on close)
    pipe, provider_name, model = _build_pipeline(prompt, mod)
    if parent_run_id:
        # Same mechanism as Pipeline.from_result(), from a persisted run id.
        pipe._parent_run_id = parent_run_id

    result = pipe.run(sink=sink, timeout=600, raise_on_failure=False)
    return _finalize_result(
        result, sink,
        prompt=prompt, modality=mod, provider_name=provider_name, model=model,
        parent_run_id=parent_run_id,
    )


def generate_campaign(
    brief: str, variant_prompts: list[str], modality: str = "image"
) -> tuple[str, list[GenerationResult]]:
    """Fan out N provable variants for one campaign brief.

    Uses Genblaze's ``Pipeline.batch_run`` — a single orchestration call
    that runs each variant independently (own Run, own manifest) and
    returns results in input order — rather than N sequential generate()
    calls. Every variant lands in B2 with full provenance and is grouped
    under a shared ``campaign_id`` (Genblaze's ``project_id``), so the
    whole set is discoverable as one unit later.

    A failed variant (e.g. a transient provider error) is skipped rather
    than aborting the whole campaign — ``fail_fast=False`` at the pipeline
    level, plus we tolerate individual finalize failures here too.
    """
    if not variant_prompts:
        raise ValueError("variant_prompts must be non-empty")
    mod = Modality(modality)
    campaign_id = str(uuid.uuid4())
    sink = get_sink()  # shared across the whole batch; closed once at the end
    pipe, provider_name, model = _build_pipeline(
        variant_prompts[0], mod,
        project_id=campaign_id, name=f"veritas-campaign:{brief[:60]}",
    )

    results = pipe.batch_run(
        prompts=variant_prompts,
        sink=sink,
        fail_fast=False,
        raise_on_failure=False,
        max_concurrency=3,
    )

    out: list[GenerationResult] = []
    for prompt, result in zip(variant_prompts, results):
        try:
            gr = _finalize_result(
                result, sink,
                prompt=prompt, modality=mod, provider_name=provider_name, model=model,
                parent_run_id=None,
            )
        except Exception:
            continue  # this variant failed; keep the rest of the campaign
        out.append(gr)
    return campaign_id, out
