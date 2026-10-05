# Platform console verification — 6 October 2026

## Release

[PR #14](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/pull/14) merged as `67d3bf8d2a3c5273d3afbca6d2cd514bcff41451`. Railway deployment `3c422238-bf32-48b3-b83b-2b6c52df649e` became active. The live portal reports module `18.0.2.14.0`; `/updates` and the homepage return HTTP 200.

Final candidate `1ffdf42fcc8d3e577e3639c99e39e899c2a0d96f` passed [CI 37383374265](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37383374265): verify, hosted-runtime and orvexa-integration. The equivalent code candidate `916157b` ran 138 native tests and 59 accounting integration checks with zero failures/errors. Hosted HTTP tests used a disposable database and proved real organization/baseline/administrator creation, tenant isolation, private RPC denial, published snapshot isolation and exception capture after rollback.

Local lint, typecheck, 60 web tests, production build and six deferred-controller regression tests passed. Production dependency audit reported zero vulnerabilities; the development tree has pre-existing ESLint advisories. Independent security and UI source reviews completed; actionable findings were corrected and regression-tested.

## Recovery and migration

A fresh paired database/filestore capture was taken from production `4ce5ba0` before rollout. The bounded writer pause lasted 6.59 seconds; capture completed in 10.224 seconds. The encrypted 73,329,214-byte artifact was downloaded off-host and decrypted locally; all 1,304 manifest hashes passed.

Encrypted artifact SHA256: `d73a16ebd6f0cc51c6965b4f2ac1fc7685e1680a63b2ea898b58790b913d6e84`.

The capture restored into an isolated, precreated database in 34.381 seconds and upgraded using the exact final candidate tree. Read-only conservation verification passed: all original accounting, audit and company rows, ledger balances, attachment contents and business metadata, and 504 referenced files were preserved. The explicitly bounded differences were 14 existing branding-image `write_date` updates and five new private-company logo attachments. Owner identities, required groups and private company membership passed. The restored copy remained neutralized, without active cron jobs.

This proves this manual recovery capture and isolated upgrade. It does not establish ongoing backup alert delivery, contractual RPO/RTO or provider image retention. Sensitive backup material and detailed evidence remain outside the public repository.

## Live verification

At 2026-10-05 23:00 UTC, fresh owner sign-in succeeded. Owner company membership was exactly the private platform home; it had no customer memberships and was excluded from customer organization/people lists. All eight read console methods passed for the owner. A tenant administrator was denied all eight methods, including with forged setup context. Public website data contained only the `seo` and `releases` allowlist; no content was published.

Native browser verification rendered all six console sections. Organization and employee dialogs opened and canceled correctly. Real organization, people and accounting audit rows loaded. SEO input updated the unsaved preview; the changelog editor exposed title, details, version and category. No client records or public content were created for these production checks; side effects were exercised in disposable hosted CI.

At 390px, the settled native layout had page width 390px and no horizontal page overflow. Organization tables scrolled inside their own panel; first-cell left edge was 13px inside a panel beginning at 12px. Desktop first-cell bounds were also inside the native container. An initial snapshot during the native shell resize transition was not treated as the final layout.

Dark-mode verification found native explicit heading colors overriding inherited console ink. A scoped `tcsi_routes.scss` correction targets only console h1/h2, preserving preview h3. Applied temporarily against the native runtime, it changed all affected headings from `rgb(33,37,41)` to the existing dark ink `rgb(237,242,248)`. Independent review and package validation passed. Final deployed contrast verification is recorded after the follow-up release.

The only captured browser connection error preceded the completed backend rollout; no console rendering errors were observed afterward. First-party monitoring covers server dispatch failures, scheduled jobs and sign-in lockouts; browser error collection, external uptime/CPU probes and alert delivery are not implemented.
