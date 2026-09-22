/** @odoo-module **/

import { router } from "@web/core/browser/router";
import { registry } from "@web/core/registry";

const TCSI_WEB_PREFIX = "/workspace";
const INTERNAL_WEB_PREFIX = "/odoo";
const USER_MENU_ITEMS_TO_REMOVE = ["documentation", "support", "odoo_account"];
const TCSI_APP_XMLID = "thirdcode_accounting.menu_thirdcode_accounting_root";
const userMenuItems = registry.category("user_menuitems");

const TCSI_LABELS = Object.freeze({
    discuss: "Workspace",
    dashboards: "Insights",
    dashboard: "Insights",
    invoicing: "Revenue",
    employees: "People",
    employee: "People",
    expenses: "Spend",
    expense: "Spend",
    "employee expenses": "People & spend",
    contacts: "Directory",
    contact: "Directory",
    accounting: "Ledger",
    reporting: "Reports",
    configuration: "Controls",
    "oca accounting reports": "Reporting library",
    "reconcile bank statement lines": "Bank reconciliation",
});

function brandedLabel(label = "") {
    const trimmed = label.trim();
    if (!trimmed) {
        return label;
    }
    const directMatch = TCSI_LABELS[trimmed.toLowerCase()];
    if (directMatch) {
        return directMatch;
    }
    return trimmed
        .replace(/\bDashboards?\b/gi, "Insights")
        .replace(/\bDiscuss\b/gi, "Workspace")
        .replace(/\bInvoicing\b/gi, "Revenue")
        .replace(/\bEmployees?\b/gi, "People")
        .replace(/\bExpenses?\b/gi, "Spend")
        .replace(/\bContacts?\b/gi, "Directory");
}

const frameworkStateToUrl = router.stateToUrl;
const frameworkUrlToState = router.urlToState;
router.stateToUrl = (state) =>
    frameworkStateToUrl(state).replace(
        new RegExp(`^${INTERNAL_WEB_PREFIX}(?=[/?#]|$)`),
        TCSI_WEB_PREFIX,
    );
router.urlToState = (urlObject) => {
    const normalizedUrl = new URL(urlObject.href);
    if (
        normalizedUrl.pathname === TCSI_WEB_PREFIX ||
        normalizedUrl.pathname.startsWith(`${TCSI_WEB_PREFIX}/`)
    ) {
        normalizedUrl.pathname = `${INTERNAL_WEB_PREFIX}${normalizedUrl.pathname.slice(TCSI_WEB_PREFIX.length)}`;
    }
    return frameworkUrlToState(normalizedUrl);
};

const currentPath = window.location.pathname;
if (currentPath === INTERNAL_WEB_PREFIX || currentPath.startsWith(`${INTERNAL_WEB_PREFIX}/`)) {
    const brandedPath = `${TCSI_WEB_PREFIX}${currentPath.slice(INTERNAL_WEB_PREFIX.length)}`;
    window.history.replaceState(
        window.history.state,
        "",
        `${brandedPath}${window.location.search}${window.location.hash}`,
    );
} else if (
    currentPath === TCSI_WEB_PREFIX ||
    currentPath.startsWith(`${TCSI_WEB_PREFIX}/`)
) {
    router.replaceState(router.urlToState(new URL(window.location.href)), { sync: true });
}

const ROUTE_CLASSES = [
    "tcsi-route-accounting-dashboard",
    "tcsi-route-dashboard",
    "tcsi-route-discuss",
    "tcsi-route-contacts",
    "tcsi-route-reconciliation",
    "tcsi-view-list",
    "tcsi-view-form",
    "tcsi-view-kanban",
    "tcsi-view-graph",
    "tcsi-view-pivot",
    "tcsi-view-calendar",
    "tcsi-view-hierarchy",
    "tcsi-view-gantt",
    "tcsi-view-activity",
    "tcsi-view-dialog",
    "tcsi-view-other",
];

const NATIVE_ROUTE_COPY = Object.freeze({
    "accounting-dashboard": {
        eyebrow: "TCSI FINANCE WORKSPACE",
        title: "Finance command center",
        description: "Keep invoices, bills, banks, and cash moving from one operational view.",
    },
    invoices: {
        eyebrow: "REVENUE OPERATIONS",
        title: "Invoices",
        description: "Track outgoing billing, due dates, and payment status in one place.",
    },
    "credit notes": {
        eyebrow: "REVENUE OPERATIONS",
        title: "Credit notes",
        description: "Review credits issued against customer invoices before they reach the ledger.",
    },
    "customer payments": {
        eyebrow: "REVENUE OPERATIONS",
        title: "Customer payments",
        description: "Monitor incoming settlements and posting status across your accounts.",
    },
    "vendor bills": {
        eyebrow: "SPEND OPERATIONS",
        title: "Vendor bills",
        description: "Review supplier costs, approvals, and due dates before posting.",
    },
    customers: {
        eyebrow: "RELATIONSHIP OPERATIONS",
        title: "Customers",
        description: "Manage customer relationships, contact details, and account activity.",
    },
    "bank reconciliation": {
        eyebrow: "LEDGER CONTROLS",
        title: "Bank reconciliation",
        description: "Clear imported bank activity against the ledger with confidence.",
    },
    "analytic reporting": {
        eyebrow: "REPORTING",
        title: "Analytic reporting",
        description: "Read operational performance without losing the underlying ledger context.",
    },
    "spend analysis": {
        eyebrow: "PEOPLE & SPEND",
        title: "Spend analysis",
        description: "Review employee spend and approval activity in one focused view.",
    },
    "financial statements": {
        eyebrow: "REPORTING",
        title: "Financial statements",
        description: "Open the statements your team uses to understand financial position and movement.",
    },
});

