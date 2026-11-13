import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";
import { chromium, expect } from "../../web/node_modules/@playwright/test/index.mjs";

const { values } = parseArgs({
  options: {
    "base-url": { type: "string", default: "http://127.0.0.1:8000" },
    "artifacts-dir": { type: "string", default: ".data/browser" },
  },
});
const baseUrl = values["base-url"];
const artifacts = path.resolve(values["artifacts-dir"]);
await mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({ channel: "msedge", headless: true });
const errors = [];
const externalRequests = new Set();

try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  page.on("pageerror", error => errors.push(error.stack || error.message));
  page.on("request", request => {
    const url = new URL(request.url());
    if (url.origin !== new URL(baseUrl).origin && url.protocol.startsWith("http")) {
      externalRequests.add(url.hostname);
    }
  });
  await page.goto(baseUrl);
  await expect(page.getByRole("button", { name: "Find my Azerbaijan" })).toBeEnabled();
  await page.screenshot({ path: path.join(artifacts, "home-desktop.png"), fullPage: true });
  await page.getByRole("button", { name: "Try London", exact: false }).click();
  await page.getByRole("button", { name: "Find my Azerbaijan" }).click();
  await expect(page.getByRole("heading", { name: "Azerbaijan, your way." })).toBeVisible();
  await expect(page.getByText("7 stays matching your preferences")).toBeVisible();

  await page.getByRole("button", { name: "Map", exact: true }).click();
  await expect(page.locator(".leaflet-container")).toBeVisible();
  await expect(page.locator(".leaflet-marker-icon")).toHaveCount(7);
  await page.getByRole("button", { name: "List", exact: true }).click();
  await page.getByRole("tab", { name: "Flights", exact: true }).click();
  assert.equal(await page.getByText("Azerbaijan Airlines (AZAL)", { exact: true }).count(), 2);
  await page.getByRole("tab", { name: "Activities", exact: true }).click();
  const removeButtons = page.getByRole("button", { name: /^Remove / });
  const beforeRemoval = await removeButtons.count();
  assert.ok(beforeRemoval > 0);
  await removeButtons.last().click();
  await expect(removeButtons).toHaveCount(beforeRemoval - 1);

  await page.getByRole("tab", { name: "Transport", exact: true }).click();
  await expect(page.getByText(/H1 baseline: 24\/7/).first()).toBeVisible();
  await page.getByRole("tab", { name: "Checklist", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Check ASAN e-visa eligibility before travel" })).toBeVisible();
  assert.ok(await page.locator('a[href="https://evisa.gov.az/en/information"]').count() > 0);
  await page.screenshot({ path: path.join(artifacts, "trip-desktop.png"), fullPage: true });

  await page.getByRole("button", { name: "Review demo basket", exact: true }).click();
  const hold = page.getByRole("button", { name: "Hold demo basket & continue", exact: true });
  await expect(hold).toBeEnabled();
  await hold.click();
  await expect(page.getByRole("heading", { name: "Who is this demonstration for?" })).toBeVisible();
  await page.getByLabel("Full name", { exact: true }).fill("Demo Traveller");
  await page.getByLabel("Email address", { exact: true }).fill("traveller@example.test");
  await page.locator("#traveller-nationality").fill("gb");
  await page.getByLabel("Sample passport expiry", { exact: true }).fill("2030-01-01");
  await page.getByLabel("Actual e-visa expiry (optional)", { exact: true }).fill("2027-05-31");
  await page.getByRole("button", { name: "Save details & review", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Review the simulated booking", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Continue to mock payment", exact: true }).click();
  const card = page.getByLabel("Published test card number", { exact: true });
  const agreement = page.getByRole("checkbox", { name: /I understand this is simulated/ });
  await card.fill("0000000000000000");
  await agreement.check();
  await page.getByRole("button", { name: "Simulate payment", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Real cards are not accepted in this demo");
  await card.fill("4242424242424242");
  await agreement.check();
  await page.getByRole("button", { name: "Simulate payment", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your plan is ready to take with you." })).toBeVisible();
  await expect(page.getByText("SIMULATED – NOT A RESERVATION", { exact: true })).toBeVisible();
  await page.screenshot({ path: path.join(artifacts, "confirmation-desktop.png"), fullPage: true });
  const pdfDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download itinerary PDF", exact: true }).click();
  const pdf = await pdfDownload;
  const pdfPath = path.join(artifacts, pdf.suggestedFilename());
  await pdf.saveAs(pdfPath);
  assert.equal((await readFile(pdfPath)).subarray(0, 4).toString(), "%PDF");
  const calendarDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "Add itinerary to calendar (.ics)", exact: true }).click();
  const calendar = await calendarDownload;
  const calendarPath = path.join(artifacts, calendar.suggestedFilename());
  await calendar.saveAs(calendarPath);
  assert.match(await readFile(calendarPath, "utf8"), /BEGIN:VCALENDAR/);

  for (const width of [390, 320]) {
    const mobile = await context.newPage();
    await mobile.setViewportSize({ width, height: 844 });
    await mobile.goto(baseUrl);
    await expect(mobile.getByRole("button", { name: "Find my Azerbaijan" })).toBeEnabled();
    const overflow = await mobile.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    assert.equal(overflow, false, `Horizontal overflow at ${width}px`);
    await mobile.getByRole("button", { name: "Find my Azerbaijan" }).click();
    await expect(mobile.getByRole("heading", { name: "Azerbaijan, your way." })).toBeVisible();
    assert.equal(
      await mobile.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
      false,
      `Trip horizontal overflow at ${width}px`,
    );
    await mobile.screenshot({ path: path.join(artifacts, `trip-mobile-${width}.png`), fullPage: true });
    await mobile.close();
  }
  assert.deepEqual(errors, [], "Uncaught browser errors");
  assert.ok(
    [...externalRequests].every(host => host.endsWith(".tile.openstreetmap.org") || host === "tile.openstreetmap.org"),
    `Unexpected external browser requests: ${[...externalRequests].join(", ")}`,
  );
  console.log(JSON.stringify({
    result: "passed",
    journey: "Search, map, trip tabs, remove activity, mock checkout, card rejection, PDF and ICS",
    responsive_widths: [1440, 390, 320],
    external_hosts: [...externalRequests],
    artifacts,
  }, null, 2));
} finally {
  await browser.close();
}
