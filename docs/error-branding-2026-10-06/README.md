# Error presentation verification — 6 October 2026

Scope: TCSI error presentation and the platform console's accounting-engine version label. This change does not claim to resolve the underlying operation that caused any particular server error.

## Reproduction

On the hosted workspace, opening the native RPC error component with a synthetic `Odoo Server Error` payload showed a branded detail title but the original product name in the message and stack heading. The shared error template read `props.message` directly; clipboard handlers did the same.

No failing financial operation was executed. Test dialogs only changed the browser's presentation.

## Candidate verification

- Three new JavaScript regression cases failed against the original patch. The completed suite passes 16 branding cases, including raw diagnostic identifier/path preservation, plus 8 palette/token cases.
- Seven Python branding checks and the 61-resource package validation pass. Scoped ESLint and `git diff --check` pass.
- The exact candidate JavaScript was loaded temporarily into the authenticated native browser runtime. The exact XML extension was processed through native `registerTemplateExtension`/`getTemplate`, then rendered with the existing Owl application.
- Server, client and network dialogs rendered TCSI titles. A validation warning retained its actual reason when the server supplied no arguments.
- The native copy button produced TCSI error headings while retaining exception class names, original diagnostic paths and the combined server/client traceback.
- Temporary patches were removed by reloading the test tab. The initially empty clipboard was restored. No accounting records were changed.
- Independent review found a risk of rewriting diagnostic identifiers in raw messages. The fix now limits diagnostic replacement to known product error headings, with regression coverage; re-review found no remaining blockers.

`candidate-server-error.png` records the native candidate render. Production release and verification are recorded below when completed.
