/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

/**
 * TCSI updates: make "The page is out of date" non-intrusive in the workspace.
 *
 * The web client (bus module) raises the outdated-page warning in two cases:
 *
 *  1. Reconnect false alarm — `OutdatedPageWatcherService` shows the loud
 *     sticky banner ("The page is out of date" / "Save your work and refresh
 *     to get the latest updates and avoid potential issues.") whenever the bus
 *     reconnects and `/bus/has_missed_notifications` answers true. That check
 *     answers true for ANY `last_notification_id` (verified against the live
 *     engine), so every engine restart surfaces the banner even when the page
 *     content is perfectly current. This service suppresses that banner.
 *
 *  2. Genuine staleness — `assetsWatchdog` shows "The page appears to be out
 *     of date." only when a `bundle_changed` event reports a server version
 *     different from the loaded session, i.e. the tab really runs an old
 *     build. Instead of asking the user to save and refresh, the page is
 *     refreshed silently whenever no work is at risk; when a form holds
 *     unsaved changes (or a dialog/blocking overlay is open) the native
 *     prompt is preserved so nothing typed can be lost.
 *
 * A short cooldown prevents reload loops when both events arrive together.
 */

const RELOAD_COOLDOWN_MS = 5 * 60 * 1000;
const STALE_TITLE = "Refresh";
const STALE_MESSAGE = "The page appears to be out of date.";
const RECONNECT_TITLE = "The page is out of date";
const RECONNECT_MESSAGE =
    "Save your work and refresh to get the latest updates and avoid potential issues.";

let lastAutoReloadAt = 0;

function hasUnsavedWork() {
    // The form renderer marks itself dirty while any field holds edits.
    if (document.querySelector(".o_form_renderer.o_form_dirty")) {
        return true;
    }
    // Open dialogs (wizards) may hold uncommitted input; blocking overlays
    // mean an action is still running and must not be interrupted.
    if (document.querySelector(".modal.show") || document.querySelector(".o_blockUI")) {
        return true;
    }
    // Someone actively typing somewhere sensible (search bar, inline edit, ...).
    const active = document.activeElement;
    if (active && active.matches("input, textarea, [contenteditable='true']")) {
        const value = active.value ?? active.textContent ?? "";
        if (String(value).trim()) {
            return true;
        }
    }
    return false;
}

function isReconnectNotice(message, options) {
    return options.title === RECONNECT_TITLE || message === RECONNECT_MESSAGE;
}

function isStaleNotice(message, options) {
    return options.title === STALE_TITLE || message === STALE_MESSAGE;
}

export const tcsiUpdatesService = {
    dependencies: ["notification"],
    start(env, { notification }) {
        const originalAdd = notification.add.bind(notification);

        const autoRefresh = () => {
            lastAutoReloadAt = Date.now();
            browser.setTimeout(() => browser.location.reload(), 700);
        };

        notification.add = (message, options = {}) => {
            if (isReconnectNotice(message, options)) {
                return () => {};
            }
            if (isStaleNotice(message, options)) {
                if (hasUnsavedWork()) {
                    // Preserve the native prompt: reloading now could lose edits.
                    return originalAdd(message, options);
                }
                if (Date.now() - lastAutoReloadAt >= RELOAD_COOLDOWN_MS) {
                    autoRefresh();
                }
                return () => {};
            }
            return originalAdd(message, options);
        };
        return {};
    },
};

registry.category("services").add("tcsi_updates", tcsiUpdatesService);
