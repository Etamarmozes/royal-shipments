/**
 * Authenticated file access — view + download with JWT.
 *
 * Why this exists:
 *   The backend protects /documents/{id}/preview, /documents/{id}/download,
 *   /shipments/{id}/product-image, /export/* with JWT (Authorization
 *   header). A plain `<a href="/api/documents/1/download">` makes the
 *   browser navigate to that URL with NO Authorization header, so the
 *   backend correctly returns 401 — and the user sees `נדרש אימות` in the
 *   tab. Same problem for `<img src=...>` and `window.open()`.
 *
 * The fix:
 *   - fetch() the URL with the JWT manually
 *   - convert the response to a Blob
 *   - hand the Blob to the browser via URL.createObjectURL() — that URL is
 *     local (`blob:`) and doesn't go through the network again, so it
 *     trivially "works" in <a>, <img>, window.open, <iframe>.
 *
 * Errors are surfaced to the user with clear Hebrew messages instead of
 * the raw 401/404/500.
 */
import { apiBase } from "../api/client";
import { getToken, clearAuth } from "../auth/store";

const RELOGIN_MSG = "ההתחברות פגה — יש להתחבר מחדש";
const NOT_FOUND_MSG = "הקובץ לא נמצא בשרת";
const NETWORK_MSG = "אין חיבור לשרת. נסה שוב או רענן.";


function joinUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  // apiBase is something like "/api"; path starts with "/"
  return `${apiBase}${path.startsWith("/") ? path : "/" + path}`;
}


/**
 * Fetch a binary resource with the JWT, return a Blob.
 * Throws an Error with a user-readable Hebrew message on failure.
 * On 401, also clears auth + redirects to /login.
 */
export async function fetchAuthedBlob(path: string): Promise<{
  blob: Blob;
  filename: string | null;
  contentType: string;
}> {
  const token = getToken();
  if (!token) {
    redirectToLogin();
    throw new Error(RELOGIN_MSG);
  }
  let res: Response;
  try {
    res = await fetch(joinUrl(path), {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (err) {
    throw new Error(NETWORK_MSG);
  }

  if (res.status === 401) {
    clearAuth();
    redirectToLogin();
    throw new Error(RELOGIN_MSG);
  }
  if (res.status === 403) {
    throw new Error("אין לך הרשאה לפתוח את הקובץ הזה.");
  }
  if (res.status === 404) {
    throw new Error(NOT_FOUND_MSG);
  }
  if (res.status === 422) {
    throw new Error("הקובץ פגום או ריק. נסה להוריד אותו מחדש.");
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.clone().json();
      if (j?.detail) detail = String(j.detail);
    } catch { /* not json */ }
    throw new Error(`שגיאה בקריאת הקובץ: ${detail}`);
  }

  const blob = await res.blob();
  const contentType = res.headers.get("Content-Type") || "application/octet-stream";

  // Pull filename out of Content-Disposition (RFC 6266 — filename* preferred,
  // filename fallback). The backend already sends both.
  let filename: string | null = null;
  const cd = res.headers.get("Content-Disposition");
  if (cd) {
    const star = cd.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
    if (star) {
      try { filename = decodeURIComponent(star[1].trim()); } catch { /* */ }
    }
    if (!filename) {
      const plain = cd.match(/filename\s*=\s*"?([^";]+)"?/i);
      if (plain) filename = plain[1].trim();
    }
  }
  return { blob, filename, contentType };
}


function redirectToLogin() {
  if (typeof window === "undefined") return;
  if (window.location.pathname.startsWith("/login")) return;
  window.location.assign("/login");
}


// ---------------------------------------------------------------
// Public helpers used by components
// ---------------------------------------------------------------

/**
 * Open a document for inline viewing in a new tab (PDF / image).
 * Uses /documents/{id}/preview which sets Content-Disposition: inline.
 */
export async function viewDocument(docId: number): Promise<void> {
  try {
    const { blob } = await fetchAuthedBlob(`/documents/${docId}/preview`);
    openBlobInNewTab(blob);
  } catch (err) {
    alert((err as Error).message);
  }
}


/**
 * Download a document (forces a save dialog).
 * Uses /documents/{id}/download which sets Content-Disposition: attachment.
 */
export async function downloadDocument(docId: number, fallbackName?: string): Promise<void> {
  try {
    const { blob, filename } = await fetchAuthedBlob(`/documents/${docId}/download`);
    triggerDownload(blob, filename || fallbackName || `document_${docId}`);
  } catch (err) {
    alert((err as Error).message);
  }
}


/**
 * Trigger an authenticated GET against any endpoint that returns a file,
 * and download it. Used for /export/excel, etc.
 */
export async function downloadAuthed(path: string, fallbackName: string): Promise<void> {
  try {
    const { blob, filename } = await fetchAuthedBlob(path);
    triggerDownload(blob, filename || fallbackName);
  } catch (err) {
    alert((err as Error).message);
  }
}


/**
 * Open any authenticated GET endpoint as a Blob in a new tab.
 */
export async function viewAuthed(path: string): Promise<void> {
  try {
    const { blob } = await fetchAuthedBlob(path);
    openBlobInNewTab(blob);
  } catch (err) {
    alert((err as Error).message);
  }
}


// ---------------------------------------------------------------
// Internals
// ---------------------------------------------------------------

function openBlobInNewTab(blob: Blob): void {
  const url = URL.createObjectURL(blob);
  // Open immediately. Revoke later — Safari needs the URL alive while the
  // tab loads. 60 seconds is enough for any plausible page load.
  const w = window.open(url, "_blank");
  if (!w) {
    // Popup blocker — fall back to inline navigation
    window.location.assign(url);
  }
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}


function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = sanitizeFilename(filename);
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 5_000);
}


function sanitizeFilename(name: string): string {
  // Replace NBSP and other unicode-whitespace artifacts in the source
  // filename so the browser's "save as" dialog shows something readable.
  return (name || "document").replace(/ /g, " ").trim() || "document";
}
