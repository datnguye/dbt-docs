import { useEffect, useMemo, useState, type ReactElement } from "react";
import {
  ErdFlow,
  registerLayout,
  type ErdNode,
  type ErdPayload,
  type ErdTheme,
  type EstimateSize,
  type LayoutEngine,
} from "@datnguye/erd-flow";
import { sortedSchemas } from "@/lib/data";
import { mostConnected, radialLayout, type LayoutEdge, type Sized } from "@/lib/layout";
import { shortName } from "@/lib/names";
import type { DbdocsData, ErdEdge, ErdNodeRecord, GraphMode } from "@/lib/types";
import "@datnguye/erd-flow/styles.css";

// The snowflake arrangement: concentric BFS rings around the focused table (or
// the most-connected one), from this repo's radialLayout. Registered into
// erd-flow's layout registry so <ErdFlow layout="snowflake"> selects it; edge
// direction is irrelevant to it (the ring walk is undirected).
const snowflakeEngine: LayoutEngine = (sized, edges, opts) => {
  const boxes: Sized[] = sized.map((n) => ({ id: n.id, width: n.width, height: n.height }));
  const layoutEdges: LayoutEdge[] = edges.map((e) => ({ source: e.from_id, target: e.to_id }));
  const center = opts.centerId ?? mostConnected(boxes, layoutEdges);
  const positions = center ? radialLayout(center, boxes, layoutEdges) : new Map();
  return sized.map((n) => ({
    id: n.id,
    x: positions.get(n.id)?.x ?? 0,
    y: positions.get(n.id)?.y ?? 0,
    dimensions: { width: n.width, height: n.height },
  }));
};
registerLayout("snowflake", snowflakeEngine);

// The layout box every table occupies in the snowflake: a fixed width and a
// header + one slot per rendered row (columns plus the "+N more columns" row
// when compact windowing dropped some).
const ERD_WIDTH = 230;
const ERD_HEADER = 34;
const ERD_ROW = 22;

export const erdEstimateSize: EstimateSize = (node) => {
  const rows = Math.max(1, node.columns.length + (node.hidden_column_count ? 1 : 0));
  return { width: ERD_WIDTH, height: ERD_HEADER + rows * ERD_ROW };
};

// Maps dbt-docs's CSS custom properties onto @datnguye/erd-flow's theme tokens
// so the ERD matches the SPA's active light/dark theme instead of the
// package's own built-in dark fallbacks. Edges keep React Flow's neutral gray
// in both themes; a selected edge takes the accent.
const ERD_THEME: ErdTheme = {
  nodeBg: "var(--bg-elev)",
  nodeFg: "var(--text)",
  border: "var(--border)",
  accent: "var(--accent)",
  fk: "var(--accent)",
  headerBg: "var(--bg-soft)",
  hoverBg: "var(--bg-soft)",
  mutedFg: "var(--text-soft)",
  linkFg: "var(--accent)",
  divider: "var(--border)",
  edge: "#b1b1b7",
  edgeSelected: "var(--accent)",
  edgeWidth: "1",
  edgeSelectedWidth: "2.5",
  minimapBg: "var(--bg-elev)",
};

const ERD_FIT_FOCUSED = { padding: 0.12, minZoom: 0.5, maxZoom: 1 };
const ERD_FIT_FULL = { padding: 0.08, maxZoom: 1 };

// dbt-docs's exact physical-resource palette, mirrored so the ERD stays
// visually consistent with the rest of the SPA (the package's own defaults
// already match these values, but this keeps the mapping explicit and themed).
const RESOURCE_META = {
  model: { color: "var(--model, #2f6feb)", badge: "M", label: "Model" },
  source: { color: "var(--source, #16a34a)", badge: "S", label: "Source" },
  seed: { color: "var(--seed, #b45309)", badge: "SD", label: "Seed" },
  snapshot: { color: "var(--snapshot, #7c3aed)", badge: "SN", label: "Snapshot" },
};

/**
 * Adapts dbt-docs's `data.erd` (label-keyed nodes) into @datnguye/erd-flow's
 * `ErdPayload` (name-keyed nodes). An optional `schema` filters nodes (and any
 * edge left dangling by the filter) before the payload reaches `<ErdFlow>`,
 * since the package has no schema-filter prop of its own.
 */
export function toErdPayload(data: DbdocsData, schema?: string | null): ErdPayload {
  const allNodes: ErdNodeRecord[] = data.erd?.nodes ?? [];
  const allEdges: ErdEdge[] = data.erd?.edges ?? [];
  const nodeRecords = schema ? allNodes.filter((n) => n.schema_name === schema) : allNodes;
  const keep = new Set(nodeRecords.map((n) => n.id));
  const edges = schema
    ? allEdges.filter((e) => keep.has(e.from_id) && keep.has(e.to_id))
    : allEdges;
  const nodes: ErdNode[] = nodeRecords.map((n) => ({ ...n, name: n.label }));
  return { nodes, edges, metadata: { erd_algo: data.metadata?.erd_algo } };
}

function erdUniqueSchemas(erdNodes: ErdNodeRecord[]): string[] {
  return sortedSchemas(erdNodes.map((n) => n.schema_name));
}

