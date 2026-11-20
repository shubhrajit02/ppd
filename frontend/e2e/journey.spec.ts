import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

test("landing to real review, evidence, patch, triage, filters, score and history", async ({ page, request, context }) => {
  const errors: string[] = []; page.on("pageerror", e => errors.push(e.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/"); await expect(page.getByRole("heading", { level: 1 })).toContainText("Understand the code");
  await page.waitForTimeout(800); // Allow the lazy canvas to paint before visual capture.
  await page.screenshot({ path: "test-results/landing.png", fullPage: true });
  await page.getByRole("link", { name: "Try a sample review" }).click();
  await page.getByRole("button", { name: "Start review", exact: true }).click();
  await expect(page).toHaveURL(/\/app\/review\//);
  await expect(page.locator(".badge-completed")).toBeVisible();
  const id = page.url().split("/").at(-1)!;
  const result = await (await request.get(`http://127.0.0.1:8000/api/reviews/${id}`)).json();
  const patchFinding = result.report.findings.find((f: { suggested_fix: unknown }) => f.suggested_fix);
  await page.getByRole("button", { name: new RegExp(patchFinding.title) }).click();
  await expect(page.getByTestId(`source-line-${patchFinding.lines.start}`)).toHaveAttribute("data-selected", "true");
  await expect(page.locator(".finding-body")).toContainText("EVIDENCE");
  await page.getByRole("button", { name: "View patch" }).click();
  await expect(page.getByRole("dialog")).toContainText("Your source has not been changed");
  await page.getByRole("button", { name: "Copy patch", exact: true }).click(); await expect(page.getByRole("button", { name: "Copied", exact: true })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain("@@");
  const download = page.waitForEvent("download"); await page.getByRole("button", { name: "Download patch" }).click(); expect((await download).suggestedFilename()).toMatch(/\.patch$/);
  await page.keyboard.press("Escape"); await expect(page.getByRole("button", { name: "View patch" })).toBeFocused();
  await page.getByLabel(`Decision for ${patchFinding.title}`).selectOption("RESOLVED"); await expect(page.getByRole("status")).toContainText("Decision saved");
  await page.getByLabel("Severity filter").selectOption("CRITICAL"); await expect(page.getByText("No findings in this view")).toBeVisible();
  await page.getByRole("button", { name: "Reset", exact: true }).click();
  await page.getByLabel(/Review score .*Why this score/).click(); await expect(page.getByRole("heading", { name: /^Why \d/ })).toBeVisible();
  await page.getByLabel(/Review score .*Why this score/).click();
  await page.getByText("Agent execution & timeline", { exact: true }).click(); await expect(page.getByText("Disabled", { exact: true })).toBeVisible();
  await page.evaluate(() => { (document.activeElement as HTMLElement)?.blur(); window.scrollTo({ top: 0, behavior: "instant" }); });
  await page.screenshot({ path: "test-results/workspace.png", fullPage: true });
  const violations = (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations;
  expect(violations).toEqual([]);
  await page.keyboard.press("Control+k"); await page.getByLabel("Search commands").fill("history"); await page.keyboard.press("Enter"); await expect(page).toHaveURL(/\/app\/history$/); await expect(page.getByText("Sample project").first()).toBeVisible();
  for (const route of ["/app", "/app/repositories", "/app/settings"]) { await page.goto(route); await expect(page.locator("h1")).toBeVisible(); }
  expect(errors).toEqual([]);
});

test("empty and disconnected API states are usable", async ({ page }) => {
  await page.route("**/api/reviews?*", route => route.fulfill({ json: [] }));
  await page.goto("/app/history"); await expect(page.getByRole("heading", { name: /No .*review/i })).toBeVisible();
  await page.unrouteAll(); await page.route("**/api/reviews?*", route => route.abort()); await page.reload();
  await expect(page.getByRole("alert").filter({ hasText: "Something needs attention" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("desktop graph survives context loss and live reduced-motion changes", async ({ page }) => {
  await page.goto("/"); await expect(page.locator("canvas")).toBeVisible();
  await page.waitForTimeout(500);
  await page.locator("canvas").evaluate(canvas => canvas.dispatchEvent(new Event("webglcontextlost", { cancelable: true })));
  await expect(page.locator(".static-graph")).toBeVisible();
  await page.emulateMedia({ reducedMotion: "reduce" }); await expect(page.locator("canvas")).toHaveCount(0);
  const accessibility = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze(); expect(accessibility.violations).toEqual([]);
});

test("browser upload and CLI return identical findings and score", async ({ page, request }) => {
  const source = "export function run(source: string) {\n  debugger;\n  return eval(source);\n}\n";
  const dir = mkdtempSync(path.join(tmpdir(), "aicr-parity-"));
  try {
    writeFileSync(path.join(dir, "sample.ts"), source);
    const executable = process.platform === "win32" ? path.resolve("../.venv/Scripts/aicr.exe") : "aicr";
    const cli = JSON.parse(execFileSync(executable, ["review", dir, "--no-ai", "--format", "json"], { encoding: "utf8" }));
    await page.goto("/app/new"); await page.locator('input[type="file"]').setInputFiles({ name: "sample.ts", mimeType: "text/plain", buffer: Buffer.from(source) });
    await page.getByRole("button", { name: "Start review", exact: true }).click(); await expect(page.locator(".badge-completed")).toBeVisible();
    const result = await (await request.get(`http://127.0.0.1:8000/api/reviews/${page.url().split("/").at(-1)}/report`)).json();
    expect(result.findings).toEqual(cli.findings); expect(result.score).toEqual(cli.score); expect(result.schema_version).toEqual(cli.schema_version);
  } finally { rmSync(dir, { recursive: true }); }
});

test("mobile, keyboard, reduced motion and static graph fallback", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 }); await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/"); await expect(page.locator(".static-graph")).toBeVisible(); await expect(page.locator("canvas")).toHaveCount(0);
  await page.getByRole("link", { name: "Try a sample review" }).click(); await page.getByRole("button", { name: "Start review", exact: true }).click(); await expect(page.locator(".badge-completed")).toBeVisible();
  await expect(page.getByLabel("Review findings")).toBeVisible(); await expect(page.getByLabel("Source viewer", { exact: true })).toBeHidden();
  await page.getByRole("button", { name: "Jump to code" }).click(); await expect(page.getByLabel("Source viewer", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Files", exact: true }).click(); await expect(page.getByLabel("Review files", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.evaluate(() => { (document.activeElement as HTMLElement)?.blur(); window.scrollTo({ top: 0, behavior: "instant" }); });
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Open command palette" }).click(); await page.getByLabel("Search commands").fill("settings"); await page.keyboard.press("ArrowDown"); await page.keyboard.press("Enter"); await expect(page).toHaveURL(/settings$/);
});

test("responsive routes and local performance budget", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    const metrics = { lcp: 0, cls: 0, longTasks: 0 };
    Object.assign(window, { aicrMetrics: metrics });
    new PerformanceObserver(list => { for (const entry of list.getEntries()) metrics.lcp = entry.startTime; }).observe({ type: "largest-contentful-paint", buffered: true });
    new PerformanceObserver(list => { for (const entry of list.getEntries()) { const shift = entry as PerformanceEntry & { hadRecentInput: boolean; value: number }; if (!shift.hadRecentInput) metrics.cls += shift.value; } }).observe({ type: "layout-shift", buffered: true });
    new PerformanceObserver(list => { metrics.longTasks += list.getEntries().length; }).observe({ type: "longtask", buffered: true });
  });
  await page.goto("/"); await expect(page.locator("canvas")).toBeVisible(); await page.waitForTimeout(1200);
  const metrics = await page.evaluate(() => (window as unknown as { aicrMetrics: { lcp: number; cls: number; longTasks: number } }).aicrMetrics);
  await testInfo.attach("local-performance.json", { body: JSON.stringify(metrics), contentType: "application/json" });
  writeFileSync("test-results/local-performance.json", JSON.stringify(metrics, null, 2));
  expect(metrics.cls).toBeLessThan(0.1); expect(metrics.lcp).toBeLessThan(5000);
  for (const viewport of [{ width: 768, height: 1024 }, { width: 1024, height: 768 }, { width: 812, height: 375 }]) {
    await page.setViewportSize(viewport);
    for (const route of ["/", "/app", "/app/new", "/app/history", "/app/repositories", "/app/settings"]) {
      await page.goto(route); await expect(page.locator("h1")).toBeVisible(); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
  }
});
