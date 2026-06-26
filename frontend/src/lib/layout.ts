import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";

// Hierarchical left-to-right layout. For lineage this reads upstream → downstream;
// for ERDs, referenced → referencing — the conventional schema-diagram direction.
const DIRECTION = "LR";
const NODE_SEP = 60;
const RANK_SEP = 140;

export interface Sized {
  id: string;
  width: number;
  height: number;
}

export type LayoutEdge = { source: string; target: string };
export type Positions = Map<string, { x: number; y: number }>;

/**
 * A layout engine maps sized nodes + edges to top-left positions. `opts.centerId`
 * is the focal node for center-based engines (radial); engines that ignore it
 * (dagre) simply don't read it. `opts.direction` overrides the default rank
 * direction for the dagre engine. New engines register via `registerLayout` and
 * are selected by name with `resolveLayout`, so call sites pick a layout by name
 * instead of hardcoding which function to call.
 */
export type LayoutEngine = (
  sized: Sized[],
  edges: LayoutEdge[],
  opts?: { centerId?: string | null; direction?: string },
) => Positions;

const LAYOUTS = new Map<string, LayoutEngine>();

export function registerLayout(name: string, engine: LayoutEngine): void {
  LAYOUTS.set(name, engine);
}

/** Resolve a layout engine by name, falling back to dagre for an unknown name. */
export function resolveLayout(name: string): LayoutEngine {
  const engine = LAYOUTS.get(name) ?? LAYOUTS.get("dagre");
  if (!engine) throw new Error("No layout engine registered (dagre fallback missing).");
  return engine;
}

/** The node touched by the most edges — the natural hub to center a radial layout
 *  on when no explicit focus is set. Ties break on `sized` order (stable). */
export function mostConnected(sized: Sized[], edges: LayoutEdge[]): string | null {
  if (!sized.length) return null;
  const degree = new Map<string, number>(sized.map((s) => [s.id, 0]));
  for (const e of edges) {
    if (degree.has(e.source)) degree.set(e.source, degree.get(e.source)! + 1);
    if (degree.has(e.target)) degree.set(e.target, degree.get(e.target)! + 1);
  }
  let best = sized[0].id;
  let bestDeg = degree.get(best) ?? 0;
  for (const s of sized) {
    const d = degree.get(s.id) ?? 0;
    if (d > bestDeg) {
      best = s.id;
      bestDeg = d;
    }
  }
  return best;
}

export function layoutNodes(sized: Sized[], edges: { source: string; target: string }[], direction?: string): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: direction ?? DIRECTION, nodesep: NODE_SEP, ranksep: RANK_SEP, marginx: 24, marginy: 24 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const node of sized) {
    g.setNode(node.id, { width: node.width, height: node.height });
  }
  for (const edge of edges) {
    if (g.hasNode(edge.source) && g.hasNode(edge.target)) {
      g.setEdge(edge.source, edge.target);
    }
  }

  dagre.layout(g);

  // dagre returns centers; xyflow positions by top-left, so shift by half-size.
  const positions = new Map<string, { x: number; y: number }>();
  for (const node of sized) {
    const laid = g.node(node.id);
    if (laid) {
      positions.set(node.id, { x: laid.x - node.width / 2, y: laid.y - node.height / 2 });
    }
  }
  return positions;
}

const RADIAL_GAP_X = 36;
const RADIAL_GAP_Y = 60;

/**
 * Radial ("snowflake") layout for a focused ERD: the focus table sits at the
 * center and its FK-related tables fan out on concentric rings, one ring per BFS
 * hop distance over the undirected FK graph. Reads like a star/snowflake schema
 * — the conventional ERD shape — where dagre's top-to-bottom ranks waste space
 * and tangle on a many-relationship fact table.
 *
 * Ring radius separates the two node dimensions: tangential spacing (arc length
 * for nodes not to overlap each other) is driven by node *width*, while radial
 * clearance from the inner ring uses half the node *height* — so a tall
 * many-FK center table doesn't inflate the whole diagram on all sides.
 * Alternating rings are offset by half a slot so spokes don't line up radially.
 * A node unreachable over edges is parked one ring beyond the last so it still
 * gets a slot. Falls back to dagre when `centerId` isn't among `sized`.
 */
