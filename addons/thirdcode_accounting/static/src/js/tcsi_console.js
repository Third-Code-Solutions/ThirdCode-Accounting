/** @odoo-module **/
import { Component, onWillStart, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

const MODEL = "thirdcode.platform.console";
const EMPTY_PAGE = () => ({ rows: [], total: 0, page: 0, page_size: 25 });

function generateInitialPassword() {
    // 64 symbols divide the byte range evenly; no modulo bias or weak fallback.
    const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    const bytes = new Uint8Array(24);
    let password;
    do {
        crypto.getRandomValues(bytes);
        password = Array.from(bytes, byte => alphabet[byte & 63]).join("");
    } while (!/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/[0-9]/.test(password) || !/[-_]/.test(password));
    return password;
}

class CreateOrganizationDialog extends Component {
    static template = "thirdcode_accounting.CreateOrganizationDialog";
    static components = { Dialog };
    static props = ["controller", "close"];
    setup() {
        this.state = useState(this.props.controller.state);
        this.password = useState({ visible: false, error: "" });
    }
    generatePassword() {
        if (this.state.busy) return;
        try {
            this.state.org.admin_password = generateInitialPassword();
            this.password.visible = true;
            this.password.error = "";
        } catch {
            this.password.error = "Secure password generation is unavailable. Enter a password manually or retry in a secure browser.";
        }
    }
    togglePassword() { this.password.visible = !this.password.visible; }
    closeCreate() { this.props.controller.closeCreate(); }
    createOrganization() { return this.props.controller.createOrganization(); }
}

class PlatformConsole extends Component {
    static template = "thirdcode_accounting.PlatformConsole";
    static props = ["*"];

    setup() {
        this.navigation = useService("tcsi_console_navigation");
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        const params = this.props.action?.params || {};
        this.state = useState({
            tab: params.tab || this.navigation.takeInitialTab(), companyId: params.company_id || false,
            data: null, denied: false, analytics: null, monitoring: null, orgs: EMPTY_PAGE(), people: EMPTY_PAGE(), audit: EMPTY_PAGE(),
            publications: [], publicationPage: 0, publicationTotal: 0, loading: false, busy: false, error: "", formError: "", query: "", status: "", days: 30,
            auditSource: "platform", createOpen: false, options: { countries: [], currencies: [] },
            org: this.emptyOrg(), draft: this.emptyDraft(), editorId: false, revision: false,
        });
        onWillStart(() => this.load());
        onMounted(() => {
            this.navigation.attach(this);
            this.timer = setInterval(() => {
                if (!this.state.denied && !this.state.busy && !this.state.createOpen && this.state.tab !== "website") this.load(false);
            }, 60000);
        });
        onWillUnmount(() => {
            clearInterval(this.timer);
            this.navigation.detach(this);
        });
    }

    emptyOrg() { return { request_id: "", name: "", country: "PH", currency: "PHP", admin_name: "", admin_login: "", admin_password: "" }; }
    emptyDraft() { return { kind: "seo", title: "", description: "", version: "", category: "improvement" }; }
    get tabs() { return [["overview", "Overview", "fa-line-chart"], ["organizations", "Organizations", "fa-building-o"], ["people", "People", "fa-users"], ["sentry", "Sentry", "fa-heartbeat"], ["audit", "Audit trail", "fa-history"], ["website", "Website & updates", "fa-globe"]]; }
    get busy() { return this.state.loading || this.state.busy; }
    get currentTitle() { return this.tabs.find(t => t[0] === this.state.tab)?.[1] || "Overview"; }
    get selectedPublication() { return this.state.publications.find(p => p.id === this.state.editorId); }
    get publishedPreview() {
        try { return JSON.parse(this.selectedPublication?.published_json || "null"); } catch { return null; }
    }
    message(error) {
        const data = error?.data;
        if (data?.name === "odoo.exceptions.AccessError") return "This console is reserved for the TCSI platform owner.";
        return data?.name === "odoo.exceptions.UserError" ? String(data.message).slice(0,240)
            : "Request could not be completed. Check your owner session and try again.";
    }
    clearData() {
        this.state.data = null;
        this.state.analytics = null;
        this.state.monitoring = null;
        this.state.orgs = EMPTY_PAGE(); this.state.people = EMPTY_PAGE(); this.state.audit = EMPTY_PAGE();
        this.state.publications = [];
    }
    handleError(error) {
        this.state.error = this.message(error);
        if (error?.data?.name === "odoo.exceptions.AccessError") {
            this.state.denied = true;
            this.clearData();
            this.removeCreateDialog?.();
            this.state.createOpen = false;
            this.state.org = this.emptyOrg(); this.state.draft = this.emptyDraft();
            this.state.options = { countries: [], currencies: [] };
            this.state.editorId = false; this.state.revision = false;
        }
        return this.state.error;
    }
    async load(showLoading = true) {
        if (this.state.loading) return;
        this.state.loading = true;
        this.navigation.notify();
        if (showLoading) this.state.error = "";
        try {
            this.state.data = await this.orm.call(MODEL, "get_console_data", []);
            this.state.denied = false;
            await this.loadTab();
            this.state.error = "";
        } catch (error) {
            this.handleError(error);
            // Never leave privileged data displayed after authorization expires.
            this.clearData();
        } finally { this.state.loading = false; this.navigation.notify(); }
    }
    async loadTab() {
        const s = this.state;
        if (s.tab === "overview") s.analytics = await this.orm.call(MODEL, "get_analytics", [Number(s.days)]);
        if (s.tab === "organizations") s.orgs = await this.orm.call(MODEL, "get_organizations", [s.query, s.status, s.orgs.page]);
        if (s.tab === "people") s.people = await this.orm.call(MODEL, "get_people", [s.companyId ? Number(s.companyId) : false, s.query, s.people.page]);
        if (s.tab === "sentry") s.monitoring = await this.orm.call(MODEL, "get_monitoring", []);
        if (s.tab === "audit") s.audit = await this.orm.call(MODEL, "get_audit", [s.query, s.companyId ? Number(s.companyId) : false, s.audit.page, s.auditSource]);
        if (s.tab === "website") {
            const publications = await this.orm.call(MODEL, "get_publications", [s.publicationPage]);
            s.publications = publications.rows; s.publicationTotal = publications.total;
        }
    }
    async selectTab(tab) {
        if (this.busy) return;
        this.state.tab = tab; this.state.query = ""; this.state.error = "";
        await this.load();
    }
    async filter() { this.state.orgs.page = 0; this.state.people.page = 0; this.state.audit.page = 0; await this.load(); }
    async page(kind, delta) { this.state[kind].page += delta; await this.load(); }
    async run(method, args, success) {
        if (this.busy) return false;
        this.state.busy = true; this.navigation.notify(); this.state.error = "";
        try {
            await this.orm.call(MODEL, method, args);
            this.notification.add(success, { type: "success" });
            await this.load();
            return true;
        } catch (error) { this.handleError(error); return false; }
        finally { this.state.busy = false; this.navigation.notify(); }
    }
    confirm(title, body, method, args, success) {
        this.dialog.add(ConfirmationDialog, { title, body, confirmLabel: "Confirm", confirm: () => this.run(method,args,success) });
    }
    lifecycle(org, operation) {
        const actions = {
            suspend: ["Suspend organization", `Disable customer employee access for ${org.name}? Accounting records and owner access are retained.`, "suspend_company", [org.id]],
            resume: ["Resume organization", `Restore the employees disabled by suspension for ${org.name}?`, "resume_company", [org.id]],
            convert: ["Activate organization", `Activate ${org.name} and remove trial watermarks? This does not approve its accounting configuration.`, "convert_to_active", [org.id]],
            trial: ["Start trial", `Start a 30-day trial for ${org.name}?`, "mark_trial", [org.id,30]],
            extend: ["Extend trial", `Add 30 days to ${org.name}'s trial?`, "extend_trial", [org.id,30]],
            baseline: ["Prepare baseline", `Initialize missing accounts, journals and the current accounting period for ${org.name}? Its country and currency will be preserved.`, "provision_baseline", [org.id]],
        };
        const item = actions[operation];
        this.confirm(...item, "Organization updated.");
    }
    async showPeople(org) { this.state.companyId = org.id; this.state.people.page = 0; await this.selectTab("people"); }
    async newOrganization() {
        try {
            this.state.options = await this.orm.call(MODEL,"get_options",[]);
            this.state.org = { ...this.emptyOrg(), request_id: crypto.randomUUID() };
            this.state.formError = ""; this.state.createOpen = true;
            this.removeCreateDialog = this.dialog.add(CreateOrganizationDialog, { controller: this }, {
                onClose: () => { this.state.createOpen = false; this.state.org = this.emptyOrg(); },
            });
        } catch (error) { this.handleError(error); }
    }
    closeCreate() { if (!this.state.busy) this.removeCreateDialog?.(); }
    async createOrganization() {
        if (this.state.busy) return;
        this.state.busy = true; this.navigation.notify(); this.state.formError = "";
        try {
            const result = await this.orm.call(MODEL,"create_organization",[{ ...this.state.org }]);
            this.removeCreateDialog?.();
            this.state.tab = "organizations"; this.state.orgs.page = 0;
            this.notification.add(`${result.name} created. Give its administrator their initial credentials privately.`, { type: "success", sticky: true });
            await this.load();
        } catch(error) { this.state.formError = this.handleError(error); }
        finally { this.state.busy = false; this.navigation.notify(); }
    }
    createPerson() {
        this.action.doAction("thirdcode_accounting.action_thirdcode_employee_wizard", {
            additionalContext: { default_company_id: Number(this.state.companyId) }, onClose: () => this.load(),
        });
    }
    personAction(person, action, role = false) {
        this.confirm("Update employee access", `${action === "role" ? "Change role to " + role : action} for ${person.name} in ${person.company}?`, "manage_person", [person.id,action,role], "Employee access updated.");
    }
    incidentState(incident, state) { this.run("set_incident_state",[incident.id,state],"Incident updated."); }
    editPublication(publication) {
        if (this.busy) return;
        this.state.editorId = publication.id; this.state.revision = publication.revision;
        this.state.draft = Object.fromEntries(Object.keys(this.emptyDraft()).map(key => [key, publication[key] || ""]));
    }
    newRelease() { if (this.busy) return; this.state.editorId = false; this.state.revision = false; this.state.draft = { ...this.emptyDraft(), kind: "release" }; }
    async publicationPage(delta) {
        if (this.busy) return;
        this.state.publicationPage += delta;
        this.state.editorId = false; this.state.revision = false; this.state.draft = this.emptyDraft();
        await this.load();
    }
    async saveDraft() {
        if (this.busy) return;
        this.state.busy = true; this.navigation.notify();
        try {
            const result = await this.orm.call(MODEL,"save_publication",[{ ...this.state.draft },this.state.editorId,this.state.revision]);
            if (!this.state.editorId) this.state.publicationPage = 0;
            this.state.editorId = result.id; this.state.revision = result.revision;
            await this.loadTab(); this.notification.add("Draft saved. Public pages are unchanged.",{type:"success"});
        } catch(error) { this.handleError(error); }
        finally { this.state.busy = false; this.navigation.notify(); }
    }
    publish(action) {
        const p = this.selectedPublication;
        const expectedRevision = this.state.revision;
        this.dialog.add(ConfirmationDialog, {
            title: "Change public website",
            body: `${action === "publish" ? "Publish the saved draft" : action === "revert" ? "Restore the previous public revision" : "Remove this content from public pages"}? Unsaved editor changes are not included.`,
            confirmLabel: "Confirm",
            confirm: async () => {
                if (await this.run("publish_content", [p.id, expectedRevision, action], "Website publication updated.")) {
                    // Keep our committed revision: a reload may already include another owner's newer edit.
                    this.state.revision = expectedRevision + 1;
                }
            },
        });
    }
}
registry.category("actions").add("tcsi_platform_console", PlatformConsole);
