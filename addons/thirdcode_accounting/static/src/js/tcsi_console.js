/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MODEL = "thirdcode.platform.console";

class PlatformConsole extends Component {
    static template = "thirdcode_accounting.PlatformConsole";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, error: "", busy: "", data: null });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.error = "";
        this.state.loading = this.state.data === null;
        try {
            this.state.data = await this.orm.call(MODEL, "get_console_data", []);
        } catch (error) {
            this.state.error = this._message(error, "The console could not load. Check the connection and retry.");
        } finally {
            this.state.loading = false;
        }
    }

    _message(error, fallback) {
        const raw = error && (error.message || error.data?.message || error);
        const text = typeof raw === "string" ? raw : "";
        return text.split("\n")[0].slice(0, 200) || fallback;
    }

    async run(key, method, args, fallback) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = key;
        this.state.error = "";
        try {
            await this.orm.call(MODEL, method, args);
            await this.load();
        } catch (error) {
            this.state.error = this._message(error, fallback);
        } finally {
            this.state.busy = "";
        }
    }

    extend(org, days) {
        this.run(`extend-${org.id}`, "extend_trial", [org.id, days], "The trial window could not be extended.");
    }

    markTrial(org) {
        this.run(`trial-${org.id}`, "mark_trial", [org.id], "The trial could not be restarted.");
    }

    convert(org) {
        this.run(`convert-${org.id}`, "convert_to_active", [org.id], "The organisation could not be converted.");
    }

    suspend(org) {
        this.run(`suspend-${org.id}`, "suspend_company", [org.id], "The organisation could not be suspended.");
    }

    resume(org) {
        this.run(`resume-${org.id}`, "resume_company", [org.id], "The organisation could not be resumed.");
    }

    baseline(org) {
        this.run(`baseline-${org.id}`, "provision_baseline", [org.id], "The baseline could not be provisioned.");
    }

    async openOrg(org) {
        const action = await this.orm.call(MODEL, "open_organization", [org.id]);
        this.action.doAction(action);
    }

    async openUsers(org) {
        const action = await this.orm.call(MODEL, "open_company_users", [org.id]);
        this.action.doAction(action);
    }

    get busy() {
        return this.state.busy !== "";
    }
}

registry.category("actions").add("tcsi_platform_console", PlatformConsole);
