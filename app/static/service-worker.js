/**
 * Service Worker: Smart Agriculture AI Platform (الخبير الزراعي)
 * Provides offline caching, network-first API routing, and app installation.
 */

const CACHE_NAME = 'smart-agri-cache-v2';
const PRECACHE_ASSETS = [
  '/',
  '/dashboard',
  '/m',
  '/offline-guide',
  '/static/offline_guide.html',
  '/static/logo.png',
  '/static/logo-512.png',
  '/static/favicon.ico',
  '/static/i18n.js',
  '/static/features_modals.js',
  '/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS).catch((err) => {
        console.warn('Pre-cache partial fail:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Network-only for API requests and auth, never serve stale cached API data
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/auth/')) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(
          JSON.stringify({
            status: 'offline',
            error: 'لا يوجد اتصال بالإنترنت حالياً. يُرجى التحقق من الشبكة والمحاولة مجدداً.'
          }),
          {
            status: 503,
            headers: { 'Content-Type': 'application/json; charset=utf-8' }
          }
        );
      })
    );
    return;
  }

  // Stale-while-revalidate for static files & pages
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      }).catch(() => cachedResponse);

      return cachedResponse || fetchPromise;
    })
  );
});
