import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import test from "node:test";
import { webcrypto } from "node:crypto";

// Execute the production controller with service doubles; native rendering is
// covered separately. Deferred requests reproduce real cross-editor races.
const source = fs.readFileSync("addons/thirdcode_accounting/static/src/js/tcsi_console.js", "utf8")
  .replace(/^import .*;\n/gm, "");
let Console;
vm.runInNewContext(source, {
  Component: class {}, Dialog: class {}, ConfirmationDialog: class {},
  registry: { category: () => ({ add: (_name, component) => { Console = component; } }) },
});
const a = { id: 1, revision: 1, kind: "release", title: "Release A", description: "A content", version: "1", category: "improvement" };
const b = { ...a, id: 2, title: "Release B", description: "B content" };
function makeConsole() {
  const app = new Console();
  app.state = { loading: false, busy: false, editorId: a.id, revision: a.revision,
    draft: {}, publicationPage: 0, publications: [a] };
  app.editPublication(a);
  app.notification = { add() {} };
  app.loadTab = async () => {};
  return app;
}

for (const [name, switchEditor] of [["select another draft", app => app.editPublication(b)], ["start new update", app => app.newRelease()]]) {
  test(`Pending save cannot ${name} and cross record contents`, async () => {
    const app = makeConsole();
    let resolveSave;
    app.orm = { call: () => new Promise(resolve => { resolveSave = resolve; }) };
    const pending = app.saveDraft();
    switchEditor(app);
    resolveSave({ id: a.id, revision: 2 });
    await pending;
    assert.equal(app.state.editorId, a.id);
    assert.equal(app.state.draft.title, a.title);
    assert.equal(app.state.revision, 2);
    assert.equal(app.state.busy, false);
    app.editPublication(b);
    assert.equal(app.state.editorId, b.id);
  });
}
for (const successful of [true, false]) {
  test(`Publish ${successful ? "success advances" : "failure preserves"} editor revision`, async () => {
    const app = makeConsole();
    let confirm;
    app.dialog = { add: (_component, props) => { confirm = props.confirm; } };
    app.run = async () => {
      if (successful) app.state.publications = [{ ...a, revision: 2 }];
      return successful;
    };
    app.publish("publish");
    await confirm();
    assert.equal(app.state.revision, successful ? 2 : 1);
    assert.equal(app.state.draft.title, a.title);
  });
}

test("Publish reload cannot rebase old editor onto another owner's newer draft", async () => {
  const app = makeConsole();
  let confirm;
  app.dialog = { add: (_component, props) => { confirm = props.confirm; } };
  app.run = async () => {
    app.state.publications = [{ ...a, revision: 3, title: "Concurrent owner edit" }];
    return true;
  };
  app.publish("publish");
  await confirm();
  assert.equal(app.state.revision, 2);
  assert.equal(app.state.draft.title, a.title);
});

test("Publishing a refreshed list still checks the editor's original revision", async () => {
  const app = makeConsole();
  app.state.publications = [{ ...a, revision: 3, title: "Newer draft" }];
  let confirm;
  app.dialog = { add: (_component, props) => { confirm = props.confirm; } };
  app.run = async (_method, args) => { assert.equal(args[1], 1); return false; };
  app.publish("publish");
  await confirm();
  assert.equal(app.state.revision, 1);
});

test("Denied session clears all loaded owner data and shows an explicit refusal", async () => {
  const app = makeConsole();
  Object.assign(app.state, { data: { organizations: [1] }, analytics: {}, monitoring: {},
    orgs: { rows: [1] }, people: { rows: [2] }, audit: { rows: [3] } });
  app.orm = { call: async () => { throw { data: { name: "odoo.exceptions.AccessError" } }; } };
  await app.load();
  assert.equal(app.state.denied, true);
  assert.match(app.state.error, /reserved for the TCSI platform owner/);
  for (const key of ["data", "analytics", "monitoring"]) assert.equal(app.state[key], null);
  for (const key of ["orgs", "people", "audit"]) assert.equal(app.state[key].rows.length, 0);
  assert.equal(app.state.publications.length, 0);
  assert.equal(app.state.loading, false);
});

