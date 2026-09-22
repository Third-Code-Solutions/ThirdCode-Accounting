/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export const APP_DESIGNS = Object.freeze({
    thirdcode_accounting: { name: "Accounting", category: "Finance", icon: "ledger", description: "Manage the ledger, approvals, reconciliation and financial reports." },
    account: { name: "Revenue", category: "Finance", icon: "revenue", description: "Prepare invoices, track customer balances and manage collections." },
    spreadsheet_dashboard: { name: "Insights", category: "Finance", icon: "insights", description: "Review financial activity and the work that needs attention." },
    hr_expense: { name: "Spend", category: "Finance", icon: "spend", description: "Capture expenses, review submissions and manage reimbursements." },
    contacts: { name: "Directory", category: "Workspace", icon: "directory", description: "Maintain customer, supplier and business contact records." },
    hr: { name: "People", category: "People", icon: "people", description: "Manage employee profiles, departments and organizational details." },
    mail: { name: "Messages", category: "Workspace", icon: "messages", description: "Work with your team and ask ORVEXA to help with accounting tasks." },
    "base.menu_administration": { name: "Settings", category: "Administration", icon: "settings", description: "Configure the workspace using your assigned administrative permissions." },
});

export function catalogApps(apps) {
    return apps.filter((app) => app.xmlid !== "base.menu_management").map((app) => {
        const design = APP_DESIGNS[app.xmlid] || APP_DESIGNS[app.xmlid?.split(".")[0]];
        return { ...app, ...(design || { name: app.name, category: "Workspace", icon: "workspace", description: "Open this installed workspace application." }) };
    }).sort((a, b) => a.name.localeCompare(b.name));
}

export function moduleCatalog(modules, menus) {
    const accessible = catalogApps(menus);
    const clean = (text) => (text || "").replace(/\bodoo\b/gi, "TCSI");
    return modules.map((module) => {
        const menu = accessible.find((app) => app.xmlid?.split(".")[0] === module.name);
        const name = clean(module.shortdesc || module.name);
        return {
            id: module.id, name, menuId: menu?.id,
            icon: menu?.icon,
            initials: name.split(/\s+/).map((word) => word[0]).slice(0, 2).join("").toUpperCase(),
            category: clean(module.category_id?.[1]) || "Other",
            description: clean(module.summary) || "Explore this business application and its setup requirements.",
            installed: module.state === "installed",
            status: module.state === "installed" ? "Installed" : module.state === "uninstalled" ? "Not installed" : module.state === "uninstallable" ? "Unavailable" : "Setup pending",
        };
    }).sort((a, b) => a.name.localeCompare(b.name));
}

class TCSIApps extends Component {
    static template = "thirdcode_accounting.TCSIApps";
    static props = ["*"];
    setup() {
        this.menu = useService("menu");
        this.orm = useService("orm");
        this.state = useState({ query: "", category: "All", status: "All", opening: null, error: "", apps: [], selected: null, loading: true });
        onWillStart(() => this.load());
    }
    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const modules = await this.orm.searchRead("ir.module.module", [["application", "=", true]], ["name", "shortdesc", "summary", "state", "category_id"]);
            this.state.apps = moduleCatalog(modules, this.menu.getApps());
        } catch {
            this.state.error = "The app catalog could not load. Check your connection or catalog permissions, then retry.";
        } finally { this.state.loading = false; }
    }
    get apps() { return this.state.apps; }
    get categories() { return ["All", ...new Set(this.apps.map((app) => app.category))]; }
    get filteredApps() {
        const query = this.state.query.trim().toLowerCase();
        return this.apps.filter((app) => (this.state.category === "All" || app.category === this.state.category)
            && (this.state.status === "All" || (this.state.status === "Installed" ? app.installed : !app.installed))
            && `${app.name} ${app.description}`.toLowerCase().includes(query));
    }
    async open(app) {
        if (this.state.opening !== null) return;
        this.state.opening = app.id;
        this.state.error = "";
        try { await this.menu.selectMenu(app.menuId); }
        catch { this.state.error = "This app could not open. Check your connection and try again. Access is controlled by your current role."; }
        finally { this.state.opening = null; }
    }
    clear() { this.state.query = ""; this.state.category = "All"; this.state.status = "All"; }
}
registry.category("actions").add("tcsi_apps", TCSIApps);
