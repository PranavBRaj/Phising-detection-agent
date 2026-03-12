'use strict';

/**
 * content.js — Injected into every http/https page
 *
 * Purpose
 * ───────
 * Detect Single-Page Application (SPA) client-side navigation events that
 * do not trigger a full page load (and therefore miss chrome.tabs.onUpdated).
 *
 * Techniques used
 * ───────────────
 * 1. Patching history.pushState / history.replaceState so programmatic
 *    URL changes are intercepted immediately.
 * 2. Listening for the native popstate event (browser Back/Forward buttons).
 * 3. A MutationObserver as a final fallback for frameworks that modify the
 *    DOM without using the History API.
 *
 * When a URL change is detected, a URL_CHANGED message is sent to the
 * background service worker which re-runs the fraud analysis for the tab.
 */

let lastReportedUrl = window.location.href;

/**
 * Send the new URL to the background service worker.
 * Only http/https URLs are sent — internal extension pages are skipped.
 * @param {string} url
 */
function reportUrlChange(url) {
  if (!url.startsWith('http://') && !url.startsWith('https://')) return;
  if (url === lastReportedUrl) return;    // de-duplicate
  lastReportedUrl = url;
  chrome.runtime.sendMessage({ type: 'URL_CHANGED', url }).catch(() => {
    // Background worker may be inactive during startup; ignore silently
  });
}

// ── History API patching ─────────────────────────────────────────────────────

const _origPushState    = history.pushState.bind(history);
const _origReplaceState = history.replaceState.bind(history);

history.pushState = function (...args) {
  _origPushState(...args);
  reportUrlChange(window.location.href);
};

history.replaceState = function (...args) {
  _origReplaceState(...args);
  reportUrlChange(window.location.href);
};

// ── Native navigation events ─────────────────────────────────────────────────

window.addEventListener('popstate', () => {
  reportUrlChange(window.location.href);
});

// ── MutationObserver fallback ────────────────────────────────────────────────
// Catches frameworks that update window.location without the History API

const observer = new MutationObserver(() => {
  const current = window.location.href;
  if (current !== lastReportedUrl) {
    reportUrlChange(current);
  }
});

observer.observe(document.documentElement, {
  subtree: true,
  childList: true,
});
