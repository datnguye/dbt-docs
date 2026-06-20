import { describe, expect, it } from "vitest";
import {
  assignErdEdgeSides,
  buildDagFlow,
  buildErdFlow,
  erdNeighborhood,
  neighborhood,
} from "@/lib/data";
import type { Edge } from "@xyflow/react";
import type { DbdocsData, ErdNodeRecord } from "@/lib/types";

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

  it("windows to keepIds, dropping nodes and edges outside the set", () => {
    const flow = buildDagFlow(DATA, new Set(["source.s.r", "model.s.a"]));
    expect(flow.nodes.map((n) => n.id).sort()).toEqual(["model.s.a", "source.s.r"]);
    // Only the edge with both endpoints kept survives.
    expect(flow.edges).toHaveLength(1);
    expect(flow.edges[0].source).toBe("source.s.r");
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
  it("collects upstream and downstream within the default depth", () => {
    expect(neighborhood(DATA, "model.s.a")).toEqual(new Set(["model.s.a", "source.s.r", "model.s.b"]));
  });

  it("bounds the walk to maxDepth hops in each direction", () => {
    // From model.s.b, depth 1 reaches its parent model.s.a but not the
    // grandparent source.s.r two hops up.
    expect(neighborhood(DATA, "model.s.b", 1)).toEqual(new Set(["model.s.b", "model.s.a"]));
  });
});

// ERD data with a chain: A → B → C (depth-2 test)
const ERD_CHAIN: DbdocsData = {
  nodes: {},
  lineage: { edges: [], parents: {}, children: {} },
  erd: {
    nodes: [
      { id: "model.s.a", label: "a", resource_type: "model", database: "db", schema: "s", columns: [] },
      { id: "model.s.b", label: "b", resource_type: "model", database: "db", schema: "s", columns: [] },
      { id: "model.s.c", label: "c", resource_type: "model", database: "db", schema: "s", columns: [] },
      { id: "model.s.d", label: "d", resource_type: "model", database: "db", schema: "s", columns: [] },
    ],
    edges: [
      { id: "e0", source: "model.s.a", target: "model.s.b", from_columns: [], to_columns: [] },
      { id: "e1", source: "model.s.b", target: "model.s.c", from_columns: [], to_columns: [] },
    ],
  },
};

describe("erdNeighborhood", () => {
  it("depth 1 returns focus + direct FK neighbors only", () => {
    const result = erdNeighborhood(ERD_CHAIN, "model.s.b", 1);
    expect(result).toEqual(new Set(["model.s.b", "model.s.a", "model.s.c"]));
    expect(result.has("model.s.d")).toBe(false);
  });

  it("depth 2 walks two hops in the undirected FK graph", () => {
    const result = erdNeighborhood(ERD_CHAIN, "model.s.c", 2);
    expect(result).toEqual(new Set(["model.s.c", "model.s.b", "model.s.a"]));
    expect(result.has("model.s.d")).toBe(false);
  });

  it("depth 0 returns only the focus node itself", () => {
    const result = erdNeighborhood(ERD_CHAIN, "model.s.b", 0);
    expect(result).toEqual(new Set(["model.s.b"]));
  });

  it("isolated node returns only itself", () => {
    const result = erdNeighborhood(ERD_CHAIN, "model.s.d", 1);
    expect(result).toEqual(new Set(["model.s.d"]));
  });

  it("edges in either direction are traversed (undirected)", () => {
    const result = erdNeighborhood(ERD_CHAIN, "model.s.a", 1);
    expect(result).toContain("model.s.b");
  });
});

// Fixture for erdRowCount / visibleColumns agreement
const makeRecord = (cols: ErdNodeRecord["columns"]): ErdNodeRecord => ({
  id: "model.s.x",
  label: "x",
  resource_type: "model",
  database: "db",
  schema: "s",
  columns: cols,
});

const ERD_HEADER = 34;
const ERD_ROW = 22;