const ROUTE_PATH_TITLES = Object.freeze({
    "/accounting": "Finance command center",
    "/customer-invoices": "Invoices",
    "/credit-notes": "Credit notes",
    "/customer-payments": "Customer payments",
    "/vendor-bills": "Vendor bills",
    "/vendor-payments": "Vendor payments",
    "/customers": "Customers",
    "/vendors": "Vendors",
    "/employees": "People",
    "/expenses": "My spend",
    "/my-expense-reports": "My reports",
    "/expense-reports": "Spend reports",
    "/org-chart": "Org chart",
    "/bank-reconciliations": "Bank reconciliation",
});

function getNativeBreadcrumbText(actionManager) {
    const breadcrumb = actionManager?.querySelector(
        ".o_control_panel .o_last_breadcrumb_item span, " +
            ".o_control_panel .o_control_panel_breadcrumbs .breadcrumb-item.active span, " +
            ".o_control_panel .o_control_panel_breadcrumbs .breadcrumb-item.active",
    );
    return breadcrumb?.textContent?.replace(/\s+/g, " ").trim() || "";
}

function getNativeRouteTitle(actionManager) {
    const title = getNativeBreadcrumbText(actionManager);
    const isForm = Boolean(actionManager?.querySelector(".o_form_view"));
    const formType = actionManager?.querySelector(".o_form_view .oe_title .o_form_label")?.textContent;
    const formTitle = actionManager?.querySelector(
        ".o_form_view .o_form_sheet h1, .o_form_view .o_form_sheet .o_form_title",
    )?.textContent;
    const rawTitle = ((isForm ? formType || formTitle : title) || "").replace(/\s+/g, " ").trim();
    if (!rawTitle) {
        const pathTitle = Object.entries(ROUTE_PATH_TITLES).find(([path]) =>
            window.location.pathname.endsWith(path) || window.location.pathname.includes(`${path}/`),
        )?.[1];
        return pathTitle || "Finance workspace";
    }
    const normalized = rawTitle.toLowerCase();
    if (normalized === "dashboard") {
        return "Finance command center";
    }
    if (window.location.pathname.includes("/vendor-bills") || normalized === "bills") {
        return "Vendor bills";
    }
    if (normalized.includes("reconcile bank statement")) {
        return "Bank reconciliation";
    }
    if (isForm && normalized.includes("vendor bill")) {
        return "Vendor bill";
    }
    if (isForm && normalized.includes("customer invoice")) {
        return "Customer invoice";
    }
    if (isForm && normalized.includes("customer payment")) {
        return "Customer payment";
    }
    if (isForm && normalized.includes("credit note")) {
        return "Credit note";
    }
    return brandedLabel(rawTitle);
}

function getNativeView(actionManager) {
    if (!actionManager) {
        return "other";
    }
    if (actionManager.querySelector(".o_form_view")) {
        return "form";
    }
    if (actionManager.querySelector(".o_kanban_view")) {
        return "kanban";
    }
    if (actionManager.querySelector(".o_list_view")) {
        return "list";
    }
    if (actionManager.querySelector(".o_graph_view")) {
        return "graph";
    }
    if (actionManager.querySelector(".o_pivot_view")) {
        return "pivot";
    }
    if (actionManager.querySelector(".o_calendar_view")) {
        return "calendar";
    }
    if (actionManager.querySelector(".o_hierarchy_view")) {
        return "hierarchy";
    }
    if (actionManager.querySelector(".o_gantt_view")) {
        return "gantt";
    }
    if (actionManager.querySelector(".o_activity_view")) {
        return "activity";
    }
    if (actionManager.querySelector(".modal-dialog, .o_dialog")) {
        return "dialog";
    }
    return "other";
}

function getNativeRouteDetails(actionManager) {
    if (!actionManager) {
        return null;
    }
    if (actionManager.querySelector(".o_account_dashboard_kanban_view")) {
        return { key: "accounting-dashboard", view: "kanban", ...NATIVE_ROUTE_COPY["accounting-dashboard"] };
    }

    const title = getNativeRouteTitle(actionManager);
    const normalizedTitle = title.toLowerCase();
    const copyKey = Object.keys(NATIVE_ROUTE_COPY).find(
        (key) => normalizedTitle === key || normalizedTitle.includes(key),
    );
    const view = getNativeView(actionManager);
    const copy = NATIVE_ROUTE_COPY[copyKey] || {
        eyebrow: "TCSI FINANCE WORKSPACE",
        title,
        description: "Work with your accounting records in a focused TCSI workspace.",
    };
    return { key: copyKey || view, view, ...copy };
}

function ensureNativeRouteHeader(actionManager, details) {
    if (!details || details.view === "form" || details.view === "dialog") {
        return;
    }
    const action = actionManager.querySelector(".o_action") || actionManager.firstElementChild;
    if (!action || action.classList.contains("tcsi-dashboard") || action.querySelector(":scope > .tcsi-native-route-header")) {
        return;
    }
    const header = document.createElement("header");
    header.className = "tcsi-native-route-header";
    header.dataset.tcsiRouteKey = details.key;

    const eyebrow = document.createElement("span");
    eyebrow.className = "tcsi-native-route-eyebrow";
    eyebrow.textContent = details.eyebrow;
    const title = document.createElement("h1");
    title.className = "tcsi-native-route-title";
    title.textContent = details.title;
    const description = document.createElement("p");
    description.className = "tcsi-native-route-description";
    description.textContent = details.description;
    header.append(eyebrow, title, description);

    const controlPanel = action.querySelector(":scope > .o_control_panel") || action.querySelector(".o_control_panel");
    action.insertBefore(header, controlPanel || action.firstChild);
}

