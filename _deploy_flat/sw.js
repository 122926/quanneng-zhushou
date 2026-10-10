/* 全能助手 PWA Service Worker：缓存应用壳，离线也能打开；API 请求不缓存。 */
var CACHE = "qnz-v1";
var CORE = [
  "/",
  "/index.html",
  "/manifest.webmanifest"
];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return c.addAll(CORE).catch(function () { /* 单个失败不阻塞安装 */ });
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (e) {
  var url = new URL(e.request.url);
  // API 与云服务请求一律走网络
  if (url.pathname.indexOf("/api/") === 0 || url.origin !== location.origin) return;
  // 壳资源：缓存优先，回源并更新
  e.respondWith(
    caches.match(e.request).then(function (hit) {
      var fetchP = fetch(e.request).then(function (res) {
        if (res && res.ok && res.type === "basic") {
          var copy = res.clone();
          caches.open(CACHE).then(function (c) { c.put(e.request, copy); });
        }
        return res;
      }).catch(function () { return hit; });
      return hit || fetchP;
    })
  );
});
