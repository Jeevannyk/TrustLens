import { useEffect, useState } from "react";
import Icon from "./Icon.jsx";

const STAGES = [
  "Reading your message",
  "Checking links & domains",
  "Looking for scam patterns",
  "Preparing your result",
];
const STEP_MS = 2500;

// Cosmetic: stages advance on a timer and stop at the last one until the result arrives.
// The bar is indeterminate on purpose; there is no real percentage to show.
export default function AnalysisProgress() {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    if (stage >= STAGES.length - 1) return undefined;
    const id = window.setTimeout(() => setStage((s) => s + 1), STEP_MS);
    return () => window.clearTimeout(id);
  }, [stage]);

  return (
    <div className="card progress-card">
      <div className="progress-bar" aria-hidden="true"><span /></div>
      <ol className="stages">
        {STAGES.map((label, i) => {
          const state = i < stage ? "done" : i === stage ? "active" : "todo";
          return (
            <li key={label} className={`stage stage-${state}`} aria-current={state === "active" ? "step" : undefined}>
              <span className="stage-dot">{state === "done" ? <Icon name="check" size={14} /> : null}</span>
              <span>{label}</span>
            </li>
          );
        })}
      </ol>
      <p className="help">Screenshots and PDFs can take a bit longer. Videos can take a minute or two.</p>
    </div>
  );
}