describe("erdRowCount vs visibleColumns agreement (via buildErdFlow sizes)", () => {
  it("non-compact: height = header + all columns (min 1)", () => {
    const record = makeRecord([
      { name: "id", type: "int", is_primary_key: true },
      { name: "name", type: "text" },
      { name: "val", type: "int" },
    ]);
    const data: DbdocsData = {
      nodes: {},
      lineage: { edges: [], parents: {}, children: {} },
      erd: { nodes: [record], edges: [] },
    };
    const flow = buildErdFlow(data, null, false);
    expect(flow.sizes[0].height).toBe(ERD_HEADER + 3 * ERD_ROW);
  });

  it("non-compact: shows every column even when key columns exist (model-page ERD)", () => {
    const record = makeRecord([
      { name: "id", type: "int", is_primary_key: true },
      { name: "fk", type: "int", is_foreign_key: true },
      { name: "extra1", type: "text" },
      { name: "extra2", type: "text" },
    ]);
    const data: DbdocsData = {
      nodes: {},
      lineage: { edges: [], parents: {}, children: {} },
      erd: { nodes: [record], edges: [] },
    };
    const flow = buildErdFlow(data, null, false);
    expect(flow.sizes[0].height).toBe(ERD_HEADER + 4 * ERD_ROW);
  });

  it("compact: shows only key cols + '+N more' row when non-key cols exist", () => {
    const record = makeRecord([
      { name: "id", type: "int", is_primary_key: true },
      { name: "fk", type: "int", is_foreign_key: true },
      { name: "extra1", type: "text" },
      { name: "extra2", type: "text" },
    ]);
    const data: DbdocsData = {
      nodes: {},
      lineage: { edges: [], parents: {}, children: {} },
      erd: { nodes: [record], edges: [] },
    };
    const flow = buildErdFlow(data, null, true);
    expect(flow.sizes[0].height).toBe(ERD_HEADER + 3 * ERD_ROW);
  });

  it("compact: falls back to all columns when no key columns exist", () => {
    const record = makeRecord([
      { name: "a", type: "text" },
      { name: "b", type: "text" },
    ]);
    const data: DbdocsData = {
      nodes: {},
      lineage: { edges: [], parents: {}, children: {} },
      erd: { nodes: [record], edges: [] },
    };
    const flow = buildErdFlow(data, null, true);
    expect(flow.sizes[0].height).toBe(ERD_HEADER + 2 * ERD_ROW);
  });

  it("compact: all columns keyed → no '+more' row", () => {
    const record = makeRecord([
      { name: "id", type: "int", is_primary_key: true },
      { name: "fk", type: "int", is_foreign_key: true },
    ]);
    const data: DbdocsData = {
      nodes: {},
      lineage: { edges: [], parents: {}, children: {} },
      erd: { nodes: [record], edges: [] },
    };
    const flow = buildErdFlow(data, null, true);
    expect(flow.sizes[0].height).toBe(ERD_HEADER + 2 * ERD_ROW);
  });

  it("non-compact empty columns: min 1 row", () => {
    const record = makeRecord([]);
    const data: DbdocsData = {
      nodes: {},
      lineage: { edges: [], parents: {}, children: {} },
      erd: { nodes: [record], edges: [] },
    };
    const flow = buildErdFlow(data, null, false);
    expect(flow.sizes[0].height).toBe(ERD_HEADER + 1 * ERD_ROW);
  });
});

describe("buildErdFlow with keepIds", () => {
  it("restricts nodes and edges to the provided keepIds set", () => {
    const flow = buildErdFlow(DATA, "model.s.a", false, new Set(["model.s.a"]));
    expect(flow.nodes).toHaveLength(1);
    expect(flow.nodes[0].id).toBe("model.s.a");
    expect(flow.edges).toHaveLength(0);
  });

  it("sets focused flag on the focus node", () => {
    const flow = buildErdFlow(DATA, "model.s.a", false, new Set(["model.s.a", "model.s.b"]));
    const focusNode = flow.nodes.find((n) => n.id === "model.s.a");
    expect((focusNode?.data as { focused?: boolean }).focused).toBe(true);
    const otherNode = flow.nodes.find((n) => n.id === "model.s.b");
    expect((otherNode?.data as { focused?: boolean }).focused).toBe(false);
  });
});

describe("assignErdEdgeSides", () => {
  const SIZES = [
    { id: "a", width: 230, height: 100 },
    { id: "b", width: 230, height: 100 },
  ];
  const edge = (data: Record<string, unknown>): Edge => ({
    id: "e0",
    source: "a",
    target: "b",
    sourceHandle: "x__out__r",
    targetHandle: "y__in__l",
    data,
  });

  it("source exits right / target enters left when target is to the right", () => {
    const pos = new Map([
      ["a", { x: 0, y: 0 }],
      ["b", { x: 1000, y: 0 }],
    ]);
    const [e] = assignErdEdgeSides([edge({ sourceCol: "x", targetCol: "y" })], pos, SIZES);
    expect(e.sourceHandle).toBe("x__out__r");
    expect(e.targetHandle).toBe("y__in__l");
  });

  it("flips to source-left / target-right when target is to the left", () => {
    const pos = new Map([
      ["a", { x: 1000, y: 0 }],
      ["b", { x: 0, y: 0 }],
    ]);
    const [e] = assignErdEdgeSides([edge({ sourceCol: "x", targetCol: "y" })], pos, SIZES);
    expect(e.sourceHandle).toBe("x__out__l");
    expect(e.targetHandle).toBe("y__in__r");
  });

  it("uses table-level handles when an endpoint has no resolved column", () => {
    const pos = new Map([
      ["a", { x: 0, y: 0 }],
      ["b", { x: 1000, y: 0 }],
    ]);
    const [e] = assignErdEdgeSides([edge({ sourceCol: null, targetCol: null })], pos, SIZES);
    expect(e.sourceHandle).toBe("__table__out__r");
    expect(e.targetHandle).toBe("__table__in__l");
  });

  it("leaves an edge untouched when a node has no position", () => {
    const pos = new Map([["a", { x: 0, y: 0 }]]);
    const orig = edge({ sourceCol: "x", targetCol: "y" });
    const [e] = assignErdEdgeSides([orig], pos, SIZES);
    expect(e.sourceHandle).toBe("x__out__r");
    expect(e.targetHandle).toBe("y__in__l");
  });
});
