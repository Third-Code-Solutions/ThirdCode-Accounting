/** @odoo-module **/
import { registry } from "@web/core/registry";
import { session } from "@web/session";

export const CONSOLE_SECTIONS = [
    ["Platform", [["overview", "Overview", "fa-line-chart"]]],
    ["Organization management", [["organizations", "Organizations", "fa-building-o"], ["people", "People", "fa-users"]]],
    ["Monitoring", [["sentry", "Sentry", "fa-heartbeat"], ["audit", "Audit trail", "fa-history"]]],
    ["Publishing", [["website", "Website & updates", "fa-globe"]]],
];
const TABS = new Set(CONSOLE_SECTIONS.flatMap(([, tabs]) => tabs.map(([tab]) => tab)));
const CONSOLE_MENU = "thirdcode_accounting.menu_thirdcode_platform_console";

export const consoleNavigationService = {
    dependencies: ["menu"],
    start(env, { menu }) {
        let controller = null;
        let opening = false;
        let pendingTab = "overview";
        const notify = (structure = false) => env.bus.trigger("TCSI:CONSOLE-NAVIGATION", { structure });
        return {
            isOwner: session.tcsi_platform_owner === true,
            sections: CONSOLE_SECTIONS,
            get active() { return Boolean(controller); },
            get activeTab() { return controller?.state.denied ? null : controller?.state.tab; },
            get busy() { return opening || Boolean(controller?.busy); },
            takeInitialTab() { const tab = pendingTab; pendingTab = "overview"; return tab; },
            attach(current) { controller = current; notify(true); },
            detach(current) { if (controller === current) { controller = null; notify(true); } },
            notify,
            async open(tab = "overview") {
                if (!this.isOwner || !TABS.has(tab) || this.busy) return;
                if (controller && !controller.state.denied) {
                    await controller.selectTab(tab);
                    return;
                }
                const root = menu.getApps().find(app => app.xmlid === "thirdcode_accounting.menu_thirdcode_accounting_root");
                const target = root && menu.getMenuAsTree(root.id).childrenTree?.find(item => item.xmlid === CONSOLE_MENU);
                if (!target) return;
                opening = true;
                pendingTab = tab;
                notify();
                try { await menu.selectMenu(target); }
                finally { opening = false; pendingTab = "overview"; notify(); }
            },
        };
    },
};
registry.category("services").add("tcsi_console_navigation", consoleNavigationService);
