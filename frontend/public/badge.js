/**
 * Veritas provenance badge.
 *
 *   <script
 *     src="https://veritas-ebon-rho.vercel.app/badge.js"
 *     data-sha256="<the asset's sha-256 hex string>"
 *     data-theme="dark"          <!-- optional: "dark" | "light" -->
 *     defer
 *   ></script>
 *
 * The script mounts a Shadow-DOM'd pill next to its own <script> element
 * that reads "Verified by Veritas" once /api/verify-hash confirms the
 * hash exists on Backblaze B2. If the hash isn't known, the pill shows
 * "Unverified" instead. Zero dependencies, zero global CSS pollution,
 * one HTTPS request.
 */
(() => {
  const script = document.currentScript;
  if (!script) return;

  const API_ORIGIN =
    script.getAttribute("data-api") ||
    new URL(script.src).origin;

  const sha256 = (script.getAttribute("data-sha256") || "").trim().toLowerCase();
  const theme = script.getAttribute("data-theme") === "light" ? "light" : "dark";

  const host = document.createElement("span");
  host.setAttribute("data-veritas-badge", "");
  script.parentNode.insertBefore(host, script.nextSibling);
  const root = host.attachShadow({ mode: "open" });

  const palette =
    theme === "light"
      ? { bg: "#f6f6f7", fg: "#0a0a0b", muted: "#6c6c72", border: "#e5e5e7", accent: "#c48f00", accentInk: "#0a0a0b", ok: "#0f7a4a", warn: "#a15d00" }
      : { bg: "#0e0e10", fg: "#fafafa", muted: "#9a9aa0", border: "#262629", accent: "#facc15", accentInk: "#0a0a0b", ok: "#3ecf8e", warn: "#e2b93b" };

  const css = `
    :host { all: initial; display: inline-block; }
    .pill {
      display: inline-flex; align-items: center; gap: 8px;
      font: 500 12px/1 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
      background: ${palette.bg}; color: ${palette.fg};
      border: 1px solid ${palette.border}; border-radius: 999px;
      padding: 7px 12px 7px 8px;
      text-decoration: none; cursor: pointer;
      transition: transform 0.15s ease, border-color 0.2s ease;
      user-select: none;
    }
    .pill:hover { transform: translateY(-1px); border-color: ${palette.accent}; }
    .dot {
      width: 22px; height: 22px; border-radius: 999px;
      display: inline-flex; align-items: center; justify-content: center;
      background: ${palette.muted}20;
    }
    .dot.ok { background: ${palette.accent}; color: ${palette.accentInk}; }
    .dot.warn { background: ${palette.warn}22; color: ${palette.warn}; }
    .dot svg { width: 12px; height: 12px; }
    .label { font-weight: 700; letter-spacing: -0.005em; }
    .sub { color: ${palette.muted}; font-weight: 500; font-size: 10.5px; }
    .brand { color: ${palette.accent}; }
  `;

  const svgCheck =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
  const svgX =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
  const svgDot =
    '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="4"/></svg>';

  const style = document.createElement("style");
  style.textContent = css;
  root.appendChild(style);

  const link = document.createElement("a");
  link.className = "pill";
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.href = `${API_ORIGIN}/verify`;
  root.appendChild(link);

  const render = (state, main, sub) => {
    const dotClass = state === "ok" ? "dot ok" : state === "warn" ? "dot warn" : "dot";
    const svg = state === "ok" ? svgCheck : state === "warn" ? svgX : svgDot;
    link.innerHTML = `
      <span class="${dotClass}">${svg}</span>
      <span class="label">${main}</span>
      ${sub ? `<span class="sub">${sub}</span>` : ""}
    `;
  };

  const isValidSha = /^[0-9a-f]{64}$/.test(sha256);
  if (!isValidSha) {
    render("neutral", "Veritas", "no sha-256 provided");
    return;
  }

  render("neutral", "Verifying…", "");

  fetch(`${API_ORIGIN}/api/verify-hash`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sha256 }),
  })
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((result) => {
      if (result.verified && result.match) {
        const model = result.match.model || result.match.provider || "AI";
        render("ok", "Verified by Veritas", `${model.split("/").pop()}`);
        link.href = `${API_ORIGIN}/verify?sha256=${sha256}`;
      } else {
        render("warn", "Unverified", "no provenance on B2");
      }
    })
    .catch(() => render("neutral", "Veritas", "check failed"));
})();
