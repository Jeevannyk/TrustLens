import { useEffect, useRef, useState } from "react";
import AnalysisProgress from "./components/AnalysisProgress.jsx";
import Footer from "./components/Footer.jsx";
import Header from "./components/Header.jsx";
import Icon from "./components/Icon.jsx";
import InputForm from "./components/InputForm.jsx";
import SubmissionSummary from "./components/SubmissionSummary.jsx";
import Toast, { useToast } from "./components/Toast.jsx";
import TrustReportCard from "./components/TrustReportCard.jsx";
import useTheme from "./hooks/useTheme.js";

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
    if (Array.isArray(body?.detail)) return "Invalid input. Check your message, link and attachment.";
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
  const [theme, toggleTheme] = useTheme();
  const [toast, showToast] = useToast();
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
      const data = await res.json();
      setReport(data);
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
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <Header
        languages={LANGUAGES}
        language={language}
        onLanguageChange={setLanguage}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      <main id="main" className="page" tabIndex={-1}>
        {view === "input" ? (
          <div className="view home">
            <h1 className="greeting">Got a message you're unsure about?</h1>
            <p className="greeting-sub">
              Paste it, add a link, or upload a screenshot, a QR code image, a file (PDF, text, email) or a short video. We will tell you if it looks like a scam and show why.
            </p>
            <InputForm
              text={text}
              setText={setText}
              link={link}
              setLink={setLink}
              file={file}
              setFile={setFile}
              hasInput={hasInput}
              textareaRef={textareaRef}
              onSubmit={analyze}
            />
          </div>
        ) : (
          <div className="view results">
            <div className="results-bar">
              <h1 id="results-heading" ref={resultsRef} tabIndex={-1}>
                {loading ? "Analyzing..." : error ? "Analysis failed" : "Your result"}
              </h1>
              <button type="button" className="btn btn-secondary" onClick={startOver}>
                Analyze another
              </button>
            </div>

            <SubmissionSummary
              text={text}
              link={link}
              file={file}
              languageLabel={LANGUAGES.find((l) => l.code === language)?.label}
              onEdit={edit}
            />

            <div role="status" className="sr-only">{status}</div>

            {loading && <AnalysisProgress />}
            {error && (
              <div className="error-box">
                <Icon name="alert-triangle" size={22} />
                <div>
                  <p>{error}</p>
                  <button type="button" className="btn btn-secondary" onClick={analyze}>
                    Retry
                  </button>
                </div>
              </div>
            )}
            {report && <TrustReportCard report={report} onToast={showToast} />}
          </div>
        )}
      </main>

      <Footer />
      <Toast toast={toast} />
    </>
  );
}
