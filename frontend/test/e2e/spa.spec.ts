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
    await filter.fill("orders");
    await expect(ordersItem).toBeVisible();
    await expect(customersItem).toBeHidden();
    await filter.fill("shaman.jf_analytics.customers");
    await expect(customersItem).toBeVisible();
    await expect(ordersItem).toBeHidden();
    await filter.fill("");
    await expect(ordersItem).toBeVisible();
    await expect(customersItem).toBeVisible();
  });

  test("the left pane collapses from the divider handle and reopens via the rail", async ({ page }) => {
    await page.setViewportSize({ width: 1200, height: 800 });
    await page.goto("index.html");
    const sidebar = page.locator(".sidebar-col");
    await expect(sidebar).toBeVisible();
    await sidebar.hover();
    await page.locator("#nav-collapse").click();
    await expect(page.locator("body")).toHaveClass(/nav-collapsed/);
    await expect(async () => {
      const box = await sidebar.boundingBox();
      expect(box?.width ?? 0).toBeLessThan(2);
    }).toPass();
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

  test("matches on a column name the full-text index covers", async ({ page }) => {
    await page.goto("index.html");
    await page.fill("#search", "count_food_items");
    const result = page.locator("#search-results a").first();
    await expect(result).toBeVisible();
    await result.click();
    await expect(page.locator("#app h1")).toContainText("orders");
  });

  test("a non-name hit shows a match-reason snippet (mkdocs-material style)", async ({ page }) => {
    await page.goto("index.html");
    await page.fill("#search", "count_food_items");
    const result = page.locator('#search-results a[href="#/node/model.jaffle_shop.orders"]');
    await expect(result).toBeVisible();
    const snippet = result.locator(".sr-snippet").first();
    await expect(snippet).toBeVisible();
    await expect(snippet.locator(".sr-snippet-field")).toContainText(/Column/i);
    await expect(snippet.locator("mark").first()).toContainText(/count|food|items/);
  });
  test("a snippet never repeats the title's own field (name/label)", async ({ page }) => {
    await page.goto("index.html");
    await page.fill("#search", "stg_locations");
    const result = page.locator("#search-results a").first();
    await expect(result).toContainText("stg_locations");
    const fields = await result.locator(".sr-snippet-field").allTextContents();
    for (const f of fields) expect(f).not.toMatch(/^Name$/i);
  });

  test("type:<resource_type> with no text lists only that type", async ({ page }) => {
    await page.goto("index.html");
    await page.fill("#search", "type:seed");
    const rows = page.locator("#search-results a");
    await expect(rows.first()).toBeVisible();
    await expect(rows.locator(".sr-meta")).toHaveCount(await rows.count());
    const metas = await rows.locator(".sr-meta").allTextContents();
    expect(metas.length).toBeGreaterThan(0);
    for (const m of metas) expect(m).toContain("seed");
  });

  test("type:<resource_type> scopes a text query to that type", async ({ page }) => {
    await page.goto("index.html");
    await page.fill("#search", "type:model orders");
    const metas = await page.locator("#search-results a .sr-meta").allTextContents();
    expect(metas.length).toBeGreaterThan(0);
    for (const m of metas) expect(m).toContain("model");
  });

  test("label:<text> matches names only, skipping SQL/description noise", async ({ page }) => {
    await page.goto("index.html");
    await page.fill("#search", "label:stg");
    const titles = await page.locator("#search-results a .sr-title").allTextContents();
    expect(titles.length).toBeGreaterThan(0);
    for (const t of titles) expect(t.toLowerCase()).toContain("stg");
  });

  test("a non-empty query with no hits shows a 'No matches.' cue", async ({ page }) => {
    await page.goto("index.html");
    await page.fill("#search", "type:bogus");
    const dropdown = page.locator("#search-results");
    await expect(dropdown).toBeVisible();
    await expect(dropdown.locator(".sr-empty")).toContainText("No matches");
    await expect(dropdown.locator("a")).toHaveCount(0);
    await expect(page.locator("#search-status")).toContainText("No matches");
  });

  test("the dropdown exposes combobox/listbox semantics", async ({ page }) => {
    await page.goto("index.html");
    const input = page.locator("#search");
    const results = page.locator("#search-results");
    await expect(input).toHaveAttribute("role", "combobox");
    await expect(input).toHaveAttribute("aria-controls", "search-results");
    await expect(input).toHaveAttribute("aria-expanded", "false");
    await expect(results).toHaveAttribute("role", "listbox");
    await page.fill("#search", "orders");
    await expect(input).toHaveAttribute("aria-expanded", "true");
    await expect(results.locator('a[role="option"]').first()).toBeVisible();
    const status = page.locator("#search-status");
    await expect(status).toHaveAttribute("role", "status");
    await expect(results).not.toHaveAttribute("aria-live", /.*/);
    await expect(status).toContainText(/results?\./);
  });

  test("arrow keys rove the results and Enter follows the active one", async ({ page }) => {
    await page.goto("index.html");
    const input = page.locator("#search");
    const results = page.locator("#search-results");
    await page.fill("#search", "orders");
    await expect(results.locator('a[role="option"]').first()).toBeVisible();
    await input.press("ArrowDown");
    const active = results.locator("a.active");
    await expect(active).toHaveCount(1);
    await expect(active).toHaveAttribute("aria-selected", "true");
    const activeId = await active.getAttribute("id");
    await expect(input).toHaveAttribute("aria-activedescendant", activeId!);
    await input.press("Enter");
    await expect(results).toBeHidden();
    await expect(input).toHaveAttribute("aria-expanded", "false");
    await expect(page.locator("#app h1")).toContainText("orders");
  });

  test("Escape closes the open dropdown", async ({ page }) => {
    await page.goto("index.html");
    const input = page.locator("#search");
    const results = page.locator("#search-results");
    await page.fill("#search", "orders");
    await expect(results).toBeVisible();
    await input.press("Escape");
    await expect(results).toBeHidden();
    await expect(input).toHaveAttribute("aria-expanded", "false");
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
    await page.goto("index.html#/node/model.jaffle_shop.stg_customers");

    const header = page.locator("table th").filter({ hasText: "Downstream impact" });
    await expect(header).toBeVisible();

    const chip = page.locator(".up-chip a").first();
    await expect(chip).toBeVisible();
    const href = await chip.getAttribute("href");
    expect(href).toMatch(/\?col=/);

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
    await expect(node).not.toHaveClass(/draggable/);
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

  test("the model_contract algo detects FK relationships and renders the ERD", async ({ page }) => {
    await page.goto("index.html#/node/model.jaffle_shop.orders");
    await expect(page.locator(".dbd-graph-empty")).toHaveCount(0);
    const tables = page.locator(".dbd-erd");
    await expect(tables.first()).toBeVisible();
    await expect(tables).toHaveCount(3);
    await expect(page.locator(".dbd-erd-focus .dbd-erd-name")).toHaveText("orders");
    await expect(page.locator(".react-flow__edge")).toHaveCount(2);
    const focus = page.locator(".dbd-erd-focus");
    await expect(focus.locator(".dbd-erd-badge.dbd-pk")).toHaveCount(1);
    await expect(focus.locator(".dbd-erd-badge.dbd-fk")).toHaveCount(1);
  });
});

test.describe("DAG layer segmented control", () => {
  test("default DAG load shows the Catalog segment active and only physical nodes", async ({ page }) => {
    await page.goto("index.html#/dag");
    const catalog = page.locator(".dbd-layer-seg button", { hasText: "Catalog" });
    await expect(catalog).toBeVisible();
    await expect(catalog).toHaveClass(/active/);
    const semantic = page.locator(".dbd-layer-seg button", { hasText: "Semantic" });
    await expect(semantic).toBeVisible();
    await expect(semantic).not.toHaveClass(/active/);
  });

  test("switching to Semantic Layer segment changes the Types trigger label", async ({ page }) => {
    await page.goto("index.html#/dag");
    const trigger = page.locator(".dbd-multi-trigger");
    await expect(trigger).toBeVisible();

    await expect(trigger).toContainText("Types: All");

    const semantic = page.locator(".dbd-layer-seg button", { hasText: "Semantic" });
    await semantic.click();
    await expect(semantic).toHaveClass(/active/);

    await expect(async () => {
      const hash = await page.evaluate(() => location.hash);
      expect(hash).toContain("layer=semantic");
    }).toPass({ timeout: 3000 });

    await expect(trigger).toContainText("Types: All");

    const catalog = page.locator(".dbd-layer-seg button", { hasText: "Catalog" });
    await catalog.click();
    await expect(catalog).toHaveClass(/active/);
    await expect(async () => {
      const hash = await page.evaluate(() => location.hash);
      expect(hash).not.toContain("layer=");
    }).toPass({ timeout: 3000 });
  });

  test("Semantic Layer segment writes layer=semantic into location.hash", async ({ page }) => {
    await page.goto("index.html#/dag");
    const semantic = page.locator(".dbd-layer-seg button", { hasText: "Semantic" });
    await expect(semantic).toBeVisible();
    await semantic.click();
    await expect(async () => {
      const hash = await page.evaluate(() => location.hash);
      expect(hash).toContain("layer=semantic");
    }).toPass({ timeout: 3000 });
  });

  test("navigating to #/dag?layer=semantic restores the Semantic Layer segment", async ({ page }) => {
    await page.goto("index.html#/dag?layer=semantic");
    const semantic = page.locator(".dbd-layer-seg button", { hasText: "Semantic" });
    await expect(semantic).toBeVisible();
    await expect(semantic).toHaveClass(/active/);
  });

  test("All segment writes layer=all into location.hash", async ({ page }) => {
    await page.goto("index.html#/dag");
    const all = page.locator(".dbd-layer-seg button", { hasText: "All" });
    await expect(all).toBeVisible();
    await all.click();
    await expect(async () => {
      const hash = await page.evaluate(() => location.hash);
      expect(hash).toContain("layer=all");
    }).toPass({ timeout: 3000 });
  });

  test("Other segment writes layer=other into location.hash", async ({ page }) => {
    await page.goto("index.html#/dag");
    const other = page.locator(".dbd-layer-seg button", { hasText: "Other" });
    await expect(other).toBeVisible();
    await other.click();
    await expect(async () => {
      const hash = await page.evaluate(() => location.hash);
      expect(hash).toContain("layer=other");
    }).toPass({ timeout: 3000 });
  });

  test("back-compat: existing #/dag?rtype=model link loads correctly with Catalog as default", async ({ page }) => {
    await page.goto("index.html#/dag?rtype=model");
    const catalog = page.locator(".dbd-layer-seg button", { hasText: "Catalog" });
    await expect(catalog).toBeVisible();
    await expect(catalog).toHaveClass(/active/);
    const trigger = page.locator(".dbd-multi-trigger");
    await expect(trigger).toContainText("Models");
  });
});

test.describe("deep-link URL state (B1 + B2)", () => {
  test("selecting the resource-type filter writes rtype= into location.hash", async ({ page }) => {
    await page.goto("index.html#/dag");
    const trigger = page.locator(".dbd-multi-trigger");
    await expect(trigger).toBeVisible();
    await trigger.click();
    const panel = page.locator(".dbd-multi-panel");
    await expect(panel).toBeVisible();
    const sourceCheckbox = panel.locator("label", { hasText: "Sources" }).locator("input");
    await sourceCheckbox.click();
    await expect(async () => {
      const hash = await page.evaluate(() => location.hash);
      expect(hash).toContain("rtype=");
      expect(hash).toContain("source");
    }).toPass({ timeout: 3000 });
  });

  test("navigating to a DAG hash with rtype= restores the filter trigger label", async ({ page }) => {
    await page.goto("index.html#/dag?rtype=source");
    const trigger = page.locator(".dbd-multi-trigger");
    await expect(trigger).toBeVisible();
    await expect(trigger).toContainText("Sources");
  });

  test("arriving at a DAG hash with focus= preserves the focus (no clobber)", async ({ page }) => {
    await page.goto("index.html");
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
    const schemaSelect = page.locator(".dbd-toolbar select").first();
    await expect(schemaSelect).toBeVisible();
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
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.goto("index.html#/node/model.jaffle_shop.orders");
    const btn = page.locator(".copy-link-btn").first();
    await expect(btn).toBeVisible();
    await expect(btn).toContainText("Copy link");
    await btn.click();
    await expect(btn).toContainText("Copied!");
    await expect(btn).toHaveClass(/copied/);
    await expect(btn).toContainText("Copy link", { timeout: 3000 });
    await expect(btn).not.toHaveClass(/copied/);
  });

  test("copy-link button exists on DAG page", async ({ page }) => {
    await page.goto("index.html#/dag");
    await expect(page.locator(".page-head")).toBeVisible();
    const btn = page.locator(".page-head .copy-link-btn");
    await expect(btn).toBeVisible();
    await expect(btn).toContainText("Copy link");
  });
});

test.describe("health check", () => {
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
    await expect(card.locator(".health-scorecard .score-chip").first()).toBeVisible();
    await card.locator(".health-card-link").click();
    await expect(page).toHaveURL(/#\/health$/);
  });

  test("an overview scorecard chip deep-links to its dimension section", async ({ page }) => {
    await page.goto("index.html#/overview");
    const chip = page.locator(".health-card .score-chip", { hasText: "Structure" });
    await chip.click();
    await expect(page).toHaveURL(/#\/health\?d=structure/);
    const section = page.locator("#health-structure");
    await expect(section).toBeVisible();
    await expect(section).toHaveJSProperty("open", true);
    await expect(section.locator(".health-section-body")).toBeVisible();
  });

  test("the health page shows a scorecard with all six dimensions", async ({ page }) => {
    await page.goto("index.html#/health");
    const chips = page.locator("#app .health-scorecard .score-chip");
    await expect(chips).toHaveCount(6);
    await expect(chips.first().locator(".score-num")).toContainText(/%/);
    await expect(page.locator("details.health-section")).toHaveCount(6);
  });

  test("a dimension section lists rule findings with node deep-links", async ({ page }) => {
    await page.goto("index.html#/health");
    const section = page.locator("details.health-section", { hasText: "Structure" });
    await expect(section).toBeVisible();
    await expect(section.locator(".health-rule").first()).toBeVisible();
    const nodeLink = section.locator('a[href^="#/node/"]').first();
    await expect(nodeLink).toBeVisible();
  });

  test("the health page no longer embeds per-test results", async ({ page }) => {
    await page.goto("index.html#/health");
    await expect(page.locator(".health-testresults")).toHaveCount(0);
  });

  test("a model page shows its data-test results with reconciling pills", async ({ page }) => {
    await page.goto("index.html#/node/model.jaffle_shop.stg_customers");
    const tests = page.locator("#node-sec-tests");
    await expect(tests).toBeVisible();
    await expect(tests.locator(".node-section-title")).toContainText("Tests");
    await expect(tests.locator("h3", { hasText: "Data tests" })).toBeVisible();
    await expect(tests.locator(".health-status").first()).toBeVisible();
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
    const section = page.locator("details.health-section", { hasText: "Structure" });
    await expect(section).toHaveJSProperty("open", true);
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

test.describe("overview ERD — toolbar, focus, full-screen", () => {
  test("overview ERD renders a toolbar with search and schema controls", async ({ page }) => {
    await page.goto("index.html#/overview");
    const toolbar = page.locator(".dbd-toolbar").first();
    await expect(toolbar).toBeVisible();
    const focusInput = toolbar.locator("input");
    await expect(focusInput).toBeVisible();
    await expect(focusInput).toHaveAttribute("placeholder", /Focus a table/i);
    const schemaSelect = toolbar.locator("select");
    await expect(schemaSelect).toHaveCount(1);
    await expect(schemaSelect.locator("option").first()).toHaveText(/All schemas/i);
  });

  test("overview ERD shows the lock/unlock button and is locked by default", async ({ page }) => {
    await page.goto("index.html#/overview");
    const erdBar = page.locator(".dbd-erd-bar");
    await expect(erdBar).toBeVisible();
    const lockBtn = erdBar.locator(".dbd-lock-btn");
    await expect(lockBtn).toBeVisible();
    await expect(lockBtn).not.toHaveClass(/on/);
    await expect(lockBtn).toContainText("Locked");
  });

  test("lock button toggles to pan & zoom on when clicked", async ({ page }) => {
    await page.goto("index.html#/overview");
    const lockBtn = page.locator(".dbd-erd-bar .dbd-lock-btn");
    await expect(lockBtn).toBeVisible();
    await lockBtn.click();
    await expect(lockBtn).toHaveClass(/on/);
    await expect(lockBtn).toContainText("Pan & zoom on");
    await lockBtn.click();
    await expect(lockBtn).not.toHaveClass(/on/);
    await expect(lockBtn).toContainText("Locked");
  });

  test("overview ERD renders all tables without a focus", async ({ page }) => {
    await page.goto("index.html#/overview");
    const canvas = page.locator(".dbd-canvas");
    await expect(canvas).toBeVisible();
    const tables = page.locator(".dbd-erd");
    await expect(tables.first()).toBeVisible();
    await expect(tables).toHaveCount(4);
  });

  test("overview ERD toolbar focus filters to a radial neighborhood", async ({ page }) => {
    await page.goto("index.html#/overview");
    const all = page.locator(".dbd-erd");
    await expect(all.first()).toBeVisible();
    await page.fill(".dbd-toolbar input", "orders");
    await expect(async () => {
      expect(await all.count()).toBeLessThan(4);
    }).toPass({ timeout: 3000 });
    await expect(page.locator(".dbd-erd-focus")).toHaveCount(1);
    await expect(page.locator(".dbd-erd-focus .dbd-erd-name")).toHaveText("orders");
  });

  test("overview ERD schema filter narrows the table set", async ({ page }) => {
    await page.goto("index.html#/overview");
    const all = page.locator(".dbd-erd");
    await expect(all.first()).toBeVisible();
    const schemaSelect = page.locator(".dbd-toolbar select").first();
    const options = schemaSelect.locator("option");
    const count = await options.count();
    if (count > 1) {
      const secondOption = await options.nth(1).getAttribute("value");
      if (secondOption) {
        await schemaSelect.selectOption(secondOption);
        await expect(async () => {
          const hash = await page.evaluate(() => location.hash);
          expect(hash).toContain("erd_schema=");
        }).toPass({ timeout: 3000 });
      }
    }
  });

  test("overview ERD focus writes erd_focus= into location.hash (deep-link)", async ({ page }) => {
    await page.goto("index.html#/overview");
    await page.fill(".dbd-toolbar input", "orders");
    await expect(async () => {
      const hash = await page.evaluate(() => location.hash);
      expect(hash).toContain("erd_focus=");
    }).toPass({ timeout: 3000 });
  });

  test("navigating to overview with erd_focus= restores the focus", async ({ page }) => {
    await page.goto("index.html#/overview?erd_focus=model.jaffle_shop.orders");
    const focused = page.locator(".dbd-erd-focus");
    await expect(focused).toBeVisible({ timeout: 5000 });
    await expect(focused.locator(".dbd-erd-name")).toHaveText("orders");
  });

  test("overview ERD full-screen button exists in the page-head-actions area", async ({ page }) => {
    await page.goto("index.html#/overview");
    const erdSection = page.locator(".page-head").filter({ has: page.locator("h2") });
    await expect(erdSection).toBeVisible();
    const fsBtn = erdSection.locator(".fs-btn");
    await expect(fsBtn).toBeVisible();
    await expect(fsBtn).toContainText("Full screen");
  });

  test("model-page Related ERD has its own full-screen button", async ({ page }) => {
    await page.goto("index.html#/node/model.jaffle_shop.orders");
    const erdSection = page.locator("#node-sec-erd");
    await expect(erdSection).toBeVisible();
    await expect(erdSection.locator(".node-section-title")).toHaveText("Related ERD");
    const fsBtn = erdSection.locator(".node-section-summary-actions .fs-btn");
    await expect(fsBtn).toBeVisible();
    await expect(fsBtn).toContainText("Full screen");
  });

  test("model-page Related ERD renders full columns (not the compact +N more)", async ({ page }) => {
    await page.goto("index.html#/node/model.jaffle_shop.orders");
    const focused = page.locator(".dbd-erd-focus");
    await expect(focused).toBeVisible({ timeout: 5000 });
    await expect(focused.locator(".dbd-erd-more")).toHaveCount(0);
    const cols = focused.locator(".dbd-erd-col");
    expect(await cols.count()).toBeGreaterThan(2);
  });
});

test.describe("unit test page", () => {
  const UT =
    "unit_test.jaffle_shop.stg_locations.test_does_location_opened_at_trunc_to_date";

  test("shows the given input and expected output fixture data as tables", async ({ page }) => {
    await page.goto("index.html#/node/" + encodeURIComponent(UT));
    const given = page.locator("#node-sec-given-0");
    await expect(given).toBeVisible();
    await expect(given.locator(".node-section-title")).toContainText("Given");
    await expect(given.locator("thead th", { hasText: "NAME" })).toBeVisible();
    await expect(given.locator("tbody")).toContainText("Vice City");

    const expect_ = page.locator("#node-sec-expect");
    await expect(expect_).toBeVisible();
    await expect(expect_.locator(".node-section-title")).toContainText("Expected output");
    await expect(expect_.locator("thead th", { hasText: "OPENED_DATE" })).toBeVisible();
    await expect(expect_.locator("tbody")).toContainText("2016-09-01");
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
    const closed = await sidebar.boundingBox();
    expect(closed && closed.x).toBeLessThan(0);
    await page.locator("#nav-toggle").click();
    await expect(page.locator("body")).toHaveClass(/nav-open/);
    await expect(async () => {
      const open = await sidebar.boundingBox();
      expect(open && open.x).toBeGreaterThanOrEqual(0);
    }).toPass();
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
