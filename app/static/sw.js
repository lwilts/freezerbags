// Minimal service worker: cache the static shell so the app opens instantly,
// but always go to the network for the page itself so the freezer list is
// never stale. Not a full offline app -- POSTs (add/eat/discard) need a
// connection, same LAN as always.
const CACHE = "freezerbags-shell-v1";
const SHELL = [
  "/static/style.css",
  "/static/app.js",
  "/static/htmx.min.js",
  "/static/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;

  // Static shell: network-first, so a redeploy (new CSS/JS) is picked up on
  // the next load instead of being stuck behind a stale cache-first hit;
  // the cache is only an offline fallback.
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Page/API GETs: network-first, cached shell only as an offline fallback for "/".
  if (url.pathname === "/") {
    event.respondWith(
      fetch(event.request).catch(() => caches.match("/static/style.css").then(() => new Response(
        "<h1>FreezerBags</h1><p>You're offline and can't reach the server on your network.</p>",
        { headers: { "Content-Type": "text/html" } }
      )))
    );
  }
});
