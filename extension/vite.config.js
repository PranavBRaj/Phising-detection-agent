import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

/**
 * Vite config for the Fraud Detector Chrome extension.
 *
 * Build output (dist/) layout
 * ───────────────────────────
 *  index.html          ← popup UI (built from src/main.jsx)
 *  assets/             ← hashed JS/CSS chunks for the popup
 *  manifest.json       ← copied from public/ unchanged
 *  background.js       ← copied from public/ unchanged (service worker)
 *  content.js          ← copied from public/ unchanged (content script)
 *
 * Files in public/ are copied verbatim by Vite — no bundling, no hashing.
 * This is intentional: content scripts and service workers must be plain
 * scripts and cannot be ES-module bundles loaded from an HTML file.
 *
 * Load the unpacked extension from the dist/ directory in Chrome.
 */
export default defineConfig({
  plugins: [react()],

  // Use relative asset paths so the popup HTML works when served from
  // a chrome-extension:// origin (no base path prefix needed).
  base: './',

  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        // Only the popup HTML is bundled by Rollup.
        popup: resolve(__dirname, 'index.html'),
      },
    },
  },
})
