import assert from "node:assert/strict";
import { test } from "node:test";

import {
    classifyDevelopmentAudit,
    evaluateAuditResult,
} from "./audit-development-dependencies.mjs";

const advisoryUrl = "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm";

function knownReport() {
    return {
        auditReportVersion: 2,
        vulnerabilities: {
            "@next/eslint-plugin-next": vulnerability("@next/eslint-plugin-next", false, ["fast-glob"], ["eslint-config-next"]),
            braces: vulnerability("braces", false, [{ url: advisoryUrl }], ["micromatch"]),
            "eslint-config-next": vulnerability("eslint-config-next", true, ["@next/eslint-plugin-next"], []),
            "fast-glob": vulnerability("fast-glob", false, ["micromatch"], ["@next/eslint-plugin-next"]),
            micromatch: vulnerability("micromatch", false, ["braces"], ["fast-glob"]),
        },
    };
}

function vulnerability(name, isDirect, via, effects) {
    return {
        name,
        severity: "high",
        isDirect,
        via,
        effects,
        nodes: [`node_modules/${name}`],
    };
}

test("classifies only the exact known development advisory chain as an unresolved warning", () => {
    assert.deepEqual(classifyDevelopmentAudit(knownReport()), {
        ok: true,
        knownUnpatchedAdvisory: true,
    });
});

test("fails an additional critical advisory", () => {
    const report = knownReport();
    report.vulnerabilities.semver = vulnerability("semver", false, [{ url: "https://github.com/advisories/GHSA-unknown" }], []);
    report.vulnerabilities.semver.severity = "critical";
    assert.equal(classifyDevelopmentAudit(report).ok, false);
});

test("fails a severity escalation in the known chain", () => {
    const report = knownReport();
    report.vulnerabilities.braces.severity = "critical";
    assert.equal(classifyDevelopmentAudit(report).ok, false);
});

test("fails an additional advisory hidden on the allowed braces entry", () => {
    const report = knownReport();
    report.vulnerabilities.braces.via.push({ url: "https://github.com/advisories/GHSA-unknown" });
    assert.equal(classifyDevelopmentAudit(report).ok, false);
});

test("fails when the known advisory appears through another dependency path", () => {
    const report = knownReport();
    report.vulnerabilities.braces.nodes.push("node_modules/runtime-package/node_modules/braces");
    assert.equal(classifyDevelopmentAudit(report).ok, false);
});

test("fails audit infrastructure errors and malformed output", () => {
    assert.equal(evaluateAuditResult(2, "{}").ok, false);
    assert.equal(evaluateAuditResult(1, "registry unavailable").ok, false);
    assert.equal(classifyDevelopmentAudit({ error: { code: "EAI_AGAIN" } }).ok, false);
    for (const vulnerabilities of [[], "invalid"]) {
        assert.equal(evaluateAuditResult(0, JSON.stringify({ auditReportVersion: 2, vulnerabilities })).ok, false);
    }
});

test("passes a clean audit report", () => {
    assert.deepEqual(evaluateAuditResult(0, JSON.stringify({
        auditReportVersion: 2,
        vulnerabilities: {},
    })), { ok: true, knownUnpatchedAdvisory: false });
});
