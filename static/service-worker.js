const CACHE_NAME = "siddhu-weather-v1";

const APP_SHELL = [
    "/",
    "/static/manifest.json",
    "/static/favicon.png",
    "/static/icon-180.png",
    "/static/icon-192.png",
    "/static/icon-512.png"
];

self.addEventListener("install", event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(APP_SHELL))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys
                    .filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            )
        ).then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", event => {
    const request = event.request;

    if (request.method !== "GET") {
        return;
    }

    event.respondWith(
        fetch(request)
            .then(response => {
                const copy = response.clone();

                caches.open(CACHE_NAME).then(cache => {
                    cache.put(request, copy);
                });

                return response;
            })
            .catch(() => caches.match(request))
    );
});
