const CACHE = "bosselli-v3";
const ASSETS = [
  "/static/css/app.css",
  "/static/js/app.js",
  "/static/vendor/bootstrap.min.css",
  "/static/vendor/bootstrap.bundle.min.js",
  "/static/vendor/bootstrap-icons.min.css",
  "/static/img/icon-192.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  // Solo cachear estáticos; las páginas siempre van a red
  if (!url.pathname.startsWith("/static/")) return;

  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        if (res && res.ok) {
          const copia = res.clone();
          caches.open(CACHE).then((cache) => cache.put(req, copia)).catch(() => {});
        }
        return res;
      }).catch(() => {
        // Devolver una respuesta vacía válida en lugar de undefined
        return new Response("", { status: 503, statusText: "Service Unavailable" });
      });
    }).catch(() => {
      return new Response("", { status: 503, statusText: "Service Unavailable" });
    })
  );
});