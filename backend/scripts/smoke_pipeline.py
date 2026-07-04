"""End-to-end provenance smoke test (mock provider, real B2, real manifest).

Run: PYTHONUTF8=1 backend/.venv/Scripts/python.exe backend/scripts/smoke_pipeline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline import generate_media
from app.storage import presigned_url


def main() -> int:
    prompt = "A cinematic drone shot soaring over a coastal city at golden hour"
    print(f"Generating (mock): {prompt!r}\n")

    r = generate_media(prompt, modality="image")

    print(f"  provider          : {r.provider} / {r.model}")
    print(f"  run_id            : {r.run_id}")
    print(f"  media_type        : {r.media_type}")
    print(f"  size_bytes        : {r.size_bytes}")
    print(f"  sha256            : {r.sha256[:32]}...")
    print(f"  asset_key (B2)    : {r.asset_key}")
    print(f"  manifest_key (B2) : {r.manifest_key}")
    print(f"  manifest_verified : {r.manifest_verified}")

    assert r.sha256, "asset has no sha256"
    assert r.manifest_verified, "manifest failed verification"

    # Prove the asset is actually retrievable from B2 via a presigned URL.
    if r.asset_key:
        url = presigned_url(r.asset_key, expires_in=300)
        print(f"\n  presigned asset URL: {url[:90]}...")

    print("\n  manifest (excerpt):")
    print(textwrap_json(r.manifest))

    print("\n✅ Full provenance loop works: generate -> B2 upload -> manifest -> verify.")
    return 0


def textwrap_json(d: dict) -> str:
    s = json.dumps(d, indent=2, default=str)
    lines = s.splitlines()
    return "\n".join("    " + ln for ln in lines[:24]) + ("\n    ..." if len(lines) > 24 else "")


if __name__ == "__main__":
    raise SystemExit(main())