function brandNativeChrome(actionManager, details) {
    if (!actionManager || !details) {
        return;
    }
    const breadcrumbItems = actionManager.querySelectorAll(
        ".o_control_panel .o_last_breadcrumb_item span, " +
            ".o_control_panel .o_control_panel_breadcrumbs .breadcrumb-item.active span, " +
            ".o_control_panel .o_control_panel_breadcrumbs .breadcrumb-item.active",
    );
    breadcrumbItems.forEach((item) => {
        const raw = item.textContent.replace(/\s+/g, " ").trim();
        if (!raw || item.children.length > 0) {
            return;
        }
        const next = raw.toLowerCase() === "dashboard"
            ? details.title
            : brandedLabel(raw);
        if (next !== raw) {
            item.textContent = next;
        }
    });

    actionManager.querySelectorAll(".o_account_dashboard_kanban_view .o_facet_value").forEach((facet) => {
        if (facet.textContent.trim().toLowerCase() === "favorites") {
            facet.textContent = "Saved views";
            facet.setAttribute("title", "Saved views");
        }
    });

    const formHeading = actionManager.querySelector(".o_form_view .o_form_sheet h1");
    const formTitle = formHeading?.textContent?.replace(/\s+/g, " ").trim();
    const formTitleMap = {
        "VENDOR BILL": "Vendor bill",
        "CUSTOMER INVOICE": "Customer invoice",
        "CREDIT NOTE": "Credit note",
        "CUSTOMER PAYMENT": "Customer payment",
    };
    if (formHeading && formTitleMap[formTitle]) {
        formHeading.textContent = formTitleMap[formTitle];
    }
    ensureNativeRouteHeader(actionManager, details);
}

function applyRouteContext() {
    const actionManager = document.querySelector(".o_action_manager");
    const path = window.location.pathname;
    const routeClasses = new Set();
    document.title = "TCSI Accounting | Third Code Solutions Inc.";
    const nativeRoute = getNativeRouteDetails(actionManager);

    if (
        path === "/dashboards" ||
        path === "/workspace/dashboards" ||
        path.endsWith("/action-425") ||
        actionManager?.querySelector(".tcsi-dashboard, .o_spreadsheet_dashboard_action")
    ) {
        routeClasses.add("tcsi-route-dashboard");
    }
    if (nativeRoute?.key === "accounting-dashboard") {
        routeClasses.add("tcsi-route-accounting-dashboard");
    }
    if (
        nativeRoute?.key === "bank reconciliation" ||
        path.includes("action-421") ||
        path.includes("bank-reconciliation") ||
        path.includes("bank-reconciliations")
    ) {
        routeClasses.add("tcsi-route-reconciliation");
    }
    if (path.includes("/discuss")) {
        routeClasses.add("tcsi-route-discuss");
    }
    if (path.includes("/contacts")) {
        routeClasses.add("tcsi-route-contacts");
    }

    if (actionManager?.querySelector(".o-mail-Discuss")) {
        routeClasses.add("tcsi-route-discuss");
    }
    const viewClass = nativeRoute?.view ? `tcsi-view-${nativeRoute.view}` : "tcsi-view-other";
    if (ROUTE_CLASSES.includes(viewClass)) {
        routeClasses.add(viewClass);
    } else if (actionManager) {
        routeClasses.add("tcsi-view-other");
    }

    if (document.querySelector(".modal.show, .o_dialog_container .modal-dialog, .o_dialog .modal-dialog")) {
        routeClasses.add("tcsi-view-dialog");
    }

    brandNativeChrome(actionManager, nativeRoute);

    for (const className of ROUTE_CLASSES) {
        document.body.classList.toggle(className, routeClasses.has(className));
    }
    document.body.dataset.tcsiRoute = [...routeClasses].find((className) => className.startsWith("tcsi-route-")) || "workspace";
    document.body.dataset.tcsiView = nativeRoute?.view || "other";
    updateNavbarContext();
    syncSidebarActiveState();
}

for (const key of USER_MENU_ITEMS_TO_REMOVE) {
    if (userMenuItems.contains(key)) {
        userMenuItems.remove(key);
    }
}

const ICON_PATHS = {
    overview: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
    dashboard: "M4 4h6v16H4zM14 9h6v11h-6zM5.5 7h3M15.5 12h3",
    discuss: "M4 5.5h16v10H10l-5 4v-4H4zM8 9.5h8M8 12.5h5",
    contacts: "M12 12a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM5 20a7 7 0 0 1 14 0M17 7.5a2.5 2.5 0 0 1 0 5M18.5 14a5.5 5.5 0 0 1 2.5 4",
    employees: "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3.5 20a4.5 4.5 0 0 1 9 0M16 11a2.5 2.5 0 1 0 0-5M15 14a4.5 4.5 0 0 1 5.5 4",
    expenses: "M5 4h14v16H5zM8 8h8M8 12h5M8 16h3",
    invoicing: "M6 3.5h9l3 3v14H6zM14 3.5v4h4M9 12h6M9 16h4",
    controls: "M5 6h14M5 12h14M5 18h14M9 6v0M15 12v0M11 18v0",
    periods: "M5 5h14v14H5zM8 3v4M16 3v4M5 10h14",
    invoices: "M6 3.5h9l3 3v14H6zM14 3.5v4h4M9 12h6M9 16h4",
    bills: "M5 4h14v16H5zM8 8h8M8 12h8M8 16h5",
    payments: "M4 7h16v11H4zM4 10h16M8 15h3",
    banking: "M3 9h18M5 9v9M9 9v9M15 9v9M19 9v9M2 18h20M4 6l8-3 8 3",
    reports: "M5 19V5h14v14zM8 16v-4M12 16V8M16 16v-6",
    settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM4 12h2M18 12h2M12 4v2M12 18v2",
    default: "M6 4h12v16H6zM9 8h6M9 12h6M9 16h3",
};

function iconKey(label = "") {
    const value = label.toLowerCase();
    if (value.includes("discuss") || value.includes("message")) return "discuss";
    if (value.includes("contact")) return "contacts";
    if (value.includes("employee") || value.includes("people") || value.includes("staff")) return "employees";
    if (value.includes("expense")) return "expenses";
    if (value.includes("dashboard") || value.includes("overview")) return "dashboard";
    if (value.includes("invoic")) return "invoicing";
    if (value.includes("period")) return "periods";
    if (value.includes("journal")) return "invoices";
    if (value.includes("bill")) return "bills";
    if (value.includes("payment")) return "payments";
    if (value.includes("bank")) return "banking";
    if (value.includes("report") || value.includes("statement")) return "reports";
    if (value.includes("control") || value.includes("profile") || value.includes("configuration")) return "controls";
    if (value.includes("setting")) return "settings";
    return "default";
}

