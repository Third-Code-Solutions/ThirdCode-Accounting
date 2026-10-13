# TCSI landing page — 6 October 2026

## Job and conversion plan

Help a company finance lead understand the product, assess fit, and request a relevant demo. Primary action: existing `/contact` demo intake. Returning customers get a distinct `/web/login` sign-in link. Public access remains invitation-based; a demo request is not a workspace registration.

Structure: outcome-led hero, clearly labeled interactive sample workspace, complete core capability inventory, controls and role story, Orvexa boundaries, guided rollout, buyer FAQs, final demo invitation. No invented customers, testimonials, performance numbers, certifications, tax approval, or self-service subscription claims.

Design references inspected 6 October 2026: https://linear.app (product-led hierarchy and contextual UI previews), https://ramp.com (finance outcomes and clear sales conversion). These inform hierarchy only; TCSI retains its own content, layout, light/dark palette, and identity. Minimal typography, restrained purple accents, fine borders, generous but deliberate spacing; no stock photography or decorative gradients.

## Acceptance criteria

- Core modules reflect the deployed accounting implementation: ledger/journals, invoices/credits, bills/payments, bank reconciliation, expenses, contacts/products, recurring work, reporting/statements, tax configuration, periods/year-end, roles/audit/company scope, migration and Orvexa.
- Light is the default independent of OS preference. A visible keyboard-accessible switch persists an explicit preference across reloads and public routes. Server reads validated cookie to avoid a theme flash.
- Preview tabs and FAQ disclosures work with pointer and keyboard. Fictional figures are labeled as sample data. No sample UI issues actual accounting operations.
- Desktop, tablet and phone layouts at 320/390/768/1024/1440px have no document overflow or overlapping controls. Reduced motion respected; text/control contrast checked.
- Existing demo intake, sign-in and accounting proxy stay intact. Verify CTA navigation without submitting a fake lead to production.
- Lint, typecheck, relevant unit and branding/token regressions, production build, browser inspection and production smoke checks pass. Record actual deployment revision and URL.

## Scope

Next.js public marketing presentation, metadata and portal theme only. Accounting addon, database, permissions and business workflows remain outside the change. Existing company tax, migration and report acceptance requirements must not be presented as completed certifications.
