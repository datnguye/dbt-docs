import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";
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
import { assignErdEdgeSides, buildDagFlow, buildErdFlow, erdNeighborhood, layerTypes, neighborhood } from "@/lib/data";
import { applyPositions, asLayoutEdges, resolveLayout } from "@/lib/layout";
import { shortName } from "@/lib/names";
import { ErdTableNode } from "@/components/nodes/ErdTableNode";
import { LineageNode } from "@/components/nodes/LineageNode";
import type { DagLayer, DbdocsData, ErdNodeRecord, GraphMode, ResourceType } from "@/lib/types";

const nodeTypes = { lineage: LineageNode, erdTable: ErdTableNode };

const MAX_UNFOCUSED_DAG_NODES = 400;

// A focused ERD shows a small neighborhood, so the `minZoom` floor clamps the fit
// *up* to keep the hub + ring legible. The full (unfocused) ERD instead fits the
// whole snowflake so every table and relationship is visible at once — clamping
// it up would zoom into the hub and hide the rest (the whole point of the
// overview is to see everything; the user zooms in from there).
const ERD_FIT_FOCUSED = { padding: 0.12, minZoom: 0.5, maxZoom: 1 };
const ERD_FIT_FULL = { padding: 0.08, maxZoom: 1 };

const CATALOG_ORDER: ResourceType[] = ["model", "source", "seed", "snapshot", "analysis", "operation"];
const SEMANTIC_ORDER: ResourceType[] = ["metric", "semantic_model", "saved_query"];
const OTHER_ORDER: ResourceType[] = ["unit_test", "exposure"];

const RTYPE_LABELS: Record<string, string> = {
  model: "Models",
  source: "Sources",
  seed: "Seeds",
  snapshot: "Snapshots",
  analysis: "Analyses",
  operation: "Operations",
  metric: "Metrics",
  semantic_model: "Semantic Models",
  saved_query: "Saved Queries",
  unit_test: "Unit Tests",
  exposure: "Exposures",
};

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

/**
 * Re-fits the view whenever the node set changes. `<ReactFlow fitView>` only
 * fires on initial mount, so when the layer/types filter narrows to a small
 * disconnected component (e.g. just saved queries), the camera stays framed for
 * the previous larger graph and the kept nodes sit off-screen. The `signature`
 * prop changes when the rendered node set changes, triggering the refit.
 */
function FitOnDataChange({
  signature,
  options,
}: {
  signature: string;
  options?: FitViewOptions;
}): null {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const t = setTimeout(() => fitView(options), 60);
    return () => clearTimeout(t);
  }, [fitView, options, signature]);
  return null;
}

interface LayerControlProps {
  layer: DagLayer;
  onChange: (next: DagLayer) => void;
}

function LayerControl({ layer, onChange }: LayerControlProps): ReactElement {
  const options: { value: DagLayer; label: string }[] = [
    { value: "catalog", label: "Catalog" },
    { value: "semantic", label: "Semantic" },
    { value: "other", label: "Other" },
    { value: "all", label: "All" },
  ];
  return (
    <div className="dbd-layer-seg" role="group" aria-label="Filter by layer">
      {options.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          className={layer === value ? "active" : ""}
          aria-pressed={layer === value}
          onClick={() => onChange(value)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

interface TypeOption {
  value: string;
  label: string;
  count: number;
}

interface RtypeDropdownProps {
  layer: DagLayer;
  selected: Set<string>;
  catalogOptions: TypeOption[];
  semanticOptions: TypeOption[];
  otherOptions: TypeOption[];
  onChange: (next: Set<string>) => void;
}

function RtypeDropdown({ layer, selected, catalogOptions, semanticOptions, otherOptions, onChange }: RtypeDropdownProps): ReactElement {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelId = "rtype-dropdown-panel";

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as HTMLElement)) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClickOutside);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClickOutside);
    };
  }, [open]);

  const activeOptions =
    layer === "catalog"
      ? catalogOptions
      : layer === "semantic"
        ? semanticOptions
        : layer === "other"
          ? otherOptions
          : [...catalogOptions, ...semanticOptions, ...otherOptions];
  const allSelected = selected.size === 0 || selected.size === activeOptions.length;

  function toggleAll() {
    onChange(new Set());
  }

  function toggleOne(value: string) {
    const next = new Set(selected);
    if (next.has(value)) {
      next.delete(value);
      if (next.size === 0) {
        onChange(new Set());
        return;
      }
    } else {
      next.add(value);
    }
    onChange(next);
  }

  let label: string;
  if (allSelected) {
    label = "Types: All";
  } else if (selected.size === 1) {
    const v = Array.from(selected)[0];
    label = "Types: " + (RTYPE_LABELS[v] ?? v);
  } else {
    label = "Types: " + selected.size + " selected";
  }

  function renderGroup(options: TypeOption[], groupLabel: string | null) {
    return (
      <div className="dbd-multi-group">
        {groupLabel && <div className="dbd-multi-group-legend">{groupLabel}</div>}
        {options.map(({ value, label: optLabel, count }) => (
          <label key={value} className="dbd-multi-option">
            <input
              type="checkbox"
              checked={selected.size === 0 || selected.has(value)}
              onChange={() => toggleOne(value)}
            />
            <span className="dbd-multi-label">{optLabel}</span>
            <span className="dbd-multi-count">({count})</span>
          </label>
        ))}
      </div>
    );
  }

  return (
    <div className="dbd-multi" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        className="dbd-multi-trigger"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label="Filter by resource type"
        onClick={() => setOpen((v) => !v)}
      >
        {label}
        <span className="dbd-multi-arrow" aria-hidden="true">▾</span>
      </button>
      {open && (
        <div
          id={panelId}
          className="dbd-multi-panel"
          role="group"
          aria-label="Resource type filter"
        >
          <label className="dbd-multi-option dbd-multi-all">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
            />
            <span className="dbd-multi-label">All types</span>
          </label>
          {layer === "all" ? (
            <>
              {renderGroup(catalogOptions, "Catalog")}
              {renderGroup(semanticOptions, "Semantic")}
              {renderGroup(otherOptions, "Other")}
            </>
          ) : (
            renderGroup(activeOptions, null)
          )}
        </div>
      )}
    </div>
  );
}

