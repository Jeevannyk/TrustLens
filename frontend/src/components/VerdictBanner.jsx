import Icon from "./Icon.jsx";

const RISK = {
  Safe: { tone: "safe", icon: "shield-check", label: "Safe" },
  Suspicious: { tone: "warn", icon: "alert-triangle", label: "Suspicious" },
  Dangerous: { tone: "danger", icon: "shield-alert", label: "Dangerous" },
};

export default function VerdictBanner({ riskLevel, summary, children }) {
  const risk = RISK[riskLevel] || { ...RISK.Suspicious, label: riskLevel || "Unknown" };
  return (
    <section className={`verdict verdict-${risk.tone}`} aria-labelledby="verdict-title">
      <div className="verdict-head">
        <Icon name={risk.icon} size={28} />
        <h2 id="verdict-title">{risk.label}</h2>
      </div>
      <p className="verdict-summary">{summary || "No summary available."}</p>
      {children}
    </section>
  );
}
