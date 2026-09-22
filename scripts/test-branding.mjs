import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { test } from "node:test";

const source = readFileSync(new URL("../addons/thirdcode_accounting/static/src/js/tcsi_brand.js", import.meta.url), "utf8");

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
