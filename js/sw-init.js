// Service worker registration + background update trigger
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');

  function swCheckUpdates() {
    // Controller is null on first install — SW already cached everything during install
    navigator.serviceWorker.controller?.postMessage({ type: 'CHECK_UPDATES' });
  }

  // Check for new exam files every time the app opens
  window.addEventListener('load', swCheckUpdates);
  // Re-check whenever connectivity is restored after being offline
  window.addEventListener('online', swCheckUpdates);
}
