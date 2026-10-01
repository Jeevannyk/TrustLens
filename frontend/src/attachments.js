// What the "file" upload accepts. Keep in sync with backend/app/main.py
// (_EXT_TO_MIME, _VIDEO_EXT_TO_MIME, _DOC_EXT_TO_MIME, MAX_IMAGE_BYTES, MAX_VIDEO_BYTES, MAX_FILE_BYTES).
const MB = 1024 * 1024;
export const MAX_IMAGE_BYTES = 8 * MB;
export const MAX_FILE_BYTES = 10 * MB;
export const MAX_VIDEO_BYTES = 25 * MB;

const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/heic", "image/heif"];
const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif"];
const VIDEO_TYPES = ["video/mp4", "video/quicktime", "video/webm", "video/3gpp"];
const VIDEO_EXTENSIONS = [".mp4", ".m4v", ".mov", ".webm", ".3gp"];
const DOCUMENT_LABELS = { ".pdf": "PDF", ".txt": "Text file", ".md": "Markdown", ".eml": "Email" };
const DOCUMENT_TYPES = {
  "application/pdf": "PDF",
  "text/plain": "Text file",
  "text/markdown": "Markdown",
  "text/x-markdown": "Markdown",
  "message/rfc822": "Email",
};

export const ACCEPT = [
  "image/*",
  ...IMAGE_EXTENSIONS,
  ...VIDEO_TYPES,
  ...VIDEO_EXTENSIONS,
  ...Object.keys(DOCUMENT_LABELS),
  "application/pdf",
  "text/plain",
  "message/rfc822",
].join(",");

export const UNSUPPORTED_MESSAGE =
  "That file type is not supported. Use an image (PNG, JPEG, WebP, HEIC, HEIF), a video (MP4, MOV, WebM, 3GP) or a PDF, TXT, EML or MD file.";

function extensionOf(name) {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot).toLowerCase();
}

// { kind: "image" | "video" | "document", typeLabel } or null when the type is not accepted.
// Like the backend, a missing/generic content type falls back to the file extension.
export function classify(file) {
  let type = (file.type || "").split(";")[0].trim().toLowerCase();
  if (type === "image/jpg") type = "image/jpeg";
  if (type === "video/x-m4v") type = "video/mp4";
  const ext = extensionOf(file.name);
  const generic = type === "" || type === "application/octet-stream";

  if (IMAGE_TYPES.includes(type) || (generic && IMAGE_EXTENSIONS.includes(ext))) {
    return { kind: "image", typeLabel: "Image" };
  }
  if (VIDEO_TYPES.includes(type) || (generic && VIDEO_EXTENSIONS.includes(ext))) {
    return { kind: "video", typeLabel: "Video" };
  }
  if (DOCUMENT_TYPES[type] || (generic && DOCUMENT_LABELS[ext])) {
    return { kind: "document", typeLabel: DOCUMENT_LABELS[ext] || DOCUMENT_TYPES[type] };
  }
  return null;
}

// Returns an error message, or null when the file can be attached.
export function validate(file) {
  const info = classify(file);
  if (!info) return UNSUPPORTED_MESSAGE;
  if (info.kind === "image" && file.size > MAX_IMAGE_BYTES) {
    return `That image is over ${MAX_IMAGE_BYTES / MB} MB. Try a smaller one.`;
  }
  if (info.kind === "video" && file.size > MAX_VIDEO_BYTES) {
    return `That video is over ${MAX_VIDEO_BYTES / MB} MB. Try a shorter clip.`;
  }
  if (info.kind === "document" && file.size > MAX_FILE_BYTES) {
    return `That file is over ${MAX_FILE_BYTES / MB} MB. Try a smaller one.`;
  }
  return null;
}

export function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < MB) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / MB).toFixed(1)} MB`;
}
