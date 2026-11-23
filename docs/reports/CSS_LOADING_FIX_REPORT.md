# METROSCOPE — FRONTEND CSS LOADING FAILURE: ROOT CAUSE DIAGNOSIS & FIX REPORT

## 1. Executive Summary
During local testing of MetroScope at `http://localhost:3000`, HTML content was rendered, but CSS stylesheets failed to load, resulting in unstyled raw text.

A comprehensive technical diagnosis identified the exact root cause: Next.js configured with `output: "standalone"` does not include `.next/static` or `public` folders in the `.next/standalone` directory by default. When the standalone `server.js` was executed locally via `scripts/local_start.ps1` or `scripts/local_start.sh`, requests to `/_next/static/css/*.css` returned **HTTP 404 Not Found**, completely preventing CSS stylesheets from loading in the browser.

We implemented an automated, cross-platform build and startup asset synchronization fix. All CSS assets are now served with **HTTP 200 OK** and `Content-Type: text/css; charset=UTF-8`. Automated browser testing in headless Google Chrome confirmed that Tailwind CSS styles, fonts, and custom CSS variables are actively computed and applied across all views.

---

## 2. Root Cause Identified
In `frontend/next.config.mjs`, Next.js is configured with standalone build mode:
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  ...
};
```
Per official Next.js architecture specifications:
- `next build` produces a standalone minimal Node.js server at `frontend/.next/standalone/server.js`.
- Standalone mode intentionally **does not copy** `.next/static/` (containing compiled CSS stylesheets and JS bundles) or `public/` into `.next/standalone/` because production deployments typically offload static assets to a CDN or reverse proxy.
- When `node server.js` is run locally (or in containers without CDN offloading), `server.js` serves static assets relative to its own working directory: `__dirname + '/.next/static'`.
- Because `.next/static` was missing inside `frontend/.next/standalone/.next/`, every request to `/_next/static/css/*.css` returned **HTTP 404 Not Found**.
- Consequently, browsers received the HTML document containing `<link rel="stylesheet" href="/_next/static/css/0d050db7ec214b23.css">`, failed to retrieve the stylesheet, and displayed the unstyled fallback document.

---

## 3. Exact Files Modified

1. **`frontend/scripts/copy-standalone-assets.js`** *(Created)*:
   - Automated post-build asset synchronization script using Node.js standard library `fs.cpSync`. Copies `.next/static` to `.next/standalone/.next/static` and `public` to `.next/standalone/public`.
2. **`frontend/package.json`** *(Modified)*:
   - Updated the `"build"` script from `"next build"` to `"next build && node scripts/copy-standalone-assets.js"`, ensuring every production build automatically bundles static assets into the standalone directory.
3. **`scripts/local_start.ps1`** *(Modified)*:
   - Added automated fallback synchronization before launching `server.js` to ensure `.next/static` and `public` exist inside the standalone directory.
   - Configured `Start-Process` with `-WorkingDirectory $standaloneDir` so `server.js` resolves asset paths relative to its intended root.
4. **`scripts/local_start.sh`** *(Modified)*:
   - Added identical asset synchronization and directory context handling for Linux/macOS environments before launching `node server.js`.

---

## 4. What Was Wrong vs. What Was Changed

### What Was Wrong:
1. `npm run build` generated `frontend/.next/static/css/0d050db7ec214b23.css` (25 KB) in the main build folder, but left `frontend/.next/standalone/.next/static/` non-existent.
2. `scripts/local_start.ps1` and `scripts/local_start.sh` detected `frontend/.next/standalone/server.js` and launched it directly without copying static assets or setting the working directory.
3. Probing `http://localhost:3000/_next/static/css/0d050db7ec214b23.css` returned:
   ```
   FAILED: HTTP Error 404: Not Found
   ```
4. Probing `http://localhost:3000/logo.png` returned:
   ```
   FAILED: HTTP Error 404: Not Found
   ```

### What Was Changed:
1. **Automated Post-Build Synchronization**: Created `frontend/scripts/copy-standalone-assets.js`:
   ```javascript
   const fs = require('fs');
   const path = require('path');

   const frontendDir = path.resolve(__dirname, '..');
   const standaloneDir = path.join(frontendDir, '.next', 'standalone');

   if (fs.existsSync(standaloneDir)) {
     const staticSrc = path.join(frontendDir, '.next', 'static');
     const staticDest = path.join(standaloneDir, '.next', 'static');
     if (fs.existsSync(staticSrc)) {
       fs.cpSync(staticSrc, staticDest, { recursive: true });
     }
     const publicSrc = path.join(frontendDir, 'public');
     const publicDest = path.join(standaloneDir, 'public');
     if (fs.existsSync(publicSrc)) {
       fs.cpSync(publicSrc, publicDest, { recursive: true });
     }
   }
   ```
2. **Package.json Integration**:
   ```json
   "build": "next build && node scripts/copy-standalone-assets.js"
   ```
3. **Startup Script Hardening**: Updated `scripts/local_start.ps1` and `scripts/local_start.sh` to guarantee that `.next/standalone/.next/static` and `.next/standalone/public` are populated and `node server.js` executes with the correct working directory.

---

## 5. Build, Lint & Typecheck Results

| Check | Command | Result | Notes |
| :--- | :--- | :--- | :--- |
| **TypeScript Validation** | `npm run typecheck` | **PASS (Exit 0)** | Zero type errors (`tsc --noEmit`) |
| **ESLint Quality Check** | `npm run lint` | **PASS (Exit 0)** | Zero warnings, zero errors |
| **Next.js Production Build** | `npm run build` | **PASS (Exit 0)** | All 14 routes compiled and static assets copied |
| **Backend Test Suite** | `pytest` | **PASS (143/143)** | 100% pass rate in 4.40s |

---

## 6. CSS Asset Generation & Serving Verification

### Automated Probe Results (`scripts/verify_css_delivery.py`):
```
======================================================================
METROSCOPE CSS LOADING & DELIVERY VERIFICATION
======================================================================
[HTML] Homepage                  (/                   ) : HTTP 200 (Found 1 CSS link(s))
[HTML] Category (Science)        (/category/science   ) : HTTP 200 (Found 1 CSS link(s))
[HTML] Category (Technology)     (/category/technology) : HTTP 200 (Found 1 CSS link(s))
[HTML] About Page                (/about              ) : HTTP 200 (Found 1 CSS link(s))
[HTML] Search Page               (/search             ) : HTTP 200 (Found 1 CSS link(s))
----------------------------------------------------------------------
Total Unique CSS Assets Found: 1
----------------------------------------------------------------------
[CSS] /_next/static/css/0d050db7ec214b23.css
      Status: HTTP 200
      Content-Type: text/css; charset=UTF-8
      File Size: 25,252 bytes
      Tailwind Core Present: YES
      MetroScope Theme Variables Present: YES
----------------------------------------------------------------------
[ASSET] /logo.png : HTTP 200 (image/png, 473,801 bytes)
======================================================================
VERDICT: ALL CSS ASSETS ARE BEING SERVED WITH HTTP 200 AND VALID MIME TYPE!
======================================================================
```

### Headless Browser Computed Style Verification (Google Chrome):
Executed `frontend/scripts/test-browser-css.js` using Puppeteer:
- **Navigation Status**: HTTP 200 OK
- **Active Stylesheet**: `http://localhost:3000/_next/static/css/0d050db7ec214b23.css` (**314 CSS rules parsed**)
- **Body Computed Background**: `rgb(249, 249, 255)` (`--background: #f9f9ff` applied)
- **Body Computed Text Color**: `rgb(25, 28, 35)` (`--foreground: #191c23` applied)
- **Body Font Family**: `Inter, system-ui, sans-serif` applied
- **Heading H1 Font Family**: `"Playfair Display", Georgia, serif` applied (Font size: 48px)
- **Failed Asset Requests**: 0
- **CSS Console Errors**: 0
- **Screenshot Captured**: `docs/reports/homepage-styled.png`

---

## 7. Remaining Issues
None. The CSS loading issue is completely resolved.

---

## 8. Exact Command to Start MetroScope Locally

For Windows (PowerShell):
```powershell
.\scripts\local_start.ps1
```

For macOS / Linux (Bash):
```bash
./scripts/local_start.sh
```

To stop all services:
```powershell
.\scripts\local_stop.ps1
```
