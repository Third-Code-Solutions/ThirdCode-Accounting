# Settings navigation in the main workspace sidebar

Move the Settings application selector and live section links into the main workspace sidebar. Remove the duplicate General Settings entry while retaining Users & Companies administration shortcuts. Hide the inner panel only when the shared sidebar is present; preserve the native fallback, fields, Save/Discard, search, permissions, and application switching. The existing mobile drawer supplies the same navigation.

The SettingsPage publishes lifecycle and section updates through a service. The branding service renders those links in the existing sidebar; section selection only scrolls/focuses the native heading. Leaving Settings detaches the page and restores ordinary workspace navigation. Active state follows scrolling, including the final section at the bottom.

Verification checkpoint: 59 focused tests pass; package validation and production Sass compilation pass. Native SettingsPage + native CSS preview confirms the inner panel is hidden, the content starts at the main sidebar edge, section focus works, and switching applications refreshes the main section list. Native fields in the preview are static fixtures; live server verification follows CI/deployment.
