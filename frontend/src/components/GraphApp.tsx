import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type FitViewOptions,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import { buildDagFlow, layerTypes, neighborhood, sortedSchemas } from "@/lib/data";
import { applyPositions, asLayoutEdges, resolveLayout } from "@/lib/layout";
import { LineageNode } from "@/components/nodes/LineageNode";
import type { DagLayer, DbdocsData, ResourceType } from "@/lib/types";

const nodeTypes = { lineage: LineageNode };

const MAX_UNFOCUSED_DAG_NODES = 400;

const DAG_FIT_FOCUSED: FitViewOptions = { padding: 0.2 };

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
  focus?: string | null;
  data: DbdocsData;
  onOpenNode?: (id: string) => void;
  initialRtype?: string;
  initialSchema?: string;
  initialLayer?: DagLayer;
}

function uniqueSchemas(data: DbdocsData): string[] {
  const records = data.nodes ?? {};
  return sortedSchemas(Object.keys(records).map((id) => records[id].schema));
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

export function GraphApp({
  focus,
  data,
  onOpenNode,
  initialRtype = "",
  initialSchema = "",
  initialLayer = "catalog",
}: Props): ReactElement {
  const initialLabel = focus && data.nodes?.[focus] ? data.nodes[focus].label : (focus ?? "");
  const [search, setSearch] = useState(initialLabel);
  const [rtype, setRtype] = useState<Set<string>>(() => parseRtypeParam(initialRtype));
  const [schema, setSchema] = useState(initialSchema);
  const [layer, setLayer] = useState<DagLayer>(initialLayer);

  const focusId = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return null;
    const ids = Object.keys(data.nodes ?? {});
    return (
      ids.find((id) => id.toLowerCase() === q) ??
      ids.find((id) => data.nodes[id].label.toLowerCase() === q) ??
      ids.find((id) => data.nodes[id].label.toLowerCase().startsWith(q)) ??
      null
    );
  }, [search, data]);

  useEffect(() => {
    history.replaceState(null, "", buildDagHash(focusId, rtype, schema, layer));
  }, [focusId, rtype, schema, layer]);

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
  }, [focusId, data, layer, rtype, schema]);

  const hasFilter = !!(rtype.size > 0 || schema || layer !== "catalog");
  const dagEmpty = !focusId && dagKeep.size === 0;
  const dagFilterEmpty = dagEmpty && hasFilter;
  const dagTooLarge = dagEmpty && !hasFilter;

  const { nodes, edges } = useMemo(() => {
    if (dagEmpty) return { nodes: [], edges: [] };

    const flow = buildDagFlow(data, dagKeep);

    const positions = resolveLayout("dagre")(flow.sizes, asLayoutEdges(flow.edges), {
      direction: focusId ? "TB" : undefined,
    });

    let laidNodes = applyPositions(flow.nodes, positions);
    const laidEdges = flow.edges.map((e) => ({
      ...e,
      animated: !!focusId,
      style: focusId ? { stroke: "var(--accent, #2f6feb)", strokeWidth: 2 } : undefined,
    }));

    laidNodes = laidNodes.map((n) => ({
      ...n,
      data: { ...n.data, dimmed: false, focused: n.id === focusId },
    }));

    return { nodes: laidNodes as Node[], edges: laidEdges as Edge[] };
  }, [focusId, data, dagKeep, dagEmpty]);

  const fitSignature = useMemo(() => nodes.map((n) => n.id).join(","), [nodes]);

  const onNodeClick: NodeMouseHandler = (_e, node) => {
    if (onOpenNode) onOpenNode(node.id);
  };

  const dagFitOptions = focusId ? DAG_FIT_FOCUSED : undefined;

  return (
    <div className="dbd-graph">
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
        ) : (
          <ReactFlowProvider>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
            fitView
            minZoom={0.1}
            proOptions={{ hideAttribution: true }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable
            {...(dagFitOptions ? { fitViewOptions: dagFitOptions } : {})}
          >
            <FitOnFullscreen options={dagFitOptions} />
            <FitOnDataChange
              signature={fitSignature}
              options={dagFitOptions}
            />
            <Background />
            <Controls showInteractive={false} />
            <MiniMap pannable zoomable />
          </ReactFlow>
          </ReactFlowProvider>
        )}
      </div>
    </div>
  );
}
