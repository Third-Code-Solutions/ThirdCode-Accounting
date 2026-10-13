import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const KNOWN_ADVISORY_URL = "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm";
const KNOWN_CHAIN = {
    "@next/eslint-plugin-next": {
        isDirect: false,
        via: ["fast-glob"],
        effects: ["eslint-config-next"],
        nodes: ["node_modules/@next/eslint-plugin-next"],
    },
    braces: {
        isDirect: false,
        via: [KNOWN_ADVISORY_URL],
        effects: ["micromatch"],
        nodes: ["node_modules/braces"],
    },
    "eslint-config-next": {
        isDirect: true,
        via: ["@next/eslint-plugin-next"],
        effects: [],
        nodes: ["node_modules/eslint-config-next"],
    },
    "fast-glob": {
        isDirect: false,
        via: ["micromatch"],
        effects: ["@next/eslint-plugin-next"],
        nodes: ["node_modules/fast-glob"],
    },
    micromatch: {
        isDirect: false,
        via: ["braces"],
        effects: ["fast-glob"],
        nodes: ["node_modules/micromatch"],
    },
};

const gatedSeverities = new Set(["high", "critical"]);

function sorted(values) {
    return [...values].sort();
}

function sameValues(actual, expected) {
    return Array.isArray(actual)
        && JSON.stringify(sorted(actual)) === JSON.stringify(sorted(expected));
}

export function classifyDevelopmentAudit(report) {
    if (!report || report.auditReportVersion !== 2 || !report.vulnerabilities
        || typeof report.vulnerabilities !== "object" || Array.isArray(report.vulnerabilities) || report.error) {
        return { ok: false, reason: "npm audit returned an invalid or error report" };
    }

    const gated = Object.entries(report.vulnerabilities)
        .filter(([, vulnerability]) => gatedSeverities.has(vulnerability?.severity));

    if (gated.length === 0) {
        return { ok: true, knownUnpatchedAdvisory: false };
    }

    if (!sameValues(gated.map(([name]) => name), Object.keys(KNOWN_CHAIN))) {
        return { ok: false, reason: "high/critical advisories differ from the single known development-only chain" };
    }

    const advisoryUrls = [];
    for (const [name, vulnerability] of gated) {
        const expected = KNOWN_CHAIN[name];
        const via = vulnerability.via?.map((item) => {
            if (typeof item === "string") return item;
            advisoryUrls.push(item?.url);
            return item?.url;
        });

        if (vulnerability.severity !== "high"
            || vulnerability.name !== name
            || vulnerability.isDirect !== expected.isDirect
            || !sameValues(via, expected.via)
            || !sameValues(vulnerability.effects, expected.effects)
            || !sameValues(vulnerability.nodes, expected.nodes)) {
            return { ok: false, reason: `unexpected dependency path or advisory data for ${name}` };
        }
    }

    if (!sameValues(advisoryUrls, [KNOWN_ADVISORY_URL])) {
        return { ok: false, reason: "expected exactly one known advisory in the development-only chain" };
    }

    return { ok: true, knownUnpatchedAdvisory: true };
}

export function evaluateAuditResult(exitCode, stdout) {
    if (exitCode !== 0 && exitCode !== 1) {
        return { ok: false, reason: `npm audit failed with exit code ${exitCode}` };
    }

    let report;
    try {
        report = JSON.parse(stdout);
    } catch {
        return { ok: false, reason: "npm audit did not return valid JSON" };
    }

    const classification = classifyDevelopmentAudit(report);
    if (!classification.ok) return classification;
    if (exitCode === 0 && classification.knownUnpatchedAdvisory) {
        return { ok: false, reason: "npm audit reported a high advisory but exited successfully" };
    }
    if (exitCode === 1 && !classification.knownUnpatchedAdvisory) {
        return { ok: false, reason: "npm audit failed without a classified high/critical advisory" };
    }
    return classification;
}

function main() {
    const onWindows = process.platform === "win32";
    const command = onWindows ? (process.env.ComSpec ?? "cmd.exe") : "npm";
    const args = onWindows
        ? ["/d", "/s", "/c", "npm audit --json --audit-level=high"]
        : ["audit", "--json", "--audit-level=high"];
    const audit = spawnSync(command, args, {
        encoding: "utf8",
        maxBuffer: 10 * 1024 * 1024,
    });

    if (audit.error || audit.status === null) {
        console.error(`Development dependency audit FAILED: ${audit.error?.message ?? "npm audit did not exit"}`);
        process.exitCode = 1;
        return;
    }

    const result = evaluateAuditResult(audit.status, audit.stdout);
    if (!result.ok) {
        console.error(`Development dependency audit FAILED: ${result.reason}`);
        if (audit.stderr) console.error(audit.stderr.trim());
        process.exitCode = 1;
        return;
    }

    if (result.knownUnpatchedAdvisory) {
        console.warn(`WARNING: unresolved ${KNOWN_ADVISORY_URL} remains in the installed eslint-config-next development-only chain. Check upstream for a compatible patched release.`);
    } else {
        console.log("Development dependency audit PASSED: no high or critical advisories.");
    }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
