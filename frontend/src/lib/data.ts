import type { Edge, Node } from "@xyflow/react";
import { colHandle, tableHandle } from "@/components/nodes/ErdTableNode";
import type { DbdocsData, ErdNodeRecord, NodeRecord } from "@/lib/types";

// Node box sizing for dagre. Lineage nodes are fixed; ERD table nodes grow with
// their column count so dagre reserves enough vertical space.
const LINEAGE_SIZE = { width: 190, height: 40 };
const ERD_WIDTH = 230;
const ERD_HEADER = 34;
const ERD_ROW = 22;

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
 * Count the rows an ERD node renders: in compact mode only its key (PK/FK)
 * columns show (plus a "+N more" row when others are hidden), falling back to all
 * columns when none are keyed. Mirrors `visibleColumns` in ErdTableNode so the
 * laid-out node box matches what's drawn.
 */
function erdRowCount(record: ErdNodeRecord, compact: boolean): number {
  const all = record.columns ?? [];
  if (!compact) return Math.max(1, all.length);
  const keyed = all.filter((c) => c.is_primary_key || c.is_foreign_key);
  if (!keyed.length) return Math.max(1, all.length);
  return keyed.length + (all.length > keyed.length ? 1 : 0);
}

/**
 * ERD flow — optionally restricted to a pre-computed keep set. When `keepIds` is
 * given, only those nodes (and edges between them) are built. When `focus` is
 * provided, that node's `data.focused` flag is set so the SPA can highlight it.
 * `compact` renders only key columns per node so a wide fact table stays small
 * enough for the radial layout to read.
 */
export function buildErdFlow(
  data: DbdocsData,
  focus?: string | null,
  compact = false,
  keepIds?: Set<string>,
): FlowResult {
  const erd = data.erd ?? { nodes: [], edges: [] };
  let nodeRecords: ErdNodeRecord[] = erd.nodes;
  let edges = erd.edges;

  if (keepIds) {
    nodeRecords = erd.nodes.filter((n) => keepIds.has(n.id));
    edges = erd.edges.filter((e) => keepIds.has(e.source) && keepIds.has(e.target));
  }

  const nodes: Node[] = nodeRecords.map((record) => ({
    id: record.id,
    type: "erdTable",
    position: { x: 0, y: 0 },
    data: { record, focused: record.id === focus, compact },
  }));

  // Which columns each table actually exposes (a join column may be absent from
  // the catalog) so we can fall back to the table-level handle.
  const columnIndex = new Map<string, Set<string>>(
    nodeRecords.map((n) => [n.id, new Set((n.columns ?? []).map((c) => c.name))]),
  );
  const has = (nodeId: string, col: string): boolean => columnIndex.get(nodeId)?.has(col) ?? false;

  // The column each endpoint exposes for this pair, picking whichever of the two
  // candidate names the endpoint owns — dbterd's from/to column order doesn't
  // always match source/target, and a join can name the FK and PK columns
  // differently. Falls back to the table-level handle when neither is present.
  const owned = (nodeId: string, ...cands: (string | undefined)[]): string | undefined =>
    cands.find((c) => c && has(nodeId, c));

  // Composite FKs join on N columns; render one connector per column pair so the
  // arrows land on the exact joined rows instead of one table-to-table line.
  const flowEdges: Edge[] = [];
  for (const e of edges) {
    const from = e.from_columns ?? [];
    const to = e.to_columns ?? [];
    const pairs = Math.max(from.length, to.length, 1);
    for (let i = 0; i < pairs; i++) {
      const fromCol = from[i] ?? from[0];
      const toCol = to[i] ?? to[0];
      const sourceCol = owned(e.source, toCol, fromCol);
      const targetCol = owned(e.target, fromCol, toCol);
      // Default to right-out → left-in; GraphApp re-picks the side per edge once
      // node positions are known (data.sourceCol/targetCol drive that choice).
      flowEdges.push({
        id: `${e.id}__${i}`,
        source: e.source,
        target: e.target,
        sourceHandle: sourceCol ? colHandle(sourceCol, "out", "r") : tableHandle("out", "r"),
        targetHandle: targetCol ? colHandle(targetCol, "in", "l") : tableHandle("in", "l"),
        type: "smoothstep",
        animated: e.type === "n1",
        data: { sourceCol: sourceCol ?? null, targetCol: targetCol ?? null },
      });
    }
  }
  const sizes = nodeRecords.map((n) => ({
    id: n.id,
    width: ERD_WIDTH,
    height: ERD_HEADER + erdRowCount(n, compact) * ERD_ROW,
  }));
  return { nodes, edges: flowEdges, sizes };
}

/**
 * Re-pick each ERD edge's source/target handle side once node positions are
 * known: the edge leaves the source from whichever side faces the target and
 * enters the target from the side facing the source (compared by node center-x).
 * Each column row has handles on both sides (see ErdTableNode), so the line stays
 * row-precise but takes the short path instead of always exiting right / entering
 * left. Falls back to the table-level handle on that side when the edge had no
 * resolved column. Pure: returns new edges, doesn't mutate the input.
 */
export function assignErdEdgeSides(
  edges: Edge[],
  positions: Map<string, { x: number; y: number }>,
  sizes: { id: string; width: number; height: number }[],
): Edge[] {
  const centerX = new Map<string, number>();
  for (const s of sizes) {
    const p = positions.get(s.id);
    if (p) centerX.set(s.id, p.x + s.width / 2);
  }
  return edges.map((e) => {
    const sx = centerX.get(e.source);
    const tx = centerX.get(e.target);
    if (sx === undefined || tx === undefined) return e;
    const sourceSide: "l" | "r" = tx >= sx ? "r" : "l";
    const targetSide: "l" | "r" = sx >= tx ? "r" : "l";
    const d = (e.data ?? {}) as { sourceCol?: string | null; targetCol?: string | null };
    return {
      ...e,
      sourceHandle: d.sourceCol ? colHandle(d.sourceCol, "out", sourceSide) : tableHandle("out", sourceSide),
      targetHandle: d.targetCol ? colHandle(d.targetCol, "in", targetSide) : tableHandle("in", targetSide),
    };
  });
}

/**
 * The N-hop undirected FK neighborhood of a focus node in the ERD graph.
 * Analogous to `neighborhood` for the DAG, but over the ERD's undirected FK
 * edges (both source→target and target→source are traversed). `depth` bounds
 * the BFS so a deeply-connected fact table doesn't pull in the whole schema.
 */
export function erdNeighborhood(data: DbdocsData, focus: string, depth = 1): Set<string> {
  const keep = new Set<string>([focus]);
  const erd = data.erd ?? { nodes: [], edges: [] };
  const adj = new Map<string, Set<string>>();
  for (const e of erd.edges) {
    if (!adj.has(e.source)) adj.set(e.source, new Set());
    if (!adj.has(e.target)) adj.set(e.target, new Set());
    adj.get(e.source)!.add(e.target);
    adj.get(e.target)!.add(e.source);
  }
  const walk = (id: string, remaining: number) => {
    if (remaining <= 0) return;
    for (const nb of adj.get(id) ?? []) {
      if (!keep.has(nb)) {
        keep.add(nb);
        walk(nb, remaining - 1);
      }
    }
  };
  walk(focus, depth);
  return keep;
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
