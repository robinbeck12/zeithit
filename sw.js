// Cache-Version bei jeder Veröffentlichung erhöhen!
const CACHE = "zeithit-v7";

const APP_FILES = [
  "./",
  "./index.html",
  "./app.js",
  "./style.css",
  "./songs.json",
  "./config.json",
  "./manifest.json",
  "./icons/icon-180.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./fonts/BebasNeue-Regular.woff2",
  "./fonts/Inter-Regular.woff2",
  "./fonts/Inter-Bold.woff2",
  "./vendor/html5-qrcode.min.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(APP_FILES))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Fremde Domains (youtube.com, ytimg.com, ...) nicht abfangen.
  if (req.method !== "GET" || url.origin !== self.location.origin) return;

  // songs.json: Stale-While-Revalidate
  if (url.pathname.endsWith("/songs.json")) {
    event.respondWith(
      caches.open(CACHE).then(async (cache) => {
        const cached = await cache.match(req);
        const network = fetch(req)
          .then((res) => {
            if (res.ok) cache.put(req, res.clone());
            return res;
          })
          .catch(() => cached);
        return cached || network;
      }),
    );
    return;
  }

  // Alle übrigen App-Dateien: Cache-First
  event.respondWith(
    caches.match(req, { ignoreSearch: true }).then((cached) => cached || fetch(req)),
  );
});
