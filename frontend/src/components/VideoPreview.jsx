import { useState } from "react";
import useObjectUrl from "../hooks/useObjectUrl.js";

// Small muted player for an attached video. Shows `fallback` instead when the browser
// cannot play the file (e.g. some 3GP or MOV files), detected by the video's error event.
export default function VideoPreview({ file, className, label, fallback = null }) {
  const url = useObjectUrl(file);
  const [failedFile, setFailedFile] = useState(null);

  if (!url || failedFile === file) return fallback;
  return (
    <video
      className={className}
      src={url}
      controls
      muted
      playsInline
      preload="metadata"
      aria-label={label}
      onError={() => setFailedFile(file)}
    />
  );
}
