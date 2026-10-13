# Founder console access

Objective: only the explicitly designated platform owner can access the owner console; company administrators keep accounting access, without platform authority.

Observed production 2026-10-06: among 54 active/archived users only superadmin uid52 has both protected owner flag and console group. Its sole company is private home15. All10 trial administrators denied8 console read APIs and a forged platform-company context (80+10 denials); founder passes8. Inactive installer uid1 remains a trusted maintenance identity. Pilot system administrator uid2 has no owner flag/console group.

Gap: direct /workspace/console URL still serves an empty owner interface to tenant users despite server RPC denial. Implement authenticated route-level403 and hide owner shell until server-authorized data loads; keep existing authority predicate and accounting membership unchanged.

Acceptance: owner HTTP200, tenant403 for canonical/trailing/nested console paths, anonymous login redirect, tenantRPC denials retained; UI access-denied and owner rendering verified. Independent review and full CI before production rollout. No account deletion or permission expansion.

Progress: implemented;8 local JS tests pass; package validation pending; hosted route tests await CI. No production changes yet.
