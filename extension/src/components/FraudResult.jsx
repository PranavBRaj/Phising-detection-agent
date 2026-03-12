/**
 * FraudResult
 *
 * Displays the full analysis result for a single URL:
 *  - Fraud / Safe verdict banner
 *  - Animated risk score bar
 *  - Metadata rows (final URL, redirect count, status, timing)
 *  - Collapsible list of detection reasons
 *  - Collapsible redirect chain
 */
function FraudResult({ result }) {
  if (!result) return null

  const {
    is_fraud,
    fraud_score,
    fraud_reasons,
    redirect_chain,
    redirect_count,
    final_url,
    original_url,
    status_code,
    response_time_ms,
  } = result

  const scorePercent = (fraud_score * 100).toFixed(1)

  return (
    <div className={`fraud-result ${is_fraud ? 'result-fraud' : 'result-safe'}`}>

      {/* Verdict banner */}
      <div className="result-header">
        <span className="result-icon">{is_fraud ? '⚠️' : '✅'}</span>
        <span>{is_fraud ? 'POTENTIAL FRAUD DETECTED' : 'APPEARS SAFE'}</span>
      </div>

      {/* Animated risk score bar */}
      <div className="score-bar">
        <span className="score-label">Risk Score</span>
        <div className="score-track">
          <div
            className={`score-fill ${is_fraud ? 'score-danger' : 'score-safe'}`}
            style={{ width: `${fraud_score * 100}%` }}
          />
        </div>
        <span className="score-value">{scorePercent}%</span>
      </div>

      {/* Final URL (only shown when different from original) */}
      {final_url && final_url !== original_url && (
        <div className="detail-row">
          <span className="detail-label">Final URL</span>
          <span className="detail-value url-value" title={final_url}>
            {final_url.length > 42 ? final_url.slice(0, 42) + '…' : final_url}
          </span>
        </div>
      )}

      {/* Redirect count */}
      <div className="detail-row">
        <span className="detail-label">Redirects</span>
        <span className="detail-value">{redirect_count}</span>
      </div>

      {/* HTTP status */}
      {status_code != null && (
        <div className="detail-row">
          <span className="detail-label">HTTP Status</span>
          <span className="detail-value">{status_code}</span>
        </div>
      )}

      {/* Response time */}
      {response_time_ms != null && (
        <div className="detail-row">
          <span className="detail-label">Trace Time</span>
          <span className="detail-value">{response_time_ms} ms</span>
        </div>
      )}

      {/* Detection reasons */}
      {fraud_reasons.length > 0 && (
        <div className="reasons-section">
          <div className="reasons-title">Detection Reasons</div>
          <ul className="reasons-list">
            {fraud_reasons.map((reason, i) => (
              <li key={i} className="reason-item">{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Redirect chain */}
      {redirect_chain.length > 0 && (
        <details className="redirect-details">
          <summary>Redirect chain — {redirect_chain.length} hop{redirect_chain.length !== 1 ? 's' : ''}</summary>
          <ol className="redirect-list">
            {redirect_chain.map((hop, i) => (
              <li key={i} className="redirect-hop">
                <span className="hop-status">[{hop.status_code ?? '?'}]</span>
                <span className="hop-url" title={hop.url}>
                  {hop.url.length > 48 ? hop.url.slice(0, 48) + '…' : hop.url}
                </span>
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  )
}

export default FraudResult
