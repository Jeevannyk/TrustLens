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
  punycode: "Address uses look-alike characters",
  ip_literal: "Address is a raw IP number, not a normal site name",
  userinfo: "Address has text before an @ that disguises the real site",
  shortener: "Shortened link that hides the real destination",
  suspicious_tld: "Ends with a domain type often used by scammers",
  http_login: "Sign-in style page without encryption (http)",
};

const WORRYING_STATUSES = ["pendingdelete", "redemptionperiod", "serverhold", "clienthold"];

export default function DomainChecksSection({ domainChecks }) {
  if (!Array.isArray(domainChecks) || domainChecks.length === 0) {
    return null;
  }

  return (
    <div className="report-card evidence-card">
      <h3>Domain evidence</h3>
      <ul className="domain-checks">
        {domainChecks.map((check, i) => {
          if (!check || typeof check !== "object") return null;
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
            lookalike_distance: lookalikeDistance,
            safe_browsing_hit: safeBrowsingHit,
            safe_browsing_threat_type: threatType,
            heuristics,
            error,
          } = check;

          const ageText = formatAge(ageDays);
          const recentlyChanged = lastChangedDays !== null && lastChangedDays !== undefined && lastChangedDays < 14;
          const expiringSoon = expiresInDays !== null && expiresInDays !== undefined && expiresInDays < 30;
          const statuses = Array.isArray(domainStatus) ? domainStatus : [];
          const worryingStatus = statuses.find((s) => WORRYING_STATUSES.includes(String(s).replace(/\s/g, "").toLowerCase()));
          const heuristicCodes = Array.isArray(heuristics) ? heuristics : [];
          const servers = Array.isArray(nameservers) ? nameservers : [];
          const hasAnySignal = heuristicCodes.length > 0 || isNew || lookalikeOf || safeBrowsingHit || recentlyChanged || expiringSoon || worryingStatus;

          return (
            <li key={domain || i} className="domain-check-item">
              <div className="domain-check-header">
                <strong>{domain || "(unknown domain)"}</strong>
                {!hasAnySignal && !error && <span className="domain-check-clean">no issues found</span>}
              </div>
              <ul className="domain-check-facts">
                {ageText && (
                  <li className={isNew ? "fact-warn" : ""}>
                    Registered: {ageText}
                    {isNew ? " — very new domain" : ""}
                  </li>
                )}
                {registrar && <li>Registrar: {registrar}</li>}
                {recentlyChanged && (
                  <li className="fact-warn">
                    Registration record last changed {formatDuration(lastChangedDays)} ago
                    {ageDays > 365 ? " — on an older domain this is often just a renewal or DNS edit, so only worth noting alongside other warning signs" : ""}
                  </li>
                )}
                {expiresInDays !== null && expiresInDays !== undefined && (
                  <li className={expiringSoon ? "fact-warn" : ""}>
                    {expiresInDays >= 0
                      ? `Expires in ${formatDuration(expiresInDays)}`
                      : `Expired ${formatDuration(expiresInDays)} ago`}
                  </li>
                )}
                {worryingStatus && (
                  <li className="fact-danger">
                    Domain status: {worryingStatus} — abandoned/about to be recycled, common for scam domains
                  </li>
                )}
                {statuses.length > 0 && !worryingStatus && (
                  <li className="fact-muted">Status: {statuses.join(", ")}</li>
                )}
                {servers.length > 0 && <li className="fact-muted">Nameservers: {servers.join(", ")}</li>}
                {lookalikeOf && (
                  <li className="fact-warn">
                    Looks like a typosquat of <strong>{lookalikeOf}</strong>
                    {typeof lookalikeDistance === "number"
                      ? ` (${lookalikeDistance} character${lookalikeDistance === 1 ? "" : "s"} off)`
                      : ""}
                  </li>
                )}
                {safeBrowsingHit && (
                  <li className="fact-danger">
                    Flagged by Google Safe Browsing{threatType ? ` as ${threatType}` : ""}
                  </li>
                )}
                {heuristicCodes.map((code) => (
                  <li key={code} className="fact-warn">{HEURISTIC_LABELS[code] || code}</li>
                ))}
                {error && <li className="fact-muted">Check unavailable: {error}</li>}
              </ul>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
