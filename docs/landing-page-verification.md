# Landing page verification — 6 October 2026

Candidate starts from production `55c58eb`. Scope is Next.js marketing UI and portal theme; no accounting addon, database, permission, or transaction changes.

## Local evidence

- Node 22.22.2; dependency install completed from existing lockfile.
- `npm run lint`: passed.
- `npm run typecheck`: passed (web, worker, contracts).
- `npm test`: 62 tests passed (contracts 4, worker 1, web 57 including theme preference tests).
- `node --test scripts/test-design-tokens.mjs scripts/test-branding.mjs`: 19 passed. Existing light/dark token values still match the accounting addon.
- `TCSI_PORTAL_ONLY=true npm run build:web`: passed; inspected with `next start` on port 3186. Port 3100 already served another checkout; that process was preserved.
- Rendered width checks: 320, 390, 768, 1024, 1440 in light and dark. No document overflow or out-of-bounds marketing text/controls.
- Browser emulating dark OS preference still started in light with no saved choice. Explicit dark toggle changed actual computed surface colors; preference survived reload.
- Preview keyboard navigation: ArrowRight selects Invoicing and moves focus; End selects Reporting; Home returns Overview. Invoice sample has four rows; report sample renders its amounts.
- FAQ disclosure opens and exposes its answer.
- axe-core WCAG 2 A/AA and 2.1 AA: zero violations in dark mobile and light desktop; 27 passing rules each. `aria-prohibited-attr` requires manual review (native SVG icons); this scan is not a full accessibility certification.
- No browser warning/error logs during inspected local homepage flows.

## Final release gates

Final theme store correction and mobile sign-in access added after initial build. Final build, navigation/keyboard checks, release CI and live deployment evidence are recorded below when complete. A demo form submission is deliberately not part of production smoke testing, avoiding a fictitious lead in the intake queue.
