const fs = require('fs');
const path = require('path');

const frontendDir = path.resolve(__dirname, '..');
const standaloneDir = path.join(frontendDir, '.next', 'standalone');

if (fs.existsSync(standaloneDir)) {
  const staticSrc = path.join(frontendDir, '.next', 'static');
  const staticDest = path.join(standaloneDir, '.next', 'static');
  if (fs.existsSync(staticSrc)) {
    fs.cpSync(staticSrc, staticDest, { recursive: true });
    console.log('[standalone] Successfully copied .next/static -> .next/standalone/.next/static');
  }

  const publicSrc = path.join(frontendDir, 'public');
  const publicDest = path.join(standaloneDir, 'public');
  if (fs.existsSync(publicSrc)) {
    fs.cpSync(publicSrc, publicDest, { recursive: true });
    console.log('[standalone] Successfully copied public -> .next/standalone/public');
  }
}
