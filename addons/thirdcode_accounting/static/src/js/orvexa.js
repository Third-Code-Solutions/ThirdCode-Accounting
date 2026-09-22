/** @odoo-module **/
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

export class OrvexaDialog extends Component {
    static template = "thirdcode_accounting.OrvexaDialog";
    static components = { Dialog };
    static props = ["close"];
    setup() {
        this.company = useService("company");
        this.bus = useService("bus_service");
        this.input = useRef("input");
        this.state = useState({ message: "", busy: false, result: null, memory: null, feedError: "", company: this.company.currentCompany.name });
        this.companyId = this.company.currentCompany.id;
        this.closed = false;
        this.refreshing = false;
        this.onActivity = (payload) => {
            if (payload.company_id === this.companyId && !this.debounce) {
                this.debounce = setTimeout(() => { this.debounce = null; this.refreshMemory(); }, 250);
            }
        };
        onMounted(() => {
            this.input.el.focus();
            this.refreshMemory();
            this.bus.subscribe("tcsi.orvexa.activity", this.onActivity);
            this.poll = setInterval(() => this.refreshMemory(), 15000);
        });
        onWillUnmount(() => {
            this.closed = true;
            clearInterval(this.poll);
            clearTimeout(this.debounce);
            this.bus.unsubscribe("tcsi.orvexa.activity", this.onActivity);
        });
    }
    async call(params) {
        return rpc("/thirdcode_accounting/orvexa", { ...params, company_id: this.companyId, csrf_token: odoo.csrf_token });
    }
    async refreshMemory() {
        if (this.refreshing || this.closed || document.hidden) return;
        this.refreshing = true;
        try {
            const result = await this.call({ memory: true });
            if (!this.closed) {
                if (result.status === "error") this.state.feedError = result.message;
                else { this.state.memory = result; this.state.feedError = ""; }
            }
        } catch {
            if (!this.closed) this.state.feedError = "Activity feed disconnected. Last successful snapshot is shown; retrying automatically.";
        } finally { this.refreshing = false; }
    }
    async submit() {
        if (this.state.busy || !this.state.message.trim() || this.state.result?.status === "confirmation_required") return;
        await this.perform({ message: this.state.message });
    }
    async confirm(cancel = false) {
        if (this.state.busy || !this.state.result?.proposal_id) return;
        await this.perform({ proposal_id: this.state.result.proposal_id, cancel });
    }
    async perform(params) {
        this.state.busy = true;
        try {
            const result = await this.call(params);
            if (!this.closed) this.state.result = result;
            await this.refreshMemory();
        } catch {
            // Keep the proposal for safe retry if the server committed but the response was lost.
            if (!this.closed) this.state.feedError = "Request interrupted. Completion is unknown. Retry the same confirmation; ORVEXA will not create it twice.";
        } finally { if (!this.closed) this.state.busy = false; }
    }
    example(value) { this.state.message = value; this.input.el.focus(); }
}

class OrvexaLauncher extends Component {
    static template = "thirdcode_accounting.OrvexaLauncher";
    static props = ["*"];
    setup() { this.dialog = useService("dialog"); }
    open() { this.dialog.add(OrvexaDialog, {}); }
}
registry.category("systray").add("thirdcode.orvexa", { Component: OrvexaLauncher }, { sequence: 5 });

registry.category("services").add("tcsi_orvexa_entry", {
    dependencies: ["dialog"],
    start(env, { dialog }) {
        // Existing branded assistant entry points now open the executor, not the onboarding bot.
        document.addEventListener("click", (event) => {
            if (event.target.closest(".tcsi-assistant-bubble, .tcsi-assistant-sidebar-channel, .tcsi-assistant-notification")) {
                event.preventDefault();
                event.stopImmediatePropagation();
                dialog.add(OrvexaDialog, {});
            }
        }, true);
    },
});
