# Veritas — provenance-first generative media studio

**Tagline:** Generate once. Prove it forever.

**Live app:** https://veritas-ebon-rho.vercel.app
**Backend API:** https://veritas-backend-9iwa.onrender.com/api/health
**Repo:** https://github.com/Vedavarshith868/veritas

> Note on Render's free tier: the backend spins down after 15 minutes of
> inactivity, so the very first request can take 30-60 seconds to wake up.
> If the app feels slow on first load, that's why — give it a moment.

---

## Inspiration

Every week there's a new story about an AI-generated image or video passed
off as real, or a real one dismissed as fake. The tooling to *generate*
media got a decade ahead of the tooling to *prove where it came from*. Once
an AI image leaves the tool that made it, there's usually no way to answer
the two questions that actually matter: was this AI-generated, and if so,
by what, when, and from what prompt?

Genblaze's core primitive — a cryptographically verifiable provenance
manifest attached to every generation — is the direct answer to that gap,
and it's the one feature of the SDK I suspected most hackathon entries
would treat as a footnote rather than the product. So I built the whole
app around it: not "a tool that also stores manifests," but a tool whose
entire value proposition *is* the manifest.

## What it does

Veritas is a generative media studio where **every image, video, or audio
asset ships with proof of its own origin**, and anyone — not just the
person who made it — can check that proof.

- **Generate** — describe an asset, pick a modality, and it's created
  through a real provider (NVIDIA NIM's `flux.1-dev` for images, with GMI
  Cloud and ElevenLabs wired for image/video/audio), uploaded to Backblaze
  B2, and stamped with a signed provenance manifest — all in one pipeline
  run.
- **Campaigns** — fan out a single brief into 2-12 prompt variants in one
  orchestrated batch (a real Genblaze `batch_run`, not a for-loop calling
  generate N times). Every variant gets its own asset, its own manifest,
  and a shared `campaign_id` so the whole set is discoverable as one unit.
- **Iterate with lineage** — "regenerate" any asset and the new run
  records a `parent_run_id` pointing at the one it came from. The
  provenance panel renders the full chain, so an asset's entire edit
  history is auditable, not just its most recent state.
- **Verify** — drop any file into the public `/verify` page. Its SHA-256 is
  checked against B2 in O(1) time (a purpose-built hash index, not a
  manifest scan). Change a single pixel and the match breaks — provenance
  isn't a label, it's cryptographic.
- **Tamper-proof storage** — a second, Object-Lock-enabled B2 bucket holds
  WORM (write-once-read-many) copies of every manifest in COMPLIANCE mode.
  I adversarially tested this: attempting to delete a locked manifest
  version, even as the account owner, returns `AccessDenied`. The proof of
  origin can't be quietly edited or deleted after the fact — by anyone,
  including me.

## How I built it

**Backend:** Python 3.12 + FastAPI. The entire generation pipeline is a
thin FastAPI layer over Genblaze:

- `Pipeline.step(provider, model=..., prompt=..., fallback_models=[...])`
  builds each generation with real fallback chains per provider (e.g. GMI's
  image path falls back from `seedream-4-0` to `seedream-3-0` on failure).
- `ObjectStorageSink` handles the B2 upload and manifest generation in one
  call — Genblaze, not my own code, owns the provenance manifest's
  cryptographic integrity.
- `Manifest.verify()` is called on every single generation before the
  result is ever returned to the frontend, so a "verified" badge in the UI
  reflects an actual passed cryptographic check, not a status flag.
- `Pipeline.batch_run(prompts=[...], max_concurrency=3, fail_fast=False)`
  powers campaigns — genuine multi-run orchestration where one bad variant
  doesn't sink the batch.
- `project_id` (campaigns) and `parent_run_id` (iteration lineage) are
  Genblaze's own lineage primitives, not something bolted on afterward.

**B2 is the entire system of record** — there's no database. Runs,
manifests, the verify-index, and WORM compliance copies all live as B2
objects:

```
veritas/runs/<date>/<run_id>/manifest.json          # provenance record
veritas/runs/<date>/<run_id>/assets/<asset_id>.png  # the media
veritas/index/sha256/<hash>.json                    # O(1) verify lookup
```

