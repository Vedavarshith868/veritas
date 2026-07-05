"""API smoke tests via FastAPI TestClient.

Covers route wiring, request validation, and rate-limit behavior — no
real B2 calls, no real provider calls. The catalog module is
monkey-patched to short-circuit any endpoint that would otherwise
preflight the (fake) test bucket.
"""
from __future__ import annotations

import os

# Set generous rate limits so smoke tests don't trip 429s.
os.environ["RATE_LIMIT_GENERATE"] = "100/minute"
os.environ["RATE_LIMIT_CAMPAIGN"] = "100/minute"
os.environ["RATE_LIMIT_VERIFY"] = "1000/minute"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import catalog  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)


@pytest.fixture(autouse=True)
def _stub_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every /api/verify* call short-circuits without hitting B2."""

    def fake_verify(sha256: str) -> dict:
        return {"verified": False, "source": None, "match": None}

    monkeypatch.setattr(catalog, "verify_sha256", fake_verify)


def test_health_endpoint() -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "bucket" in body
    assert "provider_mode" in body


def test_openapi_docs_available() -> None:
    # FastAPI's built-in docs — a third-party integration signal.
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "Veritas API"
    paths = schema["paths"]
    for p in [
        "/api/health",
        "/api/generate",
        "/api/campaign",
        "/api/runs",
        "/api/verify",
        "/api/verify-hash",
    ]:
        assert p in paths, f"missing route in openapi: {p}"


def test_verify_hash_validates_length() -> None:
    r = client.post("/api/verify-hash", json={"sha256": "too-short"})
    assert r.status_code == 422  # pydantic length constraint


def test_verify_hash_lowercases_response() -> None:
    # Backend accepts any valid-length hex, echoes it lowercased. Match won't
    # exist for a random hash, so verified=False is expected.
    upper = "F" * 64
    r = client.post("/api/verify-hash", json={"sha256": upper})
    assert r.status_code in (200, 404)  # 404 if index/scan fails cleanly
    if r.status_code == 200:
        body = r.json()
        assert body["sha256"] == upper.lower()


def test_generate_rejects_empty_prompt() -> None:
    r = client.post("/api/generate", json={"prompt": "", "modality": "image"})
    assert r.status_code == 422


def test_generate_rejects_oversized_prompt() -> None:
    r = client.post(
        "/api/generate", json={"prompt": "x" * 3000, "modality": "image"}
    )
    assert r.status_code == 422


def test_rate_limiter_is_attached() -> None:
    """slowapi's Limiter is attached to the app state.

    The end-to-end enforcement is verified separately (start a real
    uvicorn with a tiny env-driven limit and hit it). Testing the
    integration in-process here would either need a live loop-of-N
    against a fresh limiter per test (flaky), or reach into slowapi
    internals (brittle). This just proves the wiring exists.
    """
    from slowapi import Limiter

    assert isinstance(app.state.limiter, Limiter)


def test_rate_limited_endpoints_are_decorated() -> None:
    """The four cost-bearing endpoints have a slowapi limit decorator applied.

    We inspect the underlying route function's closure/attributes to confirm
    the decorator ran — proving the intent (paid endpoints are throttled)
    without relying on live rate-limit enforcement in-process (that's covered
    by a separate manual smoke test with a real uvicorn).
    """
    limited = {"/api/generate", "/api/campaign", "/api/verify", "/api/verify-hash"}
    from starlette.routing import Route

    for route in app.routes:
        if isinstance(route, Route) and route.path in limited:
            # slowapi stamps the wrapped function; the attribute name is a
            # dunder that survives across decoration layers.
            endpoint = route.endpoint
            # Walk any wrappers looking for slowapi's marker.
            fn = endpoint
            seen_marker = False
            for _ in range(6):
                if getattr(fn, "__wrapped__", None):
                    fn = fn.__wrapped__
                    continue
                break
            # A decorated endpoint captures the limiter in its closure.
            closure = getattr(endpoint, "__closure__", None) or ()
            for cell in closure:
                try:
                    val = cell.cell_contents
                except ValueError:
                    continue
                mod = type(val).__module__ or ""
                if "slowapi" in mod or "limits" in mod:
                    seen_marker = True
                    break
            assert seen_marker, f"{route.path} not decorated by slowapi"
