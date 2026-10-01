import { useEffect, useRef, useState } from "react";
import useObjectUrl from "../hooks/useObjectUrl.js";

// Keep in sync with backend/app/main.py (ALLOWED_IMAGE_MIMES, MAX_IMAGE_BYTES).
const MAX_BYTES = 8 * 1024 * 1024;
const ALLOWED_TYPES = ["image/png", "image/jpeg", "image/webp", "image/heic", "image/heif"];
const ALLOWED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif"];
const ACCEPT = [...ALLOWED_TYPES, ".heic", ".heif"].join(",");

function isAllowed(f) {
  if (ALLOWED_TYPES.includes(f.type)) return true;
  // Some browsers report an empty type for HEIC/HEIF.
  return !f.type && ALLOWED_EXTENSIONS.some((ext) => f.name.toLowerCase().endsWith(ext));
}

// The backend accepts a single image under the "file" field, so this holds one file.
export default function ImageDropzone({ file, onChange }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [message, setMessage] = useState(null); // { text, kind: "error" | "info" }
  const previewUrl = useObjectUrl(file);

  function accept(files) {
    const picked = Array.from(files || []);
    if (picked.length === 0) return;
    const image = picked[0];
    if (!isAllowed(image)) {
      setMessage({ text: "Only PNG, JPEG, WebP, HEIC or HEIF images are supported.", kind: "error" });
      return;
    }
    if (image.size > MAX_BYTES) {
      setMessage({
        text: `That image is too large. Maximum size is ${MAX_BYTES / 1024 / 1024} MB.`,
        kind: "error",
      });
      return;
    }
    setMessage(
      picked.length > 1 ? { text: "Only one image is used; using the first.", kind: "info" } : null,
    );
    onChange(image);
  }

  // Stable listeners that always call the latest accept().
  const acceptRef = useRef(accept);
  acceptRef.current = accept;

  useEffect(() => {
    function onPaste(e) {
      const files = Array.from(e.clipboardData?.files || []);
      if (files.length > 0) acceptRef.current(files);
    }
    // A missed drop would make the browser navigate to the image and lose typed text.
    function block(e) {
      e.preventDefault();
    }
    document.addEventListener("paste", onPaste);
    window.addEventListener("dragover", block);
    window.addEventListener("drop", block);
    return () => {
      document.removeEventListener("paste", onPaste);
      window.removeEventListener("dragover", block);
      window.removeEventListener("drop", block);
    };
  }, []);

  function remove() {
    setMessage(null);
    onChange(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div className="dropzone-field">
      <span className="field-label" id="dropzone-label">Screenshot (optional)</span>
      <div
        className={`dropzone${dragging ? " dropzone-active" : ""}`}
        role="group"
        aria-labelledby="dropzone-label"
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget)) setDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          accept(e.dataTransfer.files);
        }}
      >
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
        {file && previewUrl && (
          <div className="dropzone-preview">
            <img src={previewUrl} alt={`Preview of ${file.name}`} />
            <span className="dropzone-name">{file.name}</span>
            <button
              type="button"
              className="dropzone-remove"
              aria-label={`Remove ${file.name}`}
              onClick={remove}
            >
              &times;
            </button>
          </div>
        )}
        <p id="dropzone-hint" className="dropzone-hint">
          {file
            ? "Drop, paste or choose another image to replace this one."
            : "Drag and drop a screenshot here, paste with Ctrl+V, or"}
        </p>
        <button
          type="button"
          className="btn-secondary"
          aria-describedby="dropzone-hint"
          onClick={() => inputRef.current?.click()}
        >
          {file ? "Replace image" : "Choose image"}
        </button>
      </div>
      <div
        role="status"
        className={`dropzone-message${message?.kind === "error" ? " dropzone-error" : ""}`}
      >
        {message?.text}
      </div>
    </div>
  );
}
