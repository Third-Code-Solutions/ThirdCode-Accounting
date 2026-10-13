export function safeNextUrl(next: string, origin: string): URL {
  const fallback = new URL("/", origin);
  if (!next.startsWith("/") || next.startsWith("//") || next.includes("\\") || /%5c/i.test(next)) {
    return fallback;
  }
  try {
    const target = new URL(next, origin);
    return target.origin === origin ? target : fallback;
  } catch {
    return fallback;
  }
}
