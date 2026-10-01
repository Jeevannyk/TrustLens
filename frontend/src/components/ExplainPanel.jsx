import Accordion from "./Accordion.jsx";

const REASON_LABELS = {
  safe_browsing: "Google Safe Browsing lists a link as dangerous",
  lookalike: "A link imitates a real brand",
  new_domain: "A link points to a very new website",
  suspicious_link: "A link has warning signs",
  sensitive_request: "The message asks for private details or money",
  injection: "The message tries to manipulate the checker",
  payment_check: "The payment details look wrong",
  unreadable: "Nothing useful could be read in the attachment",
  incomplete: "The analysis could not be completed",
};

// For these the evidence is only a placeholder ("image", "analysis"), so it is not shown.
const NO_EVIDENCE = ["unreadable", "incomplete"];

const asList = (v) => (Array.isArray(v) ? v : []);

// Older saved reports have no floor_reasons, and then there is nothing to explain.
export default function ExplainPanel({ report }) {
  const reasons = asList(report.floor_reasons).filter((r) => r && typeof r === "object");
  if (reasons.length === 0) return null;

  const raised = Boolean(report.model_risk_level) && report.model_risk_level !== report.risk_level;
  const content = (
    <>
      {raised && (
        <p>
          The AI rated this <strong>{report.model_risk_level}</strong>. Our automatic checks require at
          least <strong>{report.floor_level || report.risk_level}</strong>.
        </p>
      )}
      <p className="help">Automatic checks that set a minimum risk level:</p>
      <ul className="facts">
        {reasons.map((reason, i) => (
          <li key={i}>
            <strong>{REASON_LABELS[reason.code] || reason.code}</strong>
            {reason.evidence && !NO_EVIDENCE.includes(reason.code) && <>: {reason.evidence}</>}
          </li>
        ))}
      </ul>
    </>
  );

  return (
    <section className="card explain" aria-label="How we decided">
      <Accordion headingLevel={2} className="accordion-flat" items={[{ id: "explain", title: "How we decided", content }]} />
    </section>
  );
}
