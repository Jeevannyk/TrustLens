import { useId, useState } from "react";

// Steps are checkable for the user's own tracking; state is local and never sent anywhere.
export default function ActionChecklist({ actions }) {
  const [done, setDone] = useState({});
  const baseId = useId();
  const count = actions.filter((_, i) => done[i]).length;

  return (
    <section className="card" aria-labelledby={`${baseId}-title`}>
      <div className="card-head">
        <h2 id={`${baseId}-title`}>What to do</h2>
        <span className="help" aria-live="polite">{count} of {actions.length} done</span>
      </div>
      <ul className="checklist">
        {actions.map((action, i) => (
          <li key={i}>
            <label className={done[i] ? "is-done" : ""}>
              <input
                type="checkbox"
                checked={Boolean(done[i])}
                onChange={(e) => setDone((d) => ({ ...d, [i]: e.target.checked }))}
              />
              <span>{action}</span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}
