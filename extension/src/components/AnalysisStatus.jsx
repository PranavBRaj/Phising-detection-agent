/**
 * AnalysisStatus
 *
 * Renders a spinner while analysis is in progress, or an error banner
 * if the API call failed.  Returns null when neither state is active.
 */
function AnalysisStatus({ loading, error }) {
  if (loading) {
    return (
      <div className="status-loading">
        <div className="spinner" />
        <span>Analysing URL…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="status-error">
        <span className="error-icon">⚠</span>
        <span className="error-message">{error}</span>
      </div>
    )
  }

  return null
}

export default AnalysisStatus
