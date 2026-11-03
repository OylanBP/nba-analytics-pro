const { test, expect } = require('@playwright/test');

const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:8765';
const pages = [
  { name: 'desktop', viewport: { width: 1440, height: 900 } },
  { name: 'iPhone 13', viewport: { width: 390, height: 844 }, isMobile: true, deviceScaleFactor: 3, hasTouch: true },
  { name: 'small mobile', viewport: { width: 320, height: 740 }, isMobile: true, hasTouch: true },
];

for (const profile of pages) {
  test.describe(profile.name, () => {
    test.use({ viewport: profile.viewport, isMobile: !!profile.isMobile, hasTouch: !!profile.hasTouch, deviceScaleFactor: profile.deviceScaleFactor || 1 });

    test('loads actual data, navigates and avoids viewport overflow', async ({ page }, testInfo) => {
      const failures = [];
      page.on('pageerror', e => failures.push(e.message));
      await page.goto(base, { waitUntil: 'domcontentloaded' });
      await expect(page.locator('h1')).toContainText('聯盟總覽');
      await expect(page.locator('#standings-body tr').first()).toBeVisible();
      await expect.poll(async () => page.locator('#standings-body tr').count(), { timeout: 30000 }).toBeGreaterThan(1);
      await expect(page.locator('#data-status')).not.toContainText('失敗');
      await expect(page.locator('#standings-body')).not.toContainText('正在載入');
      await page.locator('.tab[data-conf="West"]').click();
      await expect(page.locator('.tab[data-conf="West"]')).toHaveAttribute('aria-selected', 'true');
      await page.locator('.tab[data-conf="East"]').click();
      await expect(page.locator('.tab[data-conf="East"]')).toHaveAttribute('aria-selected', 'true');
      await page.locator('.site-nav a[href="#league"]').click();
      await expect(page).toHaveURL(/#league$/);
      await expect(page.locator('#rank-stat')).toBeVisible();
      await expect(page.locator('#rank-table')).not.toContainText('載入中', { timeout: 30000 });
      await page.locator('.site-nav a[href="#forecast"]').click();
      await expect(page.locator('#forecast')).toBeVisible();
      await expect(page.locator('#trained-model-status')).not.toContainText('正在檢查', { timeout: 30000 });
      await page.screenshot({ path: testInfo.outputPath(profile.name.replaceAll(' ', '-') + '.png'), fullPage: true });
      const horizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2);
      expect(horizontalOverflow, 'No document-wide horizontal scrolling; tables can scroll internally').toBe(false);
      expect(failures, 'No uncaught JavaScript exceptions').toEqual([]);
    });
  });
}

test('player and team selectors respond to input', async ({ page }) => {
  await page.goto(base, { waitUntil: 'domcontentloaded' });
  await expect.poll(async () => page.locator('#compare-a option').count(), { timeout: 30000 }).toBeGreaterThan(2);
  const options = await page.locator('#compare-a option').evaluateAll(items => items.map(x => x.value).filter(Boolean));
  expect(options.length).toBeGreaterThan(1);
  await page.locator('#compare-a').selectOption(options[0]);
  await page.locator('#compare-b').selectOption(options[1]);
  await expect(page.locator('#compare-output')).not.toContainText('等待戰績資料載入');
  await expect.poll(async () => page.locator('#pc-team-a option').count(), { timeout: 30000 }).toBeGreaterThan(2);
  await page.locator('#pc-team-a').selectOption({ index: 1 });
  await expect.poll(async () => page.locator('#pc-player-a option').count(), { timeout: 30000 }).toBeGreaterThan(1);
});
