/**
 * api.js — thin wrapper around the Fraud Detection backend API.
 *
 * The base URL defaults to localhost:8000.  Override the
 * VITE_API_BASE_URL environment variable during the Vite build if you
 * deploy the backend on a different host/port.
 */

const API_BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) ||
  'http://localhost:8000/api'

/**
 * POST /api/analyze
 *
 * Sends a URL to the backend for redirect tracing and fraud detection.
 *
 * @param {string} url - The fully-qualified http(s) URL to analyse.
 * @returns {Promise<Object>} The AnalysisResponse object from the backend.
 * @throws {Error} With a user-friendly message on network or API errors.
 */
export async function analyzeUrl(url) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
  } catch (networkError) {
    // fetch() itself threw — most likely the backend is not reachable
    throw new Error(
      'Cannot reach the backend. Make sure the FastAPI server is running on localhost:8000.',
    )
  }

  if (!response.ok) {
    // Try to surface the FastAPI error detail
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Server returned ${response.status}`)
  }

  return response.json()
}

/**
 * GET /api/logs
 *
 * Fetches stored analysis logs from the database.
 *
 * @param {number} [limit=50]      - Maximum number of records to return.
 * @param {boolean} [fraudOnly=false] - When true, return only fraud records.
 * @returns {Promise<Object[]>} Array of AnalysisResponse objects.
 * @throws {Error} On network or API errors.
 */
export async function getHistory(limit = 50, fraudOnly = false) {
  const params = new URLSearchParams({
    limit: String(limit),
    fraud_only: String(fraudOnly),
  })

  let response
  try {
    response = await fetch(`${API_BASE_URL}/logs?${params}`)
  } catch {
    throw new Error(
      'Cannot reach the backend. Make sure the FastAPI server is running on localhost:8000.',
    )
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Server returned ${response.status}`)
  }

  return response.json()
}
