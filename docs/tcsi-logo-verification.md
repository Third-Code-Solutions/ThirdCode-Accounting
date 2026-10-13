# TCSI logo update — 6 October 2026

- Replaced the header, footer, and product-preview text marks with the user-supplied TCSI PNG. Shared public headers and footers use the same component.
- The copied asset is unchanged: SHA-256 `f221db5104a3b39d0cb18e9313235a5582e993aee5a3a5a6300cd34a7d83b038`.
- Removed the placeholder background, padding, and corner clipping so the image retains its transparency and proportions. Adjacent brand text supplies the accessible name.
- Local `npm run lint` and `TCSI_PORTAL_ONLY=true npm run build:web` passed under Node 22.22.2.
- Standalone browser checks passed at 1440px and 390px in light and dark modes. All three images loaded at their native 512px resolution; rendered dimensions are 34px/30px. No page overflow or browser warning/error logs in tested flows. Footer was brought into view to verify lazy loading.
- Light remains the default; theme behavior and accounting workflows are unchanged.
- Release CI and production verification pending.
