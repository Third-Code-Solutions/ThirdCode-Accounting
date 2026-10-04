# Deployment attempt — 5 October 2026, Asia/Manila

> Continuation: Railway browser-console access is now available. The combined PR #6/#7 candidate passed CI, a coordinated encrypted off-host backup was verified, and the production copy restored and upgraded successfully in isolation. See the [current release checkpoint](../verification.md#unmerged-release-preparation--5-october-2026). The observations below preserve the earlier blocked attempt; they no longer describe current operator access. Live deployment verification follows the merge.

The product owner explicitly requested pushing and deploying the candidate to live production. The candidate through `8ff19d373f7c32893a90de73d0328b91104ad121` was successfully pushed to `release/accounting-18.0.2.13.0`, with [draft PR #7](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/pull/7) targeting `main`. There are nine implementation/evidence commits after the production baseline. This follow-up record changes documentation only.

## Fresh observations

- Git fetch succeeded; `origin/main` remains `25b91a7b68fc65b0d36618018cc48b86ca2672f3`. GitHub confirms repository push access.
- Vercel production alias `tcsi-accounting-portal.vercel.app` resolves in deployment metadata to `dpl_8jQqpmq39da1sFAUZaxe9uwUnHPg`, READY, production target, baseline SHA above. Team is `team_n60dl3ccO8BFGFeUKQdqPhp3`; project is `prj_7SbH7mYTyTiluJNSwMsiQVEtnDIm`.
- The branch push automatically started Vercel preview `dpl_9F7PdBtzYeockNxCp1xH9fd3W5qU`. A portal preview is not an isolated accounting engine: existing proxy configuration can route accounting requests to Railway. No synthetic accounting writes were made through the preview.
- PR CI started as [run 37237657300](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37237657300). Its live result belongs to GitHub; an in-progress run is not a passing release gate.
- Managed environment observations are current: no configured Railway secret bindings or outbound identities. No Railway connector, CLI, local Railway configuration, Railway token or Odoo operator credential is available in this workspace. Vercel access does not grant Railway administration or a ledger backup.
- `docker/odoo/cloud_start.py` automatically runs the module upgrade before serving requests when the deployed manifest version exceeds the installed module version. Actual Railway branch integration, installed version, production companies, volume and recovery configuration cannot be inspected with the available access.

## Why production was not changed

The user's implementation brief requires: "Before deployment ... Rehearse database/module upgrades against an isolated representative copy" and "Verify a recoverable database/filestore backup." It also says: "If a release gate fails, resolve it or report the specific blocker. Do not deploy an unverified accounting change to claim completion."

Local synthetic tests and restore evidence are complete, but they do not establish production backup or recoverability. Pushing `main` could trigger a live module/database upgrade through Railway's integration. The release branch was therefore published without updating `main`, merging the PR or promoting the portal to production. This is an access/recovery blocker, not a request to repeat deployment authorization.

## Required continuation

Provide authenticated operator access in a secure environment to Railway project `4af92f83-8aa1-4135-9eeb-c6bcf9f7cbc8`, its production engine/database/volume, and its recovery facilities. Do not place credentials in chat or this repository. Follow [HOSTED-OPERATIONS.md](HOSTED-OPERATIONS.md) to inspect the installed runtime, quiesce writers, capture the complete database/filestore/configuration recovery bundle, restore and reconcile an isolated copy, rehearse the candidate upgrade, and establish transaction-preserving recovery. Then release the reviewed revision and verify the installed module and ledger read-only.
