import { describe, expect, it } from "vitest";
import { buildDagHash } from "@/components/GraphApp";

// Tests for the multi-select rtype dropdown's pure-logic layer: the Set↔string
// serialization that feeds into buildDagHash and seeds from the URL hash.
// Rendering/interaction behavior is covered by the Playwright E2E suite.

describe("rtype Set serialization (multi-select dropdown)", () => {
  it("empty Set produces no rtype param", () => {
    expect(buildDagHash(null, new Set(), "")).toBe("#/dag");
  });

  it("single-type Set produces rtype=<value>", () => {
    expect(buildDagHash(null, new Set(["model"]), "")).toBe("#/dag?rtype=model");
  });

  it("multi-type Set produces comma-joined rtype sorted alphabetically", () => {
    const hash = buildDagHash(null, new Set(["metric", "model"]), "");
    const rtypeRaw = decodeURIComponent(
      hash.replace(/.*rtype=/, "").replace(/&.*/, ""),
    );
    expect(rtypeRaw.split(",").sort()).toEqual(["metric", "model"]);
  });

  it("all three types present produce a comma list with each type", () => {
    const hash = buildDagHash(null, new Set(["model", "source", "metric"]), "");
    const rtypeRaw = decodeURIComponent(
      hash.replace(/.*rtype=/, "").replace(/&.*/, ""),
    );
    const parts = rtypeRaw.split(",").sort();
    expect(parts).toEqual(["metric", "model", "source"]);
  });

  it("rtype= param round-trips: comma-split restores the original types", () => {
    const original = new Set(["model", "metric", "saved_query"]);
    const hash = buildDagHash(null, original, "");
    const raw = decodeURIComponent(
      hash.replace(/.*rtype=/, "").replace(/&.*/, ""),
    );
    const restored = new Set(raw.split(",").filter(Boolean));
    expect(restored).toEqual(original);
  });

  it("combining multi-rtype with focus and schema emits all three params", () => {
    const hash = buildDagHash("model.p.a", new Set(["model", "metric"]), "mart");
    expect(hash).toContain("focus=");
    expect(hash).toContain("rtype=");
    expect(hash).toContain("schema=mart");
  });
});
