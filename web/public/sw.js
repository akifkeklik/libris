// Libris PWA Service Worker — Strict Static-Only Caching
const STATIC_CACHE_NAME = 'libris-static-v1';

// Static assets allowlist — NEVER include personalized or authenticated endpoints
const PRECACHE_ASSETS = [
  '/',
  '/manifest.json',
  '/favicon.ico',
];

// Security guard: paths that must NEVER be cached by service worker
function isPrivateOrDynamicRoute(url) {
  const path = url.pathname;
  return (
    path.startsWith('/api/feedback') ||
    path.startsWith('/api/track') ||
    path.startsWith('/api/preferences') ||
    path.startsWith('/api/onboarding') ||
    path.startsWith('/api/recommend/personalized') ||
    path.startsWith('/api/ai/') ||
    path.startsWith('/favorites') ||
    path.startsWith('/settings')
  );
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== STATIC_CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // 1. Only handle GET requests
  if (request.method !== 'GET') {
    return;
  }

  // 2. Reject private or authenticated routes from SW cache completely
  if (isPrivateOrDynamicRoute(url)) {
    return;
  }

  // 3. For navigation requests: Network first with cached static shell fallback
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(STATIC_CACHE_NAME);
        const cachedHome = await cache.match('/');
        return cachedHome || new Response('Offline - please check your internet connection.', {
          status: 503,
          headers: { 'Content-Type': 'text/plain' },
        });
      })
    );
    return;
  }

  // 4. For static assets (CSS, JS, Fonts, Images): Stale-While-Revalidate
  if (
    url.pathname.startsWith('/_next/static/') ||
    url.pathname.match(/\.(css|js|woff2?|svg|png|jpg|ico)$/)
  ) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        const fetchPromise = fetch(request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseToCache = networkResponse.clone();
            caches.open(STATIC_CACHE_NAME).then((cache) => {
              cache.put(request, responseToCache);
            });
          }
          return networkResponse;
        }).catch(() => cachedResponse);

        return cachedResponse || fetchPromise;
      })
    );
  }
});

// Purge cache when user logs out
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'LOGOUT') {
    caches.keys().then((names) => {
      names.forEach((name) => caches.delete(name));
    });
  }
});

// ── Web Push: daily review reminder (Faz 3) ─────────────────────────────────
// Payload (backend build_reminder_push): { title, body, url, tag }. Count and time only.
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = {};
  }
  const title = data.title || 'Libris';
  event.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || '',
      tag: data.tag || 'libris-review-reminder',
      renotify: false,
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      data: { url: data.url || '/learning?utm_source=reminder&reminder_channel=push' },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || '/learning', self.location.origin);
  // Only ever open our own origin.
  const url = target.origin === self.location.origin ? target.href : self.location.origin + '/learning';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if (new URL(w.url).origin === self.location.origin && 'navigate' in w) {
          return w.navigate(url).then((c) => (c || w).focus());
        }
      }
      return self.clients.openWindow(url);
    })
  );
});

// ── PWA share target (Faz 4): another app shares a clippings/CSV file or a quote ──
// The POST never reaches the server: the file or text is parked in Cache Storage (this origin
// only) and the reader lands on /import, which picks it up once and deletes it.
const SHARE_CACHE = 'libris-share-target';
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'POST' || url.origin !== self.location.origin || url.pathname !== '/import/share') return;
  event.respondWith((async () => {
    try {
      const form = await event.request.formData();
      const cache = await caches.open(SHARE_CACHE);
      const file = form.get('file');
      if (file && typeof file === 'object' && file.size > 0 && file.size <= 4 * 1024 * 1024) {
        await cache.put('/__share/file', new Response(file, { headers: { 'x-file-name': encodeURIComponent(file.name || 'shared.txt') } }));
      } else {
        const text = [form.get('title'), form.get('text'), form.get('url')].filter((v) => typeof v === 'string' && v.trim()).join('\n');
        if (text) await cache.put('/__share/text', new Response(text.slice(0, 5000)));
      }
    } catch (e) {
      // Fall through to the import page without a payload.
    }
    return Response.redirect('/import?shared=1', 303);
  })());
});
