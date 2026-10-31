const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  try {
    for (const width of [1280,390]) {
      const page = await browser.newPage({viewport:{width,height:850}});
      const errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.route(/^https:/,route=>route.abort());
      await page.goto('http://127.0.0.1:8172');
      await page.locator('[data-conf="West"]').click();
      await page.locator('.team-button').first().click();
      await page.locator('.player-open').first().click();
      await page.locator('#close-profile').click();
      await page.locator('#close-team').click();
      assert.equal(await page.locator('#compare-a option').count(),30);
      await page.locator('#pc-output .pc-row').first().waitFor();
      await page.selectOption('#rank-stat','ts');
      await page.locator('#rank-min').fill('1');
      await page.locator('#rank-table tbody tr').first().waitFor();
      await page.selectOption('#hist-year',{index:1});
      await page.selectOption('#hist-window','10');
      assert.equal(await page.locator('#hist-table tbody tr').count(),10);
      assert.equal(await page.locator('#trend polyline').count(),2);
      assert.match(await page.locator('#model-meta').innerText(),/歷史回測/);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      assert.deepEqual(errors,[]);
      await page.close();
      console.log('通過瀏覽器操作測試，寬度',width);
    }
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
