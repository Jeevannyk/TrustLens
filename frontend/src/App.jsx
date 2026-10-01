import { useEffect, useRef, useState } from "react";
import TrustReportCard from "./components/TrustReportCard.jsx";
import DomainChecksSection from "./components/DomainChecksSection.jsx";
import ImageDropzone from "./components/ImageDropzone.jsx";
import SubmissionSummary from "./components/SubmissionSummary.jsx";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "kn", label: "ಕನ್ನಡ" },
  { code: "hi", label: "हिन्दी" },
];

const DEFAULT_LANGUAGE = "en";

async function readErrorMessage(res) {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string" && body.detail) return body.detail;
    if (Array.isArray(body?.detail)) return "Invalid input. Check your message, link and image.";
  } catch {
    // Non-JSON body; fall through to the generic message.
  }
  if (res.status >= 500) return "The server had a problem analyzing this. Please try again.";
  return `Request failed (${res.status}). Please check your input and try again.`;
}

export default function App() {
  const [text, setText] = useState("");
  const [link, setLink] = useState("");
  const [file, setFile] = useState(null);
  const [language, setLanguage] = useState(DEFAULT_LANGUAGE);
  const [view, setView] = useState("input");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [report, setReport] = useState(null);
  const abortRef = useRef(null);
  const resultsRef = useRef(null);
  const textareaRef = useRef(null);
  const focusInputRef = useRef(false);

  const hasInput = Boolean(text.trim() || link.trim() || file);

  useEffect(() => () => abortRef.current?.abort(), []);

  // Land at the top of the new view; focus the results heading for keyboard
  // and screen-reader users.
  useEffect(() => {
    window.scrollTo(0, 0);
    // preventScroll keeps the submission summary visible above the results.
    if (view === "results") resultsRef.current?.focus({ preventScroll: true });
    if (view === "input" && focusInputRef.current) {
      focusInputRef.current = false;
      textareaRef.current?.focus();
    }
  }, [view]);

  async function analyze() {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setView("results");
    resultsRef.current?.focus({ preventScroll: true }); // Retry: heading is already mounted
    setLoading(true);
    setError(null);
    setReport(null);

    const formData = new FormData();
    if (text.trim()) formData.append("text", text.trim());
    if (link.trim()) formData.append("link", link.trim());
    if (file) formData.append("file", file);
    formData.append("language", language);

    try {
      const res = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      if (!res.ok) {
        throw new Error(await readErrorMessage(res));
      }
      setReport(await res.json());
    } catch (err) {
      if (controller.signal.aborted) return;
      setError(
        err instanceof TypeError
          ? "Could not reach the server. Check your connection and try again."
          : err.message || "Something went wrong.",
      );
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (hasInput) analyze();
  }

  // Edit: back to the form with all values kept.
  function edit() {
    abortRef.current?.abort();
    setLoading(false);
    setError(null);
    setReport(null);
    focusInputRef.current = true;
    setView("input");
  }

  // Analyze another: back to a blank form.
  function startOver() {
    setText("");
    setLink("");
    setFile(null);
    setLanguage(DEFAULT_LANGUAGE);
    edit();
  }

  const status = loading
    ? "Analyzing..."
    : error
      ? `Analysis failed. ${error}`
      : report
        ? `Analysis complete: ${report.risk_level || "result ready"}`
        : "";

  return (
    <div className="page">
      <header className="header">
        <h1>TrustLens</h1>
        <p>Scam detection where every flag comes with proof.</p>
      </header>

      {view === "input" ? (
        <form className="analyze-form view" onSubmit={handleSubmit}>
          <label>
            Message text
            <textarea
              ref={textareaRef}
              rows={5}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste the suspicious message here..."
            />
          </label>

          <label>
            Link (optional)
            <input
              type="text"
              value={link}
              onChange={(e) => setLink(e.target.value)}
              placeholder="https://..."
            />
          </label>

          <ImageDropzone file={file} onChange={setFile} />

          <label>
            Language
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>

          <button type="submit" disabled={!hasInput}>
            Check for scam
          </button>
        </form>
      ) : (
        <div className="view">
          <SubmissionSummary
            text={text}
            link={link}
            file={file}
            languageLabel={LANGUAGES.find((l) => l.code === language)?.label}
            onEdit={edit}
          />
          <section className="results" aria-labelledby="results-heading">
            <div className="results-bar">
              <h2 id="results-heading" ref={resultsRef} tabIndex={-1}>
                {loading ? "Analyzing..." : error ? "Analysis failed" : "Results"}
              </h2>
              <button type="button" className="btn-secondary" onClick={startOver}>
                &larr; Analyze another
              </button>
            </div>

            <div role="status" className="sr-only">{status}</div>

            {loading && <ResultsSkeleton />}
            {error && (
              <div className="error-box">
                <p>{error}</p>
                <button type="button" className="btn-secondary" onClick={analyze}>
                  Retry
                </button>
              </div>
            )}
            {report && (
              <>
                <TrustReportCard report={report} />
                <DomainChecksSection domainChecks={report.domain_checks} />
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <div className="report-card skeleton" aria-hidden="true">
      <div className="skeleton-line skeleton-badge" />
      <div className="skeleton-line" />
      <div className="skeleton-line" />
      <div className="skeleton-line skeleton-short" />
      <div className="skeleton-line" />
    </div>
  );
}
