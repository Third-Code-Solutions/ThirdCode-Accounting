import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const root = new URL("../", import.meta.url);
const portal = readFileSync(new URL("apps/web/app/globals.css", root), "utf8");
const tokens = readFileSync(
  new URL("addons/thirdcode_accounting/static/src/scss/tcsi_tokens.scss", root),
  "utf8",
);
const routes = readFileSync(
  new URL("addons/thirdcode_accounting/static/src/scss/tcsi_routes.scss", root),
  "utf8",
);
const manifest = readFileSync(
  new URL("addons/thirdcode_accounting/__manifest__.py", root),
  "utf8",
);

// The canonical palette is declared once per surface. The portal names it
// --tcsi-<name>, the addon --tcsi-color-<name>; the values must be identical.
const canonical = [
  "canvas", "canvas-strong", "surface", "surface-soft", "surface-hover",
  "ink", "ink-muted", "ink-soft", "line", "line-strong",
  "accent", "accent-deep", "accent-soft", "accent-line", "accent-wash",
  "positive", "positive-bright", "positive-soft", "positive-text",
  "attention", "danger", "danger-soft", "danger-text",
];

function declarations(source, opener) {
  // Normalize CRLF checkouts so the gate matches CI on Windows too.
  source = source.replace(/\r\n/g, "\n");
  const start = source.indexOf(opener);
  assert.notEqual(start, -1, `missing block: ${opener}`);
  const body = source.slice(start + opener.length);
  const end = body.indexOf("}");
  assert.notEqual(end, -1, `unterminated block: ${opener}`);
  const found = {};
  for (const line of body.slice(0, end).split("\n")) {
    const match = line.match(/(--[a-z0-9-]+):\s*([^;]+);/i);
    if (match) found[match[1]] = match[2].trim().toLowerCase();
  }
  return found;
}

const portalLight = declarations(portal, ":root {");
const portalDark = declarations(portal, "@media (prefers-color-scheme: dark) {\n  :root {");
const addonLight = declarations(tokens, ":root {");
const addonDark = declarations(tokens, 'html[data-tcsi-theme="dark"] {');

test("the portal and the addon declare the same light palette", () => {
  for (const name of canonical) {
    assert.equal(
      portalLight[`--tcsi-${name}`],
      addonLight[`--tcsi-color-${name}`],
      `light ${name} drifted between apps/web/app/globals.css and tcsi_tokens.scss`,
    );
  }
});

test("the portal and the addon declare the same dark palette", () => {
  for (const name of canonical) {
    assert.equal(
      portalDark[`--tcsi-${name}`],
      addonDark[`--tcsi-color-${name}`],
      `dark ${name} drifted between apps/web/app/globals.css and tcsi_tokens.scss`,
    );
  }
});

test("the portal exposes every dark token it needs", () => {
  for (const name of canonical) {
    assert.ok(portalDark[`--tcsi-${name}`], `portal dark theme is missing --tcsi-${name}`);
  }
  assert.match(
    portal.slice(portal.indexOf("@media (prefers-color-scheme: dark)")),
    /color-scheme:\s*dark;/,
    "the portal dark theme must declare color-scheme: dark",
  );
});

test("shared radii and elevation are the same on both surfaces", () => {
  for (const token of ["--tcsi-radius-control", "--tcsi-radius-surface", "--tcsi-radius-panel"]) {
    assert.equal(portalLight[token], addonLight[token], `${token} drifted`);
  }
});

test("the workspace route layer reads the shared tokens instead of local hexes", () => {
  for (const legacy of ["#fbfbfd", "#f8fafb", "#1d2b33", "#3d4d56", "#6e7c84", "#6b48d8", "#5130b3"]) {
    assert.ok(!routes.includes(legacy), `tcsi_routes.scss still hard-codes ${legacy}`);
  }
  for (const token of [
    "--tcsi-route-page: var(--tcsi-color-canvas)",
    "--tcsi-route-surface: var(--tcsi-color-surface)",
    "--tcsi-route-ink: var(--tcsi-color-ink)",
    "--tcsi-route-line: var(--tcsi-color-line)",
    "--tcsi-route-accent: var(--tcsi-color-accent)",
    "--tcsi-route-radius: var(--tcsi-radius-panel)",
    "--tcsi-route-radius-sm: var(--tcsi-radius-control)",
    "font-family: var(--tcsi-font-ui)",
  ]) {
    assert.ok(routes.includes(token), `tcsi_routes.scss is missing ${token}`);
  }
});

test("the token layer ships in both asset bundles before its consumers", () => {
  const backend = manifest.indexOf('"web.assets_backend"');
  const frontend = manifest.indexOf('"web.assets_frontend"');
  const tokenPath = "thirdcode_accounting/static/src/scss/tcsi_tokens.scss";
  const firstBackend = manifest.indexOf(tokenPath, backend);
  const firstFrontend = manifest.indexOf(tokenPath, frontend);
  assert.ok(firstBackend > backend && firstBackend < manifest.indexOf("tcsi_brand.scss", backend), "backend bundle order");
  assert.ok(firstFrontend > frontend && firstFrontend < manifest.indexOf("tcsi_brand.scss", frontend), "frontend bundle order");
});

test("the dashboard reference keeps its documented presentation", () => {
  for (const reference of [
    ".page-heading h1 {",
    ".eyebrow {",
    ".metric-card {",
    ".panel {",
    ".button--primary {",
    "--tcsi-shell-sidebar-width: 252px",
    "--tcsi-shell-topbar-height: 72px",
  ]) {
    assert.ok(portal.includes(reference), `dashboard reference lost ${reference}`);
  }
});

test("dark surfaces never fall back to a light background", () => {
  const dark = portal.slice(portal.indexOf("@media (prefers-color-scheme: dark)"));
  for (const leak of ["background: #fff;", "background: white;", "background: #fbfbfd;"]) {
    assert.ok(!dark.includes(leak), `dark theme still sets ${leak}`);
  }
});
