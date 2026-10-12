import { createHmac } from "node:crypto";
import { isIP } from "node:net";
import { NextResponse } from "next/server";

import { demoRequestSchema } from "@tcsi/contracts";

import { getSupabaseServerClient } from "../../../lib/supabase/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_BODY_BYTES = 24_000;

export async function POST(request: Request) {
  const contentLength = Number(request.headers.get("content-length") ?? 0);
  if (contentLength > MAX_BODY_BYTES) {
    return NextResponse.json({ error: { code: "payload_too_large", message: "The request is too large." } }, { status: 413 });
  }

  let body: unknown;
  try {
    if (!request.body) {
      throw new SyntaxError("Missing request body");
    }
    const reader = request.body.getReader();
    const chunks: Uint8Array[] = [];
    let receivedBytes = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      receivedBytes += value.byteLength;
      if (receivedBytes > MAX_BODY_BYTES) {
        await reader.cancel();
        return NextResponse.json({ error: { code: "payload_too_large", message: "The request is too large." } }, { status: 413 });
      }
      chunks.push(value);
    }
    const bytes = new Uint8Array(receivedBytes);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.byteLength;
    }
    body = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    return NextResponse.json({ error: { code: "invalid_json", message: "Send a valid request." } }, { status: 400 });
  }

  const input = demoRequestSchema.safeParse(body);
  if (!input.success) {
    return NextResponse.json({ error: { code: "invalid_input", message: "Add your company, contact, work email, team size, and a short description." } }, { status: 400 });
  }

  // Quietly absorb obvious automated submissions without revealing the honeypot.
  if (input.data.website.trim()) {
    return NextResponse.json({ data: { accepted: true } }, { status: 201 });
  }

  const ingestionSecret = process.env.TCSI_DEMO_INTAKE_SECRET ?? "";
  if (!/^[0-9a-f]{64}$/.test(ingestionSecret)) {
    return NextResponse.json({ error: { code: "configuration_required", message: "The request service is not configured yet." } }, { status: 503 });
  }

  // Only Vercel's overwritten header is trusted. Other hosts share a bounded
  // bucket until they provide a verified ingress; arbitrary forwarding headers
  // must never let callers select a fresh rate-limit identity.
  const address = process.env.VERCEL === "1" ? request.headers.get("x-vercel-forwarded-for")?.trim() ?? "" : "";
  const addressVersion = address.includes("%") ? 0 : isIP(address);
  const clientAddress = addressVersion === 6 ? new URL(`http://[${address}]/`).hostname : addressVersion === 4 ? address : "unknown";
  const clientHash = createHmac("sha256", ingestionSecret).update(`demo-intake:${clientAddress}`).digest("hex");

  try {
    const supabase = await getSupabaseServerClient();
    if (!supabase) {
      return NextResponse.json({ error: { code: "configuration_required", message: "The request service is not configured yet." } }, { status: 503 });
    }
    const { error } = await supabase.rpc("submit_demo_request", {
      ingestion_secret: ingestionSecret,
      client_hash: clientHash,
      details: {
        company_name: input.data.companyName,
        contact_name: input.data.contactName,
        email: input.data.email.toLowerCase(),
        phone: input.data.phone || null,
        team_size: input.data.teamSize,
        accounting_stack: input.data.accountingStack || null,
        message: input.data.message,
      },
    }).abortSignal(AbortSignal.timeout(5_000));

    if (error?.code === "PT429" || (error?.code === "P0001" && error.message === "Demo request rate limit exceeded")) {
      return NextResponse.json({ error: { code: "rate_limited", message: "Too many requests. Please try again in an hour." } }, { status: 429, headers: { "Retry-After": "3600" } });
    }
    if (error) {
      return NextResponse.json({ error: { code: "request_failed", message: "We could not save the request. Please try again." } }, { status: 503 });
    }
  } catch {
    return NextResponse.json({ error: { code: "request_failed", message: "We could not save the request. Please try again." } }, { status: 503 });
  }

  return NextResponse.json({ data: { accepted: true } }, { status: 201 });
}