interface Props {
  mode: GraphMode;
  focus?: string | null;
  data: DbdocsData;
  onOpenNode?: (id: string) => void;
  initialRtype?: string;
  initialSchema?: string;
  initialLayer?: DagLayer;
  initialErdFocus?: string;
  initialErdSchema?: string;
}

function sortedSchemas(schemas: Iterable<string>): string[] {
  return Array.from(new Set(schemas)).filter(Boolean).sort();
}

function uniqueSchemas(data: DbdocsData): string[] {
  const records = data.nodes ?? {};
  return sortedSchemas(Object.keys(records).map((id) => records[id].schema));
}

function erdUniqueSchemas(erdNodes: ErdNodeRecord[]): string[] {
  return sortedSchemas(erdNodes.map((n) => n.schema));
}

function parseRtypeParam(raw: string): Set<string> {
  return new Set(raw.split(",").map((s) => s.trim()).filter(Boolean));
}

function serializeRtype(rtype: Set<string>): string {
  if (rtype.size === 0) return "";
  return Array.from(rtype).sort().join(",");
}

/**
 * Build the canonical DAG hash given the current filter state. Written into the
 * URL via `history.replaceState` (not by assigning `location.hash`) so the link
 * stays shareable without firing a `hashchange` that would remount the graph.
 * `layer` is omitted when it is the default ("catalog") and no types/schema are
 * selected, keeping clean URLs for the common case.
 */
export function buildDagHash(
  focusId: string | null,
  rtype: Set<string>,
  schema: string,
  layer: DagLayer = "catalog",
): string {
  const params: string[] = [];
  if (focusId) params.push("focus=" + encodeURIComponent(focusId));
  const rtypeStr = serializeRtype(rtype);
  if (rtypeStr) params.push("rtype=" + encodeURIComponent(rtypeStr));
  if (schema) params.push("schema=" + encodeURIComponent(schema));
  if (layer !== "catalog") params.push("layer=" + encodeURIComponent(layer));
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
  initialLayer = "catalog",
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
  const [rtype, setRtype] = useState<Set<string>>(() => parseRtypeParam(initialRtype));
  const [schema, setSchema] = useState(initialSchema);
  const [layer, setLayer] = useState<DagLayer>(initialLayer);

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
    history.replaceState(null, "", buildDagHash(focusId, rtype, schema, layer));
  }, [isDag, focusId, rtype, schema, layer]);

  useEffect(() => {
    if (!isErd) return;
    history.replaceState(null, "", buildErdHash(erdFocusId, erdSchema));
  }, [isErd, erdFocusId, erdSchema]);

  const layerMountedRef = useRef(false);
  useEffect(() => {
    if (!layerMountedRef.current) {
      layerMountedRef.current = true;
      return;
    }
    setRtype(new Set());
  }, [layer]);

  const { catalogOptions, semanticOptions, otherOptions } = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const id of Object.keys(data.nodes ?? {})) {
      const rt = data.nodes[id].resource_type;
      counts[rt] = (counts[rt] ?? 0) + 1;
    }
    const toOptions = (order: ResourceType[]) =>
      order
        .filter((rt) => (counts[rt] ?? 0) > 0)
        .map((rt) => ({ value: rt, label: RTYPE_LABELS[rt] ?? rt, count: counts[rt] }));
    return {
      catalogOptions: toOptions(CATALOG_ORDER),
      semanticOptions: toOptions(SEMANTIC_ORDER),
      otherOptions: toOptions(OTHER_ORDER),
    };
  }, [data]);

  const dagKeep = useMemo(() => {
    if (!isDag) return null;
    if (focusId) return neighborhood(data, focusId);
    const allowed = layerTypes(layer);
    const ids = Object.keys(data.nodes ?? {}).filter((id) => {
      const rec = data.nodes[id];
      if (!allowed.has(rec.resource_type as ResourceType)) return false;
      if (rtype.size > 0 && !rtype.has(rec.resource_type)) return false;
      if (schema && rec.schema !== schema) return false;
      return true;
    });
    if (ids.length > MAX_UNFOCUSED_DAG_NODES) return new Set<string>();
    return new Set(ids);
  }, [isDag, focusId, data, layer, rtype, schema]);

  const erdKeep = useMemo(() => {
    if (!isErd) return null;
    if (erdFocusId) return erdNeighborhood(data, erdFocusId, 1);
    const filtered = erdNodes
      .filter((n) => !erdSchema || n.schema === erdSchema)
      .map((n) => n.id);
    return new Set(filtered);
  }, [isErd, erdFocusId, erdNodes, erdSchema, data]);

  const hasFilter = !!(rtype.size > 0 || schema || layer !== "catalog");
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

  const fitSignature = useMemo(() => nodes.map((n) => n.id).join(","), [nodes]);

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
          <LayerControl layer={layer} onChange={setLayer} />
          <RtypeDropdown
            layer={layer}
            selected={rtype}
            catalogOptions={catalogOptions}
            semanticOptions={semanticOptions}
            otherOptions={otherOptions}
            onChange={setRtype}
          />
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
              layer/type/schema filter above, or focus a node to explore its
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
            <FitOnDataChange
              signature={fitSignature}
              options={isErd ? erdFitOptions : undefined}
            />
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
