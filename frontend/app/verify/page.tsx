"use client";

import { useCallback, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  UploadCloud,
  ShieldCheck,
  ShieldX,
  Loader2,
  GitBranch,
} from "lucide-react";
import { api, type VerifyResponse } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

export default function VerifyPage() {
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const check = useCallback(async (file: File) => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.verifyFile(file));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  return (
    <div className="relative mx-auto max-w-2xl -mt-10 pt-14">
      <div className="absolute inset-x-0 top-0 h-72 bg-grid-fade" />
      <div className="relative space-y-2 mb-8">
        <div className="inline-flex items-center gap-1.5 rounded-full bg-white/5 px-3 py-1 text-[11px] font-medium text-accent mb-3">
          <ShieldCheck className="h-3 w-3" />
          Content-hash lookup
        </div>
        <h1 className="text-4xl sm:text-5xl font-black uppercase tracking-tight leading-[0.98]">
          Verify an asset
        </h1>
        <p className="text-muted-foreground text-[15px] max-w-md">
          Drop any media file. If it was generated through Veritas, its SHA-256
          will match a provenance manifest on Backblaze B2.
        </p>
      </div>

      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files?.[0];
          if (f) check(f);
        }}
        className={cn(
          "relative z-10 flex min-h-52 cursor-pointer flex-col items-center justify-center gap-4 overflow-hidden rounded-3xl border-2 border-dashed p-10 text-center transition-all",
          dragging
            ? "border-accent bg-accent-soft scale-[1.01]"
            : "border-line/60 bg-surface hover:border-muted-foreground/30",
        )}
      >
        <input
          type="file"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) check(f);
            e.currentTarget.value = "";
          }}
        />
        <motion.div
          animate={busy ? { rotate: 360 } : { y: [0, -4, 0] }}
          transition={
            busy
              ? { repeat: Infinity, duration: 1, ease: "linear" }
              : { repeat: Infinity, duration: 2.5, ease: "easeInOut" }
          }
        >
          {busy ? (
            <Loader2 className="h-8 w-8 text-accent" />
          ) : (
            <UploadCloud className="h-8 w-8 text-muted-foreground/40" />
          )}
        </motion.div>
        <div>
          <span className="text-sm font-medium block">
            {busy
              ? "Hashing & checking provenance..."
              : "Drop a file or click to browse"}
          </span>
          <span className="text-xs text-muted-foreground/50 mt-1 block">
            Your file is checked, not stored
          </span>
        </div>
      </label>

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
            className="relative z-10"
          >
            <div
              className={cn(
                "mt-6 overflow-hidden rounded-3xl border p-5",
                result.verified
                  ? "border-accent/25 bg-accent-soft"
                  : "border-warn/20 bg-warn/[0.04]",
              )}
            >
              <div className="flex items-center gap-3">
                <motion.span
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{
                    type: "spring",
                    stiffness: 300,
                    damping: 15,
                    delay: 0.1,
                  }}
                  className={cn(
                    "flex h-11 w-11 items-center justify-center rounded-full",
                    result.verified
                      ? "bg-accent text-accent-ink"
                      : "bg-warn/10 text-warn",
                  )}
                >
                  {result.verified ? (
                    <ShieldCheck className="h-5 w-5" />
                  ) : (
                    <ShieldX className="h-5 w-5" />
                  )}
                </motion.span>
                <div>
                  <p className="font-bold text-sm">
                    {result.verified
                      ? "Authentic — provenance verified"
                      : "No provenance record found"}
                  </p>
                  <p className="text-xs text-muted-foreground/60 mt-0.5">
                    {result.filename} &middot; sha-256{" "}
                    <span className="font-mono">
                      {result.sha256.slice(0, 20)}...
                    </span>
                  </p>
                  {result.verified && result.source && (
                    <Badge
                      variant="outline"
                      className="mt-1.5 text-[10px] rounded-full border-line/50"
                    >
                      matched via{" "}
                      {result.source === "index"
                        ? "O(1) B2 index"
                        : "manifest scan"}
                    </Badge>
                  )}
                </div>
              </div>

              {result.verified && result.match && (
                <>
                  <Separator className="my-4 bg-line/30" />
                  <dl className="grid grid-cols-[110px_1fr] gap-y-2.5 text-xs">
                    <dt className="text-muted-foreground/60">prompt</dt>
                    <dd>{result.match.prompt}</dd>
                    <dt className="text-muted-foreground/60">provider</dt>
                    <dd>
                      {result.match.provider} / {result.match.model}
                    </dd>
                    <dt className="text-muted-foreground/60">generated</dt>
                    <dd>{result.match.date}</dd>
                    <dt className="text-muted-foreground/60">run id</dt>
                    <dd className="font-mono">{result.match.run_id}</dd>
                    {result.match.parent_run_id && (
                      <>
                        <dt className="text-muted-foreground/60">
                          iteration of
                        </dt>
                        <dd className="font-mono">
                          {result.match.parent_run_id}
                        </dd>
                      </>
                    )}
                    {result.match.campaign_id && (
                      <>
                        <dt className="text-muted-foreground/60">campaign</dt>
                        <dd className="flex items-center gap-1 font-mono text-ok">
                          <GitBranch className="h-3 w-3" />{" "}
                          {result.match.campaign_id}
                        </dd>
                      </>
                    )}
                    <dt className="text-muted-foreground/60">manifest</dt>
                    <dd className="break-all font-mono text-muted-foreground/40">
                      {result.match.manifest_key}
                    </dd>
                  </dl>
                </>
              )}

              {!result.verified && (
                <>
                  <Separator className="my-4 bg-line/30" />
                  <p className="text-xs text-muted-foreground/60">
                    This file&apos;s content hash does not appear in any
                    provenance manifest. Either it wasn&apos;t generated
                    through Veritas, or it has been modified since generation.
                  </p>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
