// Offline/online status announcements for screen readers
(function() {
  let announcer = null;
  function getAnnouncer() {
    if (!announcer) {
      announcer = document.createElement('div');
      announcer.setAttribute('role', 'alert');
      announcer.setAttribute('aria-live', 'assertive');
      announcer.setAttribute('aria-atomic', 'true');
      announcer.className = 'sr-only';
      document.body.appendChild(announcer);
    }
    return announcer;
  }
  window.addEventListener('offline', () => {
    getAnnouncer().textContent = 'You are currently offline. Showing cached content.';
  });
  window.addEventListener('online', () => {
    const el = getAnnouncer();
    el.textContent = 'You are back online.';
    setTimeout(() => { el.textContent = ''; }, 3000);
  });
})();

// Service worker registration + background update trigger
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');

  function swCheckUpdates() {
    navigator.serviceWorker.controller?.postMessage({ type: 'CHECK_UPDATES' });
  }

  function swCheckAndSignal() {
    swCheckUpdates();
    window.dispatchEvent(new CustomEvent('catalogcheck'));
  }

  // On load: update SW cache only (page still initializing, catalog not yet set)
  window.addEventListener('load', swCheckUpdates);
  // Back online: update cache + signal page to re-fetch catalog
  window.addEventListener('online', swCheckAndSignal);

  // Every 5 minutes: update cache + signal page — skip when offline
  setInterval(() => {
    if (navigator.onLine) swCheckAndSignal();
  }, 5 * 60 * 1000);

  // REFRESH_DONE: SW signals all clients to reload after force-refresh
  navigator.serviceWorker.addEventListener('message', event => {
    if (event.data?.type === 'REFRESH_DONE') window.location.reload();
  });
}
