import Accordion from "./Accordion.jsx";
import Icon from "./Icon.jsx";

function plural(n, unit) {
  return `${n} ${unit}${n === 1 ? "" : "s"}`;
}

function formatSpan(days) {
  if (days < 30) return plural(days, "day");
  const months = Math.round(days / 30);
  if (days < 365 && months < 12) return plural(months, "month");
  return plural(Number((days / 365).toFixed(1)), "year");
}

function formatAge(days) {
  if (days === null || days === undefined) return null;
  if (days < 1) return "today";
  return `${formatSpan(days)} ago`;
}

function formatDuration(days) {
  if (days === null || days === undefined) return null;
  const abs = Math.abs(days);
  if (abs < 1) return "today";
  return formatSpan(abs);
}

const HEURISTIC_LABELS = {
  punycode: ["Look-alike characters", "The address uses special characters that can imitate a real site."],
  ip_literal: ["Raw IP address", "The link is a number instead of a normal site name."],
  userinfo: ["Disguised address", "Text before an @ makes the link look like a different site."],
  shortener: ["Shortened link", "A short link hides where it really goes."],
  suspicious_tld: ["Risky domain ending", "This kind of ending is often used by scammers."],
  http_login: ["Sign-in without encryption", "A sign-in style page that isn't using a secure connection."],
};

const WORRYING_STATUSES = ["pendingdelete", "redemptionperiod", "serverhold", "clienthold"];

function Chip({ tone, icon, children }) {
  return (
    <span className={`chip-status chip-${tone}`}>
      <Icon name={icon} size={14} /> {children}
    </span>
  );
}

function DomainCard({ check, index }) {
  const {
    domain,
    age_days: ageDays,
    is_new_domain: isNew,
    last_changed_days: lastChangedDays,
    expires_in_days: expiresInDays,
    registrar,
    domain_status: domainStatus,
    nameservers,
    lookalike_of: lookalikeOf,
    safe_browsing_hit: safeBrowsingHit,
    safe_browsing_threat_type: threatType,
    safe_browsing_checked: safeBrowsingChecked,
    heuristics,
    error,
  } = check;

  const ageText = formatAge(ageDays);
  const recentlyChanged = lastChangedDays !== null && lastChangedDays !== undefined && lastChangedDays < 14;
  const expiringSoon = expiresInDays !== null && expiresInDays !== undefined && expiresInDays < 30;
  const statuses = Array.isArray(domainStatus) ? domainStatus : [];
  const worryingStatus = statuses.find((s) => WORRYING_STATUSES.includes(String(s).replace(/\s/g, "").toLowerCase()));
  const servers = Array.isArray(nameservers) ? nameservers : [];
  const codes = (Array.isArray(heuristics) ? heuristics : []).filter((c) => HEURISTIC_LABELS[c]);
  // false: the reputation check did not run, so "no hit" proves nothing. null: an older stored report.
  const sbNotRun = safeBrowsingChecked === false && !safeBrowsingHit;
  const hasSignal = isNew || lookalikeOf || safeBrowsingHit || codes.length > 0 || worryingStatus;

  const details = (
    <ul className="facts">
      {ageText && <li>Registered: {ageText}{isNew ? " (very new)" : ""}</li>}
      {registrar && <li>Registrar: {registrar}</li>}
      {expiresInDays !== null && expiresInDays !== undefined && (
        <li className={expiringSoon ? "fact-warn" : ""}>
          {expiresInDays >= 0 ? `Expires in ${formatDuration(expiresInDays)}` : `Expired ${formatDuration(expiresInDays)} ago`}
        </li>
      )}
      {recentlyChanged && <li>Registration record changed {formatDuration(lastChangedDays)} ago. On an older domain this is often just a renewal, so it only matters with other warnings.</li>}
      {worryingStatus && <li className="fact-danger">Status: {worryingStatus}. Abandoned domains like this are often recycled by scammers.</li>}
      {statuses.length > 0 && !worryingStatus && <li className="fact-muted">Status: {statuses.join(", ")}</li>}
      {servers.length > 0 && <li className="fact-muted">Nameservers: {servers.join(", ")}</li>}
      {lookalikeOf && <li className="fact-warn">Looks like a copy of {lookalikeOf}. The real one has a different address.</li>}
      {safeBrowsingHit && <li className="fact-danger">Reported as unsafe by Google Safe Browsing{threatType ? ` (${threatType})` : ""}.</li>}
      {codes.map((c) => (
        <li key={c} className="fact-warn">{HEURISTIC_LABELS[c][0]}: {HEURISTIC_LABELS[c][1]}</li>
      ))}
      {sbNotRun && <li className="fact-muted">Reputation check (Google Safe Browsing) was not run</li>}
      {error && <li className="fact-muted">Some checks were unavailable: {error}</li>}
    </ul>
  );

  return (
    <li className="card domain-card">
      <h3 className="domain-name">{domain || "(unknown domain)"}</h3>
      <div className="chips">
        {ageText && <Chip tone={isNew ? "warn" : "neutral"} icon="clock">{isNew ? `New: ${ageText}` : `Registered ${ageText}`}</Chip>}
        {lookalikeOf && <Chip tone="danger" icon="shield-alert">Looks like {lookalikeOf}</Chip>}
        {safeBrowsingHit && <Chip tone="danger" icon="shield-alert">Flagged unsafe</Chip>}
        {codes.map((c) => (
          <Chip key={c} tone="warn" icon="alert-triangle">{HEURISTIC_LABELS[c][0]}</Chip>
        ))}
        {sbNotRun && <Chip tone="neutral" icon="info">Google Safe Browsing not checked</Chip>}
        {!hasSignal && !error && !sbNotRun && <Chip tone="safe" icon="check">No issues found</Chip>}
        {error && !hasSignal && <Chip tone="neutral" icon="info">Some checks unavailable</Chip>}
      </div>
      <Accordion headingLevel={4} className="accordion-flat" items={[{ id: "d", title: "Details", content: details }]} />
    </li>
  );
}

export default function DomainChecksSection({ domainChecks }) {
  const checks = Array.isArray(domainChecks) ? domainChecks.filter((c) => c && typeof c === "object") : [];
  if (checks.length === 0) return null;

  return (
    <section aria-labelledby="domains-title" className="domains">
      <h2 id="domains-title" className="section-title">Links we checked</h2>
      <ul className="domain-grid">
        {checks.map((check, i) => (
          <DomainCard key={check.domain || i} check={check} index={i} />
        ))}
      </ul>
    </section>
  );
}
