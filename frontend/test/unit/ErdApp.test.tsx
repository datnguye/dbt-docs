import { describe, expect, it } from "vitest";
import { resolveLayout, type SizedErdNode } from "@datnguye/erd-flow";
import { buildErdHash, erdEstimateSize, toErdPayload } from "@/components/ErdApp";
import type { DbdocsData } from "@/lib/types";

const DATA: DbdocsData = {
  nodes: {},
  lineage: { edges: [], parents: {}, children: {} },
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
      {
        id: "e0",
        to_id: "model.s.a",
        from_id: "model.s.b",
        from_columns: ["a_id"],
        to_columns: ["id"],
        relationship_type: "fk",
        cardinality: "n1",
      },
    ],
  },
  metadata: { erd_algo: "model_contract" },
};

describe("toErdPayload", () => {
  it("maps each erd node's label to the package's name field", () => {
    const payload = toErdPayload(DATA);
    expect(payload.nodes).toHaveLength(2);
    expect(payload.nodes[0]).toMatchObject({ id: "model.s.a", name: "a", label: "a" });
    expect(payload.nodes[1]).toMatchObject({ id: "model.s.b", name: "b", label: "b" });
  });

  it("passes edges through unchanged when no schema filter is given", () => {
    const payload = toErdPayload(DATA);
    expect(payload.edges).toEqual(DATA.erd.edges);
  });

  it("carries erd_algo through metadata", () => {
    const payload = toErdPayload(DATA);
    expect(payload.metadata).toEqual({ erd_algo: "model_contract" });
  });

  it("filters nodes to the given schema", () => {
    const payload = toErdPayload(DATA, "raw");
    expect(payload.nodes.map((n) => n.id)).toEqual(["model.s.a"]);
  });

  it("drops edges left dangling by the schema filter", () => {
    const payload = toErdPayload(DATA, "raw");
    expect(payload.edges).toHaveLength(0);
  });

  it("keeps all nodes and edges when schema is null/undefined", () => {
    expect(toErdPayload(DATA, null).nodes).toHaveLength(2);
    expect(toErdPayload(DATA).nodes).toHaveLength(2);
  });

  it("handles a missing erd section by returning an empty payload", () => {
    const noErd = { nodes: {}, lineage: { edges: [], parents: {}, children: {} } } as unknown as DbdocsData;
    const payload = toErdPayload(noErd);
    expect(payload.nodes).toEqual([]);
    expect(payload.edges).toEqual([]);
  });
});

describe("erdEstimateSize", () => {
  const base = { id: "model.s.a", name: "a", columns: [] as { name: string }[] };

  it("uses the fixed 230px width and header + one 22px slot per column", () => {
    const node = { ...base, columns: [{ name: "id" }, { name: "x" }, { name: "y" }] };
    expect(erdEstimateSize(node, 3, false)).toEqual({ width: 230, height: 34 + 3 * 22 });
  });

  it("reserves a slot for the '+N more columns' row when columns were compacted", () => {
    const node = { ...base, columns: [{ name: "id" }], hidden_column_count: 5 };
    expect(erdEstimateSize(node, 1, false)).toEqual({ width: 230, height: 34 + 2 * 22 });
  });

  it("a column-less table still gets one row slot", () => {
    expect(erdEstimateSize(base, 0, false)).toEqual({ width: 230, height: 34 + 22 });
  });
});

describe("snowflake layout registration", () => {
  const sized = (id: string, height = 80): SizedErdNode => ({
    id,
    name: id,
    columns: [],
    width: 230,
    height,
  });

  it("importing ErdApp registers the snowflake engine (distinct from the default)", () => {
    const engine = resolveLayout("snowflake");
    expect(engine).not.toBe(resolveLayout("no-such-layout"));
  });

  it("centers on the explicit centerId with the ring math (center at origin)", () => {
    const out = resolveLayout("snowflake")(
      [sized("center", 100), sized("a"), sized("b")],
      [
        { id: "e0", from_id: "center", to_id: "a" },
        { id: "e1", from_id: "center", to_id: "b" },
      ],
      { centerId: "center" },
    );
    const center = out.find((n) => n.id === "center")!;
    expect(center.x).toBeCloseTo(-230 / 2, 0);
    expect(center.y).toBeCloseTo(-100 / 2, 0);
  });

  it("auto-centers on the most-connected node when no centerId is given", () => {
    const out = resolveLayout("snowflake")(
      [sized("hub", 100), sized("a"), sized("b")],
      [
        { id: "e0", from_id: "a", to_id: "hub" },
        { id: "e1", from_id: "b", to_id: "hub" },
      ],
      {},
    );
    const hub = out.find((n) => n.id === "hub")!;
    expect(hub.x).toBeCloseTo(-230 / 2, 0);
    expect(hub.y).toBeCloseTo(-100 / 2, 0);
  });
});

describe("buildErdHash", () => {
  it("returns #/overview when all params are default", () => {
    expect(buildErdHash(null, "")).toBe("#/overview");
  });

  it("includes erd_focus when provided", () => {
    expect(buildErdHash("model.shop.orders", "")).toBe(
      "#/overview?erd_focus=model.shop.orders",
    );
  });

  it("includes erd_schema when provided", () => {
    expect(buildErdHash(null, "analytics")).toBe("#/overview?erd_schema=analytics");
  });

  it("includes all non-default params in order: erd_focus, erd_schema", () => {
    expect(buildErdHash("model.shop.orders", "analytics")).toBe(
      "#/overview?erd_focus=model.shop.orders&erd_schema=analytics",
    );
  });

  it("URL-encodes special characters in erd_focus", () => {
    const hash = buildErdHash("model.my project.a b", "");
    expect(hash).toContain("erd_focus=model.my%20project.a%20b");
  });
});
