import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { ShieldCheck, Info } from "lucide-react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Veritas — provenance-first generative media",
  description:
    "Generate AI media with cryptographically verifiable provenance, stored on Backblaze B2.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-black">
        <TooltipProvider delay={150}>
          <header className="sticky top-0 z-30 border-b border-line/60 bg-black">
            <div className="mx-auto max-w-7xl px-6 h-16 flex items-center gap-1">
              <Link href="/" className="flex items-center gap-2 pr-6 font-bold text-sm tracking-tight">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
                  <ShieldCheck className="h-4 w-4 text-accent-ink" strokeWidth={2.75} />
                </span>
                Veritas
              </Link>
              <nav className="flex items-center gap-1 text-[13px] font-medium">
                <Link
                  href="/studio"
                  className="rounded-full px-3.5 py-1.5 text-foreground/70 hover:bg-white/5 hover:text-foreground transition-colors"
                >
                  Studio
                </Link>
                <Link
                  href="/verify"
                  className="rounded-full px-3.5 py-1.5 text-foreground/70 hover:bg-white/5 hover:text-foreground transition-colors"
                >
                  Verify
                </Link>
                <Link
                  href="/embed"
                  className="rounded-full px-3.5 py-1.5 text-foreground/70 hover:bg-white/5 hover:text-foreground transition-colors"
                >
                  Embed
                </Link>
                <Link
                  href="/studio?mode=video"
                  className="rounded-full px-3.5 py-1.5 text-foreground/70 hover:bg-white/5 hover:text-foreground transition-colors"
                >
                  Video
                </Link>
              </nav>
              <div className="ml-auto flex items-center gap-2">
                <Link
                  href="/studio?mode=video"
                  title="Full Genblaze pipeline built for video generation — script planning is live with real provenance. Clip rendering is intentionally not activated for this submission (requires paid provider credits). See the Video mode in Studio for details."
                  className="hidden sm:flex items-center gap-1.5 rounded-full border border-accent/25 bg-accent-soft px-3 py-1 text-[11px] font-medium text-accent hover:bg-accent/15 transition-colors"
                >
                  <Info className="h-3 w-3" />
                  Video: script-only (credits pending)
                </Link>
                <span className="rounded-full bg-white/5 px-3 py-1 text-[11px] font-medium text-muted-foreground">
                  Genblaze
                </span>
                <span className="rounded-full bg-white/5 px-3 py-1 text-[11px] font-medium text-muted-foreground">
                  Backblaze B2
                </span>
              </div>
            </div>
          </header>

          <main className="flex-1 mx-auto w-full max-w-7xl px-6 py-10">
            {children}
          </main>

          <footer className="border-t border-line/40 py-4 text-center text-[11px] text-muted-foreground/50">
            Every asset ships with a SHA-256 provenance manifest on Backblaze B2
          </footer>

          <Toaster position="bottom-right" theme="dark" />
        </TooltipProvider>
      </body>
    </html>
  );
}
