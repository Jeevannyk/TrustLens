import { useState } from "react";
import TrustReportCard from "./components/TrustReportCard.jsx";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "kn", label: "ಕನ್ನಡ" },
  { code: "hi", label: "हिन्दी" },
];

export default function App() {
  const [text, setText] = useState("");
  const [link, setLink] = useState("");
  const [file, setFile] = useState(null);
  const [language, setLanguage] = useState("en");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [report, setReport] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!text.trim() && !link.trim() && !file) {
      setError("Paste a message, a link, or upload a screenshot.");
      return;
    }
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
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `Request failed (${res.status})`);
      }
      const data = await res.json();
      setReport(data);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header className="header">
        <h1>TrustLens</h1>
        <p>Scam detection where every flag comes with proof.</p>
      </header>

      <form className="analyze-form" onSubmit={handleSubmit}>
        <label>
          Message text
          <textarea
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

        <label>
          Screenshot (optional)
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>

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

        <button type="submit" disabled={loading}>
          {loading ? "Analyzing..." : "Check for scam"}
        </button>
      </form>

      {error && <div className="error-box">{error}</div>}
      {report && <TrustReportCard report={report} />}
    </div>
  );
}
