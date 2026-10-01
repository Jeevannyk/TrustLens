const RISK_STYLES = {
  Safe: { className: "risk-safe", label: "Safe" },
  Suspicious: { className: "risk-suspicious", label: "Suspicious" },
  Dangerous: { className: "risk-dangerous", label: "Dangerous" },
};

const SEVERITY_ICON = {
  high: "🔴",
  medium: "🟠",
  low: "🟡",
};

export default function TrustReportCard({ report }) {
  const risk = RISK_STYLES[report.risk_level] || { className: "risk-suspicious", label: report.risk_level || "Unknown" };
  const flags = report.flags || [];
  const actions = report.recommended_actions || [];
  const extracted = report.extracted;
  const findings = Array.isArray(report.findings) ? report.findings : [];
  const asList = (v) => (Array.isArray(v) ? v : []);
  const requested = asList(extracted?.requested_items);
  const claims = asList(extracted?.claims);
  const urgency = asList(extracted?.urgency_signals);
  const hasFound =
    findings.length > 0 ||
    requested.length > 0 ||
    claims.length > 0 ||
    urgency.length > 0 ||
    Boolean(extracted?.claimed_brand || extracted?.sender || extracted?.injection_attempt);

  return (
    <div className="report-card">
      <div className={`risk-badge ${risk.className}`}>{risk.label}</div>
      <p className="summary">{report.summary || "No summary returned."}</p>

      {flags.length > 0 && (
        <div className="flags">
          <h3>Flags</h3>
          <ul>
            {flags.map((flag, i) => (
              <li key={i} className="flag-item">
                <span className="flag-icon">{SEVERITY_ICON[flag?.severity] || "⚪"}</span>
                <div>
                  <strong>{flag?.title || "Untitled flag"}</strong>
                  {flag?.evidence && <p>{flag.evidence}</p>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {actions.length > 0 && (
        <div className="actions">
          <h3>What to do</h3>
          <ul>
            {actions.map((action, i) => (
              <li key={i}>{action}</li>
            ))}
          </ul>
        </div>
      )}

      {hasFound && (
        <div className="extracted">
          <h3>What we found</h3>
          <ul className="extracted-facts">
            {findings.map((finding, i) => (
              <li key={`f${i}`}>{finding}</li>
            ))}
            {extracted?.claimed_brand && (
              <li>Claims to be from: <strong>{extracted.claimed_brand}</strong></li>
            )}
            {extracted?.sender && <li>Sender: {extracted.sender}</li>}
            {requested.length > 0 && <li>Asks you to: {requested.join("; ")}</li>}
            {claims.length > 0 && (
              <li>
                Claims made:
                <ul>
                  {claims.map((claim, i) => (
                    <li key={i}>{claim}</li>
                  ))}
                </ul>
              </li>
            )}
            {urgency.length > 0 && (
              <li className="fact-warn">Urgency pressure: {urgency.join(", ")}</li>
            )}
            {extracted?.injection_attempt && (
              <li className="fact-danger">
                Tried to manipulate this check
                {extracted.injection_evidence && `: "${extracted.injection_evidence}"`}
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
