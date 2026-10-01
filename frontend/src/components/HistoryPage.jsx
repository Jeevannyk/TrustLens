import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../api.js";
import Icon from "./Icon.jsx";
import TrustReportCard from "./TrustReportCard.jsx";

const TONE = { Safe: "safe", Suspicious: "warn", Dangerous: "danger" };

// SQLite stores "YYYY-MM-DD HH:MM:SS" in UTC.
function parseWhen(createdAt) {
  const date = new Date(`${String(createdAt).replace(" ", "T")}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatWhen(createdAt) {
  const date = parseWhen(createdAt);
  return date ? date.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "";
}

function previewOf(item) {
  const text = (item.input_text || "").trim();
  if (text) return text.length > 140 ? `${text.slice(0, 140)}...` : text;
  if (item.input_link) return item.input_link;
  if (item.file_name) return item.file_name;
  return item.has_file ? "Attachment" : "(no text)";
}

// The file is fetched with the owner header (a plain link or <img src> cannot send one) and
// shown from a blob URL, which is revoked when this unmounts.
function HistoryAttachment({ id, kind, name }) {
  const [state, setState] = useState({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    let url = null;
    setState({ status: "loading" });
    apiFetch(`/history/${id}/file`, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(String(res.status));
        return res.blob();
      })
      .then((blob) => {
        if (controller.signal.aborted) return;
        url = URL.createObjectURL(blob);
        setState({ status: "ready", url });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ status: "error" });
      });
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [id]);

  if (state.status === "loading") return <p className="help">Loading attachment...</p>;
  if (state.status === "error") return <p className="help">The attachment could not be loaded.</p>;
  if (kind === "image") {
    return <img className="history-media" src={state.url} alt={`Saved attachment ${name || ""}`.trim()} />;
  }
  if (kind === "video") {
    return <video className="history-media" src={state.url} controls playsInline preload="metadata" aria-label={`Saved video ${name || ""}`.trim()} />;
  }
  return (
    <a className="btn btn-secondary btn-sm" href={state.url} download={name || "attachment"}>
      <Icon name="file-text" size={16} /> Download {name || "attachment"}
    </a>
  );
}

function HistoryDetail({ id, onBack, onDelete, onToast }) {
  const [state, setState] = useState({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading" });
    apiFetch(`/history/${id}`, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(String(res.status));
        return res.json();
      })
      .then((item) => setState({ status: "ready", item }))
      .catch(() => {
        if (!controller.signal.aborted) setState({ status: "error" });
      });
    return () => controller.abort();
  }, [id]);

  const item = state.item;
  return (
    <div className="view results">
      <div className="results-bar">
        <h1>Saved analysis</h1>
        <div className="history-actions">
          <button type="button" className="btn btn-secondary" onClick={onBack}>Back to history</button>
          <button type="button" className="btn btn-secondary" onClick={() => onDelete(id)}>Delete</button>
        </div>
      </div>

      {state.status === "loading" && <p className="help" role="status">Loading...</p>}
      {state.status === "error" && (
        <div className="error-box">
          <Icon name="alert-triangle" size={22} />
          <p>This analysis could not be loaded. It may have been deleted.</p>
        </div>
      )}
      {item && (
        <>
          <section className="card submission" aria-labelledby="saved-heading">
            <div className="submission-head">
              <h2 id="saved-heading">Saved {formatWhen(item.created_at)}</h2>
            </div>
            {item.input_text && <p className="submission-text submission-expanded">{item.input_text}</p>}
            {item.input_link && <p className="submission-meta">Link: <span>{item.input_link}</span></p>}
            {item.has_file && (
              <>
                {item.file_name && <p className="submission-meta">Attachment: <span>{item.file_name}</span></p>}
                <HistoryAttachment id={item.id} kind={item.file_kind} name={item.file_name} />
              </>
            )}
          </section>
          <TrustReportCard report={item.report} onToast={onToast} analyzedAt={parseWhen(item.created_at)} />
        </>
      )}
    </div>
  );
}

export default function HistoryPage({ onBack, onToast }) {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("loading");
  const [selectedId, setSelectedId] = useState(null);
  const [confirmAll, setConfirmAll] = useState(false);

  const load = useCallback((signal) => {
    setStatus("loading");
    apiFetch("/history?limit=100", { signal })
      .then((res) => {
        if (!res.ok) throw new Error(String(res.status));
        return res.json();
      })
      .then((list) => {
        setItems(Array.isArray(list) ? list : []);
        setStatus("ready");
      })
      .catch(() => {
        if (!signal?.aborted) setStatus("error");
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function deleteOne(id) {
    try {
      const res = await apiFetch(`/history/${id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 404) throw new Error(String(res.status));
      setItems((list) => list.filter((item) => item.id !== id));
      setSelectedId(null);
      onToast("Deleted");
    } catch {
      onToast("Could not delete. Please try again.");
    }
  }

  async function deleteAll() {
    try {
      const res = await apiFetch("/history", { method: "DELETE" });
      if (!res.ok) throw new Error(String(res.status));
      const { deleted } = await res.json();
      setItems([]);
      setConfirmAll(false);
      onToast(`Deleted ${deleted} ${deleted === 1 ? "analysis" : "analyses"}`);
    } catch {
      onToast("Could not delete. Please try again.");
    }
  }

  if (selectedId !== null) {
    return (
      <HistoryDetail
        id={selectedId}
        onBack={() => setSelectedId(null)}
        onDelete={deleteOne}
        onToast={onToast}
      />
    );
  }

  return (
    <div className="view results">
      <div className="results-bar">
        <h1>History</h1>
        <div className="history-actions">
          <button type="button" className="btn btn-secondary" onClick={onBack}>Back</button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={items.length === 0}
            onClick={() => setConfirmAll(true)}
          >
            Delete all
          </button>
        </div>
      </div>

      <p className="help">
        History is stored under a key kept in this browser. Clearing site data or using another device loses access.
        Saved analyses are deleted automatically after 7 days.
      </p>

      {confirmAll && (
        <div className="card history-confirm" role="alertdialog" aria-labelledby="confirm-all-text">
          <p id="confirm-all-text">
            Delete all {items.length} saved {items.length === 1 ? "analysis" : "analyses"}? This cannot be undone.
          </p>
          <div className="history-actions">
            <button type="button" className="btn btn-primary" onClick={deleteAll}>Yes, delete all</button>
            <button type="button" className="btn btn-secondary" onClick={() => setConfirmAll(false)}>Cancel</button>
          </div>
        </div>
      )}

      {status === "loading" && <p className="help" role="status">Loading...</p>}
      {status === "error" && (
        <div className="error-box">
          <Icon name="alert-triangle" size={22} />
          <div>
            <p>Could not load your history.</p>
            <button type="button" className="btn btn-secondary" onClick={() => load()}>Retry</button>
          </div>
        </div>
      )}
      {status === "ready" && items.length === 0 && <p className="help">No saved analyses yet.</p>}
      {status === "ready" && items.length > 0 && (
        <ul className="history-list">
          {items.map((item) => (
            <li key={item.id} className="card history-item">
              <div className="history-main">
                <div className="history-meta">
                  <span className={`chip-status chip-${TONE[item.risk_level] || "neutral"}`}>{item.risk_level}</span>
                  <span className="help">{formatWhen(item.created_at)}</span>
                </div>
                <p className="history-preview">{previewOf(item)}</p>
              </div>
              <div className="history-actions">
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => setSelectedId(item.id)}>
                  Open
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  aria-label={`Delete analysis from ${formatWhen(item.created_at)}`}
                  onClick={() => deleteOne(item.id)}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
