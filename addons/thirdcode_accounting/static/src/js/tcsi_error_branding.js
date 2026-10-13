/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import {
    ErrorDialog, ClientErrorDialog, NetworkErrorDialog, RPCErrorDialog,
    WarningDialog, RedirectWarningDialog,
} from "@web/core/errors/error_dialogs";

// Preserve exception identifiers, file paths and the original error payload.
// Brand the presentation and copied report, including their generic headings.
ErrorDialog.title = _t("TCSI Error");
ClientErrorDialog.title = _t("TCSI Client Error");
NetworkErrorDialog.title = _t("TCSI Network Error");

const GENERIC_FALLBACKS = new Set([
    "Odoo Server Error",
    "Odoo Client Error",
    "Odoo Network Error",
    "Odoo Warning",
    "Odoo Error",
]);

const FRIENDLY_FALLBACK = _t(
    "The server could not complete this operation. Please try again, or contact your administrator if it persists."
);

function brand(text) {
    return text == null ? text : String(text).replace(/\bOdoo\b/gi, "TCSI");
}

function brandDiagnosticText(text) {
    // Never rewrite module names such as odoo.exceptions or diagnostic paths.
    return text == null ? text : String(text).replace(
        /\bOdoo (?:Server Error|Client Error|Network Error|Warning|Error|Session Expired)\b/gi,
        brand,
    );
}

function copyBrandedError(dialog) {
    browser.navigator.clipboard.writeText(
        `${dialog.props.name}\n\n${dialog.tcsiMessage}\n\n${dialog.contextDetails}\n\n${dialog.tcsiTraceback}`
    );
    dialog.showTooltip();
}

function liftRealMessage(dialog) {
    // JSON-RPC faults often carry `arguments: null` while `data.message`
    // holds the real user-facing text (for example the posted-entry delete
    // guard: "Posted accounting entries cannot be deleted..."). The stock
    // fallback then shows the generic "Odoo Server Error" line and hides the
    // actual reason. Surface the real message instead, and make sure the
    // generic placeholders never reach the user.
    const data = dialog.props.data;
    let text = dialog.message == null ? "" : String(dialog.message).trim();
    if ((!text || GENERIC_FALLBACKS.has(text)) && data && data.message && String(data.message).trim()) {
        text = String(data.message);
    }
    if (!text || GENERIC_FALLBACKS.has(text.trim())) {
        text = FRIENDLY_FALLBACK;
    }
    dialog.message = brand(text);
}

patch(ErrorDialog.prototype, {
    get tcsiTitle() {
        return brand(this.title || this.constructor.title);
    },
    get tcsiMessage() {
        return brandDiagnosticText(this.props.message);
    },
    get tcsiTraceback() {
        return brandDiagnosticText(this.traceback || this.props.traceback);
    },
    onClickClipboard() {
        copyBrandedError(this);
    },
});

patch(RPCErrorDialog.prototype, {
    inferTitle() {
        super.inferTitle();
        if (this.title) {
            this.title = brand(this.title);
        }
    },
    onClickClipboard() {
        copyBrandedError(this);
    },
});

patch(WarningDialog.prototype, {
    inferTitle() {
        return brand(super.inferTitle().toString());
    },
    setup() {
        super.setup();
        liftRealMessage(this);
    },
});

patch(RedirectWarningDialog.prototype, {
    setup() {
        super.setup();
        this.title = brand(this.title);
        this.message = brand(this.message);
    },
});
