import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { test } from "node:test";

const source = readFileSync(new URL("../addons/thirdcode_accounting/static/src/js/tcsi_brand.js", import.meta.url), "utf8");

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
    const end = source.indexOf("function syncSidebarActiveState()", start);
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
