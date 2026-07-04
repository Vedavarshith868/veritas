"""Immutable compliance copies of provenance manifests (B2 Object Lock).

When a lock-enabled bucket is configured (B2_LOCKED_BUCKET + its scoped key),
every successful generation also writes a WORM copy of the manifest there
with a retention period. Genblaze's ObjectLockConfig makes the manifest
undeletable/unoverwritable until `retain_until` — the on-disk expression of
verifiable provenance.

Absent that config, the app still runs; `enabled()` gates every call.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from .config import get_settings

logger = logging.getLogger("veritas.compliance")

RETENTION_DAYS = int(os.getenv("MANIFEST_RETENTION_DAYS", "30"))


def enabled() -> bool:
    return bool(os.getenv("B2_LOCKED_BUCKET") and os.getenv("B2_LOCKED_KEY_ID"))


@lru_cache
def _locked_backend():
    from genblaze_s3 import S3StorageBackend

    return S3StorageBackend.for_backblaze(
        os.environ["B2_LOCKED_BUCKET"],
        region=get_settings().b2_region,
        key_id=os.environ["B2_LOCKED_KEY_ID"],
        app_key=os.environ["B2_LOCKED_APP_KEY"],
        preflight=False,
    )


def write_locked_manifest(run_id: str, manifest: dict) -> str | None:
    """Write a WORM manifest copy; returns its key or None (best-effort)."""
    if not enabled():
        return None
    from genblaze_core import ObjectLockConfig

    key = f"locked-manifests/{run_id}.json"
    try:
        _locked_backend().put(
            key,
            json.dumps(manifest, ensure_ascii=False, default=str).encode("utf-8"),
            content_type="application/json",
            object_lock=ObjectLockConfig(
                retain_until=datetime.now(timezone.utc) + timedelta(days=RETENTION_DAYS),
                mode="COMPLIANCE",  # nobody, including the account owner, can delete early
            ),
        )
        return key
    except Exception:
        logger.warning("locked manifest write failed for run %s", run_id, exc_info=True)
        return None
