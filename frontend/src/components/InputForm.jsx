import { useRef, useState } from "react";
import AttachmentDropzone from "./AttachmentDropzone.jsx";

// Matches MAX_TEXT_CHARS in backend/app/text_utils.py.
export const MAX_TEXT = 10000;

const EXAMPLES = [
  {
    label: "Bank KYC text",
    text: "Dear customer, your SBI account will be blocked today. Complete KYC now: http://sbi-kyc-update.xyz/login",
  },
  {
    label: "Prize message",
    text: "Congratulations! You have won Rs 25,00,000 in the Lucky Draw. To claim, send Rs 2,500 processing fee to UPI id claim.lucky@okaxis within 1 hour.",
  },
  {
    label: "Payment receipt",
    text: "Payment of Rs 18,500 received from Rahul via UPI. Txn ID: 40291837465. Payment successful, please ship the phone today and send me the tracking number.",
  },
  {
    label: "Friendly chat",
    text: "Hey, running 10 mins late. See you at 5 outside the cafe!",
  },
];

function looksLikeLink(value) {
  return !/\s/.test(value) && /\./.test(value);
}

export default function InputForm({ text, setText, link, setLink, file, setFile, hasInput, textareaRef, onSubmit, dontSave, setDontSave }) {
  const boxRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [linkTouched, setLinkTouched] = useState(false);

  const linkError =
    linkTouched && link.trim() && !looksLikeLink(link.trim())
      ? "That does not look like a link. Include the full address, like example.com/page."
      : null;
  const nearLimit = text.length >= MAX_TEXT * 0.8;

  function applyExample(example) {
    setText(example.text);
    setLink("");
    textareaRef.current?.focus();
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (hasInput) onSubmit();
    }
  }

  return (
    <>
      <form
        ref={boxRef}
        className={`composer${dragging ? " composer-drag" : ""}`}
        onSubmit={(e) => {
          e.preventDefault();
          if (hasInput) onSubmit();
        }}
        onKeyDown={handleKeyDown}
        noValidate
      >
        <label htmlFor="msg-text" className="field-label">Message</label>
        <textarea
          id="msg-text"
          ref={textareaRef}
          rows={5}
          maxLength={MAX_TEXT}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste the message here"
          aria-describedby={nearLimit ? "msg-count" : undefined}
        />
        {nearLimit && (
          <span id="msg-count" className="counter">
            {text.length.toLocaleString()} of {MAX_TEXT.toLocaleString()} characters
          </span>
        )}

        <label htmlFor="msg-link" className="field-label">Link (optional)</label>
        <input
          id="msg-link"
          type="text"
          inputMode="url"
          autoComplete="off"
          value={link}
          onChange={(e) => setLink(e.target.value)}
          onBlur={() => setLinkTouched(true)}
          placeholder="https://"
          aria-invalid={Boolean(linkError)}
          aria-describedby="link-error"
        />
        <div id="link-error" className="field-error" role="alert">{linkError}</div>

        <label className="check-row">
          <input type="checkbox" checked={dontSave} onChange={(e) => setDontSave(e.target.checked)} />
          Don't save this analysis
        </label>

        <div className="composer-footer">
          <AttachmentDropzone file={file} onChange={setFile} containerRef={boxRef} onDraggingChange={setDragging} />
          <button type="submit" className="btn btn-primary" disabled={!hasInput}>
            Analyze
          </button>
        </div>
      </form>

      <div className="examples" role="group" aria-labelledby="examples-label">
        <span id="examples-label">Examples:</span>
        {EXAMPLES.map((ex) => (
          <button key={ex.label} type="button" className="text-btn" onClick={() => applyExample(ex)}>
            {ex.label}
          </button>
        ))}
      </div>
    </>
  );
}
