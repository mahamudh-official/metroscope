const puppeteer = require('../frontend/node_modules/puppeteer-core');
const path = require('path');
const fs = require('fs');

async function testChrome() {
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const outDir = path.resolve(__dirname, '../docs/reports/screenshots');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  console.log('Launching Chrome from:', chromePath);
  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  
  console.log('Navigating to http://localhost:3000...');
  const res = await page.goto('http://localhost:3000', { waitUntil: 'networkidle2', timeout: 15000 });
  console.log('HTTP Status:', res.status());

  const title = await page.title();
  console.log('Page Title:', title);

  const screenshotPath = path.join(outDir, '01_homepage_desktop_1440.png');
  await page.screenshot({ path: screenshotPath, fullPage: false });
  console.log('Saved screenshot to:', screenshotPath);

  await browser.close();
  console.log('Chrome test finished successfully.');
}

testChrome().catch(err => {
  console.error('Chrome test error:', err);
  process.exit(1);
});
