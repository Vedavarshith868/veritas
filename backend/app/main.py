"""Veritas FastAPI backend.

Endpoints:
  GET  /api/health                 - liveness + config sanity
  POST /api/generate               - run the provenance pipeline
  POST /api/campaign                - fan out N provable variants from one brief
  GET  /api/runs                   - list recent generated runs (from B2 manifests)
  GET  /api/manifest?key=...       - fetch a full provenance manifest
  GET  /api/asset-url?key=...      - presigned GET URL for a private asset
  POST /api/verify                 - upload a file -> is it a known, authentic asset?
  POST /api/verify-hash            - check a sha256 against known provenance
"""
from __future__ import annotations

import os

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from fastapi.responses import JSONResponse

from . import catalog, certificate as cert, stats
from .config import get_settings
from .pipeline import generate_campaign, generate_media
from .storage import presigned_url

# Per-IP rate limits. Defaults protect the paid-API endpoints against abuse
# (each /api/generate call spends real NVIDIA quota); read endpoints have
# looser limits. Judges can bump via env vars during testing.
_LIMIT_GENERATE = os.getenv("RATE_LIMIT_GENERATE", "10/hour")
_LIMIT_CAMPAIGN = os.getenv("RATE_LIMIT_CAMPAIGN", "3/hour")
_LIMIT_VERIFY = os.getenv("RATE_LIMIT_VERIFY", "60/hour")
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Veritas API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Wildcard CORS is deliberate here: the "Verified by Veritas" badge is
# designed to be embedded on any third-party website, and it fetches
# /api/verify-hash cross-origin. Per-IP rate limiting caps abuse — the
# expensive endpoints (generate, campaign) allow only single-digit
# requests per hour per IP no matter where the call originates from.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", *get_settings().cors_origins],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    modality: str = Field(default="image")
    parent_run_id: str | None = Field(default=None, description="lineage link to a previous run")


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    active = [
        name
        for name, on in (
            ("nvidia", s.has_nvidia),
            ("gmicloud", s.has_gmi),
            ("elevenlabs", s.has_elevenlabs),
        )
        if on
    ]
    return {
        "status": "ok",
        "bucket": s.b2_bucket,
        "region": s.b2_region,
        "provider_mode": "+".join(active) if active else "mock",
    }


@app.post("/api/generate")
@limiter.limit(_LIMIT_GENERATE)
def generate(request: Request, req: GenerateRequest) -> dict:
    try:
        r = generate_media(req.prompt, modality=req.modality, parent_run_id=req.parent_run_id)
    except Exception as exc:  # surface pipeline errors cleanly to the UI
        raise HTTPException(status_code=502, detail=f"generation failed: {exc}") from exc
    d = r.__dict__.copy()
    if r.asset_key:
        d["asset_signed_url"] = presigned_url(r.asset_key)
    return d


class CampaignRequest(BaseModel):
    brief: str = Field(min_length=1, max_length=500)
    variant_prompts: list[str] = Field(min_length=1, max_length=12)
    modality: str = Field(default="image")


@app.post("/api/campaign")
@limiter.limit(_LIMIT_CAMPAIGN)
def campaign(request: Request, req: CampaignRequest) -> dict:
    try:
        campaign_id, results = generate_campaign(
            req.brief, req.variant_prompts, modality=req.modality
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"campaign failed: {exc}") from exc
    variants = []
    for r in results:
        d = r.__dict__.copy()
        if r.asset_key:
            d["asset_signed_url"] = presigned_url(r.asset_key)
        variants.append(d)
    return {
        "campaign_id": campaign_id,
        "requested": len(req.variant_prompts),
        "succeeded": len(variants),
        "variants": variants,
    }


@app.get("/api/runs")
def runs(
    limit: int = Query(default=50, ge=1, le=200),
    include_failed: bool = Query(default=False),
) -> dict:
    return {"runs": catalog.list_runs(limit=limit, include_failed=include_failed)}


@app.get("/api/stats")
def get_stats(refresh: bool = Query(default=False)) -> dict:
    """Live B2 metrics — proves B2 is the entire system of record.

    Every counter is computed by listing B2 objects directly (no separate
    database, no cached metrics store). Result is cached for STATS_CACHE_TTL
    seconds (default 45s) so /api/stats doesn't hammer B2 on hot reload.
    """
    return stats.get_stats(force_refresh=refresh)


@app.get("/api/runs/by-provider")
def runs_by_provider(
    provider: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """O(list) prefix scan against the secondary by-provider index.

    Instead of scanning every manifest to find runs by provider X, we
    list a shallow B2 pseudo-directory — proves the "queryable straight
    from B2" story is real for more than one query shape.
    """
    from . import indexer

    return {"provider": provider, "runs": indexer.list_by_provider(provider, limit=limit)}


@app.get("/api/runs/by-campaign")
def runs_by_campaign(
    campaign_id: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """O(list) prefix scan against the secondary by-campaign index."""
    from . import indexer

    return {
        "campaign_id": campaign_id,
        "runs": indexer.list_by_campaign(campaign_id, limit=limit),
    }


@app.get("/api/certificate")
def certificate(
    key: str = Query(..., description="B2 manifest key for the run"),
    download: bool = Query(default=False),
):
    """Downloadable provenance certificate for one run.

    JSON body bundles the Genblaze manifest, B2 storage coordinates, WORM
    lock details when available, and a self-checksum over the certificate
    itself. Pass ?download=true to trigger a browser download instead of
    rendering the JSON inline.
    """
    try:
        payload = cert.build_certificate(key)
    except Exception as exc:
        raise HTTPException(
            status_code=404, detail=f"certificate unavailable: {exc}"
        ) from exc
    headers: dict[str, str] = {}
    if download:
        run_id = ((payload.get("run") or {}).get("run_id") or "unknown")[:12]
        filename = f"veritas-certificate-{run_id}.json"
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return JSONResponse(content=payload, headers=headers)


@app.get("/api/manifest")
def manifest(key: str = Query(...)) -> dict:
    try:
        return catalog.get_manifest(key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"manifest not found: {exc}") from exc


@app.get("/api/asset-url")
def asset_url(key: str = Query(...)) -> dict:
    return {"url": presigned_url(key)}


@app.post("/api/verify")
@limiter.limit(_LIMIT_VERIFY)
async def verify(request: Request, file: UploadFile = File(...)) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    sha = catalog.sha256_of(data)
    result = catalog.verify_sha256(sha)
    result["sha256"] = sha
    result["filename"] = file.filename
    return result


class VerifyHashRequest(BaseModel):
    sha256: str = Field(min_length=64, max_length=64)


@app.post("/api/verify-hash")
@limiter.limit(_LIMIT_VERIFY)
def verify_hash(request: Request, req: VerifyHashRequest) -> dict:
    result = catalog.verify_sha256(req.sha256)
    result["sha256"] = req.sha256.lower()
    return result
