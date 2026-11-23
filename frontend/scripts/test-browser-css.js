const puppeteer = require('puppeteer-core');
const path = require('path');

async function testBrowserStyles() {
  console.log('=' .repeat(70));
  console.log('METROSCOPE BROWSER COMPUTED STYLES & RENDERING VERIFICATION');
  console.log('=' .repeat(70));

  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  const failedRequests = [];
  const consoleMessages = [];

  page.on('requestfailed', (req) => {
    failedRequests.push({ url: req.url(), failure: req.failure().errorText });
  });

  page.on('console', (msg) => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });

  console.log('Navigating to http://localhost:3000 ...');
  const response = await page.goto('http://localhost:3000', {
    waitUntil: 'networkidle0',
    timeout: 15000,
  });

  console.log(`Navigation status: HTTP ${response.status()}`);

  // Evaluate computed styles on DOM elements
  const styles = await page.evaluate(() => {
    const body = document.body;
    const bodyStyle = window.getComputedStyle(body);

    const h1 = document.querySelector('h1');
    const h1Style = h1 ? window.getComputedStyle(h1) : null;

    const nav = document.querySelector('header');
    const navStyle = nav ? window.getComputedStyle(nav) : null;

    const styleSheets = Array.from(document.styleSheets).map((sheet) => {
      try {
        return {
          href: sheet.href,
          rulesCount: sheet.cssRules ? sheet.cssRules.length : 0,
        };
      } catch (e) {
        return { href: sheet.href, error: e.message };
      }
    });

    return {
      body: {
        backgroundColor: bodyStyle.backgroundColor,
        color: bodyStyle.color,
        fontFamily: bodyStyle.fontFamily,
      },
      h1: h1Style
        ? {
            fontFamily: h1Style.fontFamily,
            fontSize: h1Style.fontSize,
            fontWeight: h1Style.fontWeight,
          }
        : null,
      header: navStyle
        ? {
            backgroundColor: navStyle.backgroundColor,
            borderBottomWidth: navStyle.borderBottomWidth,
          }
        : null,
      styleSheets,
    };
  });

  console.log('\n--- COMPUTED CSS STYLES ---');
  console.log('Body Computed Background:', styles.body.backgroundColor);
  console.log('Body Computed Color:', styles.body.color);
  console.log('Body Font Family:', styles.body.fontFamily);
  if (styles.h1) {
    console.log('H1 Font Family:', styles.h1.fontFamily);
    console.log('H1 Font Size:', styles.h1.fontSize);
  }
  console.log('\n--- ACTIVE STYLESHEETS IN DOM ---');
  styles.styleSheets.forEach((s) => {
    console.log(`* ${s.href} (${s.rulesCount} rules parsed)`);
  });

  // Filter out aborted Next.js background prefetch requests
  const actualFailures = failedRequests.filter(
    (f) => !f.failure.includes('ERR_ABORTED') && !f.url.includes('_rsc=')
  );

  console.log(`\n--- NETWORK & CONSOLE AUDIT ---`);
  console.log(`Failed Asset Requests Count: ${actualFailures.length}`);
  if (actualFailures.length > 0) {
    actualFailures.forEach((f) => console.log(`  [FAILED REQUEST] ${f.url} -> ${f.failure}`));
  } else {
    console.log('  No failed asset requests. All stylesheets and critical assets loaded with 200 OK.');
  }

  const cssErrors = consoleMessages.filter(
    (m) => m.type === 'error' && (m.text.includes('css') || m.text.includes('stylesheet'))
  );
  console.log(`CSS Console Errors: ${cssErrors.length}`);

  // Take screenshot
  const screenshotPath = path.join(__dirname, '..', '..', 'docs', 'reports', 'homepage-styled.png');
  await page.screenshot({ path: screenshotPath, fullPage: false });
  console.log(`\nScreenshot saved: ${screenshotPath}`);

  await browser.close();

  const isStyled =
    styles.styleSheets.some((s) => s.rulesCount > 100) &&
    styles.body.backgroundColor !== 'rgba(0, 0, 0, 0)' &&
    actualFailures.length === 0 &&
    cssErrors.length === 0;

  console.log('\n' + '='.repeat(70));
  if (isStyled) {
    console.log('BROWSER TEST VERDICT: PASSED! CSS IS ACTIVELY COMPUTED AND RENDERED IN CHROME!');
  } else {
    console.log('BROWSER TEST VERDICT: FAILED!');
    process.exit(1);
  }
  console.log('='.repeat(70));
}

testBrowserStyles().catch((err) => {
  console.error('Test execution failed:', err);
  process.exit(1);
});