On top of what Genblaze writes automatically, I added a small B2-hardening
layer: every asset object gets its content hash, provider, model, and run
id stamped as B2 metadata headers via a zero-bandwidth server-side copy
(`MetadataDirective=REPLACE`), so the media is self-describing to any S3
tool, not just to this app.

**Frontend:** Next.js 16 + React 19, styled from scratch after three design
passes — the final look is intentionally close to Higgsfield's bold,
dark, high-contrast creative-tool aesthetic (swapped their lime accent for
a Backblaze-adjacent yellow), with a bento-style asymmetric gallery and a
product-mockup-styled generate console instead of a generic form.

**Deployment:** frontend on Vercel, backend on Render (via a `render.yaml`
Blueprint), with the frontend's `/api/*` rewritten server-side to the
Render backend and CORS locked to the deployed frontend origin.

## Challenges I ran into

- **Windows path bugs, twice.** Genblaze's file-transfer layer parses
  `file://` URIs with `Path(urlparse(url).path)`, which mangles
  `file:///C:/...` into a broken drive-relative path on Windows. I hit this
  in my own mock-provider code first, fixed it, then hit the *identical*
  bug inside `genblaze_nvidia`'s output-writer and had to runtime-patch
  the third-party function rather than fork the package.
- **Provider credits are a real hackathon hazard.** GMI Cloud's free-credit
  signup form closed before I could claim credits, and my ElevenLabs
  account got flagged for "unusual activity" on a residential connection.
  Rather than block on either, I kept both integrations fully wired
  (fallback chains and all) behind a priority order that puts whichever
  provider is actually funded first — NVIDIA NIM ended up as the live
  path, probed model-by-model until I found one enabled on the account's
  free tier (`flux.1-dev`; a couple of others 404'd).
- **Object Lock needed adversarial testing, not just implementation.**
  It's easy to write code that *calls* an Object Lock API; it's different
  to confirm the lock actually holds. I tested it as an attacker would —
  attempting a direct `DeleteObject` on a locked version — before trusting
  it as a judging-criteria claim.
- **Credential hygiene mid-build.** Because I was building this
  interactively, B2 and provider keys ended up in a chat transcript before
  the repo existed. Every exposed key (both B2 application keys and the
  NVIDIA key) was rotated in the Backblaze/NVIDIA consoles *before* the
  first git commit, and the backend was re-verified end-to-end against B2
  with the new keys before anything went public.

## Accomplishments I'm proud of

- A **real, adversarially-tested tamper-evidence guarantee**: flipping a
  single bit in a generated file measurably breaks its verification, and
  a locked manifest genuinely cannot be deleted, not even by the account
  owner, until its retention period expires.
- **B2 as the actual system of record**, not a file dump next to a real
  database — runs, lineage, campaigns, and the verify-index are all
  queryable straight from B2 objects.
- **Campaign fan-out that's a real orchestration primitive**, not a loop
  wearing an orchestration costume — `batch_run` with bounded concurrency
  and per-variant failure isolation.
- Shipping a fully deployed, CORS-hardened, publicly testable app —
  not just a local demo — before the writeup was even due.

## What I learned

That "provenance" is worth almost nothing as a checkbox feature and a lot
as a foundation — the moment I treated the manifest as the product instead
of an artifact of generation, features like lineage, campaigns, and WORM
compliance stopped being add-ons and started being the natural next
question ("okay, but can I prove *this specific* asset came from *that*
one?"). I also learned, the hard way, that a hackathon's real infra risk
is provider credit availability, not code — and that wiring multiple
providers behind a priority fallback is cheap insurance against exactly
that.

## What's next for Veritas

- Redeem GMI Cloud credits (or an equivalent) to run image *and* video
  generation through a second live provider, proving the multi-provider
  fallback chain end-to-end rather than just in code.
- A public, embeddable "verified by Veritas" badge — so any site hosting
  an AI-generated asset can link back to its live provenance record with
  zero integration work.
- Richer campaign analytics (cost/latency per variant, side-by-side
  comparison view).
- A signed, downloadable provenance certificate (PDF/JSON) per asset, for
  workflows that need proof outside the app itself.

## Built with

Python · FastAPI · Genblaze · Backblaze B2 · boto3 · NVIDIA NIM · GMI
Cloud · ElevenLabs · Next.js · React · TypeScript · Tailwind CSS · Framer
Motion · Vercel · Render
