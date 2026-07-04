"""Central configuration, loaded from environment (.env in dev)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env regardless of CWD.
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


class Settings:
    # Backblaze B2
    b2_key_id: str = os.getenv("B2_KEY_ID", "")
    b2_app_key: str = os.getenv("B2_APP_KEY", "")
    b2_bucket: str = os.getenv("B2_BUCKET", "")
    b2_region: str = os.getenv("B2_REGION", "us-east-005")
    b2_endpoint: str = os.getenv("B2_ENDPOINT", "")

    # AI providers
    gmi_api_key: str = os.getenv("GMI_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")

    # App
    prefix: str = os.getenv("VERITAS_PREFIX", "veritas")
    presign_expiry: int = int(os.getenv("PRESIGN_EXPIRY_SECONDS", "3600"))
    # "auto" = real providers when keys exist; "mock" = force mock (dev/no credits)
    provider_mode: str = os.getenv("VERITAS_PROVIDER", "auto")
    # Comma-separated extra allowed CORS origins (e.g. the deployed Vercel URL)
    cors_origins: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
    ]

    @property
    def has_gmi(self) -> bool:
        return bool(self.gmi_api_key) and self.provider_mode != "mock"

    @property
    def has_elevenlabs(self) -> bool:
        return bool(self.elevenlabs_api_key) and self.provider_mode != "mock"

    @property
    def has_nvidia(self) -> bool:
        return bool(self.nvidia_api_key) and self.provider_mode != "mock"

    def require_b2(self) -> None:
        missing = [k for k in ("b2_key_id", "b2_app_key", "b2_bucket") if not getattr(self, k)]
        if missing:
            raise RuntimeError(f"Missing B2 config: {missing}. Check backend/.env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
