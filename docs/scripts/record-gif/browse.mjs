// Browser half of docs/assets/img/dbt-2-info-schema.gif — run via record.sh.
// Usage: node browse.mjs <base-url> <video-dir>
import { createRequire } from "node:module";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const [baseUrl, videoDir] = process.argv.slice(2);
const size = { width: 1280, height: 720 };

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: size,
  colorScheme: "dark",
  recordVideo: { dir: videoDir, size },
});
await context.addInitScript(() => localStorage.setItem("dbdocs-theme", "dark"));
const page = await context.newPage();
const pause = (ms) => page.waitForTimeout(ms);

async function visit(hash, ms) {
  await page.goto(`${baseUrl}/${hash}`);
  await page.waitForLoadState("networkidle");
  await pause(ms);
}

async function scroll(steps, delta) {
  await page.mouse.move(820, 420);
  for (let i = 0; i < steps; i += 1) {
    await page.mouse.wheel(0, delta);
    await pause(450);
  }
}

async function showErd(hash) {
  await visit(hash, 900);
  await page.locator(".content").evaluate((content) => {
    const heading = document.getElementById("erd-heading");
    const offset = heading.getBoundingClientRect().top - content.getBoundingClientRect().top;
    content.scrollTo({ top: content.scrollTop + offset - 16, behavior: "smooth" });
  });
  await pause(3400);
}

await visit("#/overview", 2500);
await showErd("#/erd");
await showErd("#/erd?erd_focus=model.jaffle_shop.orders");
await visit("#/node/model.jaffle_shop.orders", 2000);
await scroll(3, 260);
await pause(1200);
await visit("#/node/model.jaffle_shop.orders?col=order_total", 3200);
await visit("#/dag?focus=model.jaffle_shop.order_items", 3500);
await visit("#/health", 2500);

await context.close();
await browser.close();
