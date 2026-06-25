import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { NodeRecord } from "@/lib/types";

const COLORS: Record<string, string> = {
  model: "var(--model, #2f6feb)",
  source: "var(--source, #16a34a)",
  seed: "var(--seed, #b45309)",
  snapshot: "var(--snapshot, #7c3aed)",
  metric: "var(--metric, #0891b2)",
  semantic_model: "var(--semantic_model, #be123c)",
  saved_query: "var(--saved_query, #c2410c)",
  unit_test: "var(--unit_test, #4338ca)",
  exposure: "var(--exposure, #9d174d)",
  analysis: "var(--analysis, #334155)",
  operation: "var(--operation, #065f46)",
  test: "var(--test, #4b5563)",
};

const RTYPE_BADGE: Record<string, string> = {
  model: "mdl",
  source: "src",
  seed: "seed",
  snapshot: "snap",
  analysis: "anl",
  operation: "op",
  metric: "mtrc",
  semantic_model: "sm",
  saved_query: "sq",
  unit_test: "ut",
  exposure: "exp",
  test: "tst",
};

export function LineageNode({ data }: NodeProps): JSX.Element {
  const record = (data as { record: NodeRecord; dimmed?: boolean }).record;
  const dimmed = (data as { dimmed?: boolean }).dimmed;
  const color = COLORS[record.resource_type] ?? "var(--border, #888)";
  const badge = RTYPE_BADGE[record.resource_type];
  return (
    <div className={`dbd-node${dimmed ? " dbd-dim" : ""}`} title={record.id}>
      <Handle type="target" position={Position.Left} />
      <span className="dbd-node-bar" style={{ background: color }} />
      <span className="dbd-node-label">{record.label}</span>
      {badge && (
        <span className="dbd-node-badge" style={{ background: color }}>
          {badge}
        </span>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
