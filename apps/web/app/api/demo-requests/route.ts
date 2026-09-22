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
    body = await request.json();
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

  const supabase = await getSupabaseServerClient();
  if (!supabase) {
    return NextResponse.json({ error: { code: "configuration_required", message: "The request service is not configured yet." } }, { status: 503 });
  }

  const { error } = await supabase.from("demo_requests").insert({
    company_name: input.data.companyName,
    contact_name: input.data.contactName,
    email: input.data.email.toLowerCase(),
    phone: input.data.phone || null,
    team_size: input.data.teamSize,
    accounting_stack: input.data.accountingStack || null,
    message: input.data.message,
    source: "website",
    status: "new",
  });

  if (error) {
    return NextResponse.json({ error: { code: "request_failed", message: "We could not save the request. Please try again." } }, { status: 503 });
  }

  return NextResponse.json({ data: { accepted: true } }, { status: 201 });
}
