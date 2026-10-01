import { useId } from "react";
import Icon from "./Icon.jsx";

const asList = (v) => (Array.isArray(v) ? v : []);

// Built from the report's own fields (never the raw message), so the user can review it first.
function buildComplaint(report) {
  const extracted = report.extracted || {};
  const lines = [
    "Cyber fraud complaint (draft prepared with TrustLens; please review before submitting)",
    `Date: ${new Date().toLocaleDateString("en-IN", { dateStyle: "long" })}`,
    "",
    `TrustLens verdict: ${report.risk_level}`,
  ];
  if (report.summary) lines.push(report.summary);

  const flags = asList(report.flags).filter((f) => f && f.title);
  if (flags.length) {
    lines.push("", "Warning signs found:");
    for (const flag of flags) lines.push(`- ${flag.title}${flag.evidence ? `: ${flag.evidence}` : ""}`);
  }

  const details = [];
  if (extracted.sender) details.push(`Sender: ${extracted.sender}`);
  if (extracted.claimed_brand) details.push(`Claims to be from: ${extracted.claimed_brand}`);
  const paymentIds = asList(extracted.payment_ids);
  if (paymentIds.length) details.push(`Payment IDs mentioned: ${paymentIds.join(", ")}`);
  const requested = asList(extracted.requested_items);
  if (requested.length) details.push(`It asked for: ${requested.join("; ")}`);
  const domains = asList(report.domain_checks).map((d) => d?.domain).filter(Boolean);
  if (domains.length) details.push(`Links and domains checked: ${domains.join(", ")}`);
  if (details.length) lines.push("", ...details);

  lines.push("", "Money lost (amount, date, how it was paid): ");
  return lines.join("\n");
}

export default function ActionCard({ report, onToast }) {
  const baseId = useId();
  const draft = buildComplaint(report);

  async function copy() {
    try {
      await navigator.clipboard.writeText(draft);
      onToast("Complaint draft copied");
    } catch {
      onToast("Could not copy. Select the text and copy it instead.");
    }
  }

  return (
    <section className="card action-card" aria-labelledby={`${baseId}-title`}>
      <div className="card-head">
        <h2 id={`${baseId}-title`}>If you already replied, paid or shared details</h2>
      </div>
      <ul className="facts">
        <li>
          Call the national cybercrime helpline on <a href="tel:1930"><strong>1930</strong></a>. The sooner you call,
          the better the chance of stopping a payment.
        </li>
        <li>
          Report it online at{" "}
          <a href="https://cybercrime.gov.in" target="_blank" rel="noopener noreferrer">cybercrime.gov.in</a>.
        </li>
        <li>Call your bank's official number to block the card or UPI.</li>
      </ul>

      <h3 className="action-subtitle">Prepare your complaint</h3>
      <p className="help">
        This draft is built from the result above and may contain details from the message, such as names, phone
        numbers, UPI IDs or links. Review it before you submit it anywhere. TrustLens does not file complaints for you.
      </p>
      <label htmlFor={`${baseId}-draft`} className="sr-only">Complaint draft</label>
      <textarea
        id={`${baseId}-draft`}
        className="complaint-draft"
        readOnly
        rows={12}
        value={draft}
      />
      <pre className="print-only complaint-print">{draft}</pre>
      <button type="button" className="btn btn-secondary action-copy" onClick={copy}>
        <Icon name="copy" size={18} /> Copy complaint draft
      </button>
    </section>
  );
}
