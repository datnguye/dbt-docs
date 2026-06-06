import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { NodeRecord } from "../types";

const COLORS: Record<string, string> = {
  model: "var(--model, #2f6feb)",
  source: "var(--source, #16a34a)",
  seed: "var(--seed, #b45309)",
  snapshot: "var(--snapshot, #7c3aed)",
};

export function LineageNode({ data }: NodeProps): JSX.Element {
  const record = (data as { record: NodeRecord; dimmed?: boolean }).record;
  const dimmed = (data as { dimmed?: boolean }).dimmed;
  const color = COLORS[record.resource_type] ?? "var(--border, #888)";
  return (
    <div className={`dbd-node${dimmed ? " dbd-dim" : ""}`} title={record.id}>
      <Handle type="target" position={Position.Left} />
      <span className="dbd-node-bar" style={{ background: color }} />
      <span className="dbd-node-label">{record.label}</span>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
