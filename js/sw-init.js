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
