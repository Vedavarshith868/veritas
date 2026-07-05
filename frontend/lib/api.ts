// Typed client for the Veritas FastAPI backend (proxied via /api rewrites).

export type RunSummary = {
  run_id: string;
  parent_run_id: string | null;
  campaign_id: string | null;
  date: string;
  name: string | null;
  provider: string | null;
  model: string | null;
  prompt: string | null;
  modality: string | null;
  media_type: string | null;
  sha256: string | null;
  asset_key: string | null;
  manifest_key: string;
  verified: boolean;
  caption: string | null;
  caption_model: string | null;
};

export type GenerateResponse = {
  run_id: string;
  parent_run_id: string | null;
  prompt: string;
  modality: string;
  provider: string;
  model: string;
  asset_url: string;
  asset_key: string;
  sha256: string;
  size_bytes: number | null;
  media_type: string;
  manifest_verified: boolean;
  manifest_key: string | null;
  asset_signed_url?: string;
  caption: string | null;
  caption_model: string | null;
};

export type VerifyResponse = {
  verified: boolean;
  source: "index" | "scan" | null;
  sha256: string;
  filename?: string;
  match: RunSummary | null;
};

export type CampaignResponse = {
  campaign_id: string;
  requested: number;
  succeeded: number;
  variants: GenerateResponse[];
};

export type Health = {
  status: string;
  bucket: string;
  region: string;
  provider_mode: string;
};

export type Stats = {
  generations: number;
  assets: number;
  asset_bytes: number;
  verify_index_entries: number;
  locked_manifests: number;
  multi_step_runs: number;
  with_captions: number;
  last_generation_iso: string | null;
};

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* keep statusText */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch("/api/health").then((r) => jsonOrThrow<Health>(r)),

  stats: () => fetch("/api/stats").then((r) => jsonOrThrow<Stats>(r)),

  generate: (prompt: string, modality: string, parentRunId?: string) =>
    fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        modality,
        parent_run_id: parentRunId ?? null,
      }),
    }).then((r) => jsonOrThrow<GenerateResponse>(r)),

  campaign: (brief: string, variantPrompts: string[], modality = "image") =>
    fetch("/api/campaign", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brief, variant_prompts: variantPrompts, modality }),
    }).then((r) => jsonOrThrow<CampaignResponse>(r)),

  runs: (limit = 60) =>
    fetch(`/api/runs?limit=${limit}`).then((r) =>
      jsonOrThrow<{ runs: RunSummary[] }>(r),
    ),

  assetUrl: (key: string) =>
    fetch(`/api/asset-url?key=${encodeURIComponent(key)}`).then((r) =>
      jsonOrThrow<{ url: string }>(r),
    ),

  manifest: (key: string) =>
    fetch(`/api/manifest?key=${encodeURIComponent(key)}`).then((r) =>
      jsonOrThrow<Record<string, unknown>>(r),
    ),

  certificate: (key: string) =>
    fetch(`/api/certificate?key=${encodeURIComponent(key)}`).then((r) =>
      jsonOrThrow<Record<string, unknown>>(r),
    ),

  certificateDownloadUrl: (key: string) =>
    `/api/certificate?key=${encodeURIComponent(key)}&download=true`,

  verifyFile: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/verify", { method: "POST", body: fd }).then((r) =>
      jsonOrThrow<VerifyResponse>(r),
    );
  },
};
