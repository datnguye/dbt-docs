import { useEffect, useMemo, useState, type ReactElement } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type EdgeMouseHandler,
  type FitViewOptions,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import { assignErdEdgeSides, buildDagFlow, buildErdFlow, erdNeighborhood, neighborhood } from "@/lib/data";
import { applyPositions, asLayoutEdges, resolveLayout } from "@/lib/layout";
import { shortName } from "@/lib/names";
import { ErdTableNode } from "@/components/nodes/ErdTableNode";
import { LineageNode } from "@/components/nodes/LineageNode";
import type { DbdocsData, ErdNodeRecord, GraphMode } from "@/lib/types";

const nodeTypes = { lineage: LineageNode, erdTable: ErdTableNode };

const MAX_UNFOCUSED_DAG_NODES = 400;

// A focused ERD shows a small neighborhood, so the `minZoom` floor clamps the fit
// *up* to keep the hub + ring legible. The full (unfocused) ERD instead fits the
// whole snowflake so every table and relationship is visible at once — clamping
// it up would zoom into the hub and hide the rest (the whole point of the
// overview is to see everything; the user zooms in from there).
const ERD_FIT_FOCUSED = { padding: 0.12, minZoom: 0.5, maxZoom: 1 };
const ERD_FIT_FULL = { padding: 0.08, maxZoom: 1 };

/**
 * Re-fits the view whenever the document enters/exits full screen. Full screen
 * resizes the graph host, but React Flow doesn't auto-refit on that, so the graph
 * would otherwise stay framed for the old (smaller) size. Lives inside the
 * ReactFlow provider so it can call `fitView`. A short delay lets the fullscreen
 * resize settle before measuring.
 */
function FitOnFullscreen({ options }: { options?: FitViewOptions }): null {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const onChange = () => {
      setTimeout(() => fitView(options), 120);
    };
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, [fitView, options]);
  return null;
}

interface Props {
  mode: GraphMode;
  focus?: string | null;
  data: DbdocsData;
  onOpenNode?: (id: string) => void;
  initialRtype?: string;
  initialSchema?: string;
  initialErdFocus?: string;
  initialErdSchema?: string;
}

function sortedSchemas(schemas: Iterable<string>): string[] {
  return Array.from(new Set(schemas)).sort();
}

function uniqueSchemas(data: DbdocsData): string[] {
  const records = data.nodes ?? {};
  return sortedSchemas(Object.keys(records).map((id) => records[id].schema));
}

function erdUniqueSchemas(erdNodes: ErdNodeRecord[]): string[] {
  return sortedSchemas(erdNodes.map((n) => n.schema));
}


/**
 * Build the canonical DAG hash given the current filter state. Written into the
 * URL via `history.replaceState` (not by assigning `location.hash`) so the link
 * stays shareable without firing a `hashchange` that would remount the graph.
 */
export function buildDagHash(focusId: string | null, rtype: string, schema: string): string {
  const params: string[] = [];
  if (focusId) params.push("focus=" + encodeURIComponent(focusId));
  if (rtype) params.push("rtype=" + encodeURIComponent(rtype));
  if (schema) params.push("schema=" + encodeURIComponent(schema));
  return params.length ? "#/dag?" + params.join("&") : "#/dag";
}

/**
 * Build the canonical ERD hash given the current filter state. Uses `erd_focus`,
 * `erd_schema` params — namespaced parallel to the DAG's `focus`/`schema`.
 * Written via `history.replaceState` for the same reason as `buildDagHash`.
 */
export function buildErdHash(erdFocusId: string | null, erdSchema: string): string {
  const params: string[] = [];
  if (erdFocusId) params.push("erd_focus=" + encodeURIComponent(erdFocusId));
  if (erdSchema) params.push("erd_schema=" + encodeURIComponent(erdSchema));
  return params.length ? "#/overview?" + params.join("&") : "#/overview";
}