function makeIcon(label, className = "tcsi-sidebar-icon") {
    const path = ICON_PATHS[iconKey(label)] || ICON_PATHS.default;
    const icon = document.createElement("span");
    icon.className = className;
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML = `<svg viewBox="0 0 24 24"><path d="${path}"/></svg>`;
    return icon;
}

function updateNavbarContext() {
    const context = document.querySelector(".tcsi-navbar-context");
    if (!context) {
        return;
    }
    const route = document.body.dataset.tcsiRoute;
    const nativeRoute = typeof getNativeRouteDetails === "function"
        ? getNativeRouteDetails(document.querySelector(".o_action_manager"))
        : null;
    let pageLabel = "Finance workspace";
    if (route === "tcsi-route-dashboard") {
        pageLabel = "Financial overview";
    } else if (route === "tcsi-route-discuss") {
        pageLabel = "Workspace inbox";
    } else if (route === "tcsi-route-contacts") {
        pageLabel = "Contact directory";
    } else if (route === "tcsi-route-accounting-dashboard") {
        pageLabel = "Finance command center";
    } else if (route === "tcsi-route-reconciliation") {
        pageLabel = "Bank reconciliation";
    } else if (nativeRoute?.title && nativeRoute.view !== "other") {
        pageLabel = nativeRoute.title;
    } else {
        const breadcrumb = document.querySelector(
            ".o_control_panel .o_cp_breadcrumb, .o_control_panel .o_control_panel_breadcrumbs .o_back_button a, .o_control_panel .o_control_panel_breadcrumbs .breadcrumb-item.active",
        );
        if (breadcrumb?.textContent?.trim()) {
            pageLabel = brandedLabel(breadcrumb.textContent.trim());
        }
    }
    const page = context.querySelector(".tcsi-navbar-context-page");
    if (page && page.textContent !== pageLabel) {
        page.textContent = pageLabel;
    }
}

