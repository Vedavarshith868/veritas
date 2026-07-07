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
  through a real two-step Genblaze pipeline: Replicate's `flux-schnell`
  generates the image, then an NVIDIA vision model (`llama-3.2-11b-vision-instruct`)
  captions it — both steps signed into one manifest, uploaded to Backblaze
  B2. Provenance survives even though the two steps come from different
  companies.
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
- **Embeddable "Verified by Veritas" badge** — a 4KB Shadow-DOM'd
  `<script>` any third-party site can drop next to an image; it live-checks
  the asset's hash against Veritas over one HTTPS request, no login, no SDK.
- **Downloadable provenance certificate** — one click generates a signed
  certificate (printable HTML or raw JSON) with the prompt, hash, storage
  location, and WORM lock status, for legal/editorial workflows that need
  proof outside the app itself.
- **System of record dashboard** — a live `/api/stats` panel on the
  homepage showing manifest, asset, verify-index, secondary-index, and
  WORM-copy counts computed fresh from B2 on every request — proof there's
  no hidden database behind the curtain.

## How I built it

**Backend:** Python 3.12 + FastAPI. The entire generation pipeline is a
thin FastAPI layer over Genblaze:

- `Pipeline.step(provider, model=..., prompt=..., fallback_models=[...])`
  chains two real steps per generation — Replicate for the image,
  NVIDIA's vision model for the caption (`input_from=0`) — with fallback
  models and an aggressive retry policy on both NVIDIA endpoints for their
  flaky free tier. GMI Cloud stays wired as a further fallback chain,
  auto-routing on whichever provider keys are actually present.
- `ObjectStorageSink` handles the B2 upload and manifest generation in one
  call — Genblaze, not my own code, owns the provenance manifest's
  cryptographic integrity. (One real gap found here: the synthetic
  `text:<sha256>` asset URL NVIDIA's chat provider returns isn't a real
  transferable asset — fixed by writing the caption to a local temp file
  and riding the same `file://` upload path already used for images, so
  the caption ends up a real, hash-verified `.txt` object in B2 too.)
- `Manifest.verify()` is called on every single generation before the
  result is ever returned to the frontend, so a "verified" badge in the UI
  reflects an actual passed cryptographic check, not a status flag.
- `Pipeline.batch_run(prompts=[...], max_concurrency=3, fail_fast=False)`
  powers campaigns — genuine multi-run orchestration where one bad variant
  doesn't sink the batch.
- `project_id` (campaigns) and `parent_run_id` (iteration lineage) are
  Genblaze's own lineage primitives, not something bolted on afterward.
- Per-IP rate limiting (slowapi) on every write/verify endpoint, and a
  28-test pytest suite plus GitHub Actions CI running on every push —
  production concerns, not just a working demo.
- Two secondary B2 indexes (`by-provider`, `by-campaign`) written on every
  generation, so `/api/runs/by-provider` and `/api/runs/by-campaign` do an
  O(list) prefix scan instead of a full manifest scan.

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
- **Provider credits and free-tier uptime are a real hackathon hazard.**
  GMI Cloud's free-credit signup form closed before I could claim credits,
  my ElevenLabs account got flagged for "unusual activity" on a
  residential connection and was dropped entirely, and NVIDIA's own
  free-tier `flux.1-dev` image endpoint had a sustained outage. Rather than
  block on any one provider, I kept every integration fully wired (fallback
  chains and all) behind a priority order that auto-routes to whichever
  provider is actually funded and healthy — a small paid Replicate credit
  ended up as the primary image path, with NVIDIA repurposed for the
  second, cross-provider caption step instead of sitting idle. That
  discovery — that provenance survives even when the two steps come from
  different companies — became a better hackathon story than same-vendor
  chaining would have been.
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
- **A real cross-provider chain**, not same-vendor theater — Replicate's
  image and NVIDIA's caption, signed into one manifest, surviving even
  though the two steps never touch the same company.
- **Infrastructure other sites can plug into** — the embeddable badge and
  downloadable certificate turn Veritas from a standalone tool into
  something a third party can build on with zero integration work.
- Shipping a fully deployed, CORS-hardened, publicly testable app — with
  rate limiting, a pytest suite, and CI on every push — not just a local
  demo, before the writeup was even due.

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

- Redeem GMI Cloud credits (or an equivalent) to run video generation
  through a second live provider, proving the multi-provider fallback
  chain end-to-end on a second modality, not just images.
- Richer campaign analytics (cost/latency per variant, side-by-side
  comparison view).
- A PDF export path for the provenance certificate that doesn't depend on
  the browser's print dialog, for headless/automated compliance workflows.
- Real signature/KMS-backed manifest signing, on top of Genblaze's
  built-in integrity check, for organizations that need their own key in
  the chain of custody.

## Built with

Python · FastAPI · Genblaze · Backblaze B2 · boto3 · Replicate · NVIDIA
NIM · GMI Cloud · Next.js · React · TypeScript · Tailwind CSS · Framer
Motion · Vercel · Render
