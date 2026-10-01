import { useLayoutEffect, useRef, useState } from "react";
import useObjectUrl from "../hooks/useObjectUrl.js";

export default function SubmissionSummary({ text, link, file, languageLabel, onEdit }) {
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);
  const textRef = useRef(null);
  const previewUrl = useObjectUrl(file);
  const trimmed = text.trim();

  // Real overflow check on the clamped element; only meaningful while collapsed.
  useLayoutEffect(() => {
    const el = textRef.current;
    if (!el || expanded) return undefined;
    const check = () => setOverflowing(el.scrollHeight > el.clientHeight + 1);
    check();
    if (typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(check);
    observer.observe(el);
    return () => observer.disconnect();
  }, [trimmed, expanded]);

  return (
    <section className="submission" aria-labelledby="submission-heading">
      <div className="submission-head">
        <h2 id="submission-heading">Your submission</h2>
        <button type="button" className="btn-link" onClick={onEdit}>Edit</button>
      </div>

      {trimmed && (
        <div>
          <p
            ref={textRef}
            className={`submission-text${expanded ? " submission-expanded" : " submission-clamped"}`}
          >
            {trimmed}
          </p>
          {(overflowing || expanded) && (
            <button
              type="button"
              className="btn-link"
              aria-expanded={expanded}
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
        </div>
      )}

      {link.trim() && <p className="submission-meta">Link: <span>{link.trim()}</span></p>}

      {file && previewUrl && (
        <img className="submission-image" src={previewUrl} alt={`Uploaded screenshot ${file.name}`} />
      )}

      <p className="submission-meta">Language: {languageLabel}</p>
    </section>
  );
}
