"""Backblaze B2 storage helpers built on Genblaze's S3 backend.

Wraps genblaze_s3.S3StorageBackend so the rest of the app has one place
to construct the backend and to build the Genblaze storage sink.
"""
from __future__ import annotations

from functools import lru_cache

from genblaze_core import KeyStrategy, ObjectStorageSink
from genblaze_s3 import S3StorageBackend

from .config import get_settings


@lru_cache
def get_backend() -> S3StorageBackend:
    """Raw B2 backend for direct puts / presigned URLs."""
    s = get_settings()
    s.require_b2()
    return S3StorageBackend.for_backblaze(
        s.b2_bucket,
        region=s.b2_region,
        key_id=s.b2_key_id,
        app_key=s.b2_app_key,
        preflight=False,  # skip the extra HEAD-bucket round trip on init
    )


def get_sink() -> ObjectStorageSink:
    """Genblaze sink: uploads assets + persists provenance manifests to B2.

    HIERARCHICAL keys give human-browsable paths (date/run/asset), which
    reads better in the demo than content-addressable hashes.
    """
    s = get_settings()
    return ObjectStorageSink(
        get_backend(),
        prefix=s.prefix,
        key_strategy=KeyStrategy.HIERARCHICAL,
    )


def presigned_url(key: str, expires_in: int | None = None) -> str:
    """Time-limited GET URL for a private object (how we serve media)."""
    s = get_settings()
    return get_backend().presigned_get_url(
        key, expires_in=expires_in or s.presign_expiry
    )


def list_keys(prefix: str, *, max_total: int = 5000) -> list[str]:
    """List object keys under a prefix, following pagination."""
    backend = get_backend()
    out: list[str] = []
    token: str | None = None
    while True:
        page = backend.list(prefix, continuation_token=token) if token else backend.list(prefix)
        for entry in page.entries:
            out.append(entry.key if hasattr(entry, "key") else str(entry))
        token = getattr(page, "next_token", None)
        if not token or len(out) >= max_total:
            break
    return out


def read_bytes(key: str) -> bytes:
    return get_backend().get(key)


def read_json(key: str) -> dict:
    import json

    return json.loads(read_bytes(key).decode("utf-8"))
