import { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import VideoPreview from "./VideoPreview.jsx";
import { ACCEPT, classify, formatSize, validate } from "../attachments.js";
import useObjectUrl from "../hooks/useObjectUrl.js";

// Compact attach control for ONE screenshot, document or video. Dropping a file anywhere on
// `containerRef` works, and so does pasting. The backend takes a single "file" field,
// so a new pick, drop or paste replaces the current attachment.
export default function AttachmentDropzone({ file, onChange, containerRef, onDraggingChange }) {
  const inputRef = useRef(null);
  const [message, setMessage] = useState(null); // { text, kind: "error" | "info" }
  const info = file ? classify(file) : null;
  const previewUrl = useObjectUrl(info?.kind === "image" ? file : null);

  function accept(files) {
    const picked = Array.from(files || []);
    if (picked.length === 0) return;
    const error = validate(picked[0]);
    if (error) {
      setMessage({ text: error, kind: "error" });
      return;
    }
    setMessage(picked.length > 1 ? { text: "Only one file is used. Using the first.", kind: "info" } : null);
    onChange(picked[0]);
  }

  // Listeners are registered once and always call the latest accept().
  const acceptRef = useRef(accept);
  acceptRef.current = accept;
  const draggingRef = useRef(onDraggingChange);
  draggingRef.current = onDraggingChange;

  useEffect(() => {
    const box = containerRef?.current;
    function onPaste(e) {
      const files = Array.from(e.clipboardData?.files || []);
      if (files.length > 0) acceptRef.current(files);
    }
    // A missed drop would make the browser open the file and lose the typed text.
    function block(e) {
      e.preventDefault();
    }
    function over(e) {
      e.preventDefault();
      draggingRef.current?.(true);
    }
    function leave(e) {
      if (!box.contains(e.relatedTarget)) draggingRef.current?.(false);
    }
    function drop(e) {
      e.preventDefault();
      draggingRef.current?.(false);
      acceptRef.current(e.dataTransfer.files);
    }
    document.addEventListener("paste", onPaste);
    window.addEventListener("dragover", block);
    window.addEventListener("drop", block);
    box?.addEventListener("dragover", over);
    box?.addEventListener("dragleave", leave);
    box?.addEventListener("drop", drop);
    return () => {
      document.removeEventListener("paste", onPaste);
      window.removeEventListener("dragover", block);
      window.removeEventListener("drop", block);
      box?.removeEventListener("dragover", over);
      box?.removeEventListener("dragleave", leave);
      box?.removeEventListener("drop", drop);
    };
  }, [containerRef]);

  function remove() {
    setMessage(null);
    onChange(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  const fileIcon = (
    <span className="attach-icon"><Icon name={info?.kind === "video" ? "video" : "file-text"} size={20} /></span>
  );

  return (
    <div className="attach" role="group" aria-label="Attachment: upload a screenshot, a file or a video">
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        hidden
        onChange={(e) => {
          accept(e.target.files);
          e.target.value = "";
        }}
      />
      {file && info && (
        <div className="attach-file">
          {previewUrl ? (
            <img src={previewUrl} alt={`Preview of ${file.name}`} />
          ) : info.kind === "video" ? (
            <VideoPreview file={file} className="attach-video" label={`Preview of ${file.name}`} fallback={fileIcon} />
          ) : (
            fileIcon
          )}
          <span className="attach-info">
            <span className="attach-name">{file.name}</span>
            <span className="attach-meta">{info.typeLabel} · {formatSize(file.size)}</span>
          </span>
          <button type="button" className="icon-btn" aria-label={`Remove ${file.name}`} onClick={remove}>
            <Icon name="x" size={18} />
          </button>
        </div>
      )}
      <button
        type="button"
        className="btn btn-secondary"
        aria-describedby="attach-hint"
        onClick={() => inputRef.current?.click()}
      >
        <Icon name="upload" size={18} /> {file ? "Replace" : "Upload"}
      </button>
      <span id="attach-hint" className="sr-only">
        Choose a screenshot, QR code image, PDF, text, email or Markdown file, or a short video. You can also drop one on this box or paste a screenshot with Ctrl+V.
      </span>
      <span role="status" className={`attach-message${message?.kind === "error" ? " is-error" : ""}`}>
        {message?.text}
      </span>
    </div>
  );
}
