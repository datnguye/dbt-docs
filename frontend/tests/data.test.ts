import { describe, expect, it } from "vitest";
import { buildDagFlow, buildErdFlow, neighborhood } from "../src/data";
import type { DbdocsData } from "../src/types";

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
        schema: "raw",
        columns: [{ name: "id", type: "int", is_primary_key: true }],
      },
      {
        id: "model.s.b",
        label: "b",
        resource_type: "model",
        database: "db",
        schema: "mart",
        columns: [{ name: "a_id", type: "int", is_foreign_key: true }],
      },
    ],
    edges: [
      { id: "e0", source: "model.s.a", target: "model.s.b", from_columns: ["id"], to_columns: ["a_id"], type: "n1" },
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
});

describe("buildErdFlow", () => {
  it("renders all ERD tables with column-sized boxes", () => {
    const flow = buildErdFlow(DATA, null);
    expect(flow.nodes).toHaveLength(2);
    expect(flow.edges).toHaveLength(1);
    expect(flow.nodes[0].type).toBe("erdTable");
    expect(flow.sizes[0].height).toBeGreaterThan(34);
  });

  it("restricts to the focus node and its neighbors", () => {
    const flow = buildErdFlow(DATA, "model.s.a");
    const ids = flow.nodes.map((n) => n.id).sort();
    expect(ids).toEqual(["model.s.a", "model.s.b"]);
  });
});

describe("neighborhood", () => {
  it("collects upstream and downstream", () => {
    expect(neighborhood(DATA, "model.s.a")).toEqual(new Set(["model.s.a", "source.s.r", "model.s.b"]));
  });
});
