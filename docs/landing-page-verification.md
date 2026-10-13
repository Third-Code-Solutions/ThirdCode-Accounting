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

## Final local candidate

- Full `TCSI_PORTAL_ONLY=true npm run build` (web + worker) passed after theme-store/mobile sign-in fixes. Subsequent form/contrast CSS correction passed `npm run build:web` again.
- Final browser checks use the generated standalone server with its static/public assets on port 3186.
- All five public routes (`/`, `/contact`, `/platform`, `/controls`, `/pilot`) passed axe WCAG 2 A/AA + 2.1 AA scans in both themes at 390px: **10 route/theme combinations, zero violations**. Raw results: `landing-page-evidence/public-route-checks.json`.
- Final homepage layout passed all five widths in both themes with no overflowing content. Raw results: `landing-page-evidence/responsive-checks.json`.
- Enter/Space operate theme button. Cached client navigation from home to contact retains the actual theme and correct accessible label. Form input entered text remains readable; no lead was submitted.
- Reduced-motion emulation yields `0s` transition duration. Homepage has one H1. Mobile navigation exposes Sign in.
- Public form's hard-coded light panel/input backgrounds and dark section-index colors were corrected. Color interpolation on navigation/CTAs was removed to avoid momentary low contrast on theme changes.
- No warning/error logs during final tested browser flows. axe injection and media emulation were cleared by reload/reset.
