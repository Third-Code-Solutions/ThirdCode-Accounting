/** @odoo-module **/

const STORAGE_KEY = "tcsi.accounting.theme";
const systemPreference = window.matchMedia("(prefers-color-scheme: dark)");

function savedTheme() {
    try {
        return window.localStorage.getItem(STORAGE_KEY);
    } catch {
        return null;
    }
}

function applyTheme(theme) {
    document.documentElement.dataset.tcsiTheme = theme;
    document.documentElement.setAttribute("data-bs-theme", theme);
    syncThemeButtons();
}

export function syncThemeButtons() {
    const dark = document.documentElement.dataset.tcsiTheme === "dark";
    for (const button of document.querySelectorAll("[data-tcsi-theme-toggle]")) {
        const label = dark ? "Light mode" : "Dark mode";
        button.setAttribute("aria-label", `Switch to ${label.toLowerCase()}`);
        button.setAttribute("aria-pressed", String(dark));
        const text = button.querySelector("[data-tcsi-theme-label]");
        if (text) {
            text.textContent = label;
        }
    }
}

const stored = savedTheme();
applyTheme(stored === "dark" || stored === "light" ? stored : systemPreference.matches ? "dark" : "light");

document.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-tcsi-theme-toggle]") : null;
    if (!button) {
        return;
    }
    const next = document.documentElement.dataset.tcsiTheme === "dark" ? "light" : "dark";
    try {
        window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
        // The current page can still switch theme when browser storage is unavailable.
    }
    applyTheme(next);
});

systemPreference.addEventListener("change", (event) => {
    if (savedTheme() !== "dark" && savedTheme() !== "light") {
        applyTheme(event.matches ? "dark" : "light");
    }
});

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", syncThemeButtons, { once: true });
} else {
    syncThemeButtons();
}