export function radialLayout(
  centerId: string,
  sized: Sized[],
  edges: { source: string; target: string }[],
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const byId = new Map(sized.map((s) => [s.id, s]));
  if (!byId.has(centerId)) return layoutNodes(sized, edges);

  const adj = new Map<string, Set<string>>();
  for (const s of sized) adj.set(s.id, new Set());
  for (const e of edges) {
    if (adj.has(e.source) && adj.has(e.target)) {
      adj.get(e.source)!.add(e.target);
      adj.get(e.target)!.add(e.source);
    }
  }
  const ring = new Map<string, number>([[centerId, 0]]);
  let frontier = [centerId];
  while (frontier.length) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const nb of adj.get(id) ?? []) {
        if (!ring.has(nb)) {
          ring.set(nb, ring.get(id)! + 1);
          next.push(nb);
        }
      }
    }
    frontier = next;
  }
  const maxRing = Math.max(0, ...Array.from(ring.values()));
  for (const s of sized) if (!ring.has(s.id)) ring.set(s.id, maxRing + 1);

  const rings = new Map<number, string[]>();
  for (const [id, r] of ring) {
    if (!rings.has(r)) rings.set(r, []);
    rings.get(r)!.push(id);
  }
  for (const ids of rings.values()) ids.sort();

  const center = byId.get(centerId)!;
  positions.set(centerId, { x: -center.width / 2, y: -center.height / 2 });

  let prevRadius = Math.max(center.width, center.height) / 2;
  const sortedRingNums = Array.from(rings.keys())
    .filter((r) => r > 0)
    .sort((a, b) => a - b);
  for (const r of sortedRingNums) {
    const ids = rings.get(r)!;
    const count = ids.length;
    const maxWidth = Math.max(...ids.map((id) => byId.get(id)!.width));
    const maxHeight = Math.max(...ids.map((id) => byId.get(id)!.height));
    // The ring must clear the inner ring along the largest node extent in *any*
    // direction — a node placed top/bottom needs height clearance, one placed
    // left/right needs width — so use the larger half-extent. Otherwise a tall
    // neighbor (a wide fact table) placed above/below a tiny focus overlaps it.
    const clearance = Math.max(maxHeight, maxWidth) / 2 + RADIAL_GAP_Y;
    const byArc = (count * (maxWidth + RADIAL_GAP_X)) / (2 * Math.PI);
    const radius = Math.max(prevRadius + clearance, byArc);
    // Offset alternating rings by half a slot so spokes don't line up radially,
    // but never for a ring of ≤2 (it would rotate the pair onto the vertical
    // axis, stacking tall nodes on top of the center).
    const angleOffset = r % 2 && count > 2 ? Math.PI / count : 0;
    ids.forEach((id, i) => {
      const angle = angleOffset + (2 * Math.PI * i) / count;
      const node = byId.get(id)!;
      positions.set(id, {
        x: Math.cos(angle) * radius - node.width / 2,
        y: Math.sin(angle) * radius - node.height / 2,
      });
    });
    prevRadius = radius + Math.max(maxHeight, maxWidth) / 2;
  }
  return positions;
}

export function applyPositions<T extends Node>(nodes: T[], positions: Map<string, { x: number; y: number }>): T[] {
  return nodes.map((n) => ({ ...n, position: positions.get(n.id) ?? { x: 0, y: 0 } }));
}

export function asLayoutEdges(edges: Edge[]): { source: string; target: string }[] {
  return edges.map((e) => ({ source: e.source, target: e.target }));
}

registerLayout("dagre", (sized, edges, opts) => layoutNodes(sized, edges, opts?.direction));

registerLayout("radial", (sized, edges, opts) => {
  const center = opts?.centerId ?? mostConnected(sized, edges);
  return center ? radialLayout(center, sized, edges) : layoutNodes(sized, edges);
});
