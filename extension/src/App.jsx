import { useState, useEffect, useCallback } from 'react'
import AnalysisStatus from './components/AnalysisStatus'
import FraudResult from './components/FraudResult'
import { analyzeUrl, getHistory } from './utils/api'
import './App.css'

/**
 * Root popup component.
 *
 * Flow
 * ────
 * 1. On mount, query the active tab URL via chrome.tabs.
 * 2. Ask the background service worker for a cached analysis (it may have
 *    already analysed this URL when the tab first loaded).
 * 3. If no cache exists, call the backend API directly.
 * 4. The History tab fetches recent logs from the backend on first open.
 */
function App() {
  const [currentTab, setCurrentTab]       = useState(null)
  const [analysis, setAnalysis]           = useState(null)
  const [loading, setLoading]             = useState(false)
  const [error, setError]                 = useState(null)
  const [view, setView]                   = useState('current') // 'current' | 'history'
  const [history, setHistory]             = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError]   = useState(null)

  // ── Analyse a URL against the backend ──────────────────────────────────
  const handleAnalyze = useCallback(async (url) => {
    if (!url) return
    setLoading(true)
    setError(null)
    setAnalysis(null)

    try {
      const result = await analyzeUrl(url)
      setAnalysis(result)
    } catch (err) {
      setError(err.message || 'Analysis failed. Is the backend running on localhost:8000?')
    } finally {
      setLoading(false)
    }
  }, [])

  // ── On mount: get current tab then check for cached result ─────────────
  useEffect(() => {
    if (typeof chrome === 'undefined' || !chrome.tabs) {
      // Not running inside an extension context (e.g. during vite dev)
      return
    }

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0]
      if (!tab) return
      setCurrentTab(tab)

      // Try the background service worker's cache first
      chrome.runtime.sendMessage(
        { type: 'GET_ANALYSIS', tabId: tab.id },
        (cached) => {
          if (chrome.runtime.lastError) {
            // Background script not available — fall through to direct call
          }
          if (cached) {
            setAnalysis(cached)
          } else if (tab.url?.startsWith('http')) {
            handleAnalyze(tab.url)
          }
        },
      )
    })
  }, [handleAnalyze])

  // ── Load history when the History tab is selected ──────────────────────
  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      const logs = await getHistory(25)
      setHistory(logs)
    } catch (err) {
      setHistoryError(err.message || 'Failed to load history')
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    if (view === 'history') loadHistory()
  }, [view, loadHistory])

  const currentUrl = currentTab?.url ?? ''
  const isHttpUrl  = currentUrl.startsWith('http://') || currentUrl.startsWith('https://')

  return (
    <div className="app">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <header className="app-header">
        <span className="header-icon">🛡️</span>
        <h1>Fraud Detector</h1>
      </header>

      {/* ── Navigation tabs ───────────────────────────────────────────── */}
      <nav className="nav-tabs">
        <button
          className={`tab ${view === 'current' ? 'active' : ''}`}
          onClick={() => setView('current')}
        >
          Current Page
        </button>
        <button
          className={`tab ${view === 'history' ? 'active' : ''}`}
          onClick={() => setView('history')}
        >
          History
        </button>
      </nav>

      {/* ── Current-page view ─────────────────────────────────────────── */}
      {view === 'current' && (
        <div className="current-view">
          <div className="url-display">
            <span className="url-label">URL</span>
            <span className="url-text" title={currentUrl}>
              {currentUrl || 'No URL detected'}
            </span>
          </div>

          {!isHttpUrl && currentUrl && (
            <div className="non-http-message">
              This extension only analyses HTTP/HTTPS pages.
            </div>
          )}

          <AnalysisStatus loading={loading} error={error} />

          {analysis && !loading && <FraudResult result={analysis} />}

          {isHttpUrl && (
            <button
              className="btn-analyze"
              onClick={() => handleAnalyze(currentUrl)}
              disabled={loading}
            >
              {loading ? 'Analysing…' : 'Re-analyse'}
            </button>
          )}
        </div>
      )}

      {/* ── History view ──────────────────────────────────────────────── */}
      {view === 'history' && (
        <div className="history-view">
          {historyLoading ? (
            <div className="loading-msg">Loading history…</div>
          ) : historyError ? (
            <div className="status-error">
              <span className="error-icon">⚠</span>
              <span className="error-message">{historyError}</span>
            </div>
          ) : history.length === 0 ? (
            <div className="empty-state">No analysis history yet.</div>
          ) : (
            <div className="history-list">
              {history.map((item, idx) => (
                <div
                  key={idx}
                  className={`history-item ${item.is_fraud ? 'fraud' : 'safe'}`}
                >
                  <div className="history-url" title={item.original_url}>
                    {item.original_url.length > 55
                      ? item.original_url.slice(0, 55) + '…'
                      : item.original_url}
                  </div>
                  <div className="history-meta">
                    <span className={`badge ${item.is_fraud ? 'badge-fraud' : 'badge-safe'}`}>
                      {item.is_fraud ? '⚠ FRAUD' : '✓ SAFE'}
                    </span>
                    <span className="score">
                      {(item.fraud_score * 100).toFixed(0)}% risk
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {!historyLoading && (
            <button className="btn-refresh" onClick={loadHistory}>
              ↻ Refresh
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default App
