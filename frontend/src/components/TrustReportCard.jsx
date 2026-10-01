import { useState } from "react";
import Accordion from "./Accordion.jsx";
import ActionCard from "./ActionCard.jsx";
import ActionChecklist from "./ActionChecklist.jsx";
import DomainChecksSection from "./DomainChecksSection.jsx";
import ExplainPanel from "./ExplainPanel.jsx";
import Icon from "./Icon.jsx";
import ResultActions from "./ResultActions.jsx";
import VerdictBanner from "./VerdictBanner.jsx";

const SEVERITY = {
  high: { tone: "danger", label: "High", icon: "shield-alert" },
  medium: { tone: "warn", label: "Medium", icon: "alert-triangle" },
  low: { tone: "info", label: "Low", icon: "info" },
};

const asList = (v) => (Array.isArray(v) ? v : []);

function FlagsCard({ flags }) {
  const items = flags.map((flag, i) => {
    const sev = SEVERITY[flag?.severity] || SEVERITY.medium;
    return {
      id: i,
      defaultOpen: i === 0,
      title: flag?.title || "Untitled flag",
      meta: (
        <span className={`chip-status chip-${sev.tone}`}>
          <Icon name={sev.icon} size={14} /> {sev.label}
        </span>
      ),
      content: flag?.evidence ? (
        <blockquote className="evidence-quote">{flag.evidence}</blockquote>
      ) : (
        <p className="help">No more detail for this warning.</p>
      ),
    };
  });
  return (
    <section className="card" aria-labelledby="flags-title">
      <div className="card-head">
        <h2 id="flags-title">Evidence</h2>
        <span className="help">{flags.length} {flags.length === 1 ? "warning" : "warnings"}</span>
      </div>
      <Accordion items={items} headingLevel={3} />
    </section>
  );
}

function FoundCard({ report }) {
  const extracted = report.extracted;
  const findings = asList(report.findings);
  const requested = asList(extracted?.requested_items);
  const claims = asList(extracted?.claims);
  const urgency = asList(extracted?.urgency_signals);
  const hasFound =
    findings.length > 0 ||
    requested.length > 0 ||
    claims.length > 0 ||
    urgency.length > 0 ||
    Boolean(extracted?.claimed_brand || extracted?.sender || extracted?.injection_attempt);
  if (!hasFound) return null;

  return (
    <section className="card" aria-labelledby="found-title">
      <div className="card-head"><h2 id="found-title">What we found</h2></div>
      <ul className="facts">
        {findings.map((finding, i) => (
          <li key={`f${i}`}>{finding}</li>
        ))}
        {extracted?.claimed_brand && <li>Claims to be from: <strong>{extracted.claimed_brand}</strong></li>}
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
        {urgency.length > 0 && <li className="fact-warn">Urgency pressure: {urgency.join(", ")}</li>}
        {extracted?.injection_attempt && (
          <li className="fact-danger">
            Tried to manipulate this check
            {extracted.injection_evidence && `: "${extracted.injection_evidence}"`}
          </li>
        )}
      </ul>
    </section>
  );
}

export default function TrustReportCard({ report, onToast, analyzedAt: analyzedAtProp }) {
  const flags = asList(report.flags);
  const actions = asList(report.recommended_actions);
  const [analyzedAt] = useState(() => analyzedAtProp || new Date());

  return (
    <div className="result">
      <p className="print-only print-meta">
        TrustLens scan report · Analyzed{" "}
        {analyzedAt.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
      </p>
      <VerdictBanner riskLevel={report.risk_level} summary={report.summary}>
        <ResultActions report={report} onToast={onToast} />
      </VerdictBanner>

      {actions.length > 0 && <ActionChecklist actions={actions} />}
      {report.risk_level !== "Safe" && <ActionCard report={report} onToast={onToast} />}
      {flags.length > 0 && <FlagsCard flags={flags} />}
      <FoundCard report={report} />
      <ExplainPanel report={report} />

      <DomainChecksSection domainChecks={report.domain_checks} />
    </div>
  );
}
