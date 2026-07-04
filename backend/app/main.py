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

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import catalog
from .config import get_settings
from .pipeline import generate_campaign, generate_media
from .storage import presigned_url

app = FastAPI(title="Veritas API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        *get_settings().cors_origins,
    ],
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
def generate(req: GenerateRequest) -> dict:
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
def campaign(req: CampaignRequest) -> dict:
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
async def verify(file: UploadFile = File(...)) -> dict:
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
def verify_hash(req: VerifyHashRequest) -> dict:
    result = catalog.verify_sha256(req.sha256)
    result["sha256"] = req.sha256.lower()
    return result
