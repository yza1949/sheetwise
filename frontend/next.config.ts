import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(process.cwd()),
  ...(process.env.STATIC_EXPORT === "1" ? { output: "export" as const } : {}),
  async rewrites() {
    if (process.env.STATIC_EXPORT === "1") return [];
    const target = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${target}/api/:path*` }];
  },
};

export default nextConfig;
