'use strict';

/**
 * background.js — Manifest V3 Service Worker
 *
 * Responsibilities
 * ─────────────────
 * 1. Listen for tab navigation events and automatically analyse every
 *    new http/https URL the user visits.
 * 2. Cache the analysis result in chrome.storage.local keyed by tabId.
 * 3. Update the extension action badge with a visual risk indicator.
 * 4. Respond to messages from the popup (GET_ANALYSIS, ANALYZE_NOW).
 * 5. Handle SPA URL changes forwarded by the content script (URL_CHANGED).
 * 6. Clean up cached results when a tab is closed.
 */

const API_BASE_URL = 'http://localhost:8000/api';

// ── Internal helpers ─────────────────────────────────────────────────────────

/**
 * Call the backend /api/analyze endpoint.
 * @param {string} url
 * @returns {Promise<Object>} Analysis result
 */
async function callAnalyzeApi(url) {
  const response = await fetch(`${API_BASE_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `API error ${response.status}`);
  }

  return response.json();
}

/**
 * Update the action badge for a given tab.
 * Shows a red "!" for fraud, a green "✓" for safe, nothing on error.
 *
 * @param {number} tabId
 * @param {boolean} isFraud
 */
function updateBadge(tabId, isFraud) {
  if (isFraud) {
    chrome.action.setBadgeText({ text: '!', tabId });
    chrome.action.setBadgeBackgroundColor({ color: '#ef4444', tabId });
  } else {
    chrome.action.setBadgeText({ text: '✓', tabId });
    chrome.action.setBadgeBackgroundColor({ color: '#22c55e', tabId });
  }
}

/**
 * Analyse the URL for a tab, store the result, and update the badge.
 *
 * @param {number} tabId
 * @param {string} url
 */
async function analyzeTab(tabId, url) {
  // Only analyse http/https — skip chrome://, data:, etc.
  if (!url || (!url.startsWith('http://') && !url.startsWith('https://'))) {
    return;
  }

  try {
    const result = await callAnalyzeApi(url);
    // Store result so the popup can retrieve it without a second API call
    await chrome.storage.local.set({ [`tab_analysis_${tabId}`]: result });
    updateBadge(tabId, result.is_fraud);
  } catch (err) {
    console.warn('[FraudDetector] Analysis failed for tab', tabId, ':', err.message);
    // Clear badge on failure so users know the result is stale / missing
    chrome.action.setBadgeText({ text: '', tabId });
  }
}

// ── Event listeners ──────────────────────────────────────────────────────────

/**
 * Trigger analysis when a tab starts loading a new URL.
 * Using 'loading' (not 'complete') catches redirects earlier.
 */
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'loading' && tab.url) {
    analyzeTab(tabId, tab.url);
  }
});

/**
 * Remove cached results when tabs are closed to avoid unbounded storage growth.
 */
chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.local.remove(`tab_analysis_${tabId}`);
});

/**
 * Message handler for the popup and content script.
 *
 * Supported message types
 * ───────────────────────
 * GET_ANALYSIS  { tabId }        → returns cached result or null
 * ANALYZE_NOW   { url }          → runs a fresh analysis and returns result
 * URL_CHANGED   { url }          → SPA navigation detected by content script
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'GET_ANALYSIS') {
    // Return the cached result for the requested tab (async)
    chrome.storage.local.get(`tab_analysis_${message.tabId}`, (data) => {
      sendResponse(data[`tab_analysis_${message.tabId}`] ?? null);
    });
    return true; // Keep the message channel open for async sendResponse
  }

  if (message.type === 'ANALYZE_NOW') {
    callAnalyzeApi(message.url)
      .then((result) => sendResponse({ success: true, data: result }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (message.type === 'URL_CHANGED') {
    // Forwarded from the content script (SPA client-side navigation)
    if (sender.tab?.id && message.url) {
      analyzeTab(sender.tab.id, message.url);
    }
    return false; // No response needed
  }
});
