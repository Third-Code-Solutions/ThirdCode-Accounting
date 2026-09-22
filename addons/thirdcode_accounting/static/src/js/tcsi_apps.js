/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
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

class TCSIApps extends Component {
    static template = "thirdcode_accounting.TCSIApps";
    static props = ["*"];
    setup() {
        this.menu = useService("menu");
        this.state = useState({ query: "", category: "All", opening: null, error: "" });
        // The menu service already contains the server-filtered, accessible menus.
        // Do not query the module marketplace or infer authorization in the client.
        this.apps = catalogApps(this.menu.getApps());
        this.categories = ["All", ...new Set(this.apps.map((app) => app.category))];
    }
    get filteredApps() {
        const query = this.state.query.trim().toLowerCase();
        return this.apps.filter((app) => (this.state.category === "All" || app.category === this.state.category)
            && `${app.name} ${app.description}`.toLowerCase().includes(query));
    }
    async open(app) {
        if (this.state.opening !== null) return;
        this.state.opening = app.id;
        this.state.error = "";
        try { await this.menu.selectMenu(app.id); }
        catch { this.state.error = "This app could not open. Check your connection and try again. Access is controlled by your current role."; }
        finally { this.state.opening = null; }
    }
    clear() { this.state.query = ""; this.state.category = "All"; }
}
registry.category("actions").add("tcsi_apps", TCSIApps);
