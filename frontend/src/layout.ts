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

export function layoutNodes(sized: Sized[], edges: { source: string; target: string }[]): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: DIRECTION, nodesep: NODE_SEP, ranksep: RANK_SEP, marginx: 24, marginy: 24 });
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

export function applyPositions<T extends Node>(nodes: T[], positions: Map<string, { x: number; y: number }>): T[] {
  return nodes.map((n) => ({ ...n, position: positions.get(n.id) ?? { x: 0, y: 0 } }));
}

export function asLayoutEdges(edges: Edge[]): { source: string; target: string }[] {
  return edges.map((e) => ({ source: e.source, target: e.target }));
}
