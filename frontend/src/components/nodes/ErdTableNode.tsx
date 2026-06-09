import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { ColumnRecord, ErdNodeRecord } from "@/lib/types";

const RTYPE_COLOR: Record<string, string> = {
  model: "var(--model, #2f6feb)",
  source: "var(--source, #16a34a)",
  seed: "var(--seed, #b45309)",
  snapshot: "var(--snapshot, #7c3aed)",
};

export const TABLE_IN = "__table_in";
export const TABLE_OUT = "__table_out";
export const inHandle = (col: string): string => `${col}__in`;
export const outHandle = (col: string): string => `${col}__out`;

function badge(col: ColumnRecord): string | null {
  if (col.is_primary_key) return "PK";
  if (col.is_foreign_key) return "FK";
  return null;
}

export function ErdTableNode({ data }: NodeProps): JSX.Element {
  const record = (data as { record: ErdNodeRecord; focused?: boolean }).record;
  const focused = (data as { focused?: boolean }).focused;
  const color = RTYPE_COLOR[record.resource_type] ?? "var(--border, #888)";
  return (
    <div className={`dbd-erd${focused ? " dbd-erd-focus" : ""}`} title={record.id}>
      {/* Table-level fallback handles — edges use these when a joined column
          isn't in the catalog-sourced column list (else React Flow drops them). */}
      <Handle type="target" position={Position.Left} id={TABLE_IN} className="dbd-h-table" />
      <Handle type="source" position={Position.Right} id={TABLE_OUT} className="dbd-h-table" />
      <div className="dbd-erd-head" style={{ borderTopColor: color }}>
        <span className="dbd-erd-name">{record.label}</span>
        <span className="dbd-erd-schema">{record.schema}</span>
      </div>
      <div className="dbd-erd-cols">
        {(record.columns ?? []).map((c) => {
          const b = badge(c);
          return (
            <div className="dbd-erd-col" key={c.name}>
              <Handle type="target" position={Position.Left} id={inHandle(c.name)} className="dbd-h-col" />
              {b ? <span className={`dbd-erd-badge dbd-${b.toLowerCase()}`}>{b}</span> : <span className="dbd-erd-badge dbd-none" />}
              <span className="dbd-erd-colname">{c.name}</span>
              <span className="dbd-erd-coltype">{c.type}</span>
              <Handle type="source" position={Position.Right} id={outHandle(c.name)} className="dbd-h-col" />
            </div>
          );
        })}
      </div>
    </div>
  );
}
