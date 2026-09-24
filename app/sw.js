// Service worker de Ventas IX: guarda la cascara de la app para que abra sin senal.
// Los datos (../ventas-macro.enc) NUNCA pasan por aqui: la pagina los pide con
// cache:"no-store" y guarda su propia copia descifrada en localStorage.
var CACHE = "ventas-ix-v3";
var SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];
self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (ks) {
    return Promise.all(ks.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
self.addEventListener("fetch", function (e) {
  var url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  var shell = SHELL.some(function (p) { return url.pathname === new URL(p, self.registration.scope).pathname; });
  if (!shell) return;                       // .enc y crypt.json van directo a la red
  // red primero (para tomar versiones nuevas), cache si no hay senal
  e.respondWith(fetch(e.request).then(function (r) {
    var copy = r.clone(); caches.open(CACHE).then(function (c) { c.put(e.request, copy); }); return r;
  }).catch(function () { return caches.match(e.request); }));
});
