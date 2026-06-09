import { expect, test } from "@playwright/test";

// End-to-end tests for the generated dbdocs SPA, driven against a real build of
// the committed jaffle_shop fixtures (see playwright.config.ts webServer). These
// assert the documented SPA contract — payload load, navigation, search, the
// graph, and the responsive chrome — not incidental markup.

test.describe("catalog + navigation", () => {
  test("loads the SPA from the gzipped payload with no console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => {
      // The unversioned-build versions.json probe 404s by design (caught).
      if (m.type() === "error" && !/versions\.json/.test(m.text())) errors.push(m.text());
    });

    const dataResponses: number[] = [];
    page.on("response", (r) => {
      if (r.url().includes("dbdocs-data.json.gz")) dataResponses.push(r.status());
    });

    await page.goto("index.html");
    await expect(page.locator("#brand-name")).toHaveText("dbdocs demo — jaffle_shop");
    expect(dataResponses).toContain(200);
    await expect(page.locator(".cards .card").first()).toBeVisible();
    expect(errors).toEqual([]);
  });

  test("sidebar tree renders nodes and a click opens the node page", async ({ page }) => {
    await page.goto("index.html");
    const firstNode = page.locator("#sidebar [data-node]").first();
    await expect(firstNode).toBeVisible();
    await firstNode.click();
    await expect(page.locator("#app h1")).toBeVisible();
    await expect(page.locator("#app table")).toBeVisible();
  });

  test("clicking the logo returns to the catalog overview", async ({ page }) => {
    await page.goto("index.html#/node/model.jaffle_shop.orders");
    await expect(page.locator("#app h1")).toContainText("orders");
    await page.locator(".brand-home").click();
    await expect(page).toHaveURL(/#\/overview$/);
    await expect(page.locator(".cards .card").first()).toBeVisible();
  });
});

test.describe("search", () => {
  test("filters to matching models and navigates on pick", async ({ page }) => {
    await page.goto("index.html");
    await page.fill("#search", "orders");
    const result = page.locator("#search-results a").first();
    await expect(result).toBeVisible();
    await result.click();
    await expect(page.locator("#app h1")).toContainText("orders");
  });
});

test.describe("column-level lineage", () => {
  test("an upstream chip deep-links to and highlights the target column", async ({ page }) => {
    await page.goto("index.html#/node/model.jaffle_shop.customers");
    const chip = page.locator(".up-chip a").first();
    await expect(chip).toBeVisible();
    await chip.click();
    await expect(page).toHaveURL(/\?col=/);
    const flashed = page.locator("tr.col-flash");
    await expect(flashed).toHaveCount(1);
  });
});

test.describe("graphs", () => {
  test("the DAG focuses to a node's neighborhood", async ({ page }) => {
    await page.goto("index.html#/dag");
    const all = page.locator(".react-flow__node");
    await expect(all.first()).toBeVisible();
    const total = await all.count();
    await page.fill(".dbd-toolbar input", "orders");
    await expect(async () => {
      expect(await all.count()).toBeLessThan(total);
    }).toPass();
  });

  test("an entity with no detected relationships shows the empty-ERD message", async ({ page }) => {
    await page.goto("index.html#/node/model.jaffle_shop.customers");
    const empty = page.locator(".dbd-graph-empty");
    await expect(empty).toBeVisible();
    await expect(empty).toContainText("No ERD relationships detected");
    await expect(empty.locator('a[href*="dbterd.datnguye.me"]')).toBeVisible();
  });
});

test.describe("theme", () => {
  test("toggles dark/light", async ({ page }) => {
    await page.goto("index.html");
    const html = page.locator("html");
    const before = await html.getAttribute("data-theme");
    await page.locator("#theme-toggle").click();
    await expect(html).not.toHaveAttribute("data-theme", before ?? "");
  });
});

test.describe("mobile", () => {
  test.use({ viewport: { width: 375, height: 700 } });

  test("the sidebar collapses into a drawer the hamburger toggles", async ({ page }) => {
    await page.goto("index.html");
    const sidebar = page.locator(".sidebar-col");
    // Off-canvas by default (translated out of view).
    const closed = await sidebar.boundingBox();
    expect(closed && closed.x).toBeLessThan(0);
    await page.locator("#nav-toggle").click();
    await expect(page.locator("body")).toHaveClass(/nav-open/);
    // Slid on-screen once the open transition settles.
    await expect(async () => {
      const open = await sidebar.boundingBox();
      expect(open && open.x).toBeGreaterThanOrEqual(0);
    }).toPass();
    // Navigating closes the drawer.
    await page.locator("#sidebar [data-node]").first().click();
    await expect(page.locator("body")).not.toHaveClass(/nav-open/);
  });

  test("search is behind an icon that reveals the input", async ({ page }) => {
    await page.goto("index.html");
    await expect(page.locator("#search")).toBeHidden();
    await page.locator("#search-toggle").click();
    await expect(page.locator("#search")).toBeVisible();
    await expect(page.locator("#search")).toBeFocused();
  });
});
