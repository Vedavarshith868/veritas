"""Read-side helpers: list generated runs and verify asset provenance.

Everything is derived from the manifests Genblaze persists to B2, so B2 is
the single source of truth (no separate DB needed for the MVP).
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from .config import get_settings
from .storage import list_keys, read_json


@dataclass
class RunSummary:
    run_id: str
    parent_run_id: str | None
    campaign_id: str | None
    date: str
    name: str | None
    provider: str | None
    model: str | None
    prompt: str | None
    modality: str | None
    media_type: str | None
    sha256: str | None
    asset_key: str | None
    manifest_key: str
    verified: bool
    # AI-generated caption from a chained vision-model step (may be None for
    # single-step runs like the mock provider or older manifests).
    caption: str | None = None
    caption_model: str | None = None


def _manifest_keys() -> list[str]:
    s = get_settings()
    keys = [k for k in list_keys(f"{s.prefix}/runs/") if k.endswith("manifest.json")]
    # Path embeds date + run id, so reverse-lexical ≈ newest first.
    return sorted(keys, reverse=True)


def _first_output_asset(step: dict[str, Any]) -> dict[str, Any] | None:
    for a in step.get("assets") or []:
        return a
    return None


def _extract_caption(steps: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Read a caption + its model out of a manifest's step 1 (if it exists).

    The manifest's step-1 is the chained vision-model step. Different
    Genblaze versions have written the text output in a few different
    places — probe them defensively so old and new manifests both work.
    """
    if len(steps) < 2:
        return None, None
    cap_step = steps[1]
    model = cap_step.get("model")
    for field in ("text", "output_text"):
        val = cap_step.get(field)
        if isinstance(val, str) and val.strip():
            return val.strip(), model
    for asset in cap_step.get("assets") or []:
        media = (asset.get("media_type") or "").lower()
        if media.startswith("text/"):
            val = asset.get("text") or asset.get("content")
            if isinstance(val, str) and val.strip():
                return val.strip(), model
    return None, model


def _summarize(manifest_key: str, m: dict[str, Any]) -> RunSummary:
    run = m.get("run", {})
    steps = run.get("steps") or []
    step = steps[0] if steps else {}
    asset = _first_output_asset(step) or {}
    asset_key = None
    url = asset.get("url") or ""
    bucket = get_settings().b2_bucket
    if f"{bucket}/" in url:
        asset_key = url.split(f"{bucket}/", 1)[-1]
    date = manifest_key.split("/runs/", 1)[-1].split("/", 1)[0]
    caption, caption_model = _extract_caption(steps)
    return RunSummary(
        run_id=run.get("run_id", ""),
        parent_run_id=run.get("parent_run_id"),
        campaign_id=run.get("project_id"),
        date=date,
        name=run.get("name"),
        provider=step.get("provider"),
        model=step.get("model"),
        prompt=step.get("prompt"),
        modality=step.get("modality"),
        media_type=asset.get("media_type"),
        sha256=asset.get("sha256"),
        asset_key=asset_key,
        manifest_key=manifest_key,
        verified=run.get("status") == "completed",
        caption=caption,
        caption_model=caption_model,
    )


def list_runs(limit: int = 50, include_failed: bool = False) -> list[dict[str, Any]]:
    """Newest-first run summaries. Failed runs (no output asset) are kept in
    B2 as audit records but hidden from the gallery unless requested."""
    out: list[dict[str, Any]] = []
    for key in _manifest_keys():
        if len(out) >= limit:
            break
        try:
            summary = _summarize(key, read_json(key))
        except Exception:
            continue
        if not include_failed and not summary.asset_key:
            continue
        out.append(asdict(summary))
    return out


def get_manifest(manifest_key: str) -> dict[str, Any]:
    return read_json(manifest_key)


def verify_sha256(sha256: str) -> dict[str, Any]:
    """Is this hash a known, provenance-tracked asset?

    Fast path: O(1) lookup against the B2 verify-index written at
    generation time. Fallback: scan persisted manifests (covers assets
    generated before the index existed). Powers the public /verify.
    """
    from . import indexer

    target = sha256.lower().strip()

    hit = indexer.lookup(target)
    if hit is not None:
        date = (hit.get("manifest_key") or "").split("/runs/", 1)[-1].split("/", 1)[0]
        return {
            "verified": True,
            "source": "index",
            "match": {
                "run_id": hit.get("run_id"),
                "parent_run_id": hit.get("parent_run_id"),
                "date": date,
                "name": None,
                "provider": hit.get("provider"),
                "model": hit.get("model"),
                "prompt": hit.get("prompt"),
                "modality": hit.get("modality"),
                "media_type": hit.get("media_type"),
                "sha256": hit.get("sha256"),
                "asset_key": hit.get("asset_key"),
                "manifest_key": hit.get("manifest_key"),
                "verified": True,
            },
        }

    for key in _manifest_keys():
        try:
            m = read_json(key)
        except Exception:
            continue
        for step in (m.get("run", {}).get("steps") or []):
            for a in step.get("assets") or []:
                if (a.get("sha256") or "").lower() == target:
                    return {"verified": True, "source": "scan", "match": asdict(_summarize(key, m))}
    return {"verified": False, "source": None, "match": None}


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
