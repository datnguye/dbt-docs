import { useMemo, useState, type ReactElement } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type EdgeMouseHandler,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import { buildDagFlow, buildErdFlow, neighborhood } from "./data";
import { applyPositions, asLayoutEdges, layoutNodes } from "./layout";
import { ErdTableNode } from "./nodes/ErdTableNode";
import { LineageNode } from "./nodes/LineageNode";
import type { DbdocsData, GraphMode } from "./types";

const nodeTypes = { lineage: LineageNode, erdTable: ErdTableNode };

interface Props {
  mode: GraphMode;
  focus?: string | null;
  data: DbdocsData;
  onOpenNode?: (id: string) => void;
}

function uniqueSchemas(data: DbdocsData): string[] {
  const set = new Set<string>();
  for (const id of Object.keys(data.nodes ?? {})) set.add(data.nodes[id].schema);
  return Array.from(set).sort();
}

export function GraphApp({ mode, focus, data, onOpenNode }: Props): ReactElement {
  const isDag = mode === "dag";
  // The global ERD (overview) can be unlocked for pan/zoom; the per-node ERD is
  // always locked. The DAG is always interactive.
  const [unlocked, setUnlocked] = useState(false);
  const canUnlock = mode === "erd";
  const interactive = isDag || (canUnlock && unlocked);
  const locked = !interactive;
  // The incoming `focus` is a unique_id (from "View in DAG"). Seed the search box
  // with that node's *label* so the box is readable and the highlight resolves.
  const initialLabel = focus && data.nodes?.[focus] ? data.nodes[focus].label : (focus ?? "");
  const [search, setSearch] = useState(initialLabel);
  const [rtype, setRtype] = useState("");
  const [schema, setSchema] = useState("");
  // A clicked edge highlights itself + its two tables (dimming the rest).
  const [selectedEdge, setSelectedEdge] = useState<{ source: string; target: string } | null>(null);

  // Resolve the search box to a focus id: a known unique_id wins outright, else
  // match by label (exact, then prefix).
  const focusId = useMemo(() => {
    if (!isDag) return focus ?? null;
    const q = search.trim().toLowerCase();
    if (!q) return null;
    const ids = Object.keys(data.nodes ?? {});
    return (
      ids.find((id) => id.toLowerCase() === q) ??
      ids.find((id) => data.nodes[id].label.toLowerCase() === q) ??
      ids.find((id) => data.nodes[id].label.toLowerCase().startsWith(q)) ??
      null
    );
  }, [isDag, search, focus, data]);

  const { nodes, edges } = useMemo(() => {
    const flow = isDag ? buildDagFlow(data) : buildErdFlow(data, mode === "erd-node" ? focus : null);
    const positions = layoutNodes(flow.sizes, asLayoutEdges(flow.edges));
    let laidNodes = applyPositions(flow.nodes, positions);
    let laidEdges = flow.edges;

    if (isDag) {
      const hot = focusId ? neighborhood(data, focusId) : null;
      laidNodes = laidNodes
        .filter((n) => {
          const rec = data.nodes[n.id];
          if (rtype && rec.resource_type !== rtype) return false;
          if (schema && rec.schema !== schema) return false;
          return true;
        })
        .map((n) => ({
          ...n,
          data: { ...n.data, dimmed: hot ? !hot.has(n.id) : false, focused: n.id === focusId },
        }));
      const visible = new Set(laidNodes.map((n) => n.id));
      laidEdges = flow.edges
        .filter((e) => visible.has(e.source) && visible.has(e.target))
        .map((e) => {
          const inHot = hot && hot.has(e.source) && hot.has(e.target);
          return {
            ...e,
            animated: !!inHot,
            style: hot
              ? inHot
                ? { stroke: "var(--accent, #2f6feb)", strokeWidth: 2 }
                : { opacity: 0.12 }
              : undefined,
          };
        });
    } else if (selectedEdge) {
      // ERD edge selected: highlight that relationship + its two tables; dim rest.
      const lit = new Set([selectedEdge.source, selectedEdge.target]);
      laidNodes = laidNodes.map((n) => ({ ...n, data: { ...n.data, dimmed: !lit.has(n.id) } }));
      laidEdges = flow.edges.map((e) => {
        const on = e.source === selectedEdge.source && e.target === selectedEdge.target;
        return {
          ...e,
          animated: on,
          style: on
            ? { stroke: "var(--accent, #2f6feb)", strokeWidth: 2.5 }
            : { opacity: 0.1 },
        };
      });
    }
    return { nodes: laidNodes as Node[], edges: laidEdges as Edge[] };
  }, [isDag, mode, focus, focusId, data, rtype, schema, selectedEdge]);

  const onNodeClick: NodeMouseHandler = (_e, node) => {
    if (onOpenNode) onOpenNode(node.id);
  };
  const onEdgeClick: EdgeMouseHandler = (_e, edge) => {
    // Toggle: clicking the lit relationship clears it.
    setSelectedEdge((prev) =>
      prev && prev.source === edge.source && prev.target === edge.target
        ? null
        : { source: edge.source, target: edge.target },
    );
  };
  const onPaneClick = () => setSelectedEdge(null);

  return (
    <div className="dbd-graph">
      {isDag && (
        <div className="dbd-toolbar">
          <input
            placeholder="Focus a node…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select value={rtype} onChange={(e) => setRtype(e.target.value)}>
            <option value="">All types</option>
            <option value="model">Models</option>
            <option value="source">Sources</option>
            <option value="seed">Seeds</option>
            <option value="snapshot">Snapshots</option>
          </select>
          <select value={schema} onChange={(e) => setSchema(e.target.value)}>
            <option value="">All schemas</option>
            {uniqueSchemas(data).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      )}
      {canUnlock && (
        <div className="dbd-erd-bar">
          <button
            type="button"
            className={`dbd-lock-btn${unlocked ? " on" : ""}`}
            onClick={() => setUnlocked((v) => !v)}
            title={unlocked ? "Lock pan & zoom" : "Unlock pan & zoom"}
          >
            {unlocked ? "🔓 Pan & zoom on" : "🔒 Locked — click to pan & zoom"}
          </button>
        </div>
      )}
      <div className="dbd-canvas">
        <ReactFlowProvider>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onPaneClick={onPaneClick}
            fitView
            minZoom={0.1}
            proOptions={{ hideAttribution: true }}
            {...(locked
              ? {
                  panOnDrag: false,
                  zoomOnScroll: false,
                  zoomOnPinch: false,
                  zoomOnDoubleClick: false,
                  nodesDraggable: false,
                  nodesConnectable: false,
                  // Pan/zoom locked, but edges/nodes stay selectable so a click
                  // can highlight a relationship.
                  elementsSelectable: true,
                  preventScrolling: false,
                  fitViewOptions: { padding: 0.15 },
                }
              : {})}
          >
            <Background />
            {interactive && <Controls showInteractive={false} />}
            {interactive && <MiniMap pannable zoomable />}
          </ReactFlow>
        </ReactFlowProvider>
      </div>
    </div>
  );
}
