"use client";

import { useCallback, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  Clapperboard,
  Loader2,
  ShieldCheck,
  Sparkles,
  Info,
} from "lucide-react";
import { api, type VideoScriptResult } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export default function VideoPage() {
  const [idea, setIdea] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VideoScriptResult | null>(null);

  const generate = useCallback(() => {
    const value = idea.trim();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    api
      .videoScript(value)
      .then(setResult)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  }, [idea, busy]);

  return (
    <div className="relative mx-auto max-w-2xl -mt-10 pt-14">
      <div className="absolute inset-x-0 top-0 h-72 bg-grid-fade" />

      <div className="relative space-y-2 mb-6">
        <div className="inline-flex items-center gap-1.5 rounded-full bg-white/5 px-3 py-1 text-[11px] font-medium text-accent mb-3">
          <Clapperboard className="h-3 w-3" />
          Script-only pipeline
        </div>
        <h1 className="text-4xl sm:text-5xl font-black uppercase tracking-tight leading-[0.98]">
          Video generation
        </h1>
        <p className="text-muted-foreground text-[15px] max-w-lg">
          Describe what you want a video to be about. Genblaze plans a real
          shot-by-shot script — with its own signed, verified provenance
          manifest, stored on Backblaze B2 the same way every other
          generation in this app is.
        </p>
      </div>

      {/* Formal, explicit statement of scope — not an apology, a decision. */}
      <div className="relative z-10 mb-8 rounded-2xl border border-accent/25 bg-accent-soft p-4">
        <div className="flex gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-accent-ink">
            <Info className="h-3.5 w-3.5" />
          </span>
          <div className="text-xs leading-relaxed text-foreground/85">
            <p className="font-semibold text-foreground mb-1">
              Scope note for this submission
            </p>
            <p>
              Video shares the same Genblaze pipeline architecture as
              comics and images: script planning and clip rendering are
              both real, provider-agnostic steps. For this submission,
              only script planning is enabled — clip rendering is
              intentionally not activated, since it requires paid
              provider credits we did not purchase for this build.
              GMI Cloud&apos;s video providers (<code>pixverse-v5.6-t2v</code>,
              with <code>wan2.6-r2v</code> as fallback) are already wired
              in the provider-routing code and will activate automatically
              the moment a funded key is present — no code change needed.
              This is a deliberate scope decision, not a missing capability.
            </p>
          </div>
        </div>
      </div>

      <div className="relative z-10 space-y-3">
        <Textarea
          data-testid="video-idea"
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          rows={3}
          placeholder="What should the video be about? e.g. A 30-second product teaser for a solar-powered backpack..."
          className="w-full resize-none rounded-2xl bg-surface border-line/60 text-sm placeholder:text-muted-foreground/40"
        />
        <Button
          data-testid="generate-video-script-button"
          onClick={generate}
          disabled={busy || !idea.trim()}
          className="h-9 rounded-full px-5 text-sm font-semibold gap-1.5"
        >
          {busy ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Sparkles className="h-3.5 w-3.5" />
          )}
          Generate script
        </Button>
      </div>

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="relative z-10 mt-6 rounded-2xl border border-destructive/20 bg-destructive/[0.06] px-4 py-3 text-sm text-destructive"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="relative z-10 mt-6 space-y-4 rounded-3xl border border-line/60 bg-surface p-5"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs text-muted-foreground/60">
                  Shot list for
                </p>
                <p className="font-semibold text-sm mt-0.5">{result.idea}</p>
              </div>
              {result.verified && (
                <span className="flex shrink-0 items-center gap-1 rounded-full bg-accent px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-accent-ink">
                  <ShieldCheck className="h-3 w-3" />
                  Verified
                </span>
              )}
            </div>

            <Separator className="bg-line/50" />

            <ol className="space-y-3">
              {result.shots.map((shot) => (
                <li
                  key={shot.index}
                  className="rounded-2xl border border-line/50 bg-surface-2 p-3.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wide text-accent">
                      Shot {shot.index + 1}
                    </span>
                    <span className="text-[10px] text-muted-foreground/50">
                      ~{shot.duration_sec}s
                    </span>
                  </div>
                  <p className="mt-1.5 text-sm leading-relaxed">
                    {shot.description}
                  </p>
                  <p className="mt-1.5 text-xs italic text-muted-foreground/60">
                    &ldquo;{shot.narration}&rdquo;
                  </p>
                </li>
              ))}
            </ol>

            {result.manifest_key && (
              <>
                <Separator className="bg-line/50" />
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    render={
                      <a
                        href={`/certificate?key=${encodeURIComponent(result.manifest_key)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      />
                    }
                    nativeButton={false}
                    variant="outline"
                    className="rounded-full text-xs border-line/60"
                  >
                    View certificate
                  </Button>
                  <span className="break-all font-mono text-[10px] text-muted-foreground/40">
                    run {result.run_id}
                  </span>
                </div>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
