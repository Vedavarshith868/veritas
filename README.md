# Veritas — provenance-first generative media studio

Built for the **Backblaze Generative Media Hackathon** (Genblaze + B2).

Every AI-generated image/video/audio asset is uploaded to **Backblaze B2** with a
**cryptographically verifiable provenance manifest** (via Genblaze). A public
**verify** endpoint lets anyone drop in a file and confirm whether it's an
authentic, provenance-tracked asset — and see exactly how it was made.

## Why this wins
Maps to all four (equally weighted) judging criteria:
- **Real-world utility** — brands/newsrooms need verifiable AI-content authenticity.
- **Production readiness** — private bucket + presigned serving, encryption at rest, error handling.
- **B2 storage + orchestration** — B2 is the system of record for assets *and* manifests (no separate DB).
- **Genblaze usage** — multi-provider pipeline + built-in provenance manifests (the SDK's signature feature).

## Stack
- **Backend:** Python 3.12, FastAPI, Genblaze (`genblaze[all]`), Backblaze B2 (S3-compatible).
- **Frontend:** Next.js (planned).

## Setup
```bash
# 1. Python 3.12 venv
py -3.12 -m venv backend/.venv           # or the full interpreter path
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt

# 2. Configure secrets
cp backend/.env.example backend/.env     # then fill in B2 keys (+ GMI_API_KEY when available)

# 3. Validate B2 connectivity
PYTHONUTF8=1 backend/.venv/Scripts/python backend/scripts/smoke_b2.py

# 4. Prove the full provenance loop (generate -> B2 -> manifest -> verify)
PYTHONUTF8=1 backend/.venv/Scripts/python backend/scripts/smoke_pipeline.py

# 5. Run the API (backend)
cd backend && PYTHONUTF8=1 .venv/Scripts/python -m uvicorn app.main:app --port 8000

# 6. Run the studio (frontend, in another terminal)
cd frontend && npm install && npm run dev   # http://localhost:3000
```

The frontend proxies `/api/*` to the backend. Override the target with
`BACKEND_URL` (e.g. in `frontend/.env.local`) if the backend isn't on `:8000`.

## Provider modes
- **mock** (default) — renders a real local PNG and runs the full B2 + manifest
  loop with zero API cost. Active whenever `GMI_API_KEY` is unset.
- **gmi** — real GMICloud generation once `GMI_API_KEY` is set in `.env`.

## API
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness + config |
| POST | `/api/generate` | run the provenance pipeline |
| GET | `/api/runs` | list recent runs (from B2 manifests) |
| GET | `/api/manifest?key=` | full provenance manifest |
| GET | `/api/asset-url?key=` | presigned GET URL for a private asset |
| POST | `/api/verify` | upload a file → is it authentic? |
| POST | `/api/verify-hash` | check a sha256 against known provenance |

## B2 layout
```
veritas/runs/<date>/<run_id>/manifest.json          # provenance record
veritas/runs/<date>/<run_id>/assets/<asset_id>.<ext> # the media
```

## Security notes
- `backend/.env` is git-ignored; never commit real keys.
- The B2 application key is scoped to a single bucket (not the master key).
- Regenerate the B2 key before making the repo public / submitting.
