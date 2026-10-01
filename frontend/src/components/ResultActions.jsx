import Icon from "./Icon.jsx";

function buildSummary(report) {
  const lines = [`TrustLens result: ${report.risk_level}`, report.summary || ""];
  const actions = Array.isArray(report.recommended_actions) ? report.recommended_actions : [];
  if (actions.length) lines.push("", "What to do:", ...actions.map((a) => `- ${a}`));
  return lines.join("\n").trim();
}

const SHARE_LIMIT = 1000;
const SHARE_FOOTER = "\n\nChecked with TrustLens";

// Only the verdict, summary and advice: never the message that was checked.
function buildShareText(report) {
  return buildSummary(report).slice(0, SHARE_LIMIT - SHARE_FOOTER.length) + SHARE_FOOTER;
}

// The browser's print dialog saves the page as a PDF; print styles live in components.css.
function savePdf() {
  const prevTitle = document.title;
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  // Chrome and Edge use the page title as the default PDF file name.
  document.title = `TrustLens-report-${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
  const restore = () => {
    document.title = prevTitle;
    window.removeEventListener("afterprint", restore);
  };
  window.addEventListener("afterprint", restore);
  window.print();
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

  async function share() {
    const text = buildShareText(report);
    if (navigator.share) {
      try {
        await navigator.share({ title: "TrustLens result", text });
        return;
      } catch (err) {
        if (err?.name === "AbortError") return; // the user closed the share sheet
      }
    }
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, "_blank", "noopener");
  }

  return (
    <div className="result-actions">
      <button type="button" className="btn btn-secondary" onClick={copy}>
        <Icon name="copy" size={18} /> Copy summary
      </button>
      <button type="button" className="btn btn-secondary" onClick={share}>
        <Icon name="share" size={18} /> Share with family
      </button>
      <button type="button" className="btn btn-secondary" onClick={savePdf}>
        <Icon name="file-text" size={18} /> Print / save as PDF
      </button>
    </div>
  );
}
