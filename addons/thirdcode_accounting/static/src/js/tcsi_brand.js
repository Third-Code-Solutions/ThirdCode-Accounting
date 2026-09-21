/** @odoo-module **/

import { router } from "@web/core/browser/router";
import { registry } from "@web/core/registry";

const TCSI_WEB_PREFIX = "/workspace";
const INTERNAL_WEB_PREFIX = "/odoo";
const USER_MENU_ITEMS_TO_REMOVE = ["documentation", "support", "odoo_account"];
const TCSI_APP_XMLID = "thirdcode_accounting.menu_thirdcode_accounting_root";
const userMenuItems = registry.category("user_menuitems");

const frameworkStateToUrl = router.stateToUrl;
const frameworkUrlToState = router.urlToState;
router.stateToUrl = (state) =>
    frameworkStateToUrl(state).replace(
        new RegExp(`^${INTERNAL_WEB_PREFIX}(?=/|$)`),
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
    "tcsi-route-dashboard",
    "tcsi-route-discuss",
    "tcsi-route-contacts",
    "tcsi-view-list",
    "tcsi-view-form",
    "tcsi-view-kanban",
    "tcsi-view-other",
];

function applyRouteContext() {
    const actionManager = document.querySelector(".o_action_manager");
    const path = window.location.pathname;
    const routeClasses = new Set();
    document.title = "TCSI Accounting | Third Code Solutions Inc.";

    if (path === "/dashboards" || path.endsWith("/action-425")) {
        routeClasses.add("tcsi-route-dashboard");
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
    if (actionManager?.querySelector(".o_kanban_view")) {
        routeClasses.add("tcsi-view-kanban");
    } else if (actionManager?.querySelector(".o_list_view")) {
        routeClasses.add("tcsi-view-list");
    } else if (actionManager?.querySelector(".o_form_view")) {
        routeClasses.add("tcsi-view-form");
    } else if (actionManager) {
        routeClasses.add("tcsi-view-other");
    }

    for (const className of ROUTE_CLASSES) {
        document.body.classList.toggle(className, routeClasses.has(className));
    }
    document.body.dataset.tcsiRoute = [...routeClasses].find((className) => className.startsWith("tcsi-route-")) || "workspace";
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
    let pageLabel = "Finance workspace";
    if (route === "tcsi-route-dashboard") {
        pageLabel = "Financial overview";
    } else if (route === "tcsi-route-discuss") {
        pageLabel = "Workspace inbox";
    } else if (route === "tcsi-route-contacts") {
        pageLabel = "Contact directory";
    } else {
        const breadcrumb = document.querySelector(
            ".o_control_panel .o_cp_breadcrumb, .o_control_panel .o_control_panel_breadcrumbs .o_back_button a, .o_control_panel .o_control_panel_breadcrumbs .breadcrumb-item.active",
        );
        if (breadcrumb?.textContent?.trim()) {
            pageLabel = breadcrumb.textContent.trim();
        }
    }
    const page = context.querySelector(".tcsi-navbar-context-page");
    if (page) {
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
    if (route === "tcsi-route-dashboard") {
        activeLink = sidebar.querySelector(".tcsi-sidebar-overview");
    } else if (pageText) {
        activeLink = links.find((link) => {
            const label = link.dataset.tcsiMenuName || "";
            return label && (pageText.includes(label) || label.includes(pageText));
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
    return /\/res\.partner\/2(?:\/|[?#])/i.test(source) || /(?:[?&])(?:id|res_id)=2(?:&|$)/i.test(source);
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
        if (name) {
            name.textContent = TCSI_ASSISTANT.displayName;
        }
        const itemMain = channel.querySelector(".o-mail-DiscussSidebarChannel-itemMain");
        itemMain?.setAttribute("title", TCSI_ASSISTANT.displayName);
    });

    document.querySelectorAll(".o-mail-ChatWindow").forEach((chatWindow) => {
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
    const link = document.createElement("button");
    link.type = "button";
    link.className = "tcsi-sidebar-link";
    link.title = menu.name;
    link.dataset.tcsiSearchLabel = menu.name.toLowerCase();
    link.dataset.tcsiMenuName = menu.name.toLowerCase();
    if (menu.xmlid) {
        link.dataset.tcsiMenuXmlid = menu.xmlid;
    }
    if (menu.actionID) {
        link.dataset.tcsiActionId = String(menu.actionID);
    }
    link.append(makeIcon(menu.name));

    const label = document.createElement("span");
    label.className = "tcsi-sidebar-link-label";
    label.textContent = menu.name;
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

    const group = document.createElement("details");
    group.className = "tcsi-sidebar-group";
    group.dataset.tcsiSearchLabel = menu.name.toLowerCase();
    group.dataset.tcsiMenuName = menu.name.toLowerCase();

    const summary = document.createElement("summary");
    summary.className = "tcsi-sidebar-group-title";
    summary.title = menu.name;
    summary.append(makeIcon(menu.name));
    const label = document.createElement("span");
    label.className = "tcsi-sidebar-link-label";
    label.textContent = menu.name;
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
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tcsi-app-switcher-item";
    button.classList.toggle("is-current", app.id === currentApp?.id);
    button.append(makeIcon(app.name, "tcsi-app-switcher-icon"));
    const label = document.createElement("span");
    label.textContent = app.name;
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

    currentLabel.textContent = selectedApp.name;
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
        const observer = new MutationObserver(() => {
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
        });
        observer.observe(document.body, { childList: true, subtree: true });
        return () => {
            env.bus.removeEventListener("MENUS:APP-CHANGED", onAppChanged);
            observer.disconnect();
            if (routeContextFrame) {
                window.cancelAnimationFrame(routeContextFrame);
            }
        };
    },
};

registry.category("services").add("tcsi_branding", tcsiBrandingService, { sequence: 1000 });
