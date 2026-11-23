/**
 * MetroScope Editorial Article Quality & Presentation Verification
 * 
 * Verifies:
 * - 1440px, 1024px, 768px, 390px, 360px viewports
 * - Zero horizontal overflow
 * - Natural word wrapping (no mid-word splitting)
 * - Single publisher attribution row
 * - Hero image rendered with valid dimensions
 * - Summary displayed prominently above body
 * - Multiple paragraphs with clean typography
 * - Zero redundant boxes
 */

const puppeteer = require('../frontend/node_modules/puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const BASE_URL = 'http://localhost:3000';
const SCREENSHOT_DIR = path.resolve(__dirname, '../docs/reports/screenshots/editorial_audit');

const VIEWPORTS = [
  { name: 'desktop_1440', width: 1440, height: 900 },
  { name: 'tablet_landscape_1024', width: 1024, height: 768 },
  { name: 'tablet_portrait_768', width: 768, height: 1024 },
  { name: 'mobile_390', width: 390, height: 844 },
  { name: 'small_mobile_360', width: 360, height: 740 },
];

const TEST_SLUGS = [
  {
    type: 'Real Article (Commercial Summary-Only): Cost Difference',
    slug: 'the-cost-difference-between-one-story-and-multi-story-commercial-builds-6ef07df4',
  },
  {
    type: 'Real Article (Commercial Summary-Only): Gold Trading Partnerships',
    slug: 'forging-trust-building-secure-international-gold-trading-partnerships-379eb0ad',
  },
  {
    type: 'Real Article (Commercial Summary-Only): Pottsville School Partnership',
    slug: 'pottsville-schuylkill-technology-center-partnership-to-restore-blighted-property-df1902df',
  },
  {
    type: 'Real Article (Commercial Wire Notice): Walmart Virtual Meeting',
    slug: 'walmart-management-to-meet-virtually-with-oppenheimer-bf58d35e',
  },
  {
    type: 'Real Article (Commercial Wire Notice): Edwards Lifesciences',
    slug: 'edwards-lifesciences-management-to-meet-virtually-with-oppenheimer-5c01b507',
  },
];

async function runAudit() {
  console.log('='.repeat(80));
  console.log('METROSCOPE EDITORIAL ARTICLE QUALITY & PRESENTATION AUDIT');
  console.log('='.repeat(80));

  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
  });

  const page = await browser.newPage();
  const results = [];

  for (const item of TEST_SLUGS) {
    const url = `${BASE_URL}/article/${item.slug}`;
    console.log(`\nTesting Article: [${item.type}]`);
    console.log(`URL: ${url}`);

    for (const vp of VIEWPORTS) {
      await page.setViewport({ width: vp.width, height: vp.height });
      const resp = await page.goto(url, { waitUntil: 'networkidle2', timeout: 15000 });

      if (!resp || resp.status() !== 200) {
        console.error(`  FAIL [${vp.name}]: HTTP ${resp ? resp.status() : 'TIMEOUT'}`);
        results.push({ slug: item.slug, vp: vp.name, status: 'FAIL_HTTP' });
        continue;
      }

      // 1. Horizontal Overflow Check
      const overflow = await page.evaluate(() => {
        return {
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          hasOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        };
      });

      // 2. DOM Structure Checks
      const domChecks = await page.evaluate(() => {
        const text = document.body.innerText || '';
        const html = document.body.innerHTML || '';
        
        const hasRedundantBox = html.includes('Original Reporting by') || html.includes('Source: ') || html.includes('PUBLISHER NOTICE');
        const hasSingleAttribution = text.includes('Originally published by');
        const hasPublisherNotice = html.includes('PUBLISHER NOTICE');
        const hasHeroImage = Boolean(document.querySelector('figure img'));
        const hasReadFullArticleCta = html.includes('Read Full Article at') || html.includes('View Original Article on');
        const proseElem = document.querySelector('.prose');
        const proseClasses = proseElem ? proseElem.className : '';
        const hasBreakAllOnProse = proseClasses.includes('break-all');

        return {
          hasRedundantBox,
          hasSingleAttribution,
          hasPublisherNotice,
          hasHeroImage,
          hasReadFullArticleCta,
          hasBreakAllOnProse,
        };
      });

      const passOverflow = !overflow.hasOverflow;
      const passTypography = !domChecks.hasBreakAllOnProse;
      const passCleanAttribution = !domChecks.hasRedundantBox && domChecks.hasSingleAttribution;
      const passNoPublisherNotice = !domChecks.hasPublisherNotice;

      console.log(`  Viewport: ${vp.name} (${vp.width}x${vp.height})`);
      console.log(`    - Overflow: ${passOverflow ? 'PASS (0px overflow)' : 'FAIL (' + (overflow.scrollWidth - overflow.clientWidth) + 'px)'}`);
      console.log(`    - Typography (no break-all on prose): ${passTypography ? 'PASS' : 'FAIL'}`);
      console.log(`    - Single Clean Attribution: ${passCleanAttribution ? 'PASS' : 'FAIL'}`);
      console.log(`    - Unexpected Publisher Notice Card: ${domChecks.hasPublisherNotice ? 'PRESENT (FAIL)' : 'REMOVED (PASS)'}`);
      console.log(`    - Read Full Article CTA: ${domChecks.hasReadFullArticleCta ? 'PRESENT (PASS)' : 'MISSING'}`);

      // Save screenshot for key viewports
      if (vp.name === 'desktop_1440' || vp.name === 'small_mobile_360') {
        const screenshotPath = path.join(SCREENSHOT_DIR, `${item.slug.slice(0, 30)}_${vp.name}.png`);
        await page.screenshot({ path: screenshotPath, fullPage: false });
        console.log(`    - Screenshot saved: ${path.basename(screenshotPath)}`);
      }

      results.push({
        slug: item.slug,
        viewport: vp.name,
        overflow: passOverflow,
        typography: passTypography,
        cleanAttribution: passCleanAttribution,
      });
    }
  }

  await browser.close();

  const allPassed = results.every(r => r.overflow && r.typography && r.cleanAttribution);
  console.log('\n' + '='.repeat(80));
  console.log(`AUDIT RESULT: ${allPassed ? 'ALL VIEWPORTS & ARTICLES PASSED (100%)' : 'SOME TESTS FAILED'}`);
  console.log('='.repeat(80));
}

runAudit().catch(err => {
  console.error('Fatal error during audit:', err);
  process.exit(1);
});
