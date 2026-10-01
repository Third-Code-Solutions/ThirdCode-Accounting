import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// The hosting provider injects the deployed commit; exposing it lets operators
// confirm which revision is actually serving without provider access.
const commit = process.env.VERCEL_GIT_COMMIT_SHA?.slice(0, 12) ?? null;

export function GET() {
  return NextResponse.json(
    {
      status: "ok",
      service: "tcsi-web",
      version: "0.1.0",
      commit,
      timestamp: new Date().toISOString(),
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
