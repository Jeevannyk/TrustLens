import Icon from "./Icon.jsx";

function buildSummary(report) {
  const lines = [`TrustLens result: ${report.risk_level}`, report.summary || ""];
  const actions = Array.isArray(report.recommended_actions) ? report.recommended_actions : [];
  if (actions.length) lines.push("", "What to do:", ...actions.map((a) => `- ${a}`));
  return lines.join("\n").trim();
}

export default function ResultActions({ report, onToast }) {
  async function copy() {
    try {
      await navigator.clipboard.writeText(buildSummary(report));
      onToast("Summary copied");
    } catch {
      onToast("Could not copy. Select the text and copy it instead.");
    }
  }

  return (
    <div className="result-actions">
      <button type="button" className="btn btn-secondary" onClick={copy}>
        <Icon name="copy" size={18} /> Copy summary
      </button>
    </div>
  );
}
