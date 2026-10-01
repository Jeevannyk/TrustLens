import { useLayoutEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import VideoPreview from "./VideoPreview.jsx";
import { classify, formatSize } from "../attachments.js";
import useObjectUrl from "../hooks/useObjectUrl.js";

export default function SubmissionSummary({ text, link, file, languageLabel, onEdit }) {
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);
  const textRef = useRef(null);
  const info = file ? classify(file) : null;
  const previewUrl = useObjectUrl(info?.kind === "image" ? file : null);
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
    <section className="card submission" aria-labelledby="submission-heading">
      <div className="submission-head">
        <h2 id="submission-heading">Your submission</h2>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onEdit}>
          <Icon name="pencil" size={16} /> Edit
        </button>
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
              className="btn btn-ghost btn-sm"
              aria-expanded={expanded}
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
        </div>
      )}

      {link.trim() && <p className="submission-meta">Link: <span>{link.trim()}</span></p>}

      {file && info && (
        <p className="submission-meta">
          Attachment: <span>{file.name}</span> ({info.typeLabel}, {formatSize(file.size)})
        </p>
      )}
      {previewUrl && (
        <img className="submission-image" src={previewUrl} alt={`Uploaded screenshot ${file.name}`} />
      )}
      {info?.kind === "video" && (
        <VideoPreview file={file} className="submission-video" label={`Uploaded video ${file.name}`} />
      )}

      <p className="submission-meta">Language: {languageLabel}</p>
    </section>
  );
}