test("Verified owner data restores the console after an earlier refusal", async () => {
  const app = makeConsole();
  app.state.denied = true;
  app.orm = { call: async () => ({ organizations: [] }) };
  await app.load();
  assert.equal(app.state.denied, false);
  assert.ok(app.state.data);
  assert.equal(app.state.error, "");
});

for (const operation of [app => app.run("suspend_company", [4], "Done"),
  app => app.newOrganization(), app => app.createOrganization(), app => app.saveDraft()]) {
  test(`Owner authority revoked during ${operation.toString()} closes owner controls`, async () => {
    const app = makeConsole();
    app.state.data = { organizations: [1] };
    app.state.org = { admin_password: "Unsaved-secret" };
    let closed = false;
    app.removeCreateDialog = () => { closed = true; };
    app.orm = { call: async () => { throw { data: { name: "odoo.exceptions.AccessError" } }; } };
    await operation(app);
    assert.equal(app.state.denied, true);
    assert.equal(app.state.data, null);
    assert.equal(app.state.org.admin_password, "");
    assert.equal(app.state.draft.title, "");
    assert.equal(closed, true);
  });
}

test("Business validation failure keeps owner editor and exposes error", async () => {
  const app = makeConsole();
  app.state.data = { organizations: [] };
  app.orm = { call: async () => { throw { data: { name: "odoo.exceptions.UserError", message: "Revision changed" } }; } };
  await app.saveDraft();
  assert.equal(app.state.error, "Revision changed");
  assert.ok(app.state.data);
  assert.equal(app.state.draft.title, a.title);
});

function passwordDialog(crypto = webcrypto) {
  const context = {
    crypto, Component: class {}, Dialog: class {}, useState: state => state,
  };
  vm.runInNewContext(source.slice(0, source.indexOf("class PlatformConsole")) +
    ";this.CreateDialog = CreateOrganizationDialog;", context);
  const dialog = new context.CreateDialog();
  dialog.props = { controller: { state: { busy: false, org: { admin_password: "" } } } };
  dialog.setup();
  return dialog;
}

test("Generated credentials meet initial-password policy and can be revealed or hidden", () => {
  const dialog = passwordDialog();
  const passwords = new Set();
  assert.equal(dialog.password.visible, false);
  for (let i = 0; i < 100; i++) {
    dialog.generatePassword();
    const value = dialog.state.org.admin_password;
    assert.equal(value.length, 24);
    for (const pattern of [/^[A-Za-z0-9_-]+$/, /[A-Z]/, /[a-z]/, /[0-9]/, /[-_]/]) assert.match(value, pattern);
    passwords.add(value);
  }
  assert.equal(passwords.size, 100);
  assert.equal(dialog.password.visible, true);
  const value = dialog.state.org.admin_password;
  dialog.togglePassword();
  assert.equal(dialog.password.visible, false);
  assert.equal(dialog.state.org.admin_password, value);
});

test("Generation cannot replace credentials during submission", () => {
  const dialog = passwordDialog({ getRandomValues() { assert.fail("Must not generate while busy"); } });
  dialog.state.org.admin_password = "Manually-entered-secret";
  dialog.state.busy = true;
  dialog.generatePassword();
  assert.equal(dialog.state.org.admin_password, "Manually-entered-secret");
});

test("Unavailable cryptographic randomness preserves manual input and reports failure", () => {
  const dialog = passwordDialog({ getRandomValues() { throw new Error("unavailable"); } });
  dialog.state.org.admin_password = "Manually-entered-secret";
  dialog.generatePassword();
  assert.equal(dialog.state.org.admin_password, "Manually-entered-secret");
  assert.match(dialog.password.error, /Secure password generation is unavailable/);
  assert.equal(dialog.password.visible, false);
});
