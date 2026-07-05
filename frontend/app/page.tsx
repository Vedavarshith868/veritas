"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ImageIcon,
  Video,
  AudioLines,
  Copy,
  Check,
  ShieldCheck,
  ShieldAlert,
  GitBranch,
  FileJson2,
  FileDown,
  RefreshCw,
  Loader2,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { api, type RunSummary, type Stats } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { NumberTicker } from "@/components/ui/number-ticker";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type UrlCache = Record<string, string>;
type Mode = "single" | "campaign";

const MODALITY_ICON: Record<string, typeof ImageIcon> = {
  image: ImageIcon,
  video: Video,
  audio: AudioLines,
};

export default function StudioPage() {
  const [mode, setMode] = useState<Mode>("single");
  const [prompt, setPrompt] = useState("");
  const [brief, setBrief] = useState("");
  const [variantText, setVariantText] = useState("");
  const [modality, setModality] = useState("image");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [campaignStatus, setCampaignStatus] = useState<string | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [urls, setUrls] = useState<UrlCache>({});
  const [selected, setSelected] = useState<RunSummary | null>(null);
  const [providerMode, setProviderMode] = useState<string>("...");
  const [stats, setStats] = useState<Stats | null>(null);

  const refresh = useCallback(async () => {
    const { runs } = await api.runs();
    setRuns(runs);
    // Refresh live B2 stats alongside the gallery — the numbers-are-real
    // system-of-record panel updates as new manifests land.
    api.stats().then(setStats).catch(() => {});
  }, []);

  useEffect(() => {
    refresh().catch((e) => setError(String(e)));
    api.health().then((h) => setProviderMode(h.provider_mode)).catch(() => {});
  }, [refresh]);

  useEffect(() => {
    const missing = runs
      .filter((r) => r.asset_key && !urls[r.asset_key])
      .slice(0, 24);
    if (!missing.length) return;
    let cancelled = false;
    (async () => {
      const entries: UrlCache = {};
      await Promise.all(
        missing.map(async (r) => {
          try {
            const { url } = await api.assetUrl(r.asset_key!);
            entries[r.asset_key!] = url;
          } catch {
            /* skip */
          }
        }),
      );
      if (!cancelled) setUrls((u) => ({ ...u, ...entries }));
    })();
    return () => {
      cancelled = true;
    };
  }, [runs, urls]);

  const generate = useCallback(
    async (parentRunId?: string, promptOverride?: string) => {
      const p = (promptOverride ?? prompt).trim();
      if (!p || busy) return;
      setBusy(true);
      setError(null);
      try {
        await api.generate(p, modality, parentRunId);
        await refresh();
        toast.success(parentRunId ? "Iteration generated" : "Asset generated", {
          description: "Provenance manifest verified and stored on B2.",
        });
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        toast.error("Generation failed", { description: msg });
      } finally {
        setBusy(false);
      }
    },
    [prompt, modality, busy, refresh],
  );

  const generateCampaignFn = useCallback(async () => {
    const variants = variantText
      .split("\n")
      .map((v) => v.trim())
      .filter(Boolean);
    if (!brief.trim() || variants.length < 2 || busy) return;
    setBusy(true);
    setError(null);
    setCampaignStatus(null);
    try {
      const res = await api.campaign(brief.trim(), variants, modality);
      setCampaignStatus(
        `Campaign complete: ${res.succeeded}/${res.requested} variants generated.`,
      );
      await refresh();
      toast.success(`Campaign: ${res.succeeded}/${res.requested}`, {
        description: brief.trim(),
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error("Campaign failed", { description: msg });
    } finally {
      setBusy(false);
    }
  }, [brief, variantText, modality, busy, refresh]);

  const verifiedCount = runs.filter((r) => r.verified).length;
  const campaignCount = new Set(
    runs.filter((r) => r.campaign_id).map((r) => r.campaign_id),
  ).size;

  return (
    <div className="space-y-16">
      {/* Hero — split mockup console + bold headline, Higgsfield-style */}
      <section className="relative -mx-6 -mt-10 overflow-hidden px-6 pt-14 pb-12">
        <div className="absolute inset-0 bg-grid-fade" />
        <div className="relative grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:gap-14 items-center">
          {/* LEFT — functional generate console styled as product mockup */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="rounded-[1.75rem] border border-line bg-surface p-2 shadow-2xl shadow-black/50">
            <div className="rounded-[1.4rem] bg-surface-2/70 p-5 space-y-4">
              <div className="flex items-center gap-2.5">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-[11px] font-bold text-accent-ink">
                  1
                </span>
                <span className="text-xs font-medium text-muted-foreground">
                  Describe what to generate
                </span>
                <span className="ml-auto flex items-center gap-1.5 text-[11px] text-muted-foreground/50">
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      providerMode === "mock" ? "bg-warn" : "bg-ok",
                    )}
                  />
                  {providerMode}
                </span>
              </div>

              {/* mode segmented control */}
              <div className="flex items-center gap-1 rounded-full bg-black/30 p-1 w-fit">
                <button
                  data-testid="mode-single"
                  onClick={() => setMode("single")}
                  className={cn(
                    "rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors",
                    mode === "single"
                      ? "bg-white text-black"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  Single
                </button>
                <button
                  data-testid="mode-campaign"
                  onClick={() => setMode("campaign")}
                  className={cn(
                    "rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors",
                    mode === "campaign"
                      ? "bg-white text-black"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  Campaign
                </button>
                {busy && (
                  <span className="flex items-center gap-1.5 pl-2 pr-1 text-[11px] text-accent">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Generating
                  </span>
                )}
              </div>

              <AnimatePresence mode="wait">
                {mode === "single" ? (
                  <motion.div
                    key="single"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.1 }}
                    className="space-y-3"
                  >
                    <Textarea
                      data-testid="prompt-input"
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          generate();
                        }
                      }}
                      rows={3}
                      placeholder="A steaming latte next to falling autumn leaves..."
                      className="w-full resize-none rounded-2xl bg-black/30 border-line/40 text-sm placeholder:text-muted-foreground/40"
                    />
                    <div className="flex items-center gap-2">
                      <ModalitySelect value={modality} onChange={setModality} />
                      <Button
                        data-testid="generate-button"
                        onClick={() => generate()}
                        disabled={busy || !prompt.trim()}
                        className="ml-auto h-9 rounded-full px-5 text-sm font-semibold gap-1.5"
                      >
                        <Sparkles className="h-3.5 w-3.5" />
                        Generate
                      </Button>
                    </div>
                  </motion.div>
                ) : (
                  <motion.div
                    key="campaign"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.1 }}
                    className="space-y-2"
                  >
                    <Input
                      value={brief}
                      onChange={(e) => setBrief(e.target.value)}
                      placeholder="Campaign brief, e.g. Autumn coffee shop ad"
                      className="rounded-2xl bg-black/30 border-line/40 text-sm"
                    />
                    <Textarea
                      value={variantText}
                      onChange={(e) => setVariantText(e.target.value)}
                      rows={3}
                      placeholder={"One variant per line (min 2):\nCozy coffee shop interior, warm lighting\nSteaming latte next to autumn leaves"}
                      className="resize-none rounded-2xl bg-black/30 border-line/40 text-sm font-mono"
                    />
                    <div className="flex items-center gap-2">
                      <ModalitySelect value={modality} onChange={setModality} />
                      <Button
                        onClick={generateCampaignFn}
                        disabled={
                          busy ||
                          !brief.trim() ||
                          variantText
                            .split("\n")
                            .map((v) => v.trim())
                            .filter(Boolean).length < 2
                        }
                        className="ml-auto h-9 rounded-full px-5 text-sm font-semibold gap-1.5"
                      >
                        <Sparkles className="h-3.5 w-3.5" />
                        Generate campaign
                      </Button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* metadata pills, mimicking product-mockup tag row */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                <MetaPill>Backblaze B2</MetaPill>
                <MetaPill>Genblaze SDK</MetaPill>
                <MetaPill>SHA-256 manifest</MetaPill>
              </div>

              <AnimatePresence>
                {campaignStatus && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="rounded-2xl border border-ok/20 bg-ok/[0.06] px-3 py-2 text-xs text-ok"
                  >
                    {campaignStatus}
                  </motion.div>
                )}
                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="rounded-2xl border border-destructive/20 bg-destructive/[0.06] px-3 py-2 text-xs text-destructive"
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>

          {/* RIGHT — bold headline */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.15, ease: "easeOut" }}
          >
            <div className="inline-flex items-center gap-1.5 rounded-full bg-white/5 px-3 py-1 text-[11px] font-medium text-accent mb-6">
              <Sparkles className="h-3 w-3" />
              Generate once. Prove it forever.
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black uppercase tracking-tight leading-[0.98]">
              Every asset,
              <br />
              <span className="text-accent">verified forever.</span>
            </h1>
            <p className="mt-5 max-w-md text-[15px] text-muted-foreground leading-relaxed">
              Generate images, video, and audio with a cryptographically
              verifiable provenance manifest baked in — stored durably on
              Backblaze B2 the moment it&apos;s born.
            </p>

            <div className="mt-9 flex items-center gap-8">
              <StatPill label="Generated" value={runs.length} />
              <StatPill label="Verified" value={verifiedCount} color="text-ok" />
              <StatPill label="Campaigns" value={campaignCount} />
            </div>
          </motion.div>
        </div>
      </section>

      {/* Gallery — bento-style asymmetric grid */}
      <section>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold tracking-tight">
            Generated Assets
          </h2>
          <span className="text-xs text-muted-foreground/60">
            {runs.length} total
          </span>
        </div>

        {runs.length ? (
          <div className="grid grid-cols-2 auto-rows-[190px] gap-4 lg:grid-cols-4">
            {runs.map((r, i) => (
              <GalleryCard
                key={r.run_id}
                run={r}
                url={r.asset_key ? urls[r.asset_key] : undefined}
                featured={i === 0}
                onSelect={() => setSelected(r)}
              />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center rounded-3xl border border-dashed border-line/60 py-20 text-center">
            <div className="h-12 w-12 rounded-2xl bg-surface-2 flex items-center justify-center mb-4">
              <ImageIcon className="h-5 w-5 text-muted-foreground/40" />
            </div>
            <p className="text-sm text-muted-foreground">No assets yet</p>
            <p className="text-xs text-muted-foreground/50 mt-1">
              Generate your first provenance-tracked asset above
            </p>
          </div>
        )}
      </section>

      {/* B2 System of Record — proves live metrics come straight from B2, no separate DB */}
      {stats && <SystemOfRecordSection stats={stats} />}

      {/* Provenance modal */}
      <Dialog
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        {selected && (
          <ProvenanceModal
            run={selected}
            runs={runs}
            url={selected.asset_key ? urls[selected.asset_key] : undefined}
            onRegenerate={() =>
              generate(selected.run_id, selected.prompt ?? undefined)
            }
            busy={busy}
          />
        )}
      </Dialog>
    </div>
  );
}

/* ── Sub-components ─────────────────────────────────────────── */

function MetaPill({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full bg-white/5 border border-white/5 px-2.5 py-1 text-[10.5px] font-medium text-muted-foreground/70">
      {children}
    </span>
  );
}

function SystemOfRecordSection({ stats }: { stats: Stats }) {
  const mb = stats.asset_bytes / (1024 * 1024);
  const sizeLabel =
    mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(stats.asset_bytes / 1024)} KB`;

  const cards: Array<{
    label: string;
    value: string;
    hint: string;
    accent?: boolean;
  }> = [
    {
      label: "Provenance manifests",
      value: stats.generations.toLocaleString(),
      hint: "one per generation attempt",
    },
    {
      label: "Media assets",
      value: stats.assets.toLocaleString(),
      hint: sizeLabel + " stored on B2",
    },
    {
      label: "Verify-index (O(1))",
      value: stats.verify_index_entries.toLocaleString(),
      hint: "sha-256 → run lookup objects",
    },
    {
      label: "WORM-locked copies",
      value: stats.locked_manifests.toLocaleString(),
      hint: "compliance-mode Object Lock",
    },
    {
      label: "Multi-step runs",
      value: stats.multi_step_runs.toLocaleString(),
      hint: `${stats.with_captions.toLocaleString()} with AI captions`,
      accent: true,
    },
  ];

  return (
    <section>
      <div className="flex items-end justify-between mb-5">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground/60">
            System of record
          </div>
          <h2 className="text-lg font-bold tracking-tight mt-0.5">
            Everything you see lives on Backblaze B2.
          </h2>
          <p className="text-xs text-muted-foreground/60 mt-1 max-w-md">
            No separate database — runs, manifests, lineage, verify-index, and
            WORM copies are all queried live from B2 objects on every request.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {cards.map((c) => (
          <div
            key={c.label}
            className={cn(
              "rounded-2xl border p-4",
              c.accent
                ? "border-accent/25 bg-accent-soft"
                : "border-line/60 bg-surface",
            )}
          >
            <div
              className={cn(
                "text-[10px] uppercase tracking-wider mb-2 font-medium",
                c.accent ? "text-accent" : "text-muted-foreground/60",
              )}
            >
              {c.label}
            </div>
            <div className="text-2xl font-black tabular-nums leading-none">
              {c.value}
            </div>
            <div className="text-[11px] text-muted-foreground/60 mt-2">
              {c.hint}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function StatPill({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color?: string;
}) {
  return (
    <div>
      <NumberTicker
        value={value}
        className={cn("block text-2xl font-black tabular-nums", color)}
      />
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground/60">
        {label}
      </span>
    </div>
  );
}

function ModalitySelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const Icon = MODALITY_ICON[value] ?? ImageIcon;
  return (
    <Select value={value} onValueChange={(v) => v && onChange(v)}>
      <SelectTrigger className="h-9 rounded-full bg-black/30 border-line/40 text-sm">
        <Icon className="h-3.5 w-3.5 text-muted-foreground" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="image">
          <ImageIcon className="h-3.5 w-3.5" /> Image
        </SelectItem>
        <SelectItem value="video">
          <Video className="h-3.5 w-3.5" /> Video
        </SelectItem>
        <SelectItem value="audio">
          <AudioLines className="h-3.5 w-3.5" /> Audio
        </SelectItem>
      </SelectContent>
    </Select>
  );
}

function GalleryCard({
  run,
  url,
  featured,
  onSelect,
}: {
  run: RunSummary;
  url?: string;
  featured?: boolean;
  onSelect: () => void;
}) {
  return (
    <motion.button
      data-testid="gallery-card"
      data-run-id={run.run_id}
      data-campaign={run.campaign_id ? "true" : "false"}
      onClick={onSelect}
      whileHover={{ scale: 1.015 }}
      whileTap={{ scale: 0.985 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={cn(
        "group relative overflow-hidden rounded-2xl border border-line/60 bg-surface text-left transition-shadow hover:shadow-[0_0_0_1px_var(--accent-glow)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
        featured && "col-span-2 row-span-2",
      )}
    >
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={url}
          alt={run.prompt ?? "generated asset"}
          className="h-full w-full object-cover transition-[filter] duration-300 group-hover:brightness-110"
        />
      ) : (
        <Skeleton className="h-full w-full rounded-none bg-surface-2" />
      )}

      {/* corner status tag, Higgsfield NEW/TRENDING style */}
      <div className="absolute right-2.5 top-2.5 flex flex-col items-end gap-1">
        {run.verified && (
          <span className="rounded-full bg-accent px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wide text-accent-ink">
            Verified
          </span>
        )}
        {run.campaign_id && (
          <span
            data-testid="campaign-tag"
            className="rounded-full bg-ok px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wide text-black"
          >
            Campaign
          </span>
        )}
        {run.parent_run_id && (
          <span className="rounded-full bg-pink-500 px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wide text-white">
            Iteration
          </span>
        )}
      </div>

      {/* Gradient overlay */}
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/40 to-transparent p-3.5 pt-14">
        <p
          className={cn(
            "line-clamp-2 font-medium text-white/90 leading-snug",
            featured ? "text-base" : "text-xs",
          )}
        >
          {run.prompt}
        </p>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
          <Badge
            variant="outline"
            className="border-white/10 bg-white/5 text-[10px] text-white/60 rounded-full"
          >
            {run.provider}
          </Badge>
        </div>
      </div>
    </motion.button>
  );
}

function CopyableRow({
  label,
  value,
  mono = true,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(() => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      toast.success(`${label} copied`);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [value, label]);

  return (
    <>
      <dt className="text-muted-foreground/60">{label}</dt>
      <dd className="flex items-center gap-1.5">
        <Tooltip>
          <TooltipTrigger
            className={cn("break-all text-left", mono && "font-mono")}
          >
            {value.length > 24 ? `${value.slice(0, 24)}...` : value}
          </TooltipTrigger>
          <TooltipContent className="max-w-xs break-all font-mono text-[10px]">
            {value}
          </TooltipContent>
        </Tooltip>
        <button
          onClick={copy}
          className="shrink-0 text-muted-foreground/40 hover:text-accent transition-colors"
          aria-label={`Copy ${label}`}
        >
          {copied ? (
            <Check className="h-3 w-3 text-ok" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
        </button>
      </dd>
    </>
  );
}

function ProvenanceModal({
  run,
  runs,
  url,
  onRegenerate,
  busy,
}: {
  run: RunSummary;
  runs: RunSummary[];
  url?: string;
  onRegenerate: () => void;
  busy: boolean;
}) {
  const [manifest, setManifest] = useState<Record<string, unknown> | null>(
    null,
  );
  const [showJson, setShowJson] = useState(false);

  const lineage = useMemo(() => {
    const byId = new Map(runs.map((r) => [r.run_id, r]));
    const chain: RunSummary[] = [];
    let cur: RunSummary | undefined = run;
    while (cur) {
      chain.push(cur);
      cur = cur.parent_run_id ? byId.get(cur.parent_run_id) : undefined;
      if (chain.length > 10) break;
    }
    return chain;
  }, [run, runs]);

  useEffect(() => {
    setManifest(null);
    setShowJson(false);
    api.manifest(run.manifest_key).then(setManifest).catch(() => {});
  }, [run.manifest_key]);

  return (
    <DialogContent data-testid="provenance-modal" className="sm:max-w-lg p-0 gap-0 overflow-hidden rounded-3xl">
      {url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt="" className="w-full max-h-72 object-cover" />
      )}

      <div className="space-y-4 p-5 text-sm">
        <div>
          <p className="font-medium leading-snug">{run.prompt}</p>
          <p className="text-xs text-muted-foreground/50 mt-1">
            {run.date}
          </p>
        </div>

        <div
          className={cn(
            "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-bold w-fit uppercase tracking-wide",
            run.verified
              ? "bg-accent text-accent-ink"
              : "bg-warn/15 text-warn",
          )}
        >
          {run.verified ? (
            <ShieldCheck className="h-3.5 w-3.5" />
          ) : (
            <ShieldAlert className="h-3.5 w-3.5" />
          )}
          {run.verified ? "Provenance verified" : "Unverified"}
        </div>

        <Separator className="bg-line/50" />

        <dl className="grid grid-cols-[90px_1fr] gap-y-2.5 text-xs">
          <dt className="text-muted-foreground/60">provider</dt>
          <dd>
            {run.provider} / {run.model}
          </dd>
          <CopyableRow label="sha-256" value={run.sha256 ?? ""} />
          <CopyableRow label="run id" value={run.run_id} />
          {run.campaign_id && (
            <>
              <dt className="text-muted-foreground/60">campaign</dt>
              <dd className="flex items-center gap-1 font-mono text-ok">
                <GitBranch className="h-3 w-3" />
                {run.campaign_id.slice(0, 16)}...
              </dd>
            </>
          )}
          <dt className="text-muted-foreground/60">stored at</dt>
          <dd className="break-all font-mono text-[11px] text-muted-foreground/40">
            {run.asset_key}
          </dd>
        </dl>

        {run.caption && (
          <div className="rounded-2xl border border-accent/25 bg-accent-soft p-3">
            <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-accent mb-1.5">
              <Sparkles className="h-3 w-3" />
              AI Caption
              <span className="text-muted-foreground/50 font-normal normal-case tracking-normal">
                &middot; step 2 &middot; {run.caption_model?.split("/").pop() ?? "vlm"}
              </span>
            </div>
            <p className="text-xs leading-relaxed text-foreground/85">
              &ldquo;{run.caption}&rdquo;
            </p>
          </div>
        )}

        {lineage.length > 1 && (
          <>
            <Separator className="bg-line/50" />
            <div>
              <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground/60">
                <GitBranch className="h-3.5 w-3.5" /> Iteration lineage (
                {lineage.length})
              </p>
              <ol className="space-y-1.5 text-xs">
                {lineage.map((l, i) => (
                  <li key={l.run_id} className="flex items-center gap-2">
                    <span
                      className={cn(
                        "h-1.5 w-1.5 rounded-full",
                        i === 0 ? "bg-accent" : "bg-muted-foreground/30",
                      )}
                    />
                    <span className="font-mono text-muted-foreground/60">
                      {l.run_id.slice(0, 8)}
                    </span>
                    <span className="line-clamp-1 text-muted-foreground/40">
                      {l.prompt}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          </>
        )}

        <Separator className="bg-line/50" />

        <div className="flex flex-wrap gap-2">
          <Button
            data-testid="regenerate-button"
            onClick={onRegenerate}
            disabled={busy}
            variant="outline"
            className="flex-1 rounded-full text-xs font-semibold border-line/60"
          >
            <RefreshCw
              className={cn("h-3 w-3", busy && "animate-spin")}
            />
            Regenerate (linked)
          </Button>
          <Button
            data-testid="manifest-toggle"
            onClick={() => setShowJson((s) => !s)}
            variant="outline"
            className="rounded-full text-xs border-line/60"
          >
            <FileJson2 className="h-3 w-3" />
            {showJson ? "Hide" : "Manifest"}
          </Button>
          <Button
            render={
              <a
                href={`/certificate?key=${encodeURIComponent(run.manifest_key)}`}
                target="_blank"
                rel="noopener noreferrer"
              />
            }
            nativeButton={false}
            variant="outline"
            className="rounded-full text-xs border-line/60"
          >
            <FileDown className="h-3 w-3" />
            Certificate
          </Button>
        </div>

        <AnimatePresence>
          {showJson && manifest && (
            <motion.pre
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="max-h-56 overflow-auto rounded-2xl bg-surface-2 p-3 font-mono text-[10px] leading-relaxed text-muted-foreground"
            >
              {JSON.stringify(manifest, null, 2)}
            </motion.pre>
          )}
        </AnimatePresence>
      </div>
    </DialogContent>
  );
}
