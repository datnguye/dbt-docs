# Agent Memory Index

- [Static REST api/v1 surface](static-api-v1-surface.md) — `api/v1/` JSON tree written from the same data dict; `_write_api` after copytree; `_serialize` DRYs serialization
- [Node detail fields](node-detail-fields.md) — 11 new node-record keys from manifest + catalog stats; depends-on/referenced-by derived client-side from the lineage graph
- [Per-column defined tests](per-column-tests.md) — column records carry `tests: [type, ...]` via `build_column_tests_index`; shared `manifest_test_node_metadata` helper DRYs the health extractor
- [Non-physical resource nodes](non-physical-resource-nodes.md) — metrics/semantic_models/saved_queries/unit_tests/exposures/analyses/operations as first-class nav pages; `COLLECTION_ATTRS` mapping; Semantic Layer tree bucket; macros excluded
- [Semantic-layer rendering](semantic-layer-rendering.md) — extraction cleanup (enum `.value`, object `.name`, `schema_name`) and client-side cross-linking (metric↔metric, metric↔semantic_model, sm→metrics) via service.js accessors
- [Nav 2-tab redesign](nav-tab-redesign.md) — typeless nodes no longer faked into the db tree; sidebar uses a Catalog + Semantic Layer 2-tab strip; `resourceTabs()`/`semanticLayerSections()`/`isCatalogNode()` in service.js
- [DAG layer segmented control](dag-layer-filter.md) — DAG toolbar Catalog | Semantic Layer | Both control; `layerTypes()` in `frontend/src/lib/data.ts` is the canonical partition; hash back-compat via default `layer="catalog"`
- [saved_query group_by string format](group-by-string-format.md) — manifest stores `group_by`/`where` items pre-stringified (`"Entity('customer')"`); `_object_name` + `_ENTITY_REPR` regex unwraps them, plain strings pass through
