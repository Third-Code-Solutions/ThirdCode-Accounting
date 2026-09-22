import { NextResponse } from "next/server";

import { createWorkspaceSchema } from "@tcsi/contracts";

import { getSupabaseServerClient } from "../../../lib/supabase/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const supabase = await getSupabaseServerClient();
  if (!supabase) {
    return NextResponse.json({ error: { code: "configuration_required", message: "The data workspace is not configured." } }, { status: 503 });
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Sign in is required." } }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: { code: "invalid_json", message: "Send a valid JSON body." } }, { status: 400 });
  }

  const input = createWorkspaceSchema.safeParse(body);
  if (!input.success) {
    return NextResponse.json({ error: { code: "invalid_input", message: "Workspace name and slug are invalid." } }, { status: 400 });
  }

  const { data, error } = await supabase.rpc("create_workspace", {
    workspace_name: input.data.name,
    workspace_slug: input.data.slug,
  });

  if (error) {
    const status = error.code === "23505" ? 409 : error.code === "42501" ? 403 : 400;
    return NextResponse.json({ error: { code: "workspace_creation_failed", message: "The workspace could not be created." } }, { status });
  }

  return NextResponse.json({ data }, { status: 201 });
}
