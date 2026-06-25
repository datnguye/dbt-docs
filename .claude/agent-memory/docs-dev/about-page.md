---
name: about-page
description: Pinned About link in the sidebar footer routes to renderAbout(); about_links and show_about are display-metadata config fields; footer_links was removed
metadata:
  type: project
---

The sidebar's pinned `#site-footer` contains an About link (above the coffee badge), gated `if (svc.meta().show_about !== false)` — the exact same pattern as `show_buy_me_a_coffee`. It routes in-app to `#/about`, so no `target=_blank`.

`renderAbout()` in `ui.js` is the `#/about` page renderer. It clears `app`, renders:
1. A JSON API section explaining `api/v1/` (accurate to what `_write_api` actually emits: index.json, nodes/<id>.json, lineage.json, health.json, column-lineage.json, schema/).
2. A CTA links section from `svc.aboutLinks()`, rendered only when non-empty.

Config fields (both display-metadata, NOT in `_NON_METADATA_FIELDS`, so they flow through `render_context()` into `metadata`):
- `show_about: bool = True`
- `about_links: list = []`

`service.js` accessor: `aboutLinks()` — DOM-free, guards `Array.isArray`.

The `info` icon (Lucide circle-info glyph) was added to `icons.css` + `KNOWN_ICONS` for the About link; the existing `api` icon is reused for the JSON API CTA on the page itself.

**Why:** `footer_links` was removed in the same change — CTAs belong on the About page, not scattered in the content footer.

**How to apply:** If adding more sidebar-footer pinned actions, mirror the `show_<thing> !== false` gate pattern. If extending the About page, add sections to `renderAbout()` in `ui.js`. The `about_links` shape is `[{label, href}]`.
