"""Shared pytest fixtures.

Load a fake .env before any app.* import so config.get_settings()
doesn't blow up in CI where real B2 keys aren't (and shouldn't be) set.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# Set safe placeholders BEFORE any app import — config reads at import time.
os.environ.setdefault("B2_KEY_ID", "test-key-id")
os.environ.setdefault("B2_APP_KEY", "test-app-key")
os.environ.setdefault("B2_BUCKET", "test-bucket")
os.environ.setdefault("B2_REGION", "us-east-005")
os.environ.setdefault("B2_ENDPOINT", "https://s3.us-east-005.backblazeb2.com")
os.environ.setdefault("VERITAS_PROVIDER", "mock")
os.environ.setdefault("VERITAS_PREFIX", "veritas")