/**
 * Build the canonical ERD hash given the current filter state. Uses `erd_focus`,
 * `erd_schema` params — namespaced parallel to the DAG's `focus`/`schema`.
 * Written via `history.replaceState` so the link stays shareable without
 * firing a `hashchange` that would remount the graph.
 */
export function buildErdHash(erdFocusId: string | null, erdSchema: string): string {
  const params: string[] = [];
  if (erdFocusId) params.push("erd_focus=" + encodeURIComponent(erdFocusId));
  if (erdSchema) params.push("erd_schema=" + encodeURIComponent(erdSchema));
  return params.length ? "#/overview?" + params.join("&") : "#/overview";
}

function NoRelationshipsNotice({
  erdAlgo,
  entity = false,
}: {
  erdAlgo: string;
  entity?: boolean;
}): ReactElement {
  return (
    <div className="dbd-graph-empty">
      <p>
        No ERD relationships detected{entity ? " for this entity" : ""} using the{" "}
        <code>{erdAlgo}</code> algorithm. dbterd infers foreign keys from your project; see{" "}
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
  );
}

interface Props {
  mode: Exclude<GraphMode, "dag">;
  focus?: string | null;
  data: DbdocsData;
  onOpenNode?: (id: string) => void;
  initialErdFocus?: string;
  initialErdSchema?: string;
}

/**
 * Host chrome for the ERD views (overview + per-model). Owns the focus search
 * box, schema filter, URL hash sync, and empty states; delegates the diagram
 * itself to the shared `<ErdFlow>` component from @datnguye/erd-flow. The
 * overview's lock/unlock affordance drives `<ErdFlow>`'s `interactive` prop, so
 * a locked canvas genuinely disables pan/zoom.
 */
export function ErdApp({
  mode,
  focus,
  data,
  onOpenNode,
  initialErdFocus = "",
  initialErdSchema = "",
}: Props): ReactElement {
  const isErd = mode === "erd";
  const isErdNode = mode === "erd-node";

  const [unlocked, setUnlocked] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  useEffect(() => {
    const onChange = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);
  const interactive = (isErd && unlocked) || fullscreen;

  // Every color the theme prop doesn't cover (e.g. React Flow's own dark/light
  // chrome defaults) follows the SPA's `data-theme` attribute, observed so a
  // theme toggle while the ERD is mounted restyles it without a remount.
  const [colorMode, setColorMode] = useState<"dark" | "light">(() =>
    document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light",
  );
  useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() =>
      setColorMode(root.getAttribute("data-theme") === "dark" ? "dark" : "light"),
    );
    observer.observe(root, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  const [erdSearch, setErdSearch] = useState(initialErdFocus);
  const [erdSchema, setErdSchema] = useState(initialErdSchema);

  const erdNodes = useMemo(() => data.erd?.nodes ?? [], [data]);

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
    if (!isErd) return;
    history.replaceState(null, "", buildErdHash(erdFocusId, erdSchema));
  }, [isErd, erdFocusId, erdSchema]);

  const erdAlgo = data.metadata?.erd_algo ?? "test_relationship";

  const payload = useMemo(
    () => toErdPayload(data, isErd ? erdSchema || null : null),
    [data, isErd, erdSchema],
  );

  const erdNoTables = isErd && !erdFocusId && erdNodes.length === 0;
  const erdFilterEmpty = isErd && !erdFocusId && !erdNoTables && payload.nodes.length === 0;

  const schemaOptions = useMemo(() => erdUniqueSchemas(erdNodes), [erdNodes]);

  const erdNodeEmpty =
    isErdNode &&
    !!focus &&
    !(data.erd?.edges ?? []).some((e) => e.from_id === focus || e.to_id === focus);

  const onOpen = (node: ErdNode) => {
    if (onOpenNode) onOpenNode(node.id);
  };

  return (
    <div className="dbd-graph">
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
            {schemaOptions.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      )}
      {isErd && (
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
        {erdNoTables ? (
          <NoRelationshipsNotice erdAlgo={erdAlgo} />
        ) : erdFilterEmpty ? (
          <div className="dbd-graph-empty">
            <p>
              No tables match the selected schema filter. Clear the schema
              filter above, or focus a table to explore its FK neighborhood.
            </p>
          </div>
        ) : erdNodeEmpty ? (
          <NoRelationshipsNotice erdAlgo={erdAlgo} entity />
        ) : (
          <ErdFlow
            data={payload}
            layout="snowflake"
            estimateSize={erdEstimateSize}
            focus={isErd ? erdFocusId : (focus ?? null)}
            focusDepth={1}
            compact={isErd && !!erdFocusId}
            collapseColumns={false}
            showSchema
            compositeEdges="fan"
            edgePath="smoothstep"
            animateEdge={(e) => e.cardinality === "n1"}
            dimOnSelect
            onlyRenderVisibleElements={isErd}
            fitViewOptions={isErd && erdFocusId ? ERD_FIT_FOCUSED : ERD_FIT_FULL}
            refitKey={fullscreen}
            onOpenNode={onOpen}
            resourceMeta={RESOURCE_META}
            labelFor={(n) => shortName(n.id)}
            theme={ERD_THEME}
            colorMode={colorMode}
            interactive={interactive}
            minimap={interactive}
            controls={interactive}
          />
        )}
      </div>
    </div>
  );
}
