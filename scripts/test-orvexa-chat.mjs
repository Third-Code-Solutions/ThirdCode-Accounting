import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { test } from "node:test";

const source = readFileSync(new URL("../addons/thirdcode_accounting/static/src/js/orvexa.js", import.meta.url), "utf8");
const classSource = source.slice(source.indexOf("export class OrvexaChat"), source.indexOf("class OrvexaLauncher")).replace("export class", "class");
function chat(call) {
    const context = { Component: class {}, Dialog: class {} };
    runInNewContext(`${classSource}; this.Chat = OrvexaChat;`, context);
    const dialog = new context.Chat();
    dialog.state = { message: "", busy: false, result: null, messages: [] };
    dialog.closed = false;
    dialog.call = call;
    dialog.refreshMemory = async () => {};
    return dialog;
}

test("chat retains ordered requests and engine replies without changing commands", async () => {
    const requests = [];
    const dialog = chat(async (params) => { requests.push(params.message); return { status: "complete", message: "Actual engine reply", records: [] }; });
    for (const message of ["show overdue invoices", "find \"Acme\""]) {
        dialog.state.message = message;
        await dialog.submit();
    }
    assert.deepEqual(requests, ["show overdue invoices", "find \"Acme\""]);
    assert.equal(dialog.state.messages.length, 4);
    assert.equal(dialog.state.messages[0].role, "user");
    assert.equal(dialog.state.messages[3].result.message, "Actual engine reply");
    assert.equal(dialog.state.message, "");
});

test("pending confirmation blocks new commands and retries use the same proposal", async () => {
    const calls = [];
    const proposal = { status: "confirmation_required", proposal_id: 42, message: "Review" };
    const dialog = chat(async (params) => {
        calls.push(params);
        if (calls.length === 1) throw new Error("Lost response");
        return { status: "complete", message: "Draft created", url: "/workspace/account.move/1" };
    });
    dialog.state.result = proposal;
    dialog.append("assistant", proposal);
    dialog.state.message = "show overdue invoices";
    await dialog.submit();
    assert.equal(calls.length, 0);
    await dialog.confirm();
    assert.equal(dialog.state.result, proposal);
    assert.match(dialog.state.messages.at(-1).result.message, /Completion is unknown/);
    await dialog.confirm();
    assert.equal(calls[0].proposal_id, 42);
    assert.equal(calls[1].proposal_id, 42);
    assert.equal(dialog.state.result.status, "complete");
});

test("failed request is recoverable and cancellation uses the engine", async () => {
    const dialog = chat(async () => { throw new Error("Offline"); });
    dialog.state.message = "find \"Customer\"";
    await dialog.submit();
    assert.equal(dialog.state.message, 'find "Customer"');
    assert.equal(dialog.state.busy, false);
    assert.equal(dialog.state.messages.at(-1).result.status, "error");
    dialog.state.result = { status: "confirmation_required", proposal_id: 2 };
    dialog.call = async (params) => {
        assert.equal(params.cancel, true);
        assert.equal(params.proposal_id, 2);
        return { status: "complete", message: "Cancelled" };
    };
    await dialog.confirm(true);
    assert.equal(dialog.state.result.message, "Cancelled");
});

test("Enter sends; Shift+Enter and composition do not submit", () => {
    const dialog = chat();
    let submits = 0;
    let prevented = 0;
    dialog.submit = () => { submits++; };
    for (const flags of [{ shiftKey: true }, { isComposing: true }, {}]) {
        dialog.onKeydown({ key: "Enter", ...flags, preventDefault: () => { prevented++; } });
    }
    assert.equal(submits, 1);
    assert.equal(prevented, 1);
});

test("only the configured assistant's private thread uses ORVEXA", () => {
    const start = source.indexOf("export function isOrvexaThread");
    const end = source.indexOf("patch(ThreadRecord.prototype", start);
    const context = {};
    runInNewContext(source.slice(start, end).replace("export function", "function"), context);
    const assistant = { id: 2 };
    const thread = { model: "discuss.channel", channel_type: "chat", correspondent: { id: 99, persona: { id: 2 } } };
    assert.equal(context.isOrvexaThread(thread, assistant), true);
    assert.equal(context.isOrvexaThread({ ...thread, correspondent: { id: 2, persona: { id: 9 } } }, assistant), false);
    assert.equal(context.isOrvexaThread({ ...thread, channel_type: "channel" }, assistant), false);
    assert.equal(context.isOrvexaThread({ ...thread, model: "account.move" }, assistant), false);
    assert.equal(context.isOrvexaThread(thread, undefined), false);
});

test("closing a native window during execution retains the result for reopening", async () => {
    let resolve;
    const dialog = chat(() => new Promise((done) => { resolve = done; }));
    dialog.state.message = "show overdue invoices";
    const pending = dialog.submit();
    dialog.closed = true;
    resolve({ status: "complete", message: "Completed while closed" });
    await pending;
    assert.equal(dialog.state.busy, false);
    assert.equal(dialog.state.messages.at(-1).result.message, "Completed while closed");
    const reopened = chat();
    reopened.state = dialog.state;
    reopened.append("user", { message: "Next request" });
    assert.equal(new Set(reopened.state.messages.map((message) => message.id)).size, 3);
});

test("tab memory is shared across chat surfaces but isolated by company", () => {
    let service;
    const context = { registry: { category: () => ({ add: (_, definition) => { service = definition.start(); } }) } };
    const start = source.indexOf('registry.category("services").add("tcsi_orvexa_sessions"');
    const end = source.indexOf("export function isOrvexaThread", start);
    runInNewContext(source.slice(start, end), context);
    const first = service.get({ id: 1, name: "First" });
    first.messages.push({ id: 1, role: "user" });
    assert.equal(service.get({ id: 1, name: "First" }), first);
    assert.equal(service.get({ id: 2, name: "Second" }).messages.length, 0);
});
