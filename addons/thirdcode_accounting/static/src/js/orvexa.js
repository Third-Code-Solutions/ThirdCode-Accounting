/** @odoo-module **/
import { Component, onMounted, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { ChatWindow } from "@mail/core/common/chat_window";
import { Discuss } from "@mail/core/public_web/discuss";
import { Thread } from "@mail/core/common/thread";
import { Thread as ThreadRecord } from "@mail/core/common/thread_model";
import { Composer } from "@mail/core/common/composer";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

export class OrvexaChat extends Component {
    static template = "thirdcode_accounting.OrvexaChat";
    static props = [];
    setup() {
        this.company = useService("company");
        this.bus = useService("bus_service");
        this.input = useRef("input");
        this.transcript = useRef("transcript");
        this.state = useState(useService("tcsi_orvexa_sessions").get(this.company.currentCompany));
        useEffect(() => {
            const transcript = this.transcript.el;
            if (transcript) transcript.scrollTop = transcript.scrollHeight;
            if (!this.state.busy) this.input.el?.focus();
        }, () => [this.state.messages.length, this.state.busy]);
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
        const message = this.state.message.trim();
        this.append("user", { message });
        this.state.message = "";
        await this.perform({ message });
    }
    async confirm(cancel = false) {
        if (this.state.busy || !this.state.result?.proposal_id) return;
        this.append("user", { message: cancel ? "Cancel this proposal." : "Confirm: create this draft only." });
        await this.perform({ proposal_id: this.state.result.proposal_id, cancel });
    }
    append(role, result) {
        this.state.sequence = (this.state.sequence || 0) + 1;
        this.state.messages.push({ id: this.state.sequence, role, result });
    }
    onKeydown(event) {
        if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            this.submit();
        }
    }
    async perform(params) {
        this.state.busy = true;
        try {
            const result = await this.call(params);
            this.state.result = result;
            this.append("assistant", result);
            await this.refreshMemory();
        } catch {
            // Keep the proposal for safe retry if the server committed but the response was lost.
            this.append("assistant", { status: "error", message: params.proposal_id
                    ? "Connection interrupted. Completion is unknown. Retry the same confirmation above; it will not create a second draft."
                    : "Connection interrupted. I could not retrieve a response. Please send your request again." });
            if (!params.proposal_id) this.state.message = params.message;
        } finally { this.state.busy = false; }
    }
    example(value) { this.state.message = value; this.input.el.focus(); }
}

class OrvexaLauncher extends Component {
    static template = "thirdcode_accounting.OrvexaLauncher";
    static props = ["*"];
    setup() {
        this.store = useService("mail.store");
        this.notification = useService("notification");
    }
    async open() {
        try {
            const partnerId = this.store.odoobot?.id;
            if (!partnerId) throw new Error("Assistant not loaded");
            const thread = await this.store.getChat({ partnerId });
            thread?.open();
        } catch {
            this.notification.add("ORVEXA chat could not open. Please retry after the workspace reconnects.", { type: "warning" });
        }
    }
}
registry.category("systray").add("thirdcode.orvexa", { Component: OrvexaLauncher }, { sequence: 5 });

registry.category("services").add("tcsi_orvexa_sessions", {
    start() {
        const sessions = new Map();
        return { get(company) {
            if (!sessions.has(company.id)) sessions.set(company.id, {
                message: "", busy: false, result: null, messages: [], memory: null,
                feedError: "", company: company.name, sequence: 0,
            });
            return sessions.get(company.id);
        } };
    },
});

export function isOrvexaThread(thread, assistant) {
    return Boolean(assistant?.id && thread?.model === "discuss.channel" &&
        thread.channel_type === "chat" && thread.correspondent?.persona?.id === assistant.id);
}

patch(ThreadRecord.prototype, {
    get displayName() {
        return isOrvexaThread(this, this.store.odoobot) ? "ORVEXA" : super.displayName;
    },
    get avatarUrl() {
        return isOrvexaThread(this, this.store.odoobot)
            ? "/thirdcode_accounting/static/src/img/orvexa-avatar.png"
            : super.avatarUrl;
    },
});

// Only the assistant's private conversation uses the task engine. Ordinary
// chats, channels and record chatter keep their original components untouched.
class OrvexaThread extends Component {
    static template = "thirdcode_accounting.OrvexaThread";
    static components = { Thread, OrvexaChat };
    static props = ["*"];
    setup() {
        this.store = useState(useService("mail.store"));
        this.company = useService("company");
    }
    get isAssistant() { return isOrvexaThread(this.props.thread, this.store.odoobot); }
}
class OrvexaComposer extends Component {
    static template = "thirdcode_accounting.OrvexaComposer";
    static components = { Composer };
    static props = ["*"];
    setup() { this.store = useState(useService("mail.store")); }
    get isAssistant() { return isOrvexaThread(this.props.composer?.thread, this.store.odoobot); }
}
patch(ChatWindow, { components: { ...ChatWindow.components, Thread: OrvexaThread, Composer: OrvexaComposer } });
patch(Discuss, { components: { ...Discuss.components, Thread: OrvexaThread, Composer: OrvexaComposer } });
