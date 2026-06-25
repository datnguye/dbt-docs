---
name: nav-tab-redesign
description: Typeless resource nodes no longer faked into the db tree; sidebar uses a 2-tab strip (Catalog + Semantic Layer with collapsible sub-sections)
metadata:
  type: project
---

Typeless nodes used to carry `database = "Semantic Layer"` and `schema = resource_type` so `build_tree` could slot them into the nav. This corrupted the Details panel and was semantically wrong. A 5-tab per-type strip was then simplified to 2 tabs after feedback.

**Why:** The Semantic Layer bucket was a nav hack. The 5-tab strip was too noisy for projects with only a few SL types.

**How to apply:**
- `_metric_record` etc. all set `database=""` and `schema=""`.
- `build_tree` skips non-physical prefixes (`_PHYSICAL_PREFIXES = NODE_PREFIXES + CODE_ONLY_PREFIXES + ("source.",)`).
- `service.js` exports `resourceTabs()` (2 tabs max: `"catalog"` + `"semantic"`), `semanticLayerSections()` (per-type ordered list for Semantic Layer panel), `nodesByResourceType(rtype)`, `isCatalogNode(id)`.
- `ui.js`: 2-tab strip. localStorage "dbdocs-nav-tab" valid values: `"catalog"` | `"semantic"` only — other stored values fall back to `"catalog"`. Semantic Layer panel = one `<details open>` per section (via `_buildSemanticPanel`). `highlightNav` switches to `"semantic"` and force-opens the matching sub-section.
- `_SEMANTIC_LAYER_DB` constant deleted from `nodes.py`.
- 414 tests, 100% coverage.
