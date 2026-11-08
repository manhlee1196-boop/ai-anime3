/* Service worker: app cài ra màn hình chính vẫn mở được khi mạng chập chờn.
   Không bao giờ cache API/job/file — trạng thái và ảnh phải luôn là dữ liệu thật. */

const CACHE = 'anime3-shell-v9';
const SHELL = [
  './',
  './index.html',
  './styles.css',
  './manifest.webmanifest',
  './js/core.js',
  './js/data.js',
  './js/api.js',
  './js/store.js',
  './js/ui.js',
  './icons/icon-192.png',
  './icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(SHELL))
      .catch(() => undefined)
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

function isApi(url) {
  return url.pathname.includes('/sdapi/') || url.pathname.includes('/internal/')
    || url.pathname.includes('/vi-mobile/api/');
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || isApi(url)) return;

  // Dữ liệu tag: cache trước, mạng sau — mở app là có ngay.
  if (url.pathname.includes('/data/')) {
    event.respondWith(
      caches.match(request).then((hit) => hit || fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => undefined);
        return response;
      })),
    );
    return;
  }

  // Phần còn lại: trả bản cache rồi cập nhật ngầm.
  event.respondWith(
    caches.match(request).then((hit) => {
      const network = fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => undefined);
        return response;
      }).catch(() => hit);
      return hit || network;
    }),
  );
});
