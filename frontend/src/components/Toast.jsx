import { useCallback, useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";

const DISMISS_MS = 3500;

export function useToast() {
  const [toast, setToast] = useState(null);
  const timer = useRef(null);

  const show = useCallback((message) => {
    window.clearTimeout(timer.current);
    setToast({ message, key: Date.now() });
    timer.current = window.setTimeout(() => setToast(null), DISMISS_MS);
  }, []);

  useEffect(() => () => window.clearTimeout(timer.current), []);
  return [toast, show];
}

// The live region stays mounted so announcements are reliable; focus is never moved.
export default function Toast({ toast }) {
  return (
    <div className="toast-region" role="status" aria-live="polite">
      {toast && (
        <div className="toast" key={toast.key}>
          <Icon name="check" size={18} />
          <span>{toast.message}</span>
        </div>
      )}
    </div>
  );
}
