"""B2 verify-index + asset metadata stamping.

Turns B2 into a queryable system of record:

* ``{prefix}/index/sha256/<sha>.json`` — one small JSON object per generated
  asset, keyed by content hash. Makes the public verify check a single O(1)
  GET instead of scanning every manifest.
* Asset objects are stamped (server-side copy, zero bandwidth) with B2
  metadata headers (provider, model, run id, sha256) so the media itself is
  self-describing when browsed in any S3 tool.

Both writes are best-effort enhancements: a failure degrades gracefully
(verify falls back to the manifest scan) and never breaks generation.
"""
from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from .config import get_settings
from .storage import get_backend

if TYPE_CHECKING:  # pragma: no cover
    from .pipeline import GenerationResult

logger = logging.getLogger("veritas.indexer")


def index_key(sha256: str) -> str:
    return f"{get_settings().prefix}/index/sha256/{sha256.lower()}.json"


def write_verify_index(gr: "GenerationResult") -> str | None:
    """Persist the O(1) verify-index object for a completed generation."""
    if not gr.sha256:
        return None
    key = index_key(gr.sha256)
    body = {
        "sha256": gr.sha256.lower(),
        "run_id": gr.run_id,
        "parent_run_id": gr.parent_run_id,
        "manifest_key": gr.manifest_key,
        "asset_key": gr.asset_key,
        "provider": gr.provider,
        "model": gr.model,
        "prompt": gr.prompt,
        "modality": gr.modality,
        "media_type": gr.media_type,
        "size_bytes": gr.size_bytes,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        get_backend().put(
            key,
            json.dumps(body, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
            metadata={"veritas-sha256": gr.sha256.lower(), "veritas-run-id": gr.run_id},
        )
        return key
    except Exception:
        logger.warning("verify-index write failed for %s", key, exc_info=True)
        return None


def lookup(sha256: str) -> dict[str, Any] | None:
    """O(1) index lookup; None when the hash is unknown."""
    try:
        raw = get_backend().get(index_key(sha256))
    except Exception:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        logger.warning("corrupt index object for %s", sha256, exc_info=True)
        return None


def stamp_asset_metadata(gr: "GenerationResult") -> bool:
    """Attach provenance metadata headers to the asset object in place.

    Uses S3 server-side copy with MetadataDirective=REPLACE (no bandwidth,
    two class-C transactions). Best-effort: returns False on any failure.
    """
    if not gr.asset_key:
        return False
    backend = get_backend()
    client = getattr(backend, "_client", None)
    if client is None:
        return False
    bucket = get_settings().b2_bucket
    try:
        client.copy_object(
            Bucket=bucket,
            Key=gr.asset_key,
            CopySource={"Bucket": bucket, "Key": gr.asset_key},
            MetadataDirective="REPLACE",
            ContentType=gr.media_type or "application/octet-stream",
            Metadata={
                "veritas-provider": gr.provider,
                "veritas-model": gr.model,
                "veritas-run-id": gr.run_id,
                "veritas-sha256": (gr.sha256 or "").lower(),
                "veritas-modality": gr.modality,
            },
        )
        return True
    except Exception:
        logger.warning("metadata stamp failed for %s", gr.asset_key, exc_info=True)
        return False
