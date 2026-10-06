import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import test from "node:test";

const source = readFileSync("addons/thirdcode_accounting/static/src/js/tcsi_settings.js", "utf8")
    .replace(/^import .*;\n/gm, "").replace(/^export /gm, "");
function harness(headings = []) {
    const mounted = [], unmounted = [], frames = new Map();
    let extension, observer, nextFrame = 0;
    const root = {
        scrollTop: 0, querySelectorAll: () => headings,
        getBoundingClientRect: () => ({ top: 100 }),
        addEventListener(name, listener) { this.listener = listener; },
        removeEventListener(name, listener) { assert.equal(listener, this.listener); this.removed = true; },
        scrollTo(options) { this.scrolled = options; },
    };
    const context = {
        onMounted: fn => mounted.push(fn), onWillUnmount: fn => unmounted.push(fn), useState: state => state,
        SettingsPage: class {},
        registry: { category: () => ({ add() {} }) },
        patch: (_prototype, methods) => { extension = methods; Object.setPrototypeOf(methods, { setup() {} }); },
        MutationObserver: class {
            constructor(callback) { this.callback = callback; observer = this; }
            observe() {} disconnect() { this.disconnected = true; }
        },
        requestAnimationFrame: callback => { const id = ++nextFrame; frames.set(id, callback); return id; },
        cancelAnimationFrame: id => frames.delete(id),
    };
    vm.runInNewContext(source + "\nthis.settingsNavigationService = settingsNavigationService;", context);
    const events = [];
    const navigation = context.settingsNavigationService.start({ bus: { trigger: (...args) => events.push(args) } });
    const page = Object.assign(Object.create(extension), {
        settingsRef: { el: root }, state: { selectedTab: "general_settings" },
        props: { modules: [{ key: "general_settings", string: "TCSI Settings" }] },
        env: { services: { tcsi_settings_navigation: navigation } },
        onSettingTabClick(key) { this.state.selectedTab = key; },
    });
    page.setup();
    return { context, page, root, headings, mounted, unmounted, frames, navigation, events, get observer() { return observer; } };
}
function heading(text, top = 200) {
    return {
        id: "", textContent: text, hidden: false, classHidden: false, attributes: {},
        getClientRects() { return this.hidden ? [] : [{}]; },
        closest() { return this.classHidden ? {} : null; },
        hasAttribute(name) { return name in this.attributes; },
        setAttribute(name, value) { this.attributes[name] = value; },
        getBoundingClientRect: () => ({ top }),
        focus(options) { this.focused = options; },
    };
}

test("outline contains only currently visible native sections and preserves existing identifiers", () => {
    const users = heading("Users"), hidden = heading("Hidden"), searchHidden = heading("Search hidden");
    hidden.hidden = true; searchHidden.classHidden = true; users.id = "native-users";
    const h = harness([users, hidden, searchHidden]); h.mounted[0]();
    assert.equal(h.page.tcsiOutline.sections.length, 1);
    assert.equal(h.page.tcsiOutline.sections[0].id, "native-users");
    assert.equal(users.attributes.tabindex, "-1");
    assert.equal(hidden.id, "");
});

test("newly visible sections never reuse an identifier retained by a hidden section", () => {
    const first = heading("Users"), second = heading("Accounting"); second.hidden = true;
    const h = harness([first, second]); h.mounted[0]();
    const initial = first.id;
    first.hidden = true; second.hidden = false; h.page.tcsiSyncSections();
    assert.notEqual(second.id, initial);
    first.hidden = false; h.page.tcsiSyncSections();
    assert.equal(first.id, initial);
    assert.equal(new Set(h.page.tcsiOutline.sections.map(s => s.id)).size, 2);
});

test("section jump scrolls only the settings pane and focuses the native heading", () => {
    const target = heading("Permissions", 500); const h = harness([target]); h.mounted[0]();
    h.root.scrollTop = 80; h.page.tcsiJumpToSection(target.id);
    assert.equal(h.root.scrolled.top, 464);
    assert.equal(h.root.scrolled.behavior, "auto");
    assert.equal(target.focused.preventScroll, true);
    assert.equal(h.page.tcsiOutline.active, target.id);
    h.page.tcsiJumpToSection("removed");
    assert.equal(h.root.scrolled.top, 464);
});

test("search and module changes refresh sections without replacing unchanged state", () => {
    const users = heading("Users"), email = heading("Emails", 120); const h = harness([users, email]); h.mounted[0]();
    const original = h.page.tcsiOutline.sections;
    h.page.tcsiSyncSections(); assert.equal(h.page.tcsiOutline.sections, original);
    users.hidden = true; h.page.tcsiSyncSections();
    assert.equal(h.page.tcsiOutline.sections.length, 1);
    assert.equal(h.page.tcsiOutline.active, email.id);
    email.hidden = true; h.page.tcsiSyncSections();
    assert.equal(h.page.tcsiOutline.sections.length, 0);
    assert.equal(h.page.tcsiOutline.active, "");
});

test("navigation away disconnects observers, scroll listeners, and queued updates", () => {
    const h = harness([heading("Users")]); h.mounted[0]();
    h.observer.callback(); h.observer.callback();
    assert.equal(h.frames.size, 1, "coalesce native mutations");
    h.unmounted[0]();
    assert.equal(h.observer.disconnected, true);
    assert.equal(h.root.removed, true);
    assert.equal(h.frames.size, 0);
});

test("main sidebar adapter uses native module selection and live section jumps", () => {
    const target = heading("Emails"); const h = harness([target]); h.mounted[0]();
    assert.equal(h.navigation.active, true);
    assert.equal(h.navigation.sections[0].id, target.id);
    h.navigation.openSection(target.id);
    assert.equal(target.focused.preventScroll, true);
    h.page.props.modules.push({ key: "account", string: "Accounting" });
    h.navigation.selectModule("account");
    assert.equal(h.page.state.selectedTab, "account");
    h.navigation.selectModule("unavailable");
    assert.equal(h.page.state.selectedTab, "account");
    h.page.tcsiSyncSections();
    assert.equal(h.events.at(-1)[1].structure, true);
    h.navigation.detach({});
    assert.equal(h.navigation.active, true, "an old page cannot detach the current page");
    h.unmounted[0]();
    assert.equal(h.navigation.active, false);
    assert.equal(h.navigation.sections.length, 0);
});

test("last section stays active at the bottom even when it cannot reach the pane top", () => {
    const first = heading("Permissions", 120), last = heading("About TCSI", 400);
    const h = harness([first, last]); h.mounted[0]();
    h.root.scrollTop = 400; h.root.clientHeight = 600; h.root.scrollHeight = 1000;
    h.page.tcsiSyncActiveSection();
    assert.equal(h.navigation.activeSection, last.id);
});
