"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Printer, Download, ShieldCheck, Lock } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

/**
 * Printable provenance certificate for a single generation.
 *
 * Not styled to match the app chrome — this page is styled for print
 * (white background, black text, one-page fit). A judge can click
 * "Print" and get a clean PDF via the browser's Save-as-PDF dialog.
 */
export default function CertificatePageOuter() {
  return (
    <Suspense fallback={<div className="p-10 text-sm">Loading…</div>}>
      <CertificatePage />
    </Suspense>
  );
}

function CertificatePage() {
  const params = useSearchParams();
  const key = params.get("key") || "";
  const [cert, setCert] = useState<CertificatePayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!key) return;
    api
      .certificate(key)
      .then((c) => setCert(c as unknown as CertificatePayload))
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, [key]);

  if (!key) {
    return (
      <div className="p-10 text-sm text-muted-foreground">
        Missing <code className="font-mono">key</code> query parameter.
      </div>
    );
  }
  if (err) {
    return (
      <div className="p-10 text-sm text-destructive">
        Certificate unavailable: {err}
      </div>
    );
  }
  if (!cert) {
    return <div className="p-10 text-sm">Loading certificate…</div>;
  }

  return (
    <div className="print-doc">
      <style>{PRINT_CSS}</style>

      <div className="controls no-print">
        <Button
          onClick={() => window.print()}
          className="rounded-full h-9 px-4 text-sm font-semibold gap-1.5"
        >
          <Printer className="h-3.5 w-3.5" />
          Print / Save as PDF
        </Button>
        <Button
          render={
            <a
              href={api.certificateDownloadUrl(key)}
              download
            />
          }
          nativeButton={false}
          variant="outline"
          className="rounded-full h-9 px-4 text-sm border-line/60 gap-1.5"
        >
          <Download className="h-3.5 w-3.5" />
          Download JSON
        </Button>
      </div>

      <article className="sheet">
        <header className="header">
          <div className="brand">
            <span className="mark">
              <ShieldCheck size={16} />
            </span>
            <span>Veritas</span>
          </div>
          <div className="spec">{cert.spec}</div>
        </header>

        <h1 className="title">Provenance Certificate</h1>
        <p className="lede">
          This certificate attests that the media asset identified below was
          generated through the Veritas provenance-first media studio and that
          its Genblaze manifest is stored durably on Backblaze B2.
        </p>

        <section className="grid">
          <Row label="Prompt" value={cert.run.prompt} />
          <Row
            label="Provider · model"
            value={`${cert.run.provider} · ${cert.run.model}`}
          />
          <Row label="Generated" value={cert.run.date} />
          <Row label="Run ID" value={cert.run.run_id} mono />
          {cert.run.parent_run_id && (
            <Row label="Iteration of" value={cert.run.parent_run_id} mono />
          )}
          {cert.run.campaign_id && (
            <Row label="Campaign" value={cert.run.campaign_id} mono />
          )}
        </section>

        <section className="block">
          <div className="block-label">Asset hash (SHA-256)</div>
          <code className="hash">{cert.asset.sha256}</code>
        </section>

        <section className="block">
          <div className="block-label">Storage</div>
          <div className="stored">
            <div>
              <span className="sub">Bucket</span>
              <div className="mono">{cert.asset.b2_bucket}</div>
            </div>
            <div>
              <span className="sub">Region</span>
              <div className="mono">{cert.asset.b2_region}</div>
            </div>
          </div>
          <div className="stored-key mono">{cert.asset.b2_key}</div>
        </section>

        {cert.caption && (
          <section className="block">
            <div className="block-label">AI-generated caption</div>
            <p className="caption">&ldquo;{cert.caption.text}&rdquo;</p>
            <div className="sub">
              via <span className="mono">{cert.caption.model}</span> · chained
              step in the same Genblaze manifest
            </div>
          </section>
        )}

        {cert.worm_copy?.bucket && (
          <section className="block worm">
            <div className="block-label with-icon">
              <Lock size={12} /> Immutable copy · Object Lock
            </div>
            <div className="stored-key mono">
              {cert.worm_copy.bucket}/{cert.worm_copy.key}
            </div>
            <div className="sub">
              Mode: {cert.worm_copy.object_lock_mode}
              {cert.worm_copy.retain_until &&
                ` · Retained until ${cert.worm_copy.retain_until}`}
            </div>
          </section>
        )}

        <footer className="footer">
          <div>
            <div className="sub">Certificate SHA-256</div>
            <div className="mono cert-hash">{cert.certificate_sha256}</div>
          </div>
          <div>
            <div className="sub">Live verify</div>
            <div className="mono">
              Post the asset SHA-256 to <code>/api/verify-hash</code>
            </div>
          </div>
        </footer>
      </article>
    </div>
  );
}

