"""Downloadable provenance certificate.

Bundles a run's manifest, its B2 storage coordinates, and the WORM
lock status (if enabled) into a single JSON document a user can
attach to legal / editorial / compliance workflows. The document
carries its own SHA-256 checksum over its canonical form so the
recipient can prove the certificate itself wasn't tampered with in
transit — separate from the manifest's own crypto signature.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from . import catalog, compliance
from .config import get_settings
from .storage import get_backend


def _canonical(payload: dict[str, Any]) -> str:
    """Canonical JSON — sorted keys, no whitespace surprises."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def build_certificate(manifest_key: str) -> dict[str, Any]:
    """Assemble the certificate payload for a given manifest.

    Raises FileNotFoundError-style if the manifest is missing.
    """
    manifest = catalog.get_manifest(manifest_key)
    summary = catalog._summarize(manifest_key, manifest)  # type: ignore[attr-defined]
    settings = get_settings()

    # Locate the WORM copy if compliance mode is active.
    locked_copy_key = manifest.get("locked_copy")
    locked_details: dict[str, Any] | None = None
    if compliance.enabled() and summary.run_id:
        locked_details = {
            "bucket": None,
            "key": None,
            "retention_days": compliance.RETENTION_DAYS,
            "mode": "COMPLIANCE",
        }
        try:
            import os

            client = compliance._locked_backend()._client  # type: ignore[attr-defined]
            bucket = os.environ.get("B2_LOCKED_BUCKET")
            key = f"locked-manifests/{summary.run_id}.json"
            resp = client.head_object(Bucket=bucket, Key=key)
            locked_details.update(
                {
                    "bucket": bucket,
                    "key": key,
                    "version_id": resp.get("VersionId"),
                    "object_lock_mode": resp.get("ObjectLockMode"),
                    "retain_until": (
                        resp.get("ObjectLockRetainUntilDate").isoformat()
                        if resp.get("ObjectLockRetainUntilDate")
                        else None
                    ),
                }
            )
        except Exception:
            # WORM not populated for this run — surface the intent, not a lie.
            locked_details["note"] = (
                "WORM copy not found on this run — either it predates the "
                "compliance path or the locked bucket was unavailable at write time."
            )

    payload: dict[str, Any] = {
        "spec": "veritas.provenance.certificate/v1",
        "run": {
            "run_id": summary.run_id,
            "parent_run_id": summary.parent_run_id,
            "campaign_id": summary.campaign_id,
            "date": summary.date,
            "provider": summary.provider,
            "model": summary.model,
            "prompt": summary.prompt,
            "modality": summary.modality,
            "verified": summary.verified,
        },
        "asset": {
            "sha256": summary.sha256,
            "media_type": summary.media_type,
            "b2_bucket": settings.b2_bucket,
            "b2_region": settings.b2_region,
            "b2_key": summary.asset_key,
        },
        "manifest": {
            "b2_key": manifest_key,
            "genblaze_manifest": manifest,
        },
        "caption": {
            "text": summary.caption,
            "model": summary.caption_model,
        }
        if summary.caption
        else None,
        "worm_copy": locked_details,
        "verifier": {
            "public_check_url": f"/verify?sha256={summary.sha256 or ''}",
            "recompute": "sha256(asset_bytes) must equal asset.sha256",
        },
    }

    # Self-checksum: SHA-256 over the canonical payload (before adding the
    # checksum itself). A tampered certificate that arrives with the same
    # manifest but modified metadata will not re-hash to the same value.
    canonical = _canonical(payload)
    payload["certificate_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload
