import { describe, expect, it, vi } from "vitest";

vi.mock("@vercel/functions", () => ({ experimental_upgradeWebSocket: vi.fn(() => new Response(null, { status: 200 })) }));
import { GET } from "./route";

const origin = "https://portal.example";
const cookie = `session_id=${"a".repeat(64)}`;
describe("accounting notification boundary", () => {
  it.each([
    [{ origin: "https://attacker.example", cookie, upgrade: "websocket" }, 403],
    [{ origin, upgrade: "websocket" }, 401],
    [{ origin, cookie }, 426],
  ])("rejects invalid handshake headers", async (headers, status) => {
    const response = await GET(new Request(`${origin}/websocket?version=18.0-7`, { headers }));
    expect(response.status).toBe(status);
  });
  it("rejects arbitrary upstream destinations in the version", async () => {
    const response = await GET(new Request(`${origin}/websocket?version=https://attacker.example`, { headers: { origin, cookie, upgrade: "websocket" } }));
    expect(response.status).toBe(400);
  });
  it("accepts a same-origin session handshake", async () => {
    const response = await GET(new Request(`${origin}/websocket?version=18.0-7`, { headers: { origin, cookie, upgrade: "websocket" } }));
    expect(response.status).toBe(200);
  });
});
