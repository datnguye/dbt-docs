---
name: dag-layer-filter
description: DAG toolbar layer segmented control (Catalog | Semantic Layer | Both) added 2026-06-24; layerTypes() helper in data.ts is the canonical partition; back-compat via default="catalog"
metadata:
  type: project
---

DAG toolbar now has a layer segmented control (Catalog | Semantic Layer | Both) added 2026-06-24. Default is Catalog.

**Why:** The flat multi-select was mixing physical and semantic-layer types as visual equals. The segmented control aligns the DAG filter with the sidebar's 2-tab mental model (`resourceTabs()` in service.js).

**How to apply:** 
- `CATALOG_RTYPES` / `SEMANTIC_RTYPES` / `layerTypes(layer)` in `frontend/src/lib/data.ts` are the canonical partition — import from there, don't duplicate in GraphApp.tsx.
- `buildDagHash(focusId, rtype, schema, layer)` — `layer` param is 4th, defaults to `"catalog"`, omitted from URL when it's the default.
- Hash back-compat: old `#/dag?rtype=model` links with no `layer=` param parse `layer=undefined` → `parseLayer(undefined)` → `"catalog"`. No migration needed.
- `layerMountedRef` in GraphApp prevents the layer-change `useEffect` from resetting `rtype` on initial mount (would wipe URL-seeded rtype).
- `RtypeDropdown` now receives `layer` prop and `catalogOptions`/`semanticOptions` separately; `activeOptions` is derived inside the component.
- Non-model nodes get a colored badge in `LineageNode.tsx` (e.g. "mtrc", "sm", "sq") so cross-layer edges are visually distinguishable when layer=both.
- Shell: `graphMount()` and `renderDag()` in `ui.js` accept `layer` as 7th/4th param and set `data-layer` on the host div; `main.tsx` reads `el.dataset.layer`.
- `DagLayer` type exported from `types.ts`.
- Pre-existing E2E flaky test: "a non-name hit shows a match-reason snippet" — MiniSearch sometimes returns Description before Column for count_food_items; unrelated to this change.
