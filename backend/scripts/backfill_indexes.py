"""Backfill the secondary B2 indexes for runs generated before write_secondary_indexes
was wired into the pipeline.

Usage:
    python backend/scripts/backfill_indexes.py

Reads every existing manifest under {prefix}/runs/, constructs a
GenerationResult-shaped stub, and calls indexer.write_secondary_indexes().
Idempotent — re-running just overwrites the pointer objects with the same
content.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

# Allow running from repo root or backend/
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from app import indexer  # noqa: E402
from app.catalog import _manifest_keys  # noqa: E402
from app.storage import read_json  # noqa: E402


@dataclass
class _StubResult:
    run_id: str
    parent_run_id: str | None
    prompt: str | None
    modality: str | None
    provider: str | None
    model: str | None
    asset_key: str | None
    sha256: str | None
    size_bytes: int | None
    media_type: str | None
    manifest_key: str | None
    manifest: dict


def main() -> None:
    keys = _manifest_keys()
    print(f"scanning {len(keys)} manifest(s)")

    total_p = total_c = 0
    for key in keys:
        try:
            m = read_json(key)
        except Exception as exc:
            print(f"skip {key}: {exc}")
            continue
        run = m.get("run", {}) if isinstance(m, dict) else {}
        steps = run.get("steps") or []
        step0 = steps[0] if steps else {}
        assets = step0.get("assets") or []
        asset = assets[0] if assets else {}
        asset_key = None
        url = asset.get("url") or ""
        if "veritas-genmedia-hackathon/" in url:
            asset_key = url.split("veritas-genmedia-hackathon/", 1)[-1]

        stub = _StubResult(
            run_id=run.get("run_id") or "",
            parent_run_id=run.get("parent_run_id"),
            prompt=step0.get("prompt"),
            modality=step0.get("modality"),
            provider=step0.get("provider"),
            model=step0.get("model"),
            asset_key=asset_key,
            sha256=asset.get("sha256"),
            size_bytes=asset.get("size_bytes"),
            media_type=asset.get("media_type"),
            manifest_key=key,
            manifest=m,
        )
        indexer.write_secondary_indexes(stub)  # type: ignore[arg-type]
        if stub.provider:
            total_p += 1
        if run.get("project_id"):
            total_c += 1
    print(f"wrote {total_p} provider-index entries and {total_c} campaign-index entries")


if __name__ == "__main__":
    main()
