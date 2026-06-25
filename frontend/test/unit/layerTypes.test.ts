import { describe, expect, it } from "vitest";
import { CATALOG_RTYPES, layerTypes, OTHER_RTYPES, SEMANTIC_RTYPES } from "@/lib/data";

describe("CATALOG_RTYPES", () => {
  it("contains the six physical resource types", () => {
    expect(CATALOG_RTYPES.has("model")).toBe(true);
    expect(CATALOG_RTYPES.has("source")).toBe(true);
    expect(CATALOG_RTYPES.has("seed")).toBe(true);
    expect(CATALOG_RTYPES.has("snapshot")).toBe(true);
    expect(CATALOG_RTYPES.has("analysis")).toBe(true);
    expect(CATALOG_RTYPES.has("operation")).toBe(true);
  });

  it("does not contain semantic-layer or other types", () => {
    expect(CATALOG_RTYPES.has("metric")).toBe(false);
    expect(CATALOG_RTYPES.has("semantic_model")).toBe(false);
    expect(CATALOG_RTYPES.has("saved_query")).toBe(false);
    expect(CATALOG_RTYPES.has("unit_test")).toBe(false);
    expect(CATALOG_RTYPES.has("exposure")).toBe(false);
  });
});

describe("SEMANTIC_RTYPES", () => {
  it("contains exactly the three dbt Semantic Layer resource types", () => {
    expect(SEMANTIC_RTYPES.has("metric")).toBe(true);
    expect(SEMANTIC_RTYPES.has("semantic_model")).toBe(true);
    expect(SEMANTIC_RTYPES.has("saved_query")).toBe(true);
    expect(SEMANTIC_RTYPES.size).toBe(3);
  });

  it("does not contain unit_test or exposure (those are 'other')", () => {
    expect(SEMANTIC_RTYPES.has("unit_test")).toBe(false);
    expect(SEMANTIC_RTYPES.has("exposure")).toBe(false);
  });

  it("does not contain physical types", () => {
    expect(SEMANTIC_RTYPES.has("model")).toBe(false);
    expect(SEMANTIC_RTYPES.has("source")).toBe(false);
    expect(SEMANTIC_RTYPES.has("seed")).toBe(false);
    expect(SEMANTIC_RTYPES.has("snapshot")).toBe(false);
    expect(SEMANTIC_RTYPES.has("analysis")).toBe(false);
    expect(SEMANTIC_RTYPES.has("operation")).toBe(false);
  });
});

describe("OTHER_RTYPES", () => {
  it("contains the typeless non-semantic-layer resource types", () => {
    expect(OTHER_RTYPES.has("unit_test")).toBe(true);
    expect(OTHER_RTYPES.has("exposure")).toBe(true);
    expect(OTHER_RTYPES.size).toBe(2);
  });

  it("does not overlap catalog or semantic", () => {
    expect(OTHER_RTYPES.has("model")).toBe(false);
    expect(OTHER_RTYPES.has("metric")).toBe(false);
    expect(OTHER_RTYPES.has("saved_query")).toBe(false);
  });
});

describe("layerTypes", () => {
  it("returns catalog types for layer=catalog", () => {
    const types = layerTypes("catalog");
    expect(types.has("model")).toBe(true);
    expect(types.has("source")).toBe(true);
    expect(types.has("metric")).toBe(false);
  });

  it("returns semantic types for layer=semantic", () => {
    const types = layerTypes("semantic");
    expect(types.has("metric")).toBe(true);
    expect(types.has("semantic_model")).toBe(true);
    expect(types.has("unit_test")).toBe(false);
    expect(types.has("model")).toBe(false);
  });

  it("returns other types for layer=other", () => {
    const types = layerTypes("other");
    expect(types.has("unit_test")).toBe(true);
    expect(types.has("exposure")).toBe(true);
    expect(types.has("metric")).toBe(false);
    expect(types.has("model")).toBe(false);
  });

  it("returns every type for layer=all", () => {
    const types = layerTypes("all");
    expect(types.has("model")).toBe(true);
    expect(types.has("source")).toBe(true);
    expect(types.has("metric")).toBe(true);
    expect(types.has("semantic_model")).toBe(true);
    expect(types.has("saved_query")).toBe(true);
    expect(types.has("unit_test")).toBe(true);
    expect(types.has("exposure")).toBe(true);
    expect(types.has("seed")).toBe(true);
    expect(types.has("snapshot")).toBe(true);
    expect(types.has("analysis")).toBe(true);
    expect(types.has("operation")).toBe(true);
  });

  it("the three bands are pairwise disjoint", () => {
    const bands = [layerTypes("catalog"), layerTypes("semantic"), layerTypes("other")];
    for (let i = 0; i < bands.length; i++) {
      for (let j = i + 1; j < bands.length; j++) {
        for (const t of bands[i]) {
          expect(bands[j].has(t)).toBe(false);
        }
      }
    }
  });

  it("all = union of catalog, semantic, and other", () => {
    const cat = layerTypes("catalog");
    const sem = layerTypes("semantic");
    const other = layerTypes("other");
    const all = layerTypes("all");
    for (const band of [cat, sem, other]) {
      for (const t of band) {
        expect(all.has(t)).toBe(true);
      }
    }
    expect(all.size).toBe(cat.size + sem.size + other.size);
  });
});
