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
    // The Columns table is present (a node page may also carry a Tests table).
    await expect(page.locator("#app table").first()).toBeVisible();
  });

  test("clicking the logo returns to the catalog overview", async ({ page }) => {
    await page.goto("index.html#/node/model.jaffle_shop.orders");
    await expect(page.locator("#app h1")).toContainText("orders");
    await page.locator(".brand-home").click();
    await expect(page).toHaveURL(/#\/overview$/);
    await expect(page.locator(".cards .card").first()).toBeVisible();
  });

  test("nav icons render (CSS mask is applied, not blank)", async ({ page }) => {
    await page.goto("index.html");
    const healthIcon = page.locator('[data-nav="health"] .ic--health');
    await expect(healthIcon).toBeVisible();
    // The mask data-URI must be resolved (a real url(), not empty/none).
    const mask = await healthIcon.evaluate(
      (el) => getComputedStyle(el).maskImage || getComputedStyle(el).webkitMaskImage,
    );
    expect(mask).toContain("url(");
    expect(mask).toContain("svg");
  });

  test("the sidebar tree filters by table name and by database.schema.table", async ({ page }) => {
    await page.goto("index.html");
    const filter = page.locator("#nav-filter");
    await expect(filter).toBeVisible();
    const ordersItem = page.locator('#sidebar li[data-filter] a[data-node="model.jaffle_shop.orders"]');
    const customersItem = page.locator('#sidebar li[data-filter] a[data-node="model.jaffle_shop.customers"]');
    // Filter by bare table name.
    await filter.fill("orders");
    await expect(ordersItem).toBeVisible();
    await expect(customersItem).toBeHidden();
    // Filter by fully-qualified database.schema.table.
    await filter.fill("shaman.jf_analytics.customers");
    await expect(customersItem).toBeVisible();
    await expect(ordersItem).toBeHidden();
    // Clearing restores the full tree.
    await filter.fill("");
    await expect(ordersItem).toBeVisible();
    await expect(customersItem).toBeVisible();
  });

  test("the left pane collapses from the divider handle and reopens via the rail", async ({ page }) => {
    await page.setViewportSize({ width: 1200, height: 800 });
    await page.goto("index.html");
    const sidebar = page.locator(".sidebar-col");
    await expect(sidebar).toBeVisible();
    // The « collapse handle lives on the sidebar's divider edge (hover-revealed),
    // not the top-left corner.
    await sidebar.hover();
    await page.locator("#nav-collapse").click();
    await expect(page.locator("body")).toHaveClass(/nav-collapsed/);
    await expect(async () => {
      const box = await sidebar.boundingBox();
      expect(box?.width ?? 0).toBeLessThan(2);
    }).toPass();
    // A » rail appears, flush to the left edge and vertically centered (not
    // floating mid-content at the top).
    const rail = page.locator("#nav-reopen");
    await expect(rail).toBeVisible();
    const railBox = await rail.boundingBox();
    expect(railBox!.x).toBeLessThan(4); // flush against the left edge
    expect(railBox!.y).toBeGreaterThan(200); // centered, not near the top
    await rail.click();
    await expect(page.locator("body")).not.toHaveClass(/nav-collapsed/);
    await expect(async () => {
      const box = await sidebar.boundingBox();
      expect(box?.width ?? 0).toBeGreaterThan(100);
    }).toPass();
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

  test("downstream impact column header renders and chips deep-link to the dependent column", async ({ page }) => {
    // stg_customers.customer_id feeds customers.customer_id and
    // dim_customer_segment.customer_id — a guaranteed downstream in the fixture.
    await page.goto("index.html#/node/model.jaffle_shop.stg_customers");

    // The "Downstream impact" column header must be present in the Columns table.
    const header = page.locator("table th").filter({ hasText: "Downstream impact" });
    await expect(header).toBeVisible();

    // At least one downstream chip must exist and its link must carry ?col=.
    const chip = page.locator(".up-chip a").first();
    await expect(chip).toBeVisible();
    const href = await chip.getAttribute("href");
    expect(href).toMatch(/\?col=/);

    // Clicking the chip navigates to the dependent node with the ?col= deep-link.
    await chip.click();
    await expect(page).toHaveURL(/\?col=/);
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

  test("DAG nodes are not hand-draggable (layout stays fixed)", async ({ page }) => {
    await page.goto("index.html#/dag");
    const node = page.locator(".react-flow__node").first();
    await expect(node).toBeVisible();
    // React Flow adds the `draggable` class only when nodesDraggable is on.
    await expect(node).not.toHaveClass(/draggable/);
    // Dragging a node drags the *canvas* (pan), not the node: the node and a
    // sibling keep the same relative offset (an individually-dragged node would
    // shift relative to its neighbour).
    const sibling = page.locator(".react-flow__node").nth(1);
    await expect(sibling).toBeVisible();
    const beforeNode = await node.boundingBox();
    const beforeSib = await sibling.boundingBox();
    const dx0 = beforeSib!.x - beforeNode!.x;
    const dy0 = beforeSib!.y - beforeNode!.y;
    await node.hover();
    await page.mouse.down();
    await page.mouse.move(beforeNode!.x + 120, beforeNode!.y + 80, { steps: 8 });
    await page.mouse.up();
    const afterNode = await node.boundingBox();
    const afterSib = await sibling.boundingBox();
    expect(Math.abs(afterSib!.x - afterNode!.x - dx0)).toBeLessThan(3);
    expect(Math.abs(afterSib!.y - afterNode!.y - dy0)).toBeLessThan(3);
  });

  test("a filter that matches no nodes shows a 'no match' message, not 'too many models'", async ({ page }) => {
    // Sources only live in schema 'raw'; source + jf_analytics matches nothing.
    await page.goto("index.html#/dag?rtype=source&schema=jf_analytics");
    const empty = page.locator(".dbd-graph-empty");
    await expect(empty).toBeVisible();
    await expect(empty).toContainText("No nodes match the selected filter");
    await expect(empty).not.toContainText("too many models");
  });

  test("an entity with no detected relationships shows the empty-ERD message", async ({ page }) => {
    await page.goto("index.html#/node/model.jaffle_shop.customers");
    const empty = page.locator(".dbd-graph-empty");
    await expect(empty).toBeVisible();
    await expect(empty).toContainText("No ERD relationships detected");
    await expect(empty.locator('a[href*="dbterd.datnguye.me"]')).toBeVisible();
  });
});

test.describe("deep-link URL state (B1 + B2)", () => {
  test("selecting the resource-type filter writes rtype= into location.hash", async ({ page }) => {
    await page.goto("index.html#/dag");
    // Wait for the DAG graph toolbar to appear (React rendered)
    const select = page.locator(".dbd-toolbar select").first();
    await expect(select).toBeVisible();
    await select.selectOption("model");
    // The hash should now contain rtype=model (written by the useEffect via replaceState)
    await expect(async () => {
      const hash = await page.evaluate(() => location.hash);
      expect(hash).toContain("rtype=model");
    }).toPass({ timeout: 3000 });
  });

  test("navigating to a DAG hash with rtype= restores the filter select value", async ({ page }) => {
    await page.goto("index.html#/dag?rtype=source");
    const select = page.locator(".dbd-toolbar select").first();
    await expect(select).toBeVisible();
    // The select should be seeded from the dataset attr (forwarded from the hash)
    await expect(select).toHaveValue("source");
  });

  test("arriving at a DAG hash with focus= preserves the focus (no clobber)", async ({ page }) => {
    // The replaceState effect must NOT strip an incoming focus= on mount: search
    // seeds from the focused node's label so focusId re-resolves to the same id.
    await page.goto("index.html");
    // Grab a real node id from the rendered sidebar tree.
    const focusId = await page.locator("[data-node]").first().getAttribute("data-node");
    expect(focusId).toBeTruthy();
    await page.goto("index.html#/dag?focus=" + encodeURIComponent(focusId as string));
    await expect(async () => {
      const hash = await page.evaluate(() => location.hash);
      expect(hash).toContain("focus=" + encodeURIComponent(focusId as string));
    }).toPass({ timeout: 3000 });
  });

  test("selecting the schema filter writes schema= into location.hash", async ({ page }) => {
    await page.goto("index.html#/dag");
    const schemaSelect = page.locator(".dbd-toolbar select").nth(1);
    await expect(schemaSelect).toBeVisible();
    // Pick the first non-empty schema option
    const options = schemaSelect.locator("option");
    const count = await options.count();
    if (count > 1) {
      const secondOption = await options.nth(1).getAttribute("value");
      if (secondOption) {
        await schemaSelect.selectOption(secondOption);
        await expect(async () => {
          const hash = await page.evaluate(() => location.hash);
          expect(hash).toContain("schema=");
        }).toPass({ timeout: 3000 });
      }
    }
  });

  test("copy-link button exists on node page and flips label on click", async ({ page, context }) => {
    // Grant clipboard permission so writeText doesn't throw in headless Chromium
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.goto("index.html#/node/model.jaffle_shop.orders");
    const btn = page.locator(".copy-link-btn").first();
    await expect(btn).toBeVisible();
    // The button should start with "Copy link"
    await expect(btn).toContainText("Copy link");
    await btn.click();
    // After click the label briefly changes to "Copied!" and the .copied accent
    // class is toggled on (the live CSS feedback path).
    await expect(btn).toContainText("Copied!");
    await expect(btn).toHaveClass(/copied/);
    // Then reverts back to "Copy link" and drops the .copied class after the timeout
    await expect(btn).toContainText("Copy link", { timeout: 3000 });
    await expect(btn).not.toHaveClass(/copied/);
  });

  test("copy-link button exists on DAG page", async ({ page }) => {
    await page.goto("index.html#/dag");
    // Wait for the page to render (the graph is async)
    await expect(page.locator(".page-head")).toBeVisible();
    const btn = page.locator(".page-head .copy-link-btn");
    await expect(btn).toBeVisible();
    await expect(btn).toContainText("Copy link");
  });
});

test.describe("health check", () => {
  // The demo build (docs/dbdocs-demo.yml) ships a run_results sample alongside
  // the artifacts, so the Health page renders all six DPE dimensions (manifest-
  // derived) plus the per-test pass/fail detail under the testing dimension.
  test("a Health Check nav entry appears and opens the findings page", async ({ page }) => {
    await page.goto("index.html");
    const nav = page.locator('[data-nav="health"]');
    await expect(nav).toBeVisible();
    await nav.click();
    await expect(page).toHaveURL(/#\/health$/);
    await expect(page.locator("#app h1")).toContainText("Health Check");
    await expect(nav).toHaveClass(/active/);
  });

  test("the overview shows a Health Check card with a mini scorecard", async ({ page }) => {
    await page.goto("index.html#/overview");
    const card = page.locator(".health-card");
    await expect(card).toBeVisible();
    await expect(card.locator(".health-card-title")).toContainText("Health Check");
    // The card embeds the scorecard (one chip per dimension).
    await expect(card.locator(".health-scorecard .score-chip").first()).toBeVisible();
    await card.locator(".health-card-link").click();
    await expect(page).toHaveURL(/#\/health$/);
  });

  test("an overview scorecard chip deep-links to its dimension section", async ({ page }) => {
    await page.goto("index.html#/overview");
    // Click the Structure chip on the overview card.
    const chip = page.locator(".health-card .score-chip", { hasText: "Structure" });
    await chip.click();
    await expect(page).toHaveURL(/#\/health\?d=structure/);
    // That dimension's section is rendered, open, and its body visible.
    const section = page.locator("#health-structure");
    await expect(section).toBeVisible();
    await expect(section).toHaveJSProperty("open", true);
    await expect(section.locator(".health-section-body")).toBeVisible();
  });

  test("the health page shows a scorecard with all six dimensions", async ({ page }) => {
    await page.goto("index.html#/health");
    const chips = page.locator("#app .health-scorecard .score-chip");
    await expect(chips).toHaveCount(6);
    // Each chip shows a score percentage.
    await expect(chips.first().locator(".score-num")).toContainText(/%/);
    // One collapsible section per dimension.
    await expect(page.locator("details.health-section")).toHaveCount(6);
  });

  test("a dimension section lists rule findings with node deep-links", async ({ page }) => {
    await page.goto("index.html#/health");
    // The Structure dimension has naming-convention findings in the demo.
    const section = page.locator("details.health-section", { hasText: "Structure" });
    await expect(section).toBeVisible();
    // A per-rule block with a node table is present.
    await expect(section.locator(".health-rule").first()).toBeVisible();
    const nodeLink = section.locator('a[href^="#/node/"]').first();
    await expect(nodeLink).toBeVisible();
  });

  test("the health page no longer embeds per-test results", async ({ page }) => {
    // Test pass/fail detail moved to model pages; the Health page is dimensions only.
    await page.goto("index.html#/health");
    await expect(page.locator(".health-testresults")).toHaveCount(0);
  });

  test("a model page shows its data-test results with reconciling pills", async ({ page }) => {
    // stg_customers has unique/not_null tests in the demo run_results.
    await page.goto("index.html#/node/model.jaffle_shop.stg_customers");
    const tests = page.locator(".node-tests");
    await expect(tests).toBeVisible();
    await expect(tests.locator("h2")).toContainText("Tests");
    // The data-tests subsection is present (the fixture has no unit tests).
    await expect(tests.locator("h3", { hasText: "Data tests" })).toBeVisible();
    await expect(tests.locator(".health-status").first()).toBeVisible();
    // Pills reconcile: non-total pills sum to total.
    const labels = await tests.locator(".health-pills .health-pill").allTextContents();
    const num = (s: string) => parseInt(s.trim().split(/\s+/)[0], 10) || 0;
    let total = 0;
    let sum = 0;
    for (const label of labels) {
      if (/total/.test(label)) total = num(label);
      else sum += num(label);
    }
    expect(total).toBeGreaterThan(0);
    expect(sum).toBe(total);
  });

  test("dimension sections are collapsible (toggle on click)", async ({ page }) => {
    await page.goto("index.html#/health");
    // The Structure dimension has issues, so it's open by default.
    const section = page.locator("details.health-section", { hasText: "Structure" });
    await expect(section).toHaveJSProperty("open", true);
    // Click the title (a stable target inside the summary) to collapse / expand.
    const title = section.locator(".health-section-title");
    await title.click();
    await expect(section).toHaveJSProperty("open", false);
    await title.click();
    await expect(section).toHaveJSProperty("open", true);
  });

  test("the copy-link button is present on the health page", async ({ page }) => {
    await page.goto("index.html#/health");
    const btn = page.locator(".page-head .copy-link-btn");
    await expect(btn).toBeVisible();
    await expect(btn).toContainText("Copy link");
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
