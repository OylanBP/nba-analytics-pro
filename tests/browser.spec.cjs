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

test('open forecast refreshes without duplicate games or notes', async ({page})=>{
  let reads=0;
  await page.clock.install();
  await page.route('**/data/model/predictions.json?*',route=>{
    reads++;
    return route.fulfill({json:{predictions:[{id:'fixture',home:'1',away:'2',
      date:new Date(Date.now()+86400000).toISOString(),home_win_probability:reads===1?.60:.65,
      away_win_probability:reads===1?.40:.35}]}});
  });
  await page.goto(base+'/#forecast',{waitUntil:'domcontentloaded'});
  const rows=page.locator('#trained-model-rows tr');
  await expect(rows.first()).toContainText('60.0%');
  await page.clock.fastForward(60001);
  await expect(rows.first()).toContainText('65.0%');
  await expect(rows).toHaveCount(2);
  await expect(page.locator('.injury-model-note')).toHaveCount(1);
});

test('v3 labels the role model and shows the player sample behind an adjustment', async ({page})=>{
  await page.route('**/data/model/predictions.json?*',route=>route.fulfill({json:{
    predictions:[{id:'fixture',home:'1',away:'2',date:new Date(Date.now()+86400000).toISOString(),
      baseline_home_probability:.50,home_win_probability:.55,away_win_probability:.45,
      injuries_in_model:true,player_roles_in_model:true, injuries:{
        away:{status:'verified',players:[{name:'測試球員',status:'Out',role:{games:10,minutes:32,points:21}}]},
        home:{status:'verified',players:[]}}}]
  }}));
  await page.goto(base+'/#forecast',{waitUntil:'domcontentloaded'});
  await expect(page).toHaveTitle(/v3\.0/);
  const details=page.locator('#trained-model-rows .injury-detail').first();
  await expect(details).toContainText('近 10 場平均 32 分鐘、21 分');
  await expect(details).toContainText('依球員角色調整');
  await expect(details).toContainText('50.0% → 55.0%');
});

for (const width of [1440,390,320]) {
 test(`sourced player backgrounds preserve stats at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:844});
  await page.goto(base);
  await page.locator('#standings-body .team-button').first().click();
  await page.locator('.player-open').first().click();
  const bio=page.locator('.player-background');
  await expect(bio).toContainText('出生日期');
  await expect(bio.locator('a').last()).toHaveAttribute('href',/^https:\/\/www\.espn\.com\/nba\/player\/bio/);
  await expect(page.locator('.profile-grid')).toContainText('得分');
  expect(await page.locator('.player-dialog').evaluate(e=>e.scrollWidth<=e.clientWidth+2)).toBe(true);
  await page.locator('#close-profile').click();
  await expect(page.locator('.player-modal')).toBeHidden();
 });
}

test('background failure can retry without hiding existing stats',async({page})=>{
 let fail=true;
 await page.route('**/data/biographies.json',route=>fail?route.fulfill({status:503,body:''}):route.continue());
 await page.goto(base);
 await page.locator('#standings-body .team-button').first().click();
 await page.locator('.player-open').first().click();
 await expect(page.locator('.player-background')).toContainText('暫時無法讀取');
 await expect(page.locator('.profile-grid')).toContainText('得分');
 fail=false;
 await page.getByRole('button',{name:'重新讀取背景'}).click();
 await expect(page.locator('.player-background')).toContainText('出生日期');
});

test('Curry story links to its checked source',async({page},testInfo)=>{
 const rosters=require('../data/rosters.json');
 const standings=require('../data/standings.json');
 const team=rosters.teams.find(t=>t.players.some(p=>String(p.id)==='3975'));
 const conf=standings.teams.find(t=>String(t.id)===String(team.id)).conference;
 await page.setViewportSize({width:390,height:844});
 await page.goto(base);
 await page.locator(`.tab[data-conf="${conf}"]`).click();
 await page.locator(`.team-button[data-id="${team.id}"]`).click();
 await page.locator('.player-open[data-player-id="3975"]').click();
 await expect(page.locator('.bio-story')).toContainText('Davidson');
 await expect(page.locator('.bio-story a')).toHaveAttribute('href','https://jr.nba.com/player-profile-stephen-curry/');
 await page.screenshot({path:testInfo.outputPath('player-background-mobile.png')});
});
