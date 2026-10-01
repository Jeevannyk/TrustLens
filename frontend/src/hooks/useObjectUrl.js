import { useEffect, useState } from "react";

// Returns an object URL for `file` (or null). The URL is revoked on cleanup and
// never returned for a file other than the current one.
export default function useObjectUrl(file) {
  const [entry, setEntry] = useState(null);

  useEffect(() => {
    if (!file) {
      setEntry(null);
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setEntry({ file, url });
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return entry && entry.file === file ? entry.url : null;
}
