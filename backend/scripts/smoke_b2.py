"""Validate B2 credentials end-to-end: put -> list -> presigned GET -> read back -> delete.

Run:  backend/.venv/Scripts/python.exe backend/scripts/smoke_b2.py
"""
from __future__ import annotations

import sys
import time
import urllib.request
from pathlib import Path

# Allow "import app.*" when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.storage import get_backend, presigned_url


def main() -> int:
    s = get_settings()
    print(f"Bucket   : {s.b2_bucket}")
    print(f"Endpoint : {s.b2_endpoint}  (region {s.b2_region})")

    backend = get_backend()
    key = f"{s.prefix}/_smoke/hello-{int(time.time())}.txt"
    payload = b"Veritas B2 connectivity check - provenance-first generative media."

    print(f"\n[1/5] PUT   {key} ({len(payload)} bytes)")
    backend.put(key, payload, content_type="text/plain")

    print("[2/5] HEAD  confirming object exists")
    assert backend.exists(key), "object not found after put"

    print("[3/5] URL   generating presigned GET (private bucket)")
    url = presigned_url(key, expires_in=300)
    print(f"        {url[:90]}...")

    print("[4/5] GET   fetching via presigned URL")
    with urllib.request.urlopen(url) as r:
        got = r.read()
    assert got == payload, f"round-trip mismatch: {got!r}"
    print("        round-trip byte-for-byte match ✅")

    print("[5/5] DEL   cleaning up smoke object")
    backend.delete(key)
    print("\n✅ B2 credentials + Genblaze S3 backend fully working.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
