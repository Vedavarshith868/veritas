"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Copy, Check, Sparkles, Globe2, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { api, type RunSummary } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * Public "Verified by Veritas" badge documentation + live sandbox.
 *
 * The badge script itself lives at /badge.js — this page teaches
 * third-party integrators how to drop it into their own site, and
 * renders a *real* copy of it (mounted from the same public script)
 * against a hash they choose.
 */
export default function EmbedPage() {
  const [selectedHash, setSelectedHash] = useState<string>("");
  const [recentRuns, setRecentRuns] = useState<RunSummary[]>([]);
  const [copied, setCopied] = useState(false);
  const previewRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api
      .runs(6)
      .then(({ runs }) => {
        const withSha = runs.filter((r) => r.sha256);
        setRecentRuns(withSha);
        if (withSha.length && !selectedHash) setSelectedHash(withSha[0].sha256!);
      })
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const origin =
    typeof window !== "undefined" ? window.location.origin : "https://veritas-ebon-rho.vercel.app";

  const snippet = useMemo(
    () =>
      `<script\n  src="${origin}/badge.js"\n  data-sha256="${selectedHash || "<the sha-256 of your generated asset>"}"\n  data-theme="dark"\n  defer\n></script>`,
    [origin, selectedHash],
  );

  const copy = useCallback(() => {
    navigator.clipboard.writeText(snippet).then(() => {
      setCopied(true);
      toast.success("Snippet copied");
      setTimeout(() => setCopied(false), 1500);
    });
  }, [snippet]);

  // Re-mount the live badge every time the hash changes.
  useEffect(() => {
    const host = previewRef.current;
    if (!host || !selectedHash) return;
    host.innerHTML = "";
    const script = document.createElement("script");
    script.src = "/badge.js";
    script.setAttribute("data-sha256", selectedHash);
    script.setAttribute("data-theme", "dark");
    script.defer = true;
    host.appendChild(script);
  }, [selectedHash]);

  return (
    <div className="space-y-14">
      {/* Hero */}
      <section className="relative -mx-6 -mt-10 overflow-hidden px-6 pt-14 pb-10">
        <div className="absolute inset-0 bg-grid-fade" />
        <div className="relative max-w-2xl">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-white/5 px-3 py-1 text-[11px] font-medium text-accent mb-4">
            <Globe2 className="h-3 w-3" />
            One-line embed &middot; works on any site
          </div>
          <h1 className="text-4xl sm:text-5xl font-black uppercase tracking-tight leading-[0.98]">
            Verified by <span className="text-accent">Veritas</span>
          </h1>
          <p className="mt-4 text-[15px] text-muted-foreground max-w-lg leading-relaxed">
            Drop a single &lt;script&gt; tag next to any AI-generated asset on
            your site. The badge fetches the asset&apos;s SHA-256 against the
            live B2 provenance manifest and shows a real, cryptographically
            checked verification pill — no login, no SDK, one HTTPS request.
          </p>
        </div>
      </section>

      {/* Live preview */}
      <section>
        <h2 className="text-lg font-bold tracking-tight mb-3">Live preview</h2>
        <p className="text-xs text-muted-foreground/60 mb-5 max-w-xl">
          Pick a real generated asset below. The badge below re-mounts against
          its hash and hits the same /api/verify-hash your own site would.
        </p>

        <div className="rounded-2xl border border-line/60 bg-surface p-6">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground/60 mb-3">
            The badge, rendered live
          </div>
          <div
            ref={previewRef}
            className="min-h-[44px] flex items-center flex-wrap gap-4"
          />

          <div className="mt-8 border-t border-line/40 pt-5">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground/60 mb-3">
              Use hash from
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {recentRuns.map((r) => (
                <button
                  key={r.run_id}
                  onClick={() => setSelectedHash(r.sha256!)}
                  className={cn(
                    "rounded-xl border px-3 py-2 text-left text-xs transition-colors",
                    selectedHash === r.sha256
                      ? "border-accent bg-accent-soft"
                      : "border-line/60 bg-surface-2 hover:border-muted-foreground/30",
                  )}
                >
                  <div className="line-clamp-1 font-medium">{r.prompt}</div>
                  <div className="mt-0.5 font-mono text-[10px] text-muted-foreground/60">
                    {r.sha256?.slice(0, 24)}…
                  </div>
                </button>
              ))}
            </div>
            <div className="mt-3">
              <Input
                value={selectedHash}
                onChange={(e) => setSelectedHash(e.target.value.trim().toLowerCase())}
                placeholder="…or paste a sha-256 hex string"
                className="rounded-xl bg-surface-2 border-line/50 text-xs font-mono"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Snippet */}
      <section>
        <h2 className="text-lg font-bold tracking-tight mb-3">Copy the snippet</h2>
        <p className="text-xs text-muted-foreground/60 mb-5 max-w-xl">
          Paste this next to any &lt;img&gt; on your page. Swap in the asset&apos;s
          actual SHA-256 (or fetch it from your CMS/backend).
        </p>
        <div className="relative rounded-2xl border border-line/60 bg-surface p-5 font-mono text-[12.5px] leading-relaxed">
          <pre className="whitespace-pre-wrap break-all text-foreground/85">{snippet}</pre>
          <Button
            onClick={copy}
            variant="outline"
            className="absolute right-3 top-3 h-8 rounded-full text-xs border-line/60"
          >
            {copied ? <Check className="h-3 w-3 text-ok" /> : <Copy className="h-3 w-3" />}
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      </section>

      {/* Options */}
      <section>
        <h2 className="text-lg font-bold tracking-tight mb-4">Options</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <OptionRow
            attr="data-sha256"
            note="Required. The exact hex SHA-256 of the asset bytes."
          />
          <OptionRow
            attr="data-theme"
            note='Optional. "dark" (default) or "light".'
          />
          <OptionRow
            attr="data-api"
            note="Optional. Override the origin the badge queries (defaults to the origin the script loaded from)."
          />
        </div>
      </section>

      {/* Try it */}
      <section className="rounded-2xl border border-accent/25 bg-accent-soft p-6">
        <div className="flex items-start gap-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-accent-ink">
            <Sparkles className="h-5 w-5" />
          </span>
          <div>
            <h3 className="text-base font-bold tracking-tight">
              Don&apos;t have a Veritas asset yet?
            </h3>
            <p className="mt-1 text-xs text-muted-foreground max-w-md">
              Generate one on the Studio page. Every generation returns a
              sha-256 you can paste directly into the snippet above.
            </p>
            <Button
              render={<a href="/" />}
              nativeButton={false}
              variant="outline"
              className="mt-4 h-9 rounded-full text-xs border-line/60"
            >
              Go to Studio
              <ExternalLink className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}

function OptionRow({ attr, note }: { attr: string; note: string }) {
  return (
    <div className="rounded-xl border border-line/60 bg-surface p-4">
      <div className="font-mono text-xs text-accent">{attr}</div>
      <div className="mt-1.5 text-xs text-muted-foreground/70">{note}</div>
    </div>
  );
}
