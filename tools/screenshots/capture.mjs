/**
 * Capture the documentation screenshots from a running instance of the app.
 *
 * Prerequisites (see docs/assets/README.md for the full walkthrough):
 *   - backend running on 127.0.0.1:8000 with demo data seeded
 *   - frontend dev server running on localhost:5173
 *
 * Usage:
 *   npm install
 *   npx playwright install chromium
 *   node capture.mjs
 *
 * Env overrides: BASE_URL, APP_USER, APP_PASSWORD, OUT_DIR.
 */
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const here = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.BASE_URL ?? 'http://localhost:5173';
const USER = process.env.APP_USER ?? 'demo';
const PASSWORD = process.env.APP_PASSWORD ?? 'demo12345';
const OUT = process.env.OUT_DIR ?? path.resolve(here, '../../docs/assets');

/** Hide toasts and freeze animations so screenshots are deterministic. */
const FREEZE_CSS = `
  [data-sonner-toaster] { display: none !important; }
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
    caret-color: transparent !important;
  }
`;

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1.5,
  colorScheme: 'light',
  locale: 'en-IE',
});
const page = await context.newPage();

let captured = 0;

/** Screenshot the current page (full page by default). */
async function shot(name, { fullPage = true } = {}) {
  await page.addStyleTag({ content: FREEZE_CSS });
  await page.waitForTimeout(250);
  await page.screenshot({ path: path.join(OUT, name), fullPage });
  captured += 1;
  console.log(`  captured ${name}`);
}

async function waitForServer() {
  for (let attempt = 1; attempt <= 30; attempt += 1) {
    try {
      const response = await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
      if (response && response.ok()) return;
    } catch {
      /* keep retrying */
    }
    await page.waitForTimeout(1000);
  }
  throw new Error(`No app answering at ${BASE} after 30 attempts.`);
}

/** Navigate and wait for something that proves the page rendered. */
async function go(pathname, waitFor) {
  await page.goto(`${BASE}${pathname}`, { waitUntil: 'domcontentloaded' });
  if (waitFor) await page.locator(waitFor).first().waitFor({ timeout: 20000 });
  await page.waitForTimeout(500);
}

await mkdir(OUT, { recursive: true });
console.log(`Capturing from ${BASE} into ${OUT}`);

await waitForServer();

// ---------------------------------------------------------------- sign in page
await page.locator('#username').waitFor({ timeout: 20000 });
await shot('login.png');

// ---------------------------------------------------------------- sign in
await page.fill('#username', USER);
await page.fill('#password', PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 20000 });

// ---------------------------------------------------------------- dashboard
await page.locator('text=Campaign performance').first().waitFor({ timeout: 20000 });
await page.waitForTimeout(600);
await shot('dashboard.png');

// ---------------------------------------------------------------- campaigns
await go('/campaigns', 'table');
await shot('campaigns.png');

// ---------------------------------------------------------------- campaign detail
await page.locator('a[href^="/campaigns/"]').first().click();
await page.locator('text=Budget').first().waitFor({ timeout: 20000 });
await page.waitForTimeout(500);
await shot('campaign-detail.png');

// ---------------------------------------------------------------- content
await go('/content', 'table');
await shot('content.png');

// ---------------------------------------------------------------- calendar
await go('/calendar', '[aria-label="Previous month"]');
await shot('calendar.png');

// ---------------------------------------------------------------- results
await go('/results', 'text=Metrics CSV');
await shot('results.png');

// ---------------------------------------------------------------- suggestions
await go('/suggestions', 'text=All kinds');
await shot('suggestions.png');

// ---------------------------------------------------------------- shop
await go('/products', 'table');
await shot('shop-products.png');

await go('/orders', 'table');
await shot('shop-orders.png');

await go('/channels', 'table');
await shot('shop-channels.png');

// ---------------------------------------------------------------- settings
await go('/settings', 'text=UTM builder');
await shot('settings.png');

// A second, tighter shot of the API keys card itself.
await page.locator('text=API keys & integrations').first().scrollIntoViewIfNeeded();
await page.waitForTimeout(400);
await shot('settings-apikeys.png', { fullPage: false });

await browser.close();
console.log(`Done — ${captured} screenshots written to ${OUT}`);
