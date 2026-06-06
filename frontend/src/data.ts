import type { Edge, Node } from "@xyflow/react";
import { inHandle, outHandle, TABLE_IN, TABLE_OUT } from "./nodes/ErdTableNode";
import type { DbdocsData, ErdNodeRecord, NodeRecord } from "./types";

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

/** Full lineage DAG from the node-level lineage edges. */
export function buildDagFlow(data: DbdocsData): FlowResult {
  const records = data.nodes ?? {};
  const ids = Object.keys(records);
  const nodes: Node[] = ids.map((id) => ({
    id,
    type: "lineage",
    position: { x: 0, y: 0 },
    data: { record: records[id] as NodeRecord },
  }));
  const edges: Edge[] = (data.lineage?.edges ?? []).map((e, i) => ({
    id: `l${i}`,
    source: e.source,
    target: e.target,
    type: "smoothstep",
  }));
  const sizes = ids.map((id) => ({ id, ...LINEAGE_SIZE }));
  return { nodes, edges, sizes };
}

/** ERD flow — optionally restricted to a focus node + its directly-related tables. */
export function buildErdFlow(data: DbdocsData, focus?: string | null): FlowResult {
  const erd = data.erd ?? { nodes: [], edges: [] };
  let nodeRecords: ErdNodeRecord[] = erd.nodes;
  let edges = erd.edges;

  if (focus) {
    const keep = new Set<string>([focus]);
    for (const e of erd.edges) {
      if (e.source === focus) keep.add(e.target);
      if (e.target === focus) keep.add(e.source);
    }
    nodeRecords = erd.nodes.filter((n) => keep.has(n.id));
    edges = erd.edges.filter((e) => keep.has(e.source) && keep.has(e.target));
  }

  const nodes: Node[] = nodeRecords.map((record) => ({
    id: record.id,
    type: "erdTable",
    position: { x: 0, y: 0 },
    data: { record, focused: record.id === focus },
  }));

  // Which columns each table actually exposes (a join column may be absent from
  // the catalog) so we can fall back to the table-level handle.
  const columnIndex = new Map<string, Set<string>>(
    nodeRecords.map((n) => [n.id, new Set((n.columns ?? []).map((c) => c.name))]),
  );
  const has = (nodeId: string, col: string): boolean => columnIndex.get(nodeId)?.has(col) ?? false;

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
      flowEdges.push({
        id: `${e.id}__${i}`,
        source: e.source,
        target: e.target,
        sourceHandle: fromCol && has(e.source, fromCol) ? outHandle(fromCol) : TABLE_OUT,
        targetHandle: toCol && has(e.target, toCol) ? inHandle(toCol) : TABLE_IN,
        type: "smoothstep",
        animated: e.type === "n1",
      });
    }
  }
  const sizes = nodeRecords.map((n) => ({
    id: n.id,
    width: ERD_WIDTH,
    height: ERD_HEADER + Math.max(1, (n.columns ?? []).length) * ERD_ROW,
  }));
  return { nodes, edges: flowEdges, sizes };
}

/** The upstream+downstream neighborhood of a node (for DAG focus highlighting). */
export function neighborhood(data: DbdocsData, focus: string): Set<string> {
  const keep = new Set<string>([focus]);
  const parents = data.lineage?.parents ?? {};
  const children = data.lineage?.children ?? {};
  const walk = (id: string, map: Record<string, string[]>) => {
    for (const next of map[id] ?? []) {
      if (!keep.has(next)) {
        keep.add(next);
        walk(next, map);
      }
    }
  };
  walk(focus, parents);
  walk(focus, children);
  return keep;
}
