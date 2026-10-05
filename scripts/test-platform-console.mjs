import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import test from "node:test";

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
