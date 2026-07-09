"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import {
  ShieldCheck,
  Sparkles,
  ImageIcon,
  GitBranch,
  BookOpen,
  Clapperboard,
  ArrowRight,
  Lock,
  Database,
  KeyRound,
} from "lucide-react";
import { api, type Stats } from "@/lib/api";
import { cn } from "@/lib/utils";
import { NumberTicker } from "@/components/ui/number-ticker";

const FEATURES = [
  {
    mode: "single",
    icon: ImageIcon,
    title: "Generate",
    tag: null as string | null,
    description:
      "Turn a text prompt into an image, video, or audio asset. Every generation carries a signed, SHA-256 provenance manifest — stored on Backblaze B2 the instant it's born, not bolted on after.",
  },
  {
    mode: "campaign",
    icon: GitBranch,
    title: "Campaigns",
    tag: null,
    description:
      "One brief, many variants. Batch-generate a whole set of creative directions in one run and compare every result side by side, each with its own verified lineage.",
  },
  {
    mode: "comic",
    icon: BookOpen,
    title: "Comics",
    tag: null,
    description:
      "A theme in, a full illustrated story out. A real multistep Genblaze pipeline writes the script, generates every panel, composites the strip, and narrates each page — comic or anime style.",
  },
  {
    mode: "video",
    icon: Clapperboard,
    title: "Video",
    tag: "Script-only for this submission",
    description:
      "Describe an idea and Genblaze plans a real shot-by-shot script with its own verified manifest. Clip rendering is wired and provider-ready — intentionally not activated here since it needs paid credits we didn't purchase for this build.",
  },
];

const PROOF_POINTS = [
  {
    icon: Lock,
    title: "Cryptographic provenance",
    description:
      "Every asset is hashed (SHA-256) and its full generation manifest — provider, model, prompt, lineage — is signed and stored the moment it's created.",
  },
  {
    icon: Database,
    title: "No separate database",
    description:
      "Runs, manifests, lineage, and the verify-index are all queried live from Backblaze B2 objects. What you see on screen is what's actually in the bucket.",
  },
  {
    icon: KeyRound,
    title: "Durable by construction",
    description:
      "A WORM-locked bucket in Object Lock compliance mode holds an immutable copy of every manifest — even an admin can't quietly rewrite history.",
  },
];

export default function LandingPage() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    api.stats().then(setStats).catch(() => {});
  }, []);

  return (
    <div className="space-y-28 pb-8">
      {/* Hero */}
      <section className="relative -mx-6 -mt-10 overflow-hidden px-6 pt-20 pb-16 text-center">
        <div className="absolute inset-0 bg-grid-fade" />
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="relative mx-auto max-w-3xl"
        >
          <div className="mx-auto mb-7 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent shadow-[0_0_60px_var(--accent-glow)]">
            <ShieldCheck className="h-7 w-7 text-accent-ink" strokeWidth={2.5} />
          </div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-white/5 px-3 py-1 text-[11px] font-medium text-accent mb-6">
            <Sparkles className="h-3 w-3" />
            Backblaze Generative Media Hackathon
          </div>
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-black uppercase tracking-tight leading-[0.95]">
            Generate once.
            <br />
            <span className="text-accent">Prove it forever.</span>
          </h1>
          <p className="mt-6 max-w-xl mx-auto text-[15px] sm:text-base text-muted-foreground leading-relaxed">
            Veritas is a provenance-first generative media studio. Images,
            campaigns, comics, and video scripts — every asset ships with a
            cryptographically verifiable manifest, stored durably on
            Backblaze B2 from the moment it exists.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/studio"
              className="inline-flex items-center gap-1.5 rounded-full bg-accent px-6 py-3 text-sm font-bold text-accent-ink transition-transform hover:scale-[1.03]"
            >
              Enter Studio
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/verify"
              className="inline-flex items-center gap-1.5 rounded-full border border-line/60 bg-white/5 px-6 py-3 text-sm font-semibold text-foreground/80 transition-colors hover:bg-white/10 hover:text-foreground"
            >
              Verify an asset
            </Link>
          </div>

          {stats && (
            <div className="mt-14 flex items-center justify-center gap-10 sm:gap-14">
              <HeroStat label="Assets generated" value={stats.generations} />
              <HeroStat label="Manifests verified" value={stats.verify_index_entries} />
              <HeroStat label="WORM-locked copies" value={stats.locked_manifests} />
            </div>
          )}
        </motion.div>
      </section>

      {/* Features */}
      <section>
        <div className="text-center mb-12">
          <div className="text-[11px] uppercase tracking-wider text-accent font-semibold mb-2">
            Four ways in, one provenance guarantee
          </div>
          <h2 className="text-3xl sm:text-4xl font-black uppercase tracking-tight">
            Everything Veritas builds
          </h2>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.mode}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, delay: i * 0.05, ease: "easeOut" }}
            >
              <Link
                href={`/studio?mode=${f.mode}`}
                className="group relative flex h-full flex-col rounded-3xl border border-line/60 bg-surface p-7 transition-shadow hover:shadow-[0_0_0_1px_var(--accent-glow)]"
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-accent-soft text-accent">
                  <f.icon className="h-5 w-5" />
                </span>
                <h3 className="mt-5 text-xl font-bold tracking-tight">
                  {f.title}
                </h3>
                {f.tag && (
                  <span className="mt-1.5 inline-flex w-fit items-center rounded-full border border-accent/25 bg-accent-soft px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-accent">
                    {f.tag}
                  </span>
                )}
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                  {f.description}
                </p>
                <span className="mt-5 flex items-center gap-1.5 text-sm font-semibold text-accent">
                  Try it
                  <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
                </span>
              </Link>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Proof points */}
      <section>
        <div className="text-center mb-12">
          <div className="text-[11px] uppercase tracking-wider text-accent font-semibold mb-2">
            Not a claim — a bucket you can open
          </div>
          <h2 className="text-3xl sm:text-4xl font-black uppercase tracking-tight">
            Provenance is the product
          </h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          {PROOF_POINTS.map((p, i) => (
            <motion.div
              key={p.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, delay: i * 0.05, ease: "easeOut" }}
              className="rounded-3xl border border-line/60 bg-surface p-6"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/5 text-accent">
                <p.icon className="h-4 w-4" />
              </span>
              <h3 className="mt-4 text-base font-bold tracking-tight">
                {p.title}
              </h3>
              <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
                {p.description}
              </p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Closing CTA */}
      <section className="relative -mx-6 overflow-hidden rounded-[2rem] border border-line/60 bg-surface px-6 py-16 text-center">
        <div className="absolute inset-0 bg-grid-fade opacity-60" />
        <div className="relative">
          <h2 className="text-3xl sm:text-4xl font-black uppercase tracking-tight">
            Every asset, <span className="text-accent">verified forever.</span>
          </h2>
          <p className="mt-4 max-w-md mx-auto text-sm text-muted-foreground">
            Jump into the Studio and generate your first provenance-tracked
            asset in seconds.
          </p>
          <Link
            href="/studio"
            className="mt-8 inline-flex items-center gap-1.5 rounded-full bg-accent px-6 py-3 text-sm font-bold text-accent-ink transition-transform hover:scale-[1.03]"
          >
            Enter Studio
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>
    </div>
  );
}

function HeroStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <NumberTicker
        value={value}
        className={cn("block text-3xl font-black tabular-nums")}
      />
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground/60">
        {label}
      </span>
    </div>
  );
}
