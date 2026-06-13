import { describe, expect, it } from "vitest";
import { buildDagHash } from "@/components/GraphApp";

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
