import { getOwnerKey } from "./ownerKey.js";

export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// fetch against the backend with this browser's history key attached.
export function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers);
  headers.set("X-Owner", getOwnerKey());
  return fetch(`${API_URL}${path}`, { ...options, headers });
}
