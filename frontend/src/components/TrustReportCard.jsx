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
  const risk = RISK_STYLES[report.risk_level] || RISK_STYLES.Suspicious;

  return (
    <div className="report-card">
      <div className={`risk-badge ${risk.className}`}>{risk.label}</div>
      <p className="summary">{report.summary}</p>

      {report.flags?.length > 0 && (
        <div className="flags">
          <h3>Flags</h3>
          <ul>
            {report.flags.map((flag, i) => (
              <li key={i} className="flag-item">
                <span className="flag-icon">{SEVERITY_ICON[flag.severity] || "⚪"}</span>
                <div>
                  <strong>{flag.title}</strong>
                  <p>{flag.evidence}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.recommended_actions?.length > 0 && (
        <div className="actions">
          <h3>What to do</h3>
          <ul>
            {report.recommended_actions.map((action, i) => (
              <li key={i}>{action}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
