import { describe, expect, it } from "vitest";
import { buildDagHash, buildErdHash } from "@/components/GraphApp";

describe("buildDagHash", () => {
  it("returns #/dag when all params are empty", () => {
    expect(buildDagHash(null, "", "")).toBe("#/dag");
  });

  it("includes focus when provided", () => {
    expect(buildDagHash("model.shop.orders", "", "")).toBe(
      "#/dag?focus=model.shop.orders",
    );
  });

  it("includes rtype when provided", () => {
    expect(buildDagHash(null, "model", "")).toBe("#/dag?rtype=model");
  });

  it("includes schema when provided", () => {
    expect(buildDagHash(null, "", "mart")).toBe("#/dag?schema=mart");
  });

  it("includes all non-empty params in order: focus, rtype, schema", () => {
    expect(buildDagHash("model.shop.orders", "model", "mart")).toBe(
      "#/dag?focus=model.shop.orders&rtype=model&schema=mart",
    );
  });

  it("URL-encodes special characters in values", () => {
    const hash = buildDagHash("model.my project.a b", "model", "my schema");
    expect(hash).toContain("focus=model.my%20project.a%20b");
    expect(hash).toContain("schema=my%20schema");
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
