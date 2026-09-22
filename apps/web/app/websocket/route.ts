import { experimental_upgradeWebSocket } from "@vercel/functions";
import WebSocket, { type RawData } from "ws";
import { accountingOrigin } from "../../lib/accounting-routes";

export const runtime = "nodejs";
export const maxDuration = 300;
const MAX_BUFFER = 1024 * 1024;

export async function GET(request: Request) {
  const url = new URL(request.url);
  if (request.headers.get("origin") !== url.origin) {
    return new Response("Origin not allowed", { status: 403 });
  }
  const session = request.headers.get("cookie")?.match(/(?:^|;\s*)session_id=([A-Za-z0-9_-]{20,128})(?:;|$)/)?.[1];
  if (!session) return new Response("Sign in required", { status: 401 });
  const version = url.searchParams.get("version");
  if (!version || !/^[\w.-]{1,32}$/.test(version)) {
    return new Response("Invalid notification protocol version", { status: 400 });
  }
  if (request.headers.get("upgrade")?.toLowerCase() !== "websocket") {
    return new Response("WebSocket upgrade required", { status: 426 });
  }
  return experimental_upgradeWebSocket((client) => {
    // The origin validates the existing session and authorizes each subscription.
    // Never accept an upstream URL or identity supplied by the client.
    const upstream = new WebSocket(`${accountingOrigin.replace("https:", "wss:")}/websocket?version=${encodeURIComponent(version)}`, {
      headers: { Cookie: `session_id=${session}`, Origin: accountingOrigin },
      handshakeTimeout: 10_000,
      maxPayload: MAX_BUFFER,
      perMessageDeflate: false,
    });
    let pending: Array<{ data: RawData; binary: boolean }> = [];
    let pendingBytes = 0;
    const closeClient = (code: number, reason: string) => {
      if (client.readyState === WebSocket.OPEN) client.close(code, reason);
    };
    // Reconnect before the function deadline; the engine worker resubscribes.
    const expiry = setTimeout(() => closeClient(1012, "Reconnect notifications"), 270_000);
    expiry.unref();
    client.on("message", (data: RawData, binary: boolean) => {
      const bytes = Array.isArray(data) ? data.reduce((n, b) => n + b.length, 0) : data.byteLength;
      if (bytes + pendingBytes + upstream.bufferedAmount > MAX_BUFFER) {
        closeClient(1013, "Notification buffer full");
        upstream.terminate();
      } else if (upstream.readyState === WebSocket.OPEN) {
        upstream.send(data, { binary });
      } else if (upstream.readyState === WebSocket.CONNECTING) {
        pending.push({ data, binary });
        pendingBytes += bytes;
      }
    });
    upstream.on("open", () => {
      for (const { data, binary } of pending) upstream.send(data, { binary });
      pending = [];
      pendingBytes = 0;
    });
    upstream.on("message", (data: RawData, binary: boolean) => {
      if (client.bufferedAmount > MAX_BUFFER) {
        closeClient(1013, "Notification buffer full");
        upstream.terminate();
      } else if (client.readyState === WebSocket.OPEN) client.send(data, { binary });
    });
    upstream.on("error", () => closeClient(1011, "Notification service unavailable"));
    upstream.on("close", (code, reason) => {
      clearTimeout(expiry);
      closeClient(code === 1005 || code === 1006 ? 1012 : code, reason.toString());
    });
    client.on("error", () => upstream.terminate());
    client.on("close", () => {
      clearTimeout(expiry);
      pending = [];
      upstream.terminate();
    });
  });
}
