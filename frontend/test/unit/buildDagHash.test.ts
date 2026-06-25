import { describe, expect, it } from "vitest";
import { buildDagHash, buildErdHash } from "@/components/GraphApp";

describe("buildDagHash", () => {
  it("returns #/dag when all params are empty", () => {
    expect(buildDagHash(null, new Set(), "")).toBe("#/dag");
  });

  it("includes focus when provided", () => {
    expect(buildDagHash("model.shop.orders", new Set(), "")).toBe(
      "#/dag?focus=model.shop.orders",
    );
  });

  it("includes rtype when provided as a Set with one value", () => {
    expect(buildDagHash(null, new Set(["model"]), "")).toBe("#/dag?rtype=model");
  });

  it("emits comma-joined rtype when multiple types are selected", () => {
    const hash = buildDagHash(null, new Set(["model", "metric"]), "");
    expect(hash).toContain("rtype=");
    const rtypeParam = decodeURIComponent(hash.split("rtype=")[1].split("&")[0]);
    const parts = rtypeParam.split(",").sort();
    expect(parts).toEqual(["metric", "model"]);
  });

  it("omits rtype entirely when the Set is empty (show all)", () => {
    expect(buildDagHash(null, new Set(), "")).toBe("#/dag");
  });

  it("includes schema when provided", () => {
    expect(buildDagHash(null, new Set(), "mart")).toBe("#/dag?schema=mart");
  });

  it("includes all non-empty params in order: focus, rtype, schema", () => {
    expect(buildDagHash("model.shop.orders", new Set(["model"]), "mart")).toBe(
      "#/dag?focus=model.shop.orders&rtype=model&schema=mart",
    );
  });

  it("URL-encodes special characters in values", () => {
    const hash = buildDagHash("model.my project.a b", new Set(["model"]), "my schema");
    expect(hash).toContain("focus=model.my%20project.a%20b");
    expect(hash).toContain("schema=my%20schema");
  });

  it("omits layer param when layer is the default (catalog)", () => {
    expect(buildDagHash(null, new Set(), "", "catalog")).toBe("#/dag");
  });

  it("includes layer=semantic when layer is semantic", () => {
    expect(buildDagHash(null, new Set(), "", "semantic")).toBe("#/dag?layer=semantic");
  });

  it("includes layer=other when layer is other", () => {
    expect(buildDagHash(null, new Set(), "", "other")).toBe("#/dag?layer=other");
  });

  it("includes layer=all when layer is all", () => {
    expect(buildDagHash(null, new Set(), "", "all")).toBe("#/dag?layer=all");
  });

  it("emits all params together: focus, rtype, schema, layer", () => {
    expect(
      buildDagHash("model.shop.orders", new Set(["metric"]), "mart", "semantic"),
    ).toBe("#/dag?focus=model.shop.orders&rtype=metric&schema=mart&layer=semantic");
  });

  it("layer defaults to catalog when omitted from call", () => {
    expect(buildDagHash(null, new Set(), "")).toBe("#/dag");
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
