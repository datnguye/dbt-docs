import { Handle, Position, type NodeProps } from "@xyflow/react";
import { shortName } from "@/lib/names";
import type { ColumnRecord, ErdNodeRecord } from "@/lib/types";

const RTYPE_COLOR: Record<string, string> = {
  model: "var(--model, #2f6feb)",
  source: "var(--source, #16a34a)",
  seed: "var(--seed, #b45309)",
  snapshot: "var(--snapshot, #7c3aed)",
};

export type Side = "l" | "r";

// Per-column handles exist on BOTH sides (l/r) for both directions (in/out), so
// an edge can enter/exit a row from whichever side faces the other table. The
// side is chosen per edge after layout (see GraphApp), keeping the line short and
// landing it on the exact column row. Table-level handles are the fallback when a
// joined column isn't in the catalog-sourced column list.
export const tableHandle = (dir: "in" | "out", side: Side): string => `__table__${dir}__${side}`;
export const colHandle = (col: string, dir: "in" | "out", side: Side): string =>
  `${col}__${dir}__${side}`;

export const TABLE_IN = tableHandle("in", "l");
export const TABLE_OUT = tableHandle("out", "r");
export const inHandle = (col: string): string => colHandle(col, "in", "l");
export const outHandle = (col: string): string => colHandle(col, "out", "r");

function badge(col: ColumnRecord): string | null {
  if (col.is_primary_key) return "PK";
  if (col.is_foreign_key) return "FK";
  return null;
}

// In compact mode an ERD node shows only its key (PK/FK) columns — the ones that
// carry relationships — so a wide fact table stays a few rows tall and the radial
// layout reads. A table with no keyed columns falls back to showing all of them.
function visibleColumns(columns: ColumnRecord[], compact?: boolean): ColumnRecord[] {
  if (!compact) return columns;
  const keyed = columns.filter((c) => c.is_primary_key || c.is_foreign_key);
  return keyed.length ? keyed : columns;
}

export function ErdTableNode({ data }: NodeProps): JSX.Element {
  const record = (data as { record: ErdNodeRecord; focused?: boolean; compact?: boolean }).record;
  const focused = (data as { focused?: boolean }).focused;
  const compact = (data as { compact?: boolean }).compact;
  const color = RTYPE_COLOR[record.resource_type] ?? "var(--border, #888)";
  const all = record.columns ?? [];
  const shown = visibleColumns(all, compact);
  const hidden = all.length - shown.length;
  return (
    <div className={`dbd-erd${focused ? " dbd-erd-focus" : ""}`} title={record.id}>
      <Handle type="target" position={Position.Left} id={tableHandle("in", "l")} className="dbd-h-table" />
      <Handle type="source" position={Position.Left} id={tableHandle("out", "l")} className="dbd-h-table" />
      <Handle type="target" position={Position.Right} id={tableHandle("in", "r")} className="dbd-h-table" />
      <Handle type="source" position={Position.Right} id={tableHandle("out", "r")} className="dbd-h-table" />
      <div className="dbd-erd-head" style={{ borderTopColor: color }}>
        <span className="dbd-erd-name">{shortName(record.label)}</span>
        <span className="dbd-erd-schema">{record.schema}</span>
      </div>
      <div className="dbd-erd-cols">
        {shown.map((c) => {
          const b = badge(c);
          return (
            <div className="dbd-erd-col" key={c.name}>
              <Handle type="target" position={Position.Left} id={colHandle(c.name, "in", "l")} className="dbd-h-col" />
              <Handle type="source" position={Position.Left} id={colHandle(c.name, "out", "l")} className="dbd-h-col" />
              {b ? <span className={`dbd-erd-badge dbd-${b.toLowerCase()}`}>{b}</span> : <span className="dbd-erd-badge dbd-none" />}
              <span className="dbd-erd-colname">{c.name}</span>
              <span className="dbd-erd-coltype">{c.type}</span>
              <Handle type="target" position={Position.Right} id={colHandle(c.name, "in", "r")} className="dbd-h-col" />
              <Handle type="source" position={Position.Right} id={colHandle(c.name, "out", "r")} className="dbd-h-col" />
            </div>
          );
        })}
        {hidden > 0 ? <div className="dbd-erd-more">+{hidden} more columns</div> : null}
      </div>
    </div>
  );
}
