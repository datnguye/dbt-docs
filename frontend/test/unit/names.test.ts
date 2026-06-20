import { describe, expect, it } from "vitest";
import { shortName } from "@/lib/names";

describe("shortName", () => {
  it("returns the last dot-segment of a unique_id", () => {
    expect(shortName("model.jaffle_shop.orders")).toBe("orders");
    expect(shortName("model.mandai_athena_dbt.fact_sales_all")).toBe("fact_sales_all");
  });

  it("returns the value unchanged when there is no dot", () => {
    expect(shortName("orders")).toBe("orders");
  });

  it("falls back to the full id rather than an empty string for a trailing dot", () => {
    expect(shortName("model.")).toBe("model.");
  });
});
