import type { NextConfig } from "next";
import { accountingOrigin, accountingRoutePrefixes } from "./lib/accounting-routes";

const accountingAddonStaticPattern = "[a-zA-Z0-9][a-zA-Z0-9_]*";

const accountingSources = [
  ...accountingRoutePrefixes.filter((prefix) => prefix !== "websocket").map((prefix) => `/${prefix}/:path*`),
  "/websocket/:path+",
  `/:addon(${accountingAddonStaticPattern})/static/:path*`,
  "/logo.png",
];

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "X-Frame-Options", value: "DENY" },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  transpilePackages: ["@tcsi/contracts"],
  async headers() {
    return [
      { source: "/(.*)", headers: securityHeaders },
      ...accountingSources.map((source) => ({ source, headers: [
        { key: "x-vercel-enable-rewrite-caching", value: "0" },
        { key: "Cache-Control", value: "private, no-store" },
        { key: "X-Frame-Options", value: "SAMEORIGIN" },
      ] })),
    ];
  },
  async rewrites() {
    if (process.env.VERCEL !== "1" && process.env.TCSI_PORTAL_ONLY !== "true") return [];
    return { beforeFiles: accountingSources.map((source) => ({
      source,
      destination: `${accountingOrigin}${source.replace(`(${accountingAddonStaticPattern})`, "")}`,
    })) };
  },
};

export default nextConfig;
