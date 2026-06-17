// Service Worker — offline-first exam caching
// Bump CACHE_VERSION on each deploy to invalidate old caches

const CACHE_VERSION = 'v4';
const CACHE = `exam-prep-${CACHE_VERSION}`;

// App shell — always cached on install
const SHELL = [
  '/',
  '/index.html',
  '/exam.html',
  '/review.html',
  '/profile.html',
  '/css/styles.css',
  '/js/utils.js',
  '/js/theme.js',
  '/js/gist.js',
  '/js/sw-init.js',
  '/exams/hints.json',
  '/manifest.json',
  '/icons/icon.svg',
  '/icons/icon-maskable.svg',
];

// ── Install: cache shell + all exam files from catalog ──
self.addEventListener('install', event => {
  event.waitUntil(populateCache());
  self.skipWaiting();
});

async function populateCache() {
  const cache = await caches.open(CACHE);

  // Cache shell assets (individually so one failure doesn't abort the rest)
  await Promise.allSettled(
    SHELL.map(async url => {
      try {
        const res = await fetch(url);
        if (res.ok) await cache.put(url, res);
      } catch {}
    })
  );

  await cacheExamsFromCatalog(cache, { onlyMissing: false });
}

// ── Message: CHECK_UPDATES — fetch catalog fresh, cache any new exam files ──
self.addEventListener('message', event => {
  if (event.data?.type === 'CHECK_UPDATES') {
    event.waitUntil(
      caches.open(CACHE).then(cache => cacheExamsFromCatalog(cache, { onlyMissing: true }))
    );
  }
});

// Fetch catalog.json from network, update its cache entry, then cache exam files.
// onlyMissing=true skips files already in cache (fast background check).
// onlyMissing=false caches everything (used during install).
async function cacheExamsFromCatalog(cache, { onlyMissing }) {
  try {
    const catalogRes = await fetch('/exams/catalog.json', { cache: 'no-cache' });
    if (!catalogRes.ok) return;
    await cache.put('/exams/catalog.json', catalogRes.clone());
    const catalog = await catalogRes.json();

    const examPaths = [];
    for (const cert of catalog.certifications || []) {
      for (const entry of cert.exams || []) {
        const file = typeof entry === 'string' ? entry : entry?.file;
        if (file) examPaths.push(file.startsWith('/') ? file : `/${file}`);
      }
    }

    // Cache in batches of 8 to avoid saturating the connection
    for (let i = 0; i < examPaths.length; i += 8) {
      await Promise.allSettled(
        examPaths.slice(i, i + 8).map(async path => {
          try {
            if (onlyMissing && await cache.match(path)) return; // already cached
            const res = await fetch(path);
            if (res.ok) await cache.put(path, res);
          } catch {}
        })
      );
    }
  } catch {}
}

// ── Activate: delete stale caches, take control immediately ──
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch: cache-first for app assets, network-only for GitHub API ──
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // GitHub Gist API — never intercept, must be live
  if (url.hostname === 'api.github.com') {
    event.respondWith(
      fetch(request).catch(() => new Response('', { status: 503 }))
    );
    return;
  }

  // Only handle same-origin requests
  if (url.origin !== self.location.origin) return;

  event.respondWith(handleFetch(request));
});

async function handleFetch(request) {
  const isNav = request.mode === 'navigate';

  // Cache-first: for navigations ignore the query string (cert/exam params)
  // so ?cert=X&exam=Y correctly serves the cached base HTML file
  const cached = await caches.match(request, isNav ? { ignoreSearch: true } : undefined);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE);
      cache.put(request, response.clone()); // cache newly seen assets
    }
    return response;
  } catch {
    // Offline and not in cache — return the index as a fallback for navigations
    if (isNav) {
      const fallback = await caches.match('/index.html');
      if (fallback) return fallback;
    }
    return new Response('Offline', { status: 503, headers: { 'Content-Type': 'text/plain' } });
  }
}
