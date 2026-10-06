import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { test } from "node:test";

const errorSource = readFileSync(new URL("../addons/thirdcode_accounting/static/src/js/tcsi_error_branding.js", import.meta.url), "utf8");

function errorDialogHarness() {
    class ErrorDialog {
        constructor(props) { this.props = props; }
        showTooltip() { this.copied = true; }
    }
    class RPCErrorDialog extends ErrorDialog {}
    class ClientErrorDialog extends ErrorDialog {}
    class NetworkErrorDialog extends ErrorDialog {}
    class WarningDialog {}
    class RedirectWarningDialog {}
    let clipboard;
    const context = {
        ErrorDialog, RPCErrorDialog, ClientErrorDialog, NetworkErrorDialog,
        WarningDialog, RedirectWarningDialog,
        _t: (text) => text,
        browser: { navigator: { clipboard: { writeText: (text) => { clipboard = text; } } } },
        patch: (target, extension) => Object.defineProperties(target, Object.getOwnPropertyDescriptors(extension)),
    };
    runInNewContext(errorSource.replace(/^import[\s\S]*?from\s+"[^"]+";\s*/gm, ""), context);
    return { ...context, get clipboard() { return clipboard; } };
}

test("server error display brands the message and diagnostic heading without changing exception identifiers", () => {
    const { RPCErrorDialog } = errorDialogHarness();
    const props = Object.freeze({
        message: "Odoo Server Error",
        traceback: "RPC_ERROR: Odoo Server Error\n  at /odoo/addons/web/file.js:42\nodoo.exceptions.ValidationError: Invalid entry",
    });
    const dialog = new RPCErrorDialog(props);
    dialog.title = "TCSI Server Error";
    assert.equal(dialog.tcsiTitle, "TCSI Server Error");
    assert.equal(dialog.tcsiMessage, "TCSI Server Error");
    assert.equal(dialog.tcsiTraceback, props.traceback.replace("Odoo Server Error", "TCSI Server Error"));
    assert.equal(props.message, "Odoo Server Error", "original diagnostic payload stays intact");
});

test("client and network errors use branded static titles and preserve actionable messages", () => {
    const { ClientErrorDialog, NetworkErrorDialog } = errorDialogHarness();
    for (const [Dialog, title] of [[ClientErrorDialog, "TCSI Client Error"], [NetworkErrorDialog, "TCSI Network Error"]]) {
        const dialog = new Dialog({ message: "Connection lost. Check your connection." });
        assert.equal(dialog.tcsiTitle, title);
        assert.equal(dialog.tcsiMessage, "Connection lost. Check your connection.");
        assert.equal(dialog.tcsiTraceback, undefined);
    }
});

test("raw client diagnostics retain runtime identifiers and paths in display and copied reports", () => {
    const harness = errorDialogHarness();
    for (const message of ["odoo is not defined", "Cannot read properties of undefined (reading 'odoo')", "Failed at /odoo/addons/web/file.js:42"]) {
        const dialog = new harness.ClientErrorDialog({ message });
        assert.equal(dialog.tcsiMessage, message);
        dialog.onClickClipboard();
        assert.ok(harness.clipboard.includes(message));
    }
});

test("copied base and RPC reports use branded headings and retain the complete combined traceback", () => {
    const harness = errorDialogHarness();
    for (const Dialog of [harness.ErrorDialog, harness.RPCErrorDialog]) {
        const dialog = new Dialog({ name: "RPC_ERROR", message: "Odoo Server Error", traceback: "client stack" });
        dialog.contextDetails = "Occurred on model account.move";
        dialog.traceback = "odoo.exceptions.ValidationError: Keep this reason\nRPC_ERROR: Odoo Server Error\nclient stack";
        dialog.onClickClipboard();
        assert.equal(harness.clipboard, "RPC_ERROR\n\nTCSI Server Error\n\nOccurred on model account.move\n\nodoo.exceptions.ValidationError: Keep this reason\nRPC_ERROR: TCSI Server Error\nclient stack");
        assert.equal(dialog.copied, true);
    }
});

test("warning fallback keeps the real validation reason when arguments are missing", () => {
    const harness = errorDialogHarness();
    const dialog = { message: "Odoo Server Error", props: { data: { arguments: null, message: "Posted accounting entries cannot be deleted." } } };
    harness.liftRealMessage(dialog);
    assert.equal(dialog.message, "Posted accounting entries cannot be deleted.");
});

const source = readFileSync(new URL("../addons/thirdcode_accounting/static/src/js/tcsi_brand.js", import.meta.url), "utf8");

test("workspace picker removes only Insights and People and preserves Dashboard's authorized target", () => {
    const context = {
        TCSI_APP_XMLID: "thirdcode_accounting.menu_thirdcode_accounting_root",
        DASHBOARDS_APP_XMLID: "spreadsheet_dashboard.spreadsheet_dashboard_menu_root",
        brandedLabel: name => name,
    };
    runInNewContext(source.slice(source.indexOf("function workspaceAppLabel"), source.indexOf("function makeAppButton")), context);
    const dashboard = { id: 7, name: "TCSI Accounting", xmlid: context.TCSI_APP_XMLID };
    const revenue = { id: 8, name: "Revenue", xmlid: "account.menu_finance" };
    const apps = [dashboard, revenue,
        { id: 9, xmlid: context.DASHBOARDS_APP_XMLID }, { id: 10, xmlid: "hr.menu_hr_root" }];
    const filtered = context.workspaceApps({ getApps: () => apps });
    assert.equal(filtered.length, 2);
    assert.equal(filtered[0], dashboard);
    assert.equal(filtered[1], revenue);
    assert.equal(context.workspaceAppLabel(dashboard), "Dashboard");
    assert.equal(context.workspaceAppLabel(revenue), "Revenue");
    assert.equal(context.workspaceApps({ getApps: () => [] }).length, 0);
    assert.equal(apps.length, 4);
});

test("workspace router brands root, query, fragment and record links", () => {
    const router = { stateToUrl: (value) => value, urlToState: (url) => url.href };
    const start = source.indexOf("const frameworkStateToUrl");
    const end = source.indexOf("const currentPath", start);
    runInNewContext(source.slice(start, end), { router, URL, INTERNAL_WEB_PREFIX: "/odoo", TCSI_WEB_PREFIX: "/workspace" });
    for (const suffix of ["", "?debug=1", "#menu_id=4", "/action-408", "/account.move/42?debug=1#tab"]) {
        assert.equal(router.stateToUrl(`/odoo${suffix}`), `/workspace${suffix}`);
        assert.equal(router.urlToState(new URL(`https://tcsi.example/workspace${suffix}`)), `https://tcsi.example/odoo${suffix}`);
    }
    assert.equal(router.stateToUrl("/odoo-other"), "/odoo-other");
});

test("navbar branding does not trigger another mutation for unchanged text", () => {
    const start = source.indexOf("function updateNavbarContext()");
    const end = source.indexOf("function syncSidebarActiveState(", start);
    let writes = 0;
    let label = "Finance workspace";
    const page = {
        get textContent() { return label; },
        set textContent(value) { label = value; writes++; },
    };
    const document = {
        body: { dataset: { tcsiRoute: "workspace" } },
        querySelector: (selector) => selector === ".tcsi-navbar-context"
            ? { querySelector: () => page } : null,
    };
    const context = { document };
    runInNewContext(source.slice(start, end), context);
    context.updateNavbarContext();
    assert.equal(writes, 0);
    document.body.dataset.tcsiRoute = "tcsi-route-dashboard";
    context.updateNavbarContext();
    context.updateNavbarContext();
    assert.equal(label, "Financial overview");
    assert.equal(writes, 1);
});

test("rendered internal links are branded without changing external links or repeating writes", () => {
    let writes = 0;
    const anchors = ["/odoo?debug=1#tab", "/odoo/account.move/42", "https://outside.example/odoo", "/odoo-other"].map((href) => {
        const url = new URL(href, "https://tcsi.example");
        url.setAttribute = (_, value) => { writes++; url.href = new URL(value, url).href; };
        return url;
    });
    const context = {
        window: { location: { origin: "https://tcsi.example" } },
        TCSI_WEB_PREFIX: "/workspace",
        document: { querySelectorAll: (selector) => selector === "a[href]" ? anchors : [] },
    };
    const start = source.indexOf("function removeOdooPromotions()");
    const end = source.indexOf("function sanitizeBrandingAttributes()", start);
    runInNewContext(source.slice(start, end), context);
    context.removeOdooPromotions();
    context.removeOdooPromotions();
    assert.equal(writes, 2);
    assert.equal(anchors[0].href, "https://tcsi.example/workspace?debug=1#tab");
    assert.equal(anchors[1].pathname, "/workspace/account.move/42");
    assert.equal(anchors[2].href, "https://outside.example/odoo");
    assert.equal(anchors[3].pathname, "/odoo-other");
});

function createRouteHeaderHarness() {
    let textWrites = 0;
    function createElement(tagName) {
        let text = "";
        return {
            tagName,
            className: "",
            dataset: {},
            children: [],
            parentNode: null,
            get textContent() { return text; },
            set textContent(value) { text = value; textWrites++; },
            get firstChild() { return this.children[0] || null; },
            get firstElementChild() { return this.firstChild; },
            matches(selector) {
                return selector.split(",").some((part) => this.className.split(/\s+/).includes(part.trim().slice(1)));
            },
            querySelector(selector) {
                const direct = selector.startsWith(":scope > ");
                const match = direct ? selector.slice(9) : selector;
                for (const child of this.children) {
                    if (child.matches(match)) return child;
                    if (!direct) {
                        const nested = child.querySelector(match);
                        if (nested) return nested;
                    }
                }
                return null;
            },
            append(child) { child.parentNode = this; this.children.push(child); },
            insertBefore(child, next) {
                child.parentNode = this;
                const index = next ? this.children.indexOf(next) : this.children.length;
                assert.notEqual(index, -1, "insertion target must belong to action");
                this.children.splice(index, 0, child);
            },
            remove() {
                if (!this.parentNode) return;
                const siblings = this.parentNode.children;
                siblings.splice(siblings.indexOf(this), 1);
                this.parentNode = null;
            },
        };
    }
    const manager = createElement("main");
    const action = createElement("section");
    action.className = "o_action";
    const panel = createElement("div");
    panel.className = "o_control_panel";
    action.append(panel);
    manager.append(action);
    const context = { document: { createElement } };
    const start = source.indexOf("function ensureNativeRouteHeader(");
    const end = source.indexOf("function brandNativeChrome(", start);
    runInNewContext(source.slice(start, end), context);
    return {
        manager, action, panel,
        update: (details) => context.ensureNativeRouteHeader(manager, details),
        get header() { return action.querySelector(":scope > .tcsi-native-route-header"); },
        get textWrites() { return textWrites; },
    };
}

const invoiceRoute = {
    key: "invoices", view: "list", eyebrow: "REVENUE OPERATIONS",
    title: "Invoices", description: "Track invoices and payment status.",
};

test("reused native controller updates route copy without duplicating its header", () => {
    const ui = createRouteHeaderHarness();
    ui.update(invoiceRoute);
    const header = ui.header;
    assert.ok(header);
    assert.equal(ui.action.children[0], header);
    assert.equal(ui.action.children[1], ui.panel);

    ui.update({
        key: "vendor bills", view: "list", eyebrow: "SPEND OPERATIONS",
        title: "Vendor bills", description: "Review supplier costs and due dates.",
    });
    assert.equal(ui.header, header, "navigation should reuse the existing header");
    assert.equal(ui.action.children.length, 2);
    assert.equal(header.dataset.tcsiRouteKey, "vendor bills");
    assert.equal(header.querySelector(".tcsi-native-route-eyebrow").textContent, "SPEND OPERATIONS");
    assert.equal(header.querySelector(".tcsi-native-route-title").textContent, "Vendor bills");
    assert.equal(header.querySelector(".tcsi-native-route-description").textContent, "Review supplier costs and due dates.");
});

test("unchanged route copy avoids repeated text mutations and missing copy hides stale content", () => {
    const ui = createRouteHeaderHarness();
    ui.update(invoiceRoute);
    const initialWrites = ui.textWrites;
    assert.equal(initialWrites, 3);
    ui.update({ ...invoiceRoute });
    ui.update({ ...invoiceRoute });
    assert.equal(ui.textWrites, initialWrites);

    ui.update({ key: "records", view: "list", title: "Records" });
    const eyebrow = ui.header.querySelector(".tcsi-native-route-eyebrow");
    const description = ui.header.querySelector(".tcsi-native-route-description");
    assert.equal(eyebrow.textContent, "");
    assert.equal(description.textContent, "");
    assert.equal(eyebrow.hidden, true);
    assert.equal(description.hidden, true);
    ui.update(invoiceRoute);
    assert.equal(eyebrow.hidden, false);
    assert.equal(description.hidden, false);
});

for (const [name, view, className] of [
    ["record forms", "form", ""],
    ["custom dashboards", "list", "tcsi-dashboard"],
    ["application catalogs", "kanban", "tcsi-app-catalog"],
    ["Discuss", "list", "o-mail-Discuss"],
    ["settings", "list", "o_base_settings_view"],
]) {
    test(`navigation to ${name} removes a reused native route header`, () => {
        const ui = createRouteHeaderHarness();
        ui.update(invoiceRoute);
        const previousHeader = ui.header;
        ui.action.className = `o_action ${className}`;
        ui.update({ ...invoiceRoute, view });
        assert.equal(ui.header, null);
        assert.equal(previousHeader.parentNode, null);
        assert.deepEqual(ui.action.children, [ui.panel]);
        ui.update({ ...invoiceRoute, view });
        assert.equal(ui.header, null, "excluded views must not recreate the header");
    });
}

test("native form titles prefer the actual record heading over the field label", () => {
    const context = {
        window: { location: { pathname: "/workspace/action-411/res.company/1" } },
        brandedLabel: (label) => label,
    };
    const start = source.indexOf("const ROUTE_PATH_TITLES");
    const end = source.indexOf("function getNativeView(", start);
    runInNewContext(source.slice(start, end), context);
    let heading = "  Third Code\nSolutions Inc.  ";
    let breadcrumb = "FY 2026";
    const manager = {
        querySelector(selector) {
            if (selector === ".o_form_view") return {};
            if (selector === ".o_form_view .oe_title .o_form_label") return { textContent: "Company Name" };
            if (selector.startsWith(".o_form_view .o_form_sheet h1")) return heading ? { textContent: heading } : null;
            if (selector.startsWith(".o_control_panel")) return { textContent: breadcrumb };
            return null;
        },
    };
    assert.equal(context.getNativeRouteTitle(manager), "Third Code Solutions Inc.");
    heading = "";
    assert.equal(context.getNativeRouteTitle(manager), "FY 2026", "breadcrumb precedes a generic field label");
    breadcrumb = "";
    assert.equal(context.getNativeRouteTitle(manager), "Company Name", "field label remains a final fallback");
});

test("owner console exposes a working Settings link only when the native Settings app is allowed", async () => {
    const root = { id: 10, xmlid: "thirdcode_accounting.menu_thirdcode_accounting_root", name: "TCSI Accounting" };
    const settings = { id: 20, xmlid: "base.menu_administration", name: "Settings" };
    function element() {
        return {
            dataset: {}, children: [], events: {},
            classList: { add() {}, remove() {}, toggle() {} },
            append(...children) { this.children.push(...children); },
            replaceChildren(...children) { this.children = children; },
            addEventListener(name, handler) { this.events[name] = handler; },
            setAttribute() {},
        };
    }
    for (const allowed of [true, false]) {
        const selected = [];
        const nav = element();
        const label = element();
        const sidebar = { querySelector: selector => ({ ".tcsi-sidebar-nav": nav, ".tcsi-sidebar-app-name": label })[selector] || null };
        const menu = {
            getApps: () => allowed ? [root, settings] : [root],
            getCurrentApp: () => root,
            getMenuAsTree: () => ({ childrenTree: [] }),
            selectMenu: async item => selected.push(item),
        };
        const context = {
            document: { createElement: element, body: element() },
            window: { location: { pathname: "/workspace/console" } },
            TCSI_APP_XMLID: root.xmlid, DASHBOARDS_APP_XMLID: "spreadsheet_dashboard.spreadsheet_dashboard_menu_root",
            TCSI_WEB_PREFIX: "/workspace", INTERNAL_WEB_PREFIX: "/odoo",
            makeIcon: element, brandedLabel: text => text, syncSidebarActiveState() {},
        };
        runInNewContext(source.slice(source.indexOf("function makeSidebarLink"), source.indexOf("function filterSidebarNavigation")), context);
        context.renderSidebar(sidebar, menu, { isOwner: true, active: true, sections: [] });
        const link = nav.children.find(child => child.dataset.tcsiMenuXmlid === settings.xmlid);
        assert.equal(Boolean(link), allowed);
        if (allowed) {
            await link.events.click();
            assert.deepEqual(selected, [settings], "use native menu selection, retaining access and routing");
        }
    }
});

test("Settings sections replace the inner navigation in the main sidebar and restore on exit", () => {
    function element() {
        return { dataset: {}, children: [], events: {}, attributes: {},
            classList: { toggle() {}, remove() {} },
            append(...items) { this.children.push(...items); },
            replaceChildren(...items) { this.children = items; },
            addEventListener(name, handler) { this.events[name] = handler; },
            setAttribute(name, value) { this.attributes[name] = value; },
        };
    }
    const root = { id: 1, xmlid: "thirdcode_accounting.menu_thirdcode_accounting_root", name: "Dashboard" };
    const app = { id: 2, xmlid: "base.menu_administration", name: "Settings" };
    const general = { id: 3, xmlid: "base_setup.menu_config", name: "General Settings" };
    const nav = element(), label = element(), body = element();
    const toggles = [];
    body.classList.toggle = (...args) => toggles.push(args);
    const sidebar = { querySelector: selector => ({ ".tcsi-sidebar-nav": nav, ".tcsi-sidebar-app-name": label })[selector] };
    const menu = { getCurrentApp: () => app, getApps: () => [root, app], getMenuAsTree: () => ({ childrenTree: [general] }) };
    const jumps = [], modules = [];
    const settings = { active: true, activeSection: "emails", selectedModule: "general_settings",
        modules: [{ key: "general_settings", string: "TCSI Settings" }], sections: [{ id: "emails", label: "Emails" }],
        openSection: id => jumps.push(id), selectModule: id => modules.push(id),
    };
    const context = {
        document: { createElement: element, body }, window: { location: { pathname: "/workspace/settings" } },
        TCSI_APP_XMLID: root.xmlid, DASHBOARDS_APP_XMLID: "spreadsheet_dashboard.spreadsheet_dashboard_menu_root",
        TCSI_WEB_PREFIX: "/workspace", INTERNAL_WEB_PREFIX: "/odoo",
        makeIcon: element, brandedLabel: text => text, syncSidebarActiveState() {},
    };
    runInNewContext(source.slice(source.indexOf("function makeSidebarLink"), source.indexOf("function filterSidebarNavigation")), context);
    context.renderSidebar(sidebar, menu, { isOwner: true, active: false }, settings);
    const link = nav.children.find(child => child.dataset.tcsiSettingsSection === "emails");
    assert.ok(link); link.events.click();
    assert.deepEqual(jumps, ["emails"]);
    const moduleLink = nav.children.find(child => child.attributes["aria-pressed"] === "true");
    moduleLink.events.click(); assert.deepEqual(modules, ["general_settings"]);
    assert.equal(nav.children.some(child => child.dataset.tcsiMenuXmlid === general.xmlid), false);
    assert.deepEqual(toggles.at(-1), ["tcsi-settings-in-main-sidebar", true]);
    settings.active = false;
    context.renderSidebar(sidebar, menu, { isOwner: true, active: false }, settings);
    assert.equal(nav.children.some(child => child.dataset.tcsiSettingsSection), false);
    assert.equal(nav.children.some(child => child.dataset.tcsiMenuXmlid === general.xmlid), true);
    assert.deepEqual(toggles.at(-1), ["tcsi-settings-in-main-sidebar", false]);
});