export function GraphApp({
  mode,
  focus,
  data,
  onOpenNode,
  initialRtype = "",
  initialSchema = "",
  initialErdFocus = "",
  initialErdSchema = "",
}: Props): ReactElement {
  const isDag = mode === "dag";
  const isErd = mode === "erd";
  const isErdNode = mode === "erd-node";

  // The global ERD (overview) can be unlocked for pan/zoom; the per-node ERD is
  // locked by default. The DAG is always interactive. Full screen always enables
  // pan/zoom — the diagram is large there and exploring it is the point — so an
  // ERD (overview or model-page) becomes interactive while full-screened
  // regardless of the lock toggle.
  const [unlocked, setUnlocked] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  useEffect(() => {
    const onChange = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);
  const canUnlock = isErd;
  const interactive = isDag || (canUnlock && unlocked) || ((isErd || isErdNode) && fullscreen);
  const locked = !interactive;

  const initialLabel =
    isDag && focus && data.nodes?.[focus] ? data.nodes[focus].label : (isDag ? (focus ?? "") : "");
  const [search, setSearch] = useState(initialLabel);
  const [rtype, setRtype] = useState(initialRtype);
  const [schema, setSchema] = useState(initialSchema);

  const [erdSearch, setErdSearch] = useState(initialErdFocus);
  const [erdSchema, setErdSchema] = useState(initialErdSchema);

  const [selectedEdge, setSelectedEdge] = useState<{ source: string; target: string } | null>(null);

  const erdNodes = data.erd?.nodes ?? [];

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

  const erdFocusId = useMemo(() => {
    if (!isErd) return isErdNode ? (focus ?? null) : null;
    const q = erdSearch.trim().toLowerCase();
    if (!q) return null;
    const short = (n: ErdNodeRecord) => shortName(n.label).toLowerCase();
    return (
      erdNodes.find((n) => n.id.toLowerCase() === q)?.id ??
      erdNodes.find((n) => short(n) === q)?.id ??
      erdNodes.find((n) => n.label.toLowerCase() === q)?.id ??
      erdNodes.find((n) => short(n).startsWith(q))?.id ??
      erdNodes.find((n) => n.id.toLowerCase().includes(q))?.id ??
      null
    );
  }, [isErd, isErdNode, erdSearch, focus, erdNodes]);

  useEffect(() => {
    if (!isDag) return;
    history.replaceState(null, "", buildDagHash(focusId, rtype, schema));
  }, [isDag, focusId, rtype, schema]);

  useEffect(() => {
    if (!isErd) return;
    history.replaceState(null, "", buildErdHash(erdFocusId, erdSchema));
  }, [isErd, erdFocusId, erdSchema]);

  const dagKeep = useMemo(() => {
    if (!isDag) return null;
    if (focusId) return neighborhood(data, focusId);
    const ids = Object.keys(data.nodes ?? {}).filter((id) => {
      const rec = data.nodes[id];
      if (rtype && rec.resource_type !== rtype) return false;
      if (schema && rec.schema !== schema) return false;
      return true;
    });
    if (ids.length > MAX_UNFOCUSED_DAG_NODES) return new Set<string>();
    return new Set(ids);
  }, [isDag, focusId, data, rtype, schema]);

  const erdKeep = useMemo(() => {
    if (!isErd) return null;
    if (erdFocusId) return erdNeighborhood(data, erdFocusId, 1);
    const filtered = erdNodes
      .filter((n) => !erdSchema || n.schema === erdSchema)
      .map((n) => n.id);
    return new Set(filtered);
  }, [isErd, erdFocusId, erdNodes, erdSchema, data]);

  const hasFilter = !!(rtype || schema);
  const dagEmpty = isDag && !focusId && dagKeep !== null && dagKeep.size === 0;
  const dagFilterEmpty = dagEmpty && hasFilter;
  const dagTooLarge = dagEmpty && !hasFilter;

  const erdEmpty = isErd && !erdFocusId && erdKeep !== null && erdKeep.size === 0;
  const erdNoTables = erdEmpty && erdNodes.length === 0;
  const erdFilterEmpty = erdEmpty && !erdNoTables;

  const { nodes, edges } = useMemo(() => {
    if (dagEmpty || erdEmpty) return { nodes: [], edges: [] };

    let flow;
    if (isDag) {
      flow = buildDagFlow(data, dagKeep ?? undefined);
    } else if (isErd) {
      flow = buildErdFlow(data, erdFocusId, !!erdFocusId, erdKeep ?? undefined);
    } else {
      const keep = focus ? erdNeighborhood(data, focus, 1) : undefined;
      flow = buildErdFlow(data, focus, false, keep);
    }

    const layoutName = isDag ? "dagre" : "radial";
    const centerId = isErd ? erdFocusId : focus;
    const positions = resolveLayout(layoutName)(flow.sizes, asLayoutEdges(flow.edges), {
      centerId,
    });

    let laidNodes = applyPositions(flow.nodes, positions);
    let laidEdges = isDag ? flow.edges : assignErdEdgeSides(flow.edges, positions, flow.sizes);

    if (isDag) {
      laidNodes = laidNodes.map((n) => ({
        ...n,
        data: { ...n.data, dimmed: false, focused: n.id === focusId },
      }));
      laidEdges = laidEdges.map((e) => ({
        ...e,
        animated: !!focusId,
        style: focusId ? { stroke: "var(--accent, #2f6feb)", strokeWidth: 2 } : undefined,
      }));
    } else if (selectedEdge) {
      const lit = new Set([selectedEdge.source, selectedEdge.target]);
      laidNodes = laidNodes.map((n) => ({ ...n, data: { ...n.data, dimmed: !lit.has(n.id) } }));
      laidEdges = laidEdges.map((e) => {
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
  }, [isDag, isErd, isErdNode, focus, erdFocusId, focusId, data, dagKeep, erdKeep, dagEmpty, erdEmpty, selectedEdge]);

  const erdNodeEmpty = isErdNode && edges.length === 0;
  const erdAlgo = data.metadata?.erd_algo ?? "test_relationship";

  const onNodeClick: NodeMouseHandler = (_e, node) => {
    if (onOpenNode) onOpenNode(node.id);
  };
  const onEdgeClick: EdgeMouseHandler = (_e, edge) => {
    setSelectedEdge((prev) =>
      prev && prev.source === edge.source && prev.target === edge.target
        ? null
        : { source: edge.source, target: edge.target },
    );
  };
  const onPaneClick = () => setSelectedEdge(null);

  // The model-page ERD (erd-node) always fits its whole neighborhood in the
  // window (no minZoom floor). On the overview, a focused table lands at the
  // readable floor while the full snowflake fits everything.
  const erdFitOptions = isErd && erdFocusId ? ERD_FIT_FOCUSED : ERD_FIT_FULL;

  return (
    <div className="dbd-graph">
      {isDag && (
        <div className="dbd-toolbar">
          <input
            aria-label="Focus a node"
            placeholder="Focus a node…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select aria-label="Filter by resource type" value={rtype} onChange={(e) => setRtype(e.target.value)}>
            <option value="">All types</option>
            <option value="model">Models</option>
            <option value="source">Sources</option>
            <option value="seed">Seeds</option>
            <option value="snapshot">Snapshots</option>
          </select>
          <select aria-label="Filter by schema" value={schema} onChange={(e) => setSchema(e.target.value)}>
            <option value="">All schemas</option>
            {uniqueSchemas(data).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      )}
      {isErd && (
        <div className="dbd-toolbar">
          <input
            aria-label="Focus a table"
            placeholder="Focus a table…"
            value={erdSearch}
            onChange={(e) => setErdSearch(e.target.value)}
          />
          <select aria-label="Filter by schema" value={erdSchema} onChange={(e) => setErdSchema(e.target.value)}>
            <option value="">All schemas</option>
            {erdUniqueSchemas(erdNodes).map((s) => (
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
        {dagFilterEmpty ? (
          <div className="dbd-graph-empty">
            <p>
              No nodes match the selected filter. Clear or change the
              type/schema filter above, or focus a node to explore its
              neighborhood.
            </p>
          </div>
        ) : dagTooLarge ? (
          <div className="dbd-graph-empty">
            <p>
              This project has too many models to draw the full lineage at once.
              Focus a node above (or filter by type/schema) to explore its
              neighborhood.
            </p>
          </div>
        ) : erdNoTables ? (
          <div className="dbd-graph-empty">
            <p>
              No ERD relationships detected using the <code>{erdAlgo}</code>{" "}
              algorithm. dbterd infers foreign keys from your project; see{" "}
              <a
                href="https://dbterd.datnguye.me/latest/nav/guide/choose-algo.html"
                target="_blank"
                rel="noopener"
              >
                choosing a dbterd algorithm
              </a>{" "}
              to configure detection.
            </p>
          </div>
        ) : erdFilterEmpty ? (
          <div className="dbd-graph-empty">
            <p>
              No tables match the selected schema filter. Clear the schema
              filter above, or focus a table to explore its FK neighborhood.
            </p>
          </div>
        ) : erdNodeEmpty ? (
          <div className="dbd-graph-empty">
            <p>
              No ERD relationships detected for this entity using the{" "}
              <code>{erdAlgo}</code> algorithm. dbterd infers foreign keys from
              your project; see{" "}
              <a
                href="https://dbterd.datnguye.me/latest/nav/guide/choose-algo.html"
                target="_blank"
                rel="noopener"
              >
                choosing a dbterd algorithm
              </a>{" "}
              to configure detection.
            </p>
          </div>
        ) : (
          <ReactFlowProvider>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onPaneClick={onPaneClick}
            fitView
            minZoom={isErd ? 0.05 : 0.1}
            onlyRenderVisibleElements={isErd}
            proOptions={{ hideAttribution: true }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable
            {...(locked
              ? {
                  panOnDrag: false,
                  zoomOnScroll: false,
                  zoomOnPinch: false,
                  zoomOnDoubleClick: false,
                  preventScrolling: false,
                  fitViewOptions: erdFitOptions,
                }
              : isErd
                ? { fitViewOptions: erdFitOptions }
                : {})}
          >
            <FitOnFullscreen options={isErd ? erdFitOptions : undefined} />
            <Background />
            {interactive && <Controls showInteractive={false} />}
            {interactive && <MiniMap pannable zoomable />}
          </ReactFlow>
          </ReactFlowProvider>
        )}
      </div>
    </div>
  );
}
