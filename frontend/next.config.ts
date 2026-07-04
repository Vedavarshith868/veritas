import type { NextConfig } from "next";

// Backend URL is configurable so the proxy target isn't hard-coded.
// Defaults to the conventional local FastAPI port; override with BACKEND_URL.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    // Proxy API calls to the FastAPI backend (same-origin in the browser).
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