function syncSidebarActiveState() {
    const sidebar = document.querySelector(".tcsi-workspace-sidebar");
    if (!sidebar) {
        return;
    }

    const route = document.body.dataset.tcsiRoute || "";
    const breadcrumb = document.querySelector(
        ".o_control_panel .o_cp_breadcrumb, .o_control_panel .o_control_panel_breadcrumbs .breadcrumb-item.active, .o_control_panel .o_control_panel_breadcrumbs .breadcrumb",
    );
    const pageText = [
        breadcrumb?.textContent,
        document.querySelector(".tcsi-navbar-context-page")?.textContent,
        document.querySelector(".o_form_view .o_form_sheet h1, .o_form_view .o_form_sheet .o_form_title")?.textContent,
    ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .replace(/\s+/g, " ");

    const links = [...sidebar.querySelectorAll(".tcsi-sidebar-link[data-tcsi-menu-name]")];
    let activeLink = null;
    if (route === "tcsi-route-dashboard" || route === "tcsi-route-accounting-dashboard") {
        activeLink = sidebar.querySelector(".tcsi-sidebar-overview");
    } else if (pageText) {
        activeLink = links.find((link) => {
            const labels = [link.dataset.tcsiMenuName, link.dataset.tcsiDisplayName]
                .filter(Boolean)
                .map((label) => label.toLowerCase());
            return labels.some((label) => pageText.includes(label) || label.includes(pageText));
        });
    }

    sidebar.querySelectorAll(".tcsi-sidebar-link").forEach((link) => {
        link.classList.toggle("is-active", link === activeLink);
        if (link === activeLink) {
            link.setAttribute("aria-current", "page");
        } else {
            link.removeAttribute("aria-current");
        }
    });

    const activeGroup = activeLink?.closest("details.tcsi-sidebar-group");
    if (activeGroup) {
        activeGroup.open = true;
    }
}

function removeOdooPromotions() {
    document.querySelectorAll("a[href]").forEach((anchor) => {
        // Native anchor properties also tolerate malformed user-entered links.
        if (anchor.origin !== window.location.origin) return;
        const brandedPath = anchor.pathname.replace(/^\/odoo(?=\/|$)/, TCSI_WEB_PREFIX);
        if (brandedPath !== anchor.pathname) {
            anchor.setAttribute("href", `${brandedPath}${anchor.search}${anchor.hash}`);
        }
    });
    document.querySelectorAll(".o_brand_promotion, a[href*='odoo.com']").forEach((element) => {
        const container = element.closest(".dropdown-item, .o_brand_promotion, p") || element;
        container.classList.add("d-none");
    });
}

function sanitizeBrandingAttributes() {
    document.querySelectorAll("[placeholder], [title], [aria-label], [alt]").forEach((element) => {
        for (const attribute of ["placeholder", "title", "aria-label", "alt"]) {
            const value = element.getAttribute(attribute);
            if (!value || !/odoo/i.test(value)) {
                continue;
            }
            element.setAttribute(
                attribute,
                value
                    .replace(/https?:\/\/(?:www\.)?odoo\.com/gi, "https://www.thirdcodesolutions.com")
                    .replace(/\bodoo\b/gi, "TCSI"),
            );
        }
    });
}

const SYSTRAY_ICON_PATHS = {
    Messages: "M4 5.5h16v10H10l-5 4v-4H4zM8 9.5h8M8 12.5h5",
    Activities: "M12 6v6l4 2M20 12a8 8 0 1 1-16 0 8 8 0 0 1 16 0z",
};

const TCSI_ASSISTANT = Object.freeze({
    displayName: "Orvexa",
    role: "TCSI finance assistant",
    avatarUrl: "/thirdcode_accounting/static/src/img/orvexa-avatar.png?v=2.8.0",
});

const ASSISTANT_COPY_REPLACEMENTS = [
    {
        marker: "Odoo's chat helps employees collaborate efficiently",
        text: "Hi — I’m Orvexa, your TCSI finance workspace assistant. I can help you find invoices, review balances, and start the right accounting task.",
    },
    {
        marker: "Not exactly. To continue the tour",
        text: "I can help you move through the workspace. Ask about invoices, payments, reconciliations, or financial reports.",
    },
    {
        marker: "To access special commands",
        text: "Tip: start with a clear request such as “show overdue invoices” or “open payment batches.”",
    },
];

function decorateSystrayIcons() {
    document.querySelectorAll(".o_menu_systray i[aria-label]").forEach((icon) => {
        const path = SYSTRAY_ICON_PATHS[icon.getAttribute("aria-label")];
        if (!path || icon.dataset.tcsiStyled === "true") {
            return;
        }
        icon.dataset.tcsiStyled = "true";
        icon.className = "tcsi-systray-icon";
        icon.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"/></svg>`;
    });
}

function replaceAssistantMessageCopy(message) {
    if (message.classList.contains("o-selfAuthored")) {
        return;
    }
    const body = message.querySelector(".o-mail-Message-richBody");
    const currentText = body?.textContent?.replace(/\s+/g, " ").trim();
    const replacement = ASSISTANT_COPY_REPLACEMENTS.find(({ marker }) => currentText?.includes(marker));
    if (!body || !replacement || message.dataset.tcsiAssistantCopy === replacement.marker) {
        return;
    }
    const paragraph = body.querySelector("p");
    if (!paragraph) {
        return;
    }
    paragraph.textContent = replacement.text;
    message.dataset.tcsiAssistantCopy = replacement.marker;
}

function isAssistantAvatarSource(source = "") {
    return /\/res\.partner\/2(?:\/|[?#])/i.test(source) || /(?:[?&])(?:id|res_id)=2(?:&|$)/i.test(source)
        || source.includes("/thirdcode_accounting/static/src/img/orvexa-avatar.png");
}

function replaceAssistantAvatar(avatar) {
    avatar.classList.add("tcsi-assistant-avatar");
    const image = avatar.matches("img") ? avatar : avatar.querySelector("img");
    if (image) {
        image.setAttribute("src", TCSI_ASSISTANT.avatarUrl);
        image.removeAttribute("srcset");
        image.setAttribute("alt", `${TCSI_ASSISTANT.displayName} avatar`);
    } else {
        avatar.style.setProperty("background-image", `url(${TCSI_ASSISTANT.avatarUrl})`, "important");
        avatar.style.setProperty("background-position", "center", "important");
        avatar.style.setProperty("background-repeat", "no-repeat", "important");
        avatar.style.setProperty("background-size", "cover", "important");
        avatar.setAttribute("role", "img");
        avatar.setAttribute("aria-label", `${TCSI_ASSISTANT.displayName} avatar`);
    }
    avatar.setAttribute("alt", `${TCSI_ASSISTANT.displayName} avatar`);
}

function replaceAssistantAvatarSources() {
    const assistantSurfaceSelector = [
        ".o-mail-Message",
        ".o-mail-ChatBubble",
        ".o-mail-ChatWindow",
        ".o-mail-NotificationItem",
        ".o-mail-DiscussSidebarChannel",
        ".o-mail-Thread",
        ".o-mail-ChatHub",
    ].join(", ");

    document.querySelectorAll(`${assistantSurfaceSelector} img`).forEach((avatar) => {
        if (avatar.classList.contains("tcsi-assistant-avatar") || isAssistantAvatarSource(avatar.getAttribute("src") || "")) {
            replaceAssistantAvatar(avatar);
        }
    });
}

function brandAssistantChat() {
    document.querySelectorAll(".o-mail-Message:not(.o-selfAuthored)").forEach(replaceAssistantMessageCopy);
    replaceAssistantAvatarSources();
    document.querySelectorAll(
        ".o-mail-Message-avatar[src*='/res.partner/2/'], .o-mail-Message-avatar.tcsi-assistant-avatar, " +
            ".o-mail-ChatBubble-avatar[src*='/res.partner/2/'], .o-mail-ChatBubble-avatar.tcsi-assistant-avatar",
    ).forEach((avatar) => {
        replaceAssistantAvatar(avatar);
    });

    document.querySelectorAll(".o-mail-ChatBubble, .o-mail-ChatHub-bubbleBtn").forEach((bubble) => {
        const avatar = bubble.querySelector(
            ".o-mail-ChatBubble-avatar, .o-mail-ThreadAvatar, img[class*='avatar'], [class*='Avatar']",
        );
        const botMarker = bubble.querySelector(".fa-heart, [title='Bot'], [aria-label*='System' i]");
        if (
            !avatar ||
            (!botMarker &&
                !avatar.classList.contains("tcsi-assistant-avatar") &&
                !isAssistantAvatarSource(avatar.getAttribute("src") || avatar.style.backgroundImage))
        ) {
            return;
        }
        bubble.classList.add("tcsi-assistant-bubble");
        replaceAssistantAvatar(avatar);
        const status = bubble.querySelector(".o-mail-ImStatus");
        status?.setAttribute("aria-label", TCSI_ASSISTANT.displayName + " online");
        status?.setAttribute("title", TCSI_ASSISTANT.displayName + " online");
    });

    document.querySelectorAll(".o-mail-NotificationItem").forEach((item) => {
        const sourceAvatar = [...item.querySelectorAll("img")].find(
            (avatar) => avatar.classList.contains("tcsi-assistant-avatar") || isAssistantAvatarSource(avatar.src),
        );
        if (!sourceAvatar && !item.classList.contains("tcsi-assistant-notification")) {
            return;
        }
        item.classList.add("tcsi-assistant-notification");
        const avatar = item.querySelector(".o-mail-NotificationItem-avatarContainer img");
        if (avatar) {
            replaceAssistantAvatar(avatar);
        }
        const name = item.querySelector(".o-mail-NotificationItem-name");
        if (name && name.textContent !== TCSI_ASSISTANT.displayName) {
            name.textContent = TCSI_ASSISTANT.displayName;
        }
        const preview = item.querySelector(".o-mail-NotificationItem-text");
        if (preview?.textContent.includes("To access special commands")) {
            preview.textContent = "Ask Orvexa for a finance shortcut.";
        }
    });

    document.querySelectorAll(".o-mail-DiscussSidebarChannel").forEach((channel) => {
        const name = channel.querySelector(".o-mail-DiscussSidebarChannel-itemName");
        const avatar = [...channel.querySelectorAll("img")].find(
            (candidate) => candidate.classList.contains("tcsi-assistant-avatar") || isAssistantAvatarSource(candidate.src),
        );
        const isAssistant =
            Boolean(avatar) ||
            /^(system|odoo)$/i.test(name?.textContent?.trim() || "") ||
            /^(system|odoo)$/i.test(channel.querySelector("[title]")?.getAttribute("title") || "");
        if (!isAssistant) {
            return;
        }
        channel.classList.add("tcsi-assistant-sidebar-channel");
        if (avatar) {
            replaceAssistantAvatar(avatar);
        }
        if (name && name.textContent !== TCSI_ASSISTANT.displayName) {
            name.textContent = TCSI_ASSISTANT.displayName;
        }
        const itemMain = channel.querySelector(".o-mail-DiscussSidebarChannel-itemMain");
        itemMain?.setAttribute("title", TCSI_ASSISTANT.displayName);
    });

    document.querySelectorAll(".o-mail-ChatWindow").forEach((chatWindow) => {
        const assistantAvatar = [...chatWindow.querySelectorAll("img")].some(
            (avatar) => avatar.classList.contains("tcsi-assistant-avatar") ||
                isAssistantAvatarSource(avatar.getAttribute("src") || ""),
        );
        if (!assistantAvatar) {
            return;
        }
        chatWindow.classList.add("tcsi-chat-window");
        chatWindow.dataset.tcsiAssistant = TCSI_ASSISTANT.displayName.toLowerCase();

        chatWindow.querySelectorAll(".o-mail-ChatWindow-threadAvatar img").forEach((avatar) => {
            replaceAssistantAvatar(avatar);
        });

        const header = chatWindow.querySelector(".o-mail-ChatWindow-header");
        const command = header?.querySelector(".o-mail-ChatWindow-command");
        const title = command?.querySelector(".text-truncate.fw-bold, .tcsi-chat-title");
        if (title) {
            title.classList.add("tcsi-chat-title");
            title.setAttribute("title", TCSI_ASSISTANT.displayName);
            if (title.textContent !== TCSI_ASSISTANT.displayName) {
                title.textContent = TCSI_ASSISTANT.displayName;
            }
            title.dataset.tcsiSubtitle = TCSI_ASSISTANT.role;
        }

        const status = header?.querySelector(".o-mail-ThreadIcon");
        if (status) {
            status.classList.add("tcsi-chat-status");
            status.setAttribute("aria-label", `${TCSI_ASSISTANT.displayName} online`);
            status.setAttribute("title", `${TCSI_ASSISTANT.displayName} online`);
        }

        const composerInput = chatWindow.querySelector(".o-mail-Composer-input");
        if (composerInput) {
            composerInput.setAttribute(
                "placeholder",
                `Ask ${TCSI_ASSISTANT.displayName} about invoices, payments, or reports…`,
            );
            composerInput.setAttribute("aria-label", `Message ${TCSI_ASSISTANT.displayName}`);
        }
    });
}

function normalizeInternalLinks() {
    document.querySelectorAll("a[href]").forEach((anchor) => {
        const rawHref = anchor.getAttribute("href");
        if (!rawHref || rawHref.startsWith("#")) {
            return;
        }
        let url;
        try {
            url = new URL(rawHref, window.location.origin);
        } catch {
            return;
        }
        if (
            url.origin !== window.location.origin ||
            (url.pathname !== INTERNAL_WEB_PREFIX && !url.pathname.startsWith(`${INTERNAL_WEB_PREFIX}/`))
        ) {
            return;
        }
        url.pathname = `${TCSI_WEB_PREFIX}${url.pathname.slice(INTERNAL_WEB_PREFIX.length)}`;
        anchor.setAttribute("href", `${url.pathname}${url.search}${url.hash}`);
    });
}

function makeSidebarLink(menu, menuService) {
    const displayName = brandedLabel(menu.name);
    const link = document.createElement("button");
    link.type = "button";
    link.className = "tcsi-sidebar-link";
    link.title = displayName;
    link.dataset.tcsiSearchLabel = `${menu.name} ${displayName}`.toLowerCase();
    link.dataset.tcsiMenuName = menu.name.toLowerCase();
    link.dataset.tcsiDisplayName = displayName.toLowerCase();
    if (menu.xmlid) {
        link.dataset.tcsiMenuXmlid = menu.xmlid;
    }
    if (menu.actionID) {
        link.dataset.tcsiActionId = String(menu.actionID);
    }
    link.append(makeIcon(menu.name));

    const label = document.createElement("span");
    label.className = "tcsi-sidebar-link-label";
    label.textContent = displayName;
    link.append(label);

    link.addEventListener("click", async () => {
        link.classList.add("is-loading");
        try {
            await menuService.selectMenu(menu);
        } finally {
            link.classList.remove("is-loading");
        }
    });
    return link;
}

function makeSidebarGroup(menu, menuService) {
    if (!menu.childrenTree?.length) {
        return makeSidebarLink(menu, menuService);
    }

    const displayName = brandedLabel(menu.name);
    const group = document.createElement("details");
    group.className = "tcsi-sidebar-group";
    group.dataset.tcsiSearchLabel = `${menu.name} ${displayName}`.toLowerCase();
    group.dataset.tcsiMenuName = menu.name.toLowerCase();
    group.dataset.tcsiDisplayName = displayName.toLowerCase();

    const summary = document.createElement("summary");
    summary.className = "tcsi-sidebar-group-title";
    summary.title = displayName;
    summary.append(makeIcon(menu.name));
    const label = document.createElement("span");
    label.className = "tcsi-sidebar-link-label";
    label.textContent = displayName;
    summary.append(label);
    group.append(summary);

    const children = document.createElement("div");
    children.className = "tcsi-sidebar-group-children";
    for (const child of menu.childrenTree) {
        children.append(makeSidebarGroup(child, menuService));
    }
    group.append(children);
    return group;
}

function makeSectionHeading(label) {
    const heading = document.createElement("div");
    heading.className = "tcsi-sidebar-section-label";
    heading.textContent = label;
    return heading;
}

function makeAppButton(app, menuService, currentApp) {
    const displayName = brandedLabel(app.name);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tcsi-app-switcher-item";
    button.classList.toggle("is-current", app.id === currentApp?.id);
    button.title = displayName;
    button.append(makeIcon(app.name, "tcsi-app-switcher-icon"));
    const label = document.createElement("span");
    label.textContent = displayName;
    button.append(label);
    button.addEventListener("click", async () => {
        const sidebar = document.querySelector(".tcsi-workspace-sidebar");
        const switcher = sidebar?.querySelector(".tcsi-sidebar-app-switcher");
        const appList = sidebar?.querySelector(".tcsi-app-switcher-list");
        sidebar?.classList.remove("is-apps-open");
        switcher?.setAttribute("aria-expanded", "false");
        if (appList) {
            appList.hidden = true;
        }
        await menuService.selectMenu(app);
    });
    return button;
}

function getTCSIApp(menuService) {
    return menuService.getApps().find((app) => app.xmlid === TCSI_APP_XMLID) || menuService.getCurrentApp();
}

function renderSidebar(sidebar, menuService) {
    const tcsiApp = getTCSIApp(menuService);
    const selectedApp = menuService.getCurrentApp() || tcsiApp;
    const nav = sidebar.querySelector(".tcsi-sidebar-nav");
    const appSwitcher = sidebar.querySelector(".tcsi-app-switcher-list");
    const currentLabel = sidebar.querySelector(".tcsi-sidebar-app-name");
    if (!nav || !tcsiApp || !selectedApp || !currentLabel) {
        return;
    }

    currentLabel.textContent = brandedLabel(selectedApp.name);
    nav.replaceChildren();

    const overview = document.createElement("button");
    overview.type = "button";
    overview.className = "tcsi-sidebar-link tcsi-sidebar-overview is-active";
    overview.title = "Overview";
    overview.dataset.tcsiMenuName = "overview";
    overview.append(makeIcon("overview"));
    const overviewLabel = document.createElement("span");
    overviewLabel.className = "tcsi-sidebar-link-label";
    overviewLabel.textContent = "Overview";
    overview.append(overviewLabel);
    overview.addEventListener("click", () => menuService.selectMenu(tcsiApp));
    nav.append(overview, makeSectionHeading("Workspace"));

    const tree = menuService.getMenuAsTree(selectedApp.id);
    for (const menu of tree.childrenTree || []) {
        nav.append(makeSidebarGroup(menu, menuService));
    }

    syncSidebarActiveState();

    if (appSwitcher) {
        appSwitcher.replaceChildren();
        sidebar.classList.remove("is-apps-open");
        appSwitcher.hidden = true;
        sidebar.querySelector(".tcsi-sidebar-app-switcher")?.setAttribute("aria-expanded", "false");
        for (const app of menuService.getApps()) {
            appSwitcher.append(makeAppButton(app, menuService, selectedApp));
        }
    }
}

function filterSidebarNavigation(sidebar, query = "") {
    const normalized = query.trim().toLowerCase();
    const tokens = normalized.split(/\s+/).filter(Boolean).map((token) => token.endsWith("s") ? token.slice(0, -1) : token);
    sidebar.querySelectorAll(".tcsi-sidebar-nav > .tcsi-sidebar-link, .tcsi-sidebar-nav > .tcsi-sidebar-group").forEach((item) => {
        const haystack = item.textContent.toLowerCase();
        const matches = !normalized || tokens.every((token) => haystack.includes(token));
        item.classList.toggle("is-search-hidden", !matches);
        if (normalized && matches && item.matches("details")) {
            item.open = true;
        }
    });
}

function mountWorkspaceNavigation(env) {
    const navbar = document.querySelector(".o_main_navbar");
    if (!navbar || document.querySelector(".tcsi-workspace-sidebar")) {
        return;
    }

    const menuService = env.services.menu;
    const sidebar = document.createElement("aside");
    sidebar.className = "tcsi-workspace-sidebar";
    sidebar.setAttribute("aria-label", "TCSI workspace navigation");
    sidebar.innerHTML = `
        <div class="tcsi-sidebar-header">
            <a class="tcsi-sidebar-brand" href="/workspace" aria-label="TCSI Accounting home">
                <img src="/thirdcode_accounting/static/src/img/tcsi-mark.svg?v=2.5.0" alt="" aria-hidden="true" />
                <span><strong>Third Code</strong><small>TCSI ACCOUNTING</small></span>
            </a>
        </div>
        <button class="tcsi-sidebar-app-switcher" type="button" aria-expanded="false" aria-controls="tcsi-app-switcher">
            <span class="tcsi-sidebar-app-switcher-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 5h16v14H4zM8 9h8M8 13h5"/></svg></span>
            <span class="tcsi-sidebar-app-copy"><small>Current workspace</small><strong class="tcsi-sidebar-app-name">TCSI Accounting</strong></span>
            <span class="tcsi-sidebar-chevron" aria-hidden="true">⌄</span>
        </button>
        <div class="tcsi-app-switcher-list" id="tcsi-app-switcher" hidden></div>
        <div class="tcsi-sidebar-search" role="search">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/></svg>
            <input class="tcsi-sidebar-search-input" type="search" placeholder="Quick search..." aria-label="Search workspace navigation" autocomplete="off" />
            <kbd>Ctrl K</kbd>
        </div>
        <nav class="tcsi-sidebar-nav" aria-label="Accounting navigation"></nav>
        <div class="tcsi-sidebar-footer">
            <span class="tcsi-sidebar-status-dot" aria-hidden="true"></span>
            <span class="tcsi-sidebar-link-label">Workspace ready</span>
        </div>
    `;

    const mobileToggle = document.createElement("button");
    mobileToggle.type = "button";
    mobileToggle.className = "tcsi-sidebar-mobile-toggle";
    mobileToggle.setAttribute("aria-label", "Open workspace navigation");
    mobileToggle.innerHTML = "<span aria-hidden='true'>☰</span>";
    mobileToggle.addEventListener("click", () => {
        document.body.classList.toggle("tcsi-sidebar-mobile-open");
    });
    navbar.prepend(mobileToggle);

    const navbarContext = document.createElement("div");
    navbarContext.className = "tcsi-navbar-context";
    navbarContext.setAttribute("aria-live", "polite");
    navbarContext.innerHTML = `
        <span class="tcsi-navbar-context-mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 4h6v16H5zM14 8h5v12h-5zM7 7h2M16 11h1"/></svg></span>
        <span class="tcsi-navbar-context-copy"><small>TCSI workspace</small><strong class="tcsi-navbar-context-page">Finance workspace</strong></span>
    `;
    navbar.insertBefore(navbarContext, mobileToggle.nextSibling);

    const switcher = sidebar.querySelector(".tcsi-sidebar-app-switcher");
    const appList = sidebar.querySelector(".tcsi-app-switcher-list");
    const searchInput = sidebar.querySelector(".tcsi-sidebar-search-input");
    const closeAppSwitcher = (restoreFocus = false) => {
        sidebar.classList.remove("is-apps-open");
        switcher.setAttribute("aria-expanded", "false");
        appList.hidden = true;
        if (restoreFocus) {
            switcher.focus();
        }
    };

    switcher.addEventListener("click", () => {
        const isOpen = sidebar.classList.toggle("is-apps-open");
        switcher.setAttribute("aria-expanded", String(isOpen));
        appList.hidden = !isOpen;
    });

    appList.addEventListener("click", (event) => event.stopPropagation());
    document.addEventListener("click", (event) => {
        if (!sidebar.contains(event.target)) {
            closeAppSwitcher();
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && sidebar.classList.contains("is-apps-open")) {
            closeAppSwitcher(true);
        }
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
            event.preventDefault();
            searchInput.focus();
            searchInput.select();
        }
    });

    searchInput.addEventListener("input", () => filterSidebarNavigation(sidebar, searchInput.value));
    searchInput.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            searchInput.value = "";
            filterSidebarNavigation(sidebar);
            searchInput.blur();
        }
    });

    document.body.prepend(sidebar);
    document.body.classList.add("tcsi-shell-active");
    renderSidebar(sidebar, menuService);
}

