// The shape of the data dbdocs injects as window.dbdocsData. We only declare the
// slices the graph bundle reads (nodes, lineage, columnLineage, erd).

export type ResourceType =
  | "model"
  | "source"
  | "seed"
  | "snapshot"
  | "analysis"
  | "operation"
  | "metric"
  | "semantic_model"
  | "saved_query"
  | "unit_test"
  | "exposure";

export interface ColumnRecord {
  name: string;
  type: string;
  description?: string;
  is_primary_key?: boolean;
  is_foreign_key?: boolean;
}

export interface NodeRecord {
  id: string;
  label: string;
  resource_type: ResourceType;
  database: string;
  schema: string;
  columns?: ColumnRecord[];
}

export interface LineageEdge {
  source: string;
  target: string;
}

export interface ErdNodeRecord extends NodeRecord {
  columns: ColumnRecord[];
}

export interface ErdEdge {
  id: string;
  source: string;
  target: string;
  from_columns: string[];
  to_columns: string[];
  label?: string | null;
  type?: string;
}

export interface DbdocsData {
  metadata?: { erd_algo?: string };
  nodes: Record<string, NodeRecord>;
  lineage: {
    edges: LineageEdge[];
    parents: Record<string, string[]>;
    children: Record<string, string[]>;
  };
  erd: { nodes: ErdNodeRecord[]; edges: ErdEdge[] };
}

export type GraphMode = "dag" | "erd" | "erd-node";

export type DagLayer = "catalog" | "semantic" | "other" | "all";

export interface MountOptions {
  mode: GraphMode;
  focus?: string | null;
  data: DbdocsData;
  onOpenNode?: (id: string) => void;
}
