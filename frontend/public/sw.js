/* Royal Linen Shipments — minimal service worker.
 *
 * Strategy:
 *   - Pre-cache the app shell + offline fallback on install
 *   - Network-first for navigation requests, fall back to cached shell / offline page
 *   - Stale-while-revalidate for static assets (/assets/*, /icons/*, /manifest)
 *   - NEVER cache /api/* (backend) — always go to network so auth + data stay fresh
 *
 * Bump CACHE_VERSION to force clients to drop the old cache.
 */

const CACHE_VERSION = "v1";
const CACHE_NAME = `royal-linen-${CACHE_VERSION}`;

const APP_SHELL = [
  "/",
  "/offline.html",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k.startsWith("royal-linen-") && k !== CACHE_NAME)
            .map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

function isApiRequest(url) {
  return url.pathname.startsWith("/api/") || url.pathname.startsWith("/auth/");
}

function isStaticAsset(url) {
  return (
    url.pathname.startsWith("/assets/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname === "/manifest.webmanifest" ||
    url.pathname.endsWith(".js") ||
    url.pathname.endsWith(".css") ||
    url.pathname.endsWith(".png") ||
    url.pathname.endsWith(".svg") ||
    url.pathname.endsWith(".woff2")
  );
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Same-origin only — let cross-origin (Google Fonts, Gmail OAuth) go straight to network
  if (url.origin !== self.location.origin) return;

  // Never cache backend / auth — always live network
  if (isApiRequest(url)) return;

  // Navigations (HTML) — network first, fall back to cached shell, then offline.html
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          // Update cached "/" with the latest index.html
          const copy = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put("/", copy));
          return res;
        })
        .catch(() =>
          caches
            .match("/")
            .then((res) => res || caches.match("/offline.html"))
        )
    );
    return;
  }

  // Static assets — stale-while-revalidate
  if (isStaticAsset(url)) {
    event.respondWith(
      caches.match(req).then((cached) => {
        const networkFetch = fetch(req)
          .then((res) => {
            if (res && res.status === 200) {
              const copy = res.clone();
              caches.open(CACHE_NAME).then((c) => c.put(req, copy));
            }
            return res;
          })
          .catch(() => cached);
        return cached || networkFetch;
      })
    );
  }
});

self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
});
