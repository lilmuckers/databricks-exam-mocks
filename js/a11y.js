// Shared accessibility helpers: focus trapping and live-region announcements.

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])'
].join(',');

let _trapEl = null;
let _trapReturn = null;
let _trapHandler = null;

export function trapFocus(dialogEl, returnFocusEl) {
  _trapEl = dialogEl;
  _trapReturn = returnFocusEl || document.activeElement;

  const focusables = () => Array.from(dialogEl.querySelectorAll(FOCUSABLE));
  const first = focusables()[0];
  if (first) first.focus();

  _trapHandler = e => {
    if (e.key !== 'Tab') return;
    const els = focusables();
    if (!els.length) return;
    const firstEl = els[0];
    const lastEl = els[els.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === firstEl) { e.preventDefault(); lastEl.focus(); }
    } else {
      if (document.activeElement === lastEl) { e.preventDefault(); firstEl.focus(); }
    }
  };
  dialogEl.addEventListener('keydown', _trapHandler);
}

export function releaseFocus() {
  if (_trapEl && _trapHandler) {
    _trapEl.removeEventListener('keydown', _trapHandler);
  }
  if (_trapReturn && typeof _trapReturn.focus === 'function') {
    _trapReturn.focus();
  }
  _trapEl = null;
  _trapReturn = null;
  _trapHandler = null;
}

let _liveRegion = null;

export function announce(msg, priority = 'polite') {
  if (!_liveRegion) {
    _liveRegion = document.createElement('div');
    _liveRegion.className = 'sr-only';
    _liveRegion.setAttribute('aria-atomic', 'true');
    document.body.appendChild(_liveRegion);
  }
  _liveRegion.setAttribute('aria-live', priority);
  _liveRegion.textContent = '';
  // Timeout lets screen readers detect the content change as a new announcement.
  setTimeout(() => { _liveRegion.textContent = msg; }, 50);
}
