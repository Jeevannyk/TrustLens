// The browser's secret history key: 32 random bytes as 64 hex characters, kept in localStorage.
// It is sent as the X-Owner header and the server stores only its SHA-256, so it never goes in a URL.
const STORAGE_KEY = "trustlens_owner";
const VALID_KEY = /^[0-9a-f]{64}$/;

// Used when localStorage is unavailable (blocked or private mode): the key lasts for this page load.
let memoryKey = null;

function generateKey() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function getOwnerKey() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && VALID_KEY.test(stored)) return stored;
    memoryKey ??= generateKey();
    localStorage.setItem(STORAGE_KEY, memoryKey);
    return memoryKey;
  } catch {
    memoryKey ??= generateKey();
    return memoryKey;
  }
}
