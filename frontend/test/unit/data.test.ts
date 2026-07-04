import { describe, expect, it } from "vitest";
import { buildDagFlow, neighborhood } from "@/lib/data";
import type { DbdocsData } from "@/lib/types";

const DATA: DbdocsData = {
  nodes: {
    "model.s.a": { id: "model.s.a", label: "a", resource_type: "model", database: "db", schema: "raw" },
    "model.s.b": { id: "model.s.b", label: "b", resource_type: "model", database: "db", schema: "mart" },
    "source.s.r": { id: "source.s.r", label: "r", resource_type: "source", database: "db", schema: "raw" },
  },
  lineage: {
    edges: [
      { source: "source.s.r", target: "model.s.a" },
      { source: "model.s.a", target: "model.s.b" },
    ],
    parents: { "model.s.a": ["source.s.r"], "model.s.b": ["model.s.a"], "source.s.r": [] },
    children: { "source.s.r": ["model.s.a"], "model.s.a": ["model.s.b"], "model.s.b": [] },
  },
  erd: {
    nodes: [
      {
        id: "model.s.a",
        label: "a",
        resource_type: "model",
        database: "db",
        schema_name: "raw",
        columns: [{ name: "id", data_type: "int", is_primary_key: true }],
      },
      {
        id: "model.s.b",
        label: "b",
        resource_type: "model",
        database: "db",
        schema_name: "mart",
        columns: [{ name: "a_id", data_type: "int", is_foreign_key: true }],
      },
    ],
    edges: [
      { id: "e0", to_id: "model.s.a", from_id: "model.s.b", from_columns: ["a_id"], to_columns: ["id"], relationship_type: "fk", cardinality: "n1" },
    ],
  },
};

describe("buildDagFlow", () => {
  it("maps every node and lineage edge", () => {
    const flow = buildDagFlow(DATA);
    expect(flow.nodes).toHaveLength(3);
    expect(flow.edges).toHaveLength(2);
    expect(flow.sizes).toHaveLength(3);
    expect(flow.nodes[0].type).toBe("lineage");
  });

  it("windows to keepIds, dropping nodes and edges outside the set", () => {
    const flow = buildDagFlow(DATA, new Set(["source.s.r", "model.s.a"]));
    expect(flow.nodes.map((n) => n.id).sort()).toEqual(["model.s.a", "source.s.r"]);
    // Only the edge with both endpoints kept survives.
    expect(flow.edges).toHaveLength(1);
    expect(flow.edges[0].source).toBe("source.s.r");
  });
});

describe("neighborhood", () => {
  it("collects upstream and downstream within the default depth", () => {
    expect(neighborhood(DATA, "model.s.a")).toEqual(new Set(["model.s.a", "source.s.r", "model.s.b"]));
  });

  it("bounds the walk to maxDepth hops in each direction", () => {
    // From model.s.b, depth 1 reaches its parent model.s.a but not the
    // grandparent source.s.r two hops up.
    expect(neighborhood(DATA, "model.s.b", 1)).toEqual(new Set(["model.s.b", "model.s.a"]));
  });
});
