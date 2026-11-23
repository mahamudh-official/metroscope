const puppeteer = require('../frontend/node_modules/puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const BASE_URL = 'http://localhost:3000';
const SCREENSHOT_DIR = path.resolve(__dirname, '../docs/reports/screenshots/homepage_audit');

async function testHomepage() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
  });

  const page = await browser.newPage();
  const viewports = [
    { name: 'desktop_1440', width: 1440, height: 900 },
    { name: 'tablet_768', width: 768, height: 1024 },
    { name: 'mobile_360', width: 360, height: 740 },
  ];

  for (const vp of viewports) {
    await page.setViewport({ width: vp.width, height: vp.height });
    await page.goto(BASE_URL, { waitUntil: 'networkidle2', timeout: 15000 });

    const checks = await page.evaluate(() => {
      const html = document.body.innerHTML;
      const hasDevelopingStories = html.includes('Essential Developing Stories');
      const hasVerifiedCoverage = html.includes('Verified Coverage');
      const hasPublisherNotice = html.includes('PUBLISHER NOTICE');
      const scrollWidth = document.documentElement.scrollWidth;
      const clientWidth = document.documentElement.clientWidth;

      return {
        hasDevelopingStories,
        hasVerifiedCoverage,
        hasPublisherNotice,
        hasOverflow: scrollWidth > clientWidth,
        overflowDelta: scrollWidth - clientWidth,
      };
    });

    console.log(`Homepage [${vp.name}]:`);
    console.log(`  - Horizontal Overflow: ${checks.hasOverflow ? 'FAIL (' + checks.overflowDelta + 'px)' : 'PASS (0px)'}`);
    console.log(`  - Unexpected "Essential Developing Stories" Section: ${checks.hasDevelopingStories ? 'PRESENT (FAIL)' : 'REMOVED (PASS)'}`);
    console.log(`  - Fake "Verified Coverage" Content: ${checks.hasVerifiedCoverage ? 'PRESENT (FAIL)' : 'REMOVED (PASS)'}`);
    console.log(`  - Unexpected "Publisher Notice": ${checks.hasPublisherNotice ? 'PRESENT (FAIL)' : 'REMOVED (PASS)'}`);

    const screenshotPath = path.join(SCREENSHOT_DIR, `homepage_${vp.name}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: false });
    console.log(`  - Screenshot saved: ${path.basename(screenshotPath)}`);
  }

  await browser.close();
}

testHomepage().catch(err => {
  console.error(err);
  process.exit(1);
});
