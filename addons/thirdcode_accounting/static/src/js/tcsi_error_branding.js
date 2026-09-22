/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import {
    ErrorDialog, ClientErrorDialog, NetworkErrorDialog, RPCErrorDialog,
    WarningDialog, RedirectWarningDialog,
} from "@web/core/errors/error_dialogs";

// Keep exception identifiers and diagnostic tracebacks intact for support.
ErrorDialog.title = _t("TCSI Error");
ClientErrorDialog.title = _t("TCSI Client Error");
NetworkErrorDialog.title = _t("TCSI Network Error");
patch(RPCErrorDialog.prototype, {
    inferTitle() {
        super.inferTitle();
        if (this.title) {
            this.title = this.title.toString().replace(/\bOdoo\b/g, "TCSI");
        }
    },
});
patch(WarningDialog.prototype, {
    inferTitle() {
        return super.inferTitle().toString().replace(/\bOdoo\b/g, "TCSI");
    },
});
patch(RedirectWarningDialog.prototype, {
    setup() {
        super.setup();
        this.title = this.title.toString().replace(/\bOdoo\b/g, "TCSI");
    },
});