/* ---- printable component pieces ---- */

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
}) {
  if (!value) return null;
  return (
    <div className="row">
      <div className="row-label">{label}</div>
      <div className={mono ? "row-value mono" : "row-value"}>{value}</div>
    </div>
  );
}

type CertificatePayload = {
  spec: string;
  certificate_sha256: string;
  run: {
    run_id: string;
    parent_run_id: string | null;
    campaign_id: string | null;
    date: string;
    provider: string;
    model: string;
    prompt: string;
    modality: string;
    verified: boolean;
  };
  asset: {
    sha256: string;
    media_type: string;
    b2_bucket: string;
    b2_region: string;
    b2_key: string;
  };
  caption: { text: string; model: string } | null;
  worm_copy: {
    bucket: string | null;
    key: string | null;
    version_id?: string;
    object_lock_mode?: string;
    retain_until?: string | null;
    retention_days?: number;
    mode?: string;
    note?: string;
  } | null;
};

/* ---- print CSS scoped via <style> so it doesn't fight the dark app theme ---- */

const PRINT_CSS = `
.print-doc {
  min-height: 100vh;
  background: #f4f4f6;
  color: #0a0a0b;
  padding: 32px 16px 64px;
  display: flex; flex-direction: column; align-items: center; gap: 20px;
  font-family: "Inter", ui-sans-serif, system-ui, sans-serif;
}
.print-doc .controls { display: flex; gap: 12px; }
.print-doc .sheet {
  background: #ffffff; color: #0a0a0b;
  width: 100%; max-width: 780px;
  border: 1px solid #dcdce0; border-radius: 6px;
  padding: 56px 56px 44px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.12);
}
.print-doc .header {
  display: flex; align-items: center; justify-content: space-between;
  padding-bottom: 24px; border-bottom: 2px solid #0a0a0b;
  margin-bottom: 28px;
}
.print-doc .brand {
  display: inline-flex; align-items: center; gap: 8px;
  font-weight: 800; font-size: 20px; letter-spacing: -0.01em;
}
.print-doc .brand .mark {
  width: 28px; height: 28px; border-radius: 6px; background: #facc15;
  display: inline-flex; align-items: center; justify-content: center;
  color: #0a0a0b;
}
.print-doc .spec { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px; color: #6c6c72; }
.print-doc .title {
  font-size: 34px; font-weight: 900; letter-spacing: -0.02em;
  margin: 8px 0 12px;
}
.print-doc .lede { font-size: 13px; line-height: 1.55; color: #3f3f45; margin-bottom: 28px; }
.print-doc .grid { display: grid; grid-template-columns: 1fr; gap: 12px; margin-bottom: 24px; }
.print-doc .row { display: grid; grid-template-columns: 160px 1fr; gap: 16px; padding: 8px 0; border-bottom: 1px solid #efeff2; }
.print-doc .row-label { font-size: 11px; color: #6c6c72; letter-spacing: 0.05em; text-transform: uppercase; font-weight: 600; padding-top: 2px; }
.print-doc .row-value { font-size: 13px; color: #0a0a0b; }
.print-doc .block { margin: 20px 0; }
.print-doc .block-label { font-size: 11px; color: #6c6c72; letter-spacing: 0.05em; text-transform: uppercase; font-weight: 700; margin-bottom: 8px; display: inline-flex; align-items: center; gap: 6px; }
.print-doc .block-label.with-icon svg { color: #a15d00; }
.print-doc .hash {
  display: block; padding: 12px 14px; border-radius: 6px;
  background: #f8f8fa; border: 1px solid #e5e5e8;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 12px; line-height: 1.5; word-break: break-all;
}
.print-doc .stored { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 8px; }
.print-doc .sub { font-size: 10.5px; color: #6c6c72; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
.print-doc .mono { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11.5px; word-break: break-all; }
.print-doc .stored-key { padding: 10px 12px; background: #f8f8fa; border: 1px solid #e5e5e8; border-radius: 6px; margin-top: 4px; }
.print-doc .caption { font-size: 14px; line-height: 1.55; color: #0a0a0b; font-style: italic; margin-bottom: 6px; }
.print-doc .worm { background: #fff8e5; border: 1px solid #f2d47b; border-radius: 6px; padding: 14px 18px; }
.print-doc .footer {
  margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e5e8;
  display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
}
.print-doc .cert-hash { font-size: 10px; word-break: break-all; color: #3f3f45; }
@media print {
  .print-doc { background: #ffffff; padding: 0; }
  .print-doc .no-print { display: none !important; }
  .print-doc .sheet { border: none; box-shadow: none; padding: 32px 40px; max-width: 720px; }
}
`;
