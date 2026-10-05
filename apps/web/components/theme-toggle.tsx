"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

import { portalThemeCookie, resolvePortalTheme, type PortalTheme } from "../lib/portal-theme";

const themeEvent = "tcsi-portal-theme-change";
function subscribe(callback: () => void) {
  window.addEventListener(themeEvent, callback);
  return () => window.removeEventListener(themeEvent, callback);
}
function snapshot() {
  return resolvePortalTheme(document.documentElement.dataset.portalTheme);
}

export function ThemeToggle({ initialTheme }: { initialTheme: PortalTheme }) {
  // The document remains authoritative when navigating through prefetched pages.
  const theme = useSyncExternalStore(subscribe, snapshot, () => initialTheme);

  function toggleTheme() {
    const next = document.documentElement.dataset.portalTheme === "dark" ? "light" : "dark";
    document.documentElement.dataset.portalTheme = next;
    document.cookie = `${portalThemeCookie}=${next}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
    window.dispatchEvent(new Event(themeEvent));
  }

  return (
    <button className="marketing-theme-toggle" type="button" onClick={toggleTheme}
      aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
      title={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}>
      {theme === "light" ? <Moon size={18} aria-hidden="true" /> : <Sun size={18} aria-hidden="true" />}
    </button>
  );
}
