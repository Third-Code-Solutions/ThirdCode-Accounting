import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { test } from "node:test";

const source = readFileSync(new URL("../addons/thirdcode_accounting/static/src/js/tcsi_apps.js", import.meta.url), "utf8");
const context = {};
runInNewContext(source.slice(source.indexOf("export const APP_DESIGNS"), source.indexOf("class TCSIApps")).replaceAll("export ", "") + "; this.designs = APP_DESIGNS;", context);

test("open targets come only from authorized menus", () => {
    const apps = context.catalogApps([{ id: 1, xmlid: "account.menu_finance", name: "Invoicing" }, { id: 2, xmlid: "base.menu_management", name: "Apps" }]);
    assert.equal(apps.length, 1);
    assert.equal(apps[0].name, "Revenue");
    assert.equal(apps[0].id, 1);
    assert.equal(context.catalogApps([]).length, 0);
});
test("full catalog preserves uninstalled modules and distinguishes accessible apps", () => {
    const modules = [
        { id: 10, name: "sale", shortdesc: "Sales", state: "uninstalled", category_id: [1, "Sales"] },
        { id: 11, name: "account", shortdesc: "Invoicing", state: "installed" },
        { id: 12, name: "auditlog", shortdesc: "Audit Log", state: "installed" },
        { id: 13, name: "vendor", shortdesc: "Odoo Extension", summary: "Odoo tools", state: "uninstallable" },
    ];
    const apps = context.moduleCatalog(modules, [{ id: 7, xmlid: "account.menu_finance", name: "Revenue" }]);
    assert.equal(apps.length, 4);
    assert.equal(apps.find((a) => a.id === 10).status, "Not installed");
    assert.equal(apps.find((a) => a.id === 10).menuId, undefined);
    assert.equal(apps.find((a) => a.id === 11).menuId, 7);
    assert.equal(apps.find((a) => a.id === 12).menuId, undefined);
    assert.equal(apps.find((a) => a.id === 13).name, "TCSI Extension");
    assert.equal(apps.find((a) => a.id === 13).status, "Unavailable");
});
test("each known app has a distinct bundled TCSI icon", () => {
    const icons = Object.values(context.designs).map((design) => design.icon);
    assert.equal(new Set(icons).size, icons.length);
    for (const icon of [...icons, "workspace"]) {
        const file = new URL(`../addons/thirdcode_accounting/static/src/img/apps/${icon}.svg`, import.meta.url);
        assert.ok(existsSync(file));
        assert.doesNotMatch(readFileSync(file, "utf8"), /odoo|https?:\/\/(?!www.w3.org)/i);
    }
});
test("unknown installed apps remain reachable instead of silently disappearing", () => {
    const apps = context.catalogApps([{ id: 5, xmlid: "custom.menu", name: "Client extension" }]);
    assert.equal(apps[0].name, "Client extension");
    assert.equal(apps[0].icon, "workspace");
});
test("customer launcher contains no marketplace installation or vendor links", () => {
    const xml = readFileSync(new URL("../addons/thirdcode_accounting/static/src/xml/tcsi_apps.xml", import.meta.url), "utf8");
    assert.doesNotMatch(xml, /odoo|Request Access|button_immediate_install|https?:/i);
    assert.match(xml, /role="alert"/);
    assert.match(xml, /No matching apps/);
});
