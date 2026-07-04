import type { Edge, Node } from "@xyflow/react";
import type { DbdocsData, DagLayer, NodeRecord, ResourceType } from "@/lib/types";

/**
 * Canonical set of resource types belonging to each DAG layer. Mirrors the
 * `_CATALOG_RTYPES` / `_SEMANTIC_TYPES` / `_OTHER_TYPES` partitioning in
 * service.js so the graph bundle and the shell SPA agree on layer membership
 * without duplicating logic in JS-only string constants.
 *
 * Three disjoint bands: `catalog` (physical, database/schema-bearing), `semantic`
 * (the dbt Semantic Layer proper — metrics, semantic models, saved queries), and
 * `other` (typeless resources that aren't Semantic Layer: unit tests, exposures).
 */
export const CATALOG_RTYPES: ReadonlySet<ResourceType> = new Set([
  "model",
  "source",
  "seed",
  "snapshot",
  "analysis",
  "operation",
]);

export const SEMANTIC_RTYPES: ReadonlySet<ResourceType> = new Set([
  "metric",
  "semantic_model",
  "saved_query",
]);

export const OTHER_RTYPES: ReadonlySet<ResourceType> = new Set(["unit_test", "exposure"]);

const ALL_RTYPES: ReadonlySet<ResourceType> = new Set([
  ...CATALOG_RTYPES,
  ...SEMANTIC_RTYPES,
  ...OTHER_RTYPES,
]);

/** Returns the canonical set of resource types for the given DAG layer. */
export function layerTypes(layer: DagLayer): ReadonlySet<ResourceType> {
  if (layer === "semantic") return SEMANTIC_RTYPES;
  if (layer === "other") return OTHER_RTYPES;
  if (layer === "all") return ALL_RTYPES;
  return CATALOG_RTYPES;
}

/** Distinct non-empty schema names, sorted — shared by the DAG and ERD toolbars. */
export function sortedSchemas(schemas: Iterable<string>): string[] {
  return Array.from(new Set(schemas)).filter(Boolean).sort();
}

// Node box sizing for dagre. Lineage nodes are fixed.
const LINEAGE_SIZE = { width: 190, height: 40 };

export interface FlowResult {
  nodes: Node[];
  edges: Edge[];
  sizes: { id: string; width: number; height: number }[];
}

/**
 * Lineage DAG from the node-level lineage edges. When `keepIds` is given, only
 * those nodes (and edges between them) are built — the caller windows large
 * graphs to a tractable subset *before* layout, so dagre never sees 1000s of
 * nodes.
 */
export function buildDagFlow(data: DbdocsData, keepIds?: Set<string>): FlowResult {
  const records = data.nodes ?? {};
  const ids = Object.keys(records).filter((id) => !keepIds || keepIds.has(id));
  const nodes: Node[] = ids.map((id) => ({
    id,
    type: "lineage",
    position: { x: 0, y: 0 },
    data: { record: records[id] as NodeRecord },
  }));
  const edges: Edge[] = (data.lineage?.edges ?? [])
    .filter((e) => !keepIds || (keepIds.has(e.source) && keepIds.has(e.target)))
    .map((e, i) => ({
      id: `l${i}`,
      source: e.source,
      target: e.target,
      type: "smoothstep",
    }));
  const sizes = ids.map((id) => ({ id, ...LINEAGE_SIZE }));
  return { nodes, edges, sizes };
}

/**
 * The upstream+downstream neighborhood of a node, bounded to `maxDepth` hops in
 * each direction. Bounding keeps the focused DAG render tractable on large
 * (1000s-of-models) projects — an unbounded transitive closure can still pull in
 * the whole graph. `maxDepth = Infinity` walks the full closure.
 */
export function neighborhood(data: DbdocsData, focus: string, maxDepth = 2): Set<string> {
  const keep = new Set<string>([focus]);
  const parents = data.lineage?.parents ?? {};
  const children = data.lineage?.children ?? {};
  const walk = (id: string, map: Record<string, string[]>, depth: number) => {
    if (depth >= maxDepth) return;
    for (const next of map[id] ?? []) {
      if (!keep.has(next)) {
        keep.add(next);
        walk(next, map, depth + 1);
      }
    }
  };
  walk(focus, parents, 0);
  walk(focus, children, 0);
  return keep;
}
