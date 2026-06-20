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

  test("matches on a column name the full-text index covers", async ({ page }) => {
    await page.goto("index.html");
    // count_food_items is a column of model.jaffle_shop.orders — not a model name,
    // so a hit proves the index reaches column names, not just labels.
    await page.fill("#search", "count_food_items");
    const result = page.locator("#search-results a").first();
    await expect(result).toBeVisible();
    await result.click();
    await expect(page.locator("#app h1")).toContainText("orders");
  });

  test("a non-name hit shows a match-reason snippet (mkdocs-material style)", async ({ page }) => {
    await page.goto("index.html");
    // count_food_items only lives in a column, so the result must explain *why*
    // it matched: a snippet labelled with the matched field + the term marked.
    await page.fill("#search", "count_food_items");
    const result = page.locator("#search-results a").first();
    await expect(result).toBeVisible();
    const snippet = result.locator(".sr-snippet").first();
    await expect(snippet).toBeVisible();
    await expect(snippet.locator(".sr-snippet-field")).toContainText(/Column/i);
    // MiniSearch tokenizes count_food_items into count/food/items, so the marked
    // terms are the tokens — assert at least one matched token is highlighted.
    await expect(snippet.locator("mark").first()).toContainText(/count|food|items/);
  });
  test("a snippet never repeats the title's own field (name/label)", async ({ page }) => {
    await page.goto("index.html");
    await page.fill("#search", "stg_locations");
    const result = page.locator("#search-results a").first();
    await expect(result).toContainText("stg_locations");
    // The title carries the name; any snippet is for a *different* field that also
    // matched (relation/SQL/…), never a redundant "Name" snippet.
    const fields = await result.locator(".sr-snippet-field").allTextContents();
    for (const f of fields) expect(f).not.toMatch(/^Name$/i);
  });

  test("type:<resource_type> with no text lists only that type", async ({ page }) => {
    await page.goto("index.html");
    // Bare `type:seed` lists every seed and nothing else (the fixture's seeds are
    // the raw_* tables; no model/source should appear).
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
    // `type:model orders` finds models matching "orders" — never the seeds/sources
    // that also carry the token.
    await page.fill("#search", "type:model orders");
    const metas = await page.locator("#search-results a .sr-meta").allTextContents();
    expect(metas.length).toBeGreaterThan(0);
    for (const m of metas) expect(m).toContain("model");
  });

  test("label:<text> matches names only, skipping SQL/description noise", async ({ page }) => {
    await page.goto("index.html");
    // Every hit's title must contain "stg" — a label-scoped query must not surface
    // a model that only mentions a staging table in its SQL body.
    await page.fill("#search", "label:stg");
    const titles = await page.locator("#search-results a .sr-title").allTextContents();
    expect(titles.length).toBeGreaterThan(0);
    for (const t of titles) expect(t.toLowerCase()).toContain("stg");
  });

  test("a non-empty query with no hits shows a 'No matches.' cue", async ({ page }) => {
    await page.goto("index.html");
    // type:bogus is a valid operator with an unmatched value — the dropdown must
    // explain there are no results, not silently hide.
    await page.fill("#search", "type:bogus");
    const dropdown = page.locator("#search-results");
    await expect(dropdown).toBeVisible();
    await expect(dropdown.locator(".sr-empty")).toContainText("No matches");
    await expect(dropdown.locator("a")).toHaveCount(0);
    // ...and the live region announces it too.
    await expect(page.locator("#search-status")).toContainText("No matches");
  });

  test("the dropdown exposes combobox/listbox semantics", async ({ page }) => {
    await page.goto("index.html");
    const input = page.locator("#search");
    const results = page.locator("#search-results");
    // Closed: combobox advertises a controlled, collapsed listbox.
    await expect(input).toHaveAttribute("role", "combobox");
    await expect(input).toHaveAttribute("aria-controls", "search-results");
    await expect(input).toHaveAttribute("aria-expanded", "false");
    await expect(results).toHaveAttribute("role", "listbox");
    // Open: aria-expanded flips and each row is an option.
    await page.fill("#search", "orders");
    await expect(input).toHaveAttribute("aria-expanded", "true");
    await expect(results.locator('a[role="option"]').first()).toBeVisible();
    // The count is announced via a separate live region (role=status), not the
    // listbox itself — so a screen reader hears "N results." without the option
    // list being re-read on every keystroke.
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
    // ↓ selects the first row: it gets .active + aria-selected, and the input
    // points its aria-activedescendant at it (focus stays on the input).
    await input.press("ArrowDown");
    const active = results.locator("a.active");
    await expect(active).toHaveCount(1);
    await expect(active).toHaveAttribute("aria-selected", "true");
    const activeId = await active.getAttribute("id");
    await expect(input).toHaveAttribute("aria-activedescendant", activeId!);
    // Enter navigates to the roved node and closes the dropdown.
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

  test("the model_contract algo detects FK relationships and renders the ERD", async ({ page }) => {
    // The demo is built with `algo: model_contract` (docs/dbdocs-demo.yml), so
    // dbterd derives FKs from each model's contract constraints rather than from
    // `relationships` tests. orders' contract has location_id → locations and is
    // referenced by fct_customer_segment_orders, so its per-node ERD windows to
    // orders plus those two directly-related tables.
    await page.goto("index.html#/node/model.jaffle_shop.orders");
    // No empty-state placeholder — model_contract detected relationships.
    await expect(page.locator(".dbd-graph-empty")).toHaveCount(0);
    const tables = page.locator(".dbd-erd");
    await expect(tables.first()).toBeVisible();
    await expect(tables).toHaveCount(3);
    // entity_name_format: table → the label is the bare model name.
    await expect(page.locator(".dbd-erd-focus .dbd-erd-name")).toHaveText("orders");
    await expect(page.locator(".react-flow__edge")).toHaveCount(2);
    // model_contract populates PK/FK badges from the contract: orders carries a
    // PK (order_id) and an FK (location_id) — test_relationship would not.
    const focus = page.locator(".dbd-erd-focus");
    await expect(focus.locator(".dbd-erd-badge.dbd-pk")).toHaveCount(1);
    await expect(focus.locator(".dbd-erd-badge.dbd-fk")).toHaveCount(1);
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
    const erdSection = page
      .locator(".page-head")
      .filter({ has: page.locator("h2", { hasText: "Related ERD" }) });
    await expect(erdSection).toBeVisible();
    const fsBtn = erdSection.locator(".fs-btn");
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