const tcsiBrandingService = {
    dependencies: ["menu"],

    start(env) {
        let routeContextFrame = 0;
        let observerPassTimer = 0;
        let observerPassRunning = false;
        let lastObserverPassAt = 0;
        const scheduleRouteContext = () => {
            if (routeContextFrame) {
                return;
            }
            routeContextFrame = window.requestAnimationFrame(() => {
                routeContextFrame = 0;
                applyRouteContext();
            });
        };

        const apply = () => {
            document.title = "TCSI Accounting | Third Code Solutions Inc.";
            mountWorkspaceNavigation(env);
            removeOdooPromotions();
            sanitizeBrandingAttributes();
            normalizeInternalLinks();
            decorateSystrayIcons();
            brandAssistantChat();
            scheduleRouteContext();
        };

        const refreshSidebar = () => {
            const sidebar = document.querySelector(".tcsi-workspace-sidebar");
            if (sidebar) {
                renderSidebar(sidebar, env.services.menu);
                filterSidebarNavigation(sidebar, sidebar.querySelector(".tcsi-sidebar-search-input")?.value || "");
            }
        };

        const onAppChanged = () => {
            apply();
            refreshSidebar();
        };

        apply();
        env.bus.addEventListener("MENUS:APP-CHANGED", onAppChanged);
        const runObserverPass = () => {
            if (observerPassRunning) {
                return;
            }
            observerPassRunning = true;
            lastObserverPassAt = Date.now();
            try {
                if (!document.querySelector(".tcsi-workspace-sidebar")) {
                    apply();
                } else {
                    removeOdooPromotions();
                    sanitizeBrandingAttributes();
                    normalizeInternalLinks();
                    decorateSystrayIcons();
                    brandAssistantChat();
                    scheduleRouteContext();
                }
            } finally {
                observerPassRunning = false;
            }
        };
        const scheduleObserverPass = () => {
            if (observerPassTimer) {
                return;
            }
            const wait = Math.max(0, 200 - (Date.now() - lastObserverPassAt));
            observerPassTimer = window.setTimeout(() => {
                observerPassTimer = 0;
                runObserverPass();
            }, wait);
        };
        const observer = new MutationObserver((records) => {
            const needsBrandingPass = records.some((record) => {
                const target = record.target instanceof Element ? record.target : record.target.parentElement;
                return (
                    target === document.body ||
                    target?.closest(".o_action_manager, .o_main_navbar, .tcsi-workspace-sidebar")
                );
            });
            if (needsBrandingPass) {
                scheduleObserverPass();
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });
        return () => {
            env.bus.removeEventListener("MENUS:APP-CHANGED", onAppChanged);
            observer.disconnect();
            if (observerPassTimer) {
                window.clearTimeout(observerPassTimer);
            }
            if (routeContextFrame) {
                window.cancelAnimationFrame(routeContextFrame);
            }
        };
    },
};

registry.category("services").add("tcsi_branding", tcsiBrandingService, { sequence: 1000 });
