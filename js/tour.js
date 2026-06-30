// Guided tour + explain mode.
// Two ways to learn the app, both driven by the same spotlight/popover renderer:
//   - Guided tour: sequential, scripted steps (TOUR_STEPS), can span multiple pages.
//   - Explain mode: ad-hoc — hover/tap any [data-help] element to see what it does.
// State:
//   localStorage.tour_offer_decision  'accepted' | 'declined' — first-load auto-offer, set once
//   sessionStorage.tour_active        {stepIndex, fromOffer}  — current tour position, survives navigation
//   localStorage.help_mode            'on' | absent           — explain mode, persists across pages

const TOUR_STEPS = [
  {
    page: 'index.html',
    selector: '#searchInput',
    title: 'Search',
    body: 'Find a certification by name, code, or platform.'
  },
  {
    page: 'index.html',
    selector: '.pf-btn[data-platform="all"]',
    title: 'Platform filters',
    body: 'Narrow the list down to one vendor — Databricks, Snowflake, AWS, and more.'
  },
  {
    page: 'index.html',
    selector: '.cert-card .qt-shortcut-btn',
    title: '5-minute shortcut',
    body: 'Jump straight into a quick 5-minute test for just this certification — no setup needed.'
  },
  {
    page: 'index.html',
    selector: '.cert-card .btn--primary',
    title: 'Start a full exam',
    body: 'Begin a complete, timed mock exam that mirrors the real certification format.'
  },
  {
    page: 'index.html',
    selector: '#qtNavBtn',
    title: 'Quick Test',
    body: 'Build a custom quiz — pick platforms, certifications, subjects, and a time limit.'
  },
  {
    page: 'index.html',
    selector: 'a[href="profile.html"]',
    title: 'My Progress',
    body: "Let's see where your results and sync settings live →"
  },
  {
    page: 'profile.html',
    selector: '#statCards',
    title: 'Your stats',
    body: 'Attempts, pass rate, best and average scores — all tracked automatically as you go.'
  },
  {
    page: 'profile.html',
    selector: '#syncSection',
    title: 'Sync across devices',
    body: "Connect a GitHub token here to keep your progress in sync between your phone and laptop. That's the tour — happy studying!"
  },
];

const MARK = 'data-help';

// ── DOM scaffolding (lazily created once per page) ──────────────────────────────

let overlayEl, holeEl, popoverEl;

function ensureOverlay() {
  if (overlayEl) return;
  overlayEl = document.createElement('div');
  overlayEl.id = 'tourOverlay';
  holeEl = document.createElement('div');
  holeEl.id = 'tourHole';
  popoverEl = document.createElement('div');
  popoverEl.id = 'tourPopover';
  popoverEl.setAttribute('role', 'dialog');
  popoverEl.setAttribute('aria-live', 'polite');
  document.body.append(overlayEl, holeEl, popoverEl);
}

function positionPopover(targetRect) {
  popoverEl.style.left = '0px';
  popoverEl.style.top = '0px';
  const pw = popoverEl.offsetWidth, ph = popoverEl.offsetHeight;
  const vw = window.innerWidth, vh = window.innerHeight;
  let top = targetRect.bottom + 14;
  if (top + ph > vh - 12) top = targetRect.top - ph - 14;
  if (top < 12) top = Math.max(12, (vh - ph) / 2);
  let left = targetRect.left;
  if (left + pw > vw - 12) left = vw - pw - 12;
  if (left < 12) left = 12;
  popoverEl.style.top = `${top}px`;
  popoverEl.style.left = `${left}px`;
}

// Content + display are set synchronously so callers can wire button listeners
// immediately after this call returns. Only position/size (which needs layout
// after scroll-into-view settles) is deferred to the next frames.
function renderSpotlight(target, html, { dim = true, small = false } = {}) {
  ensureOverlay();
  target.scrollIntoView({ block: 'center', behavior: 'smooth' });

  popoverEl.innerHTML = html;
  popoverEl.className = small ? 'tour-popover tour-popover--small' : 'tour-popover';
  popoverEl.style.display = 'block';
  popoverEl.style.visibility = 'hidden'; // hide until positioned, to avoid a flash at the wrong spot
  overlayEl.style.display = dim ? 'block' : 'none';
  holeEl.style.display = dim ? 'block' : 'none';

  requestAnimationFrame(() => requestAnimationFrame(() => {
    const r = target.getBoundingClientRect();
    holeEl.style.left = `${r.left - 6}px`;
    holeEl.style.top = `${r.top - 6}px`;
    holeEl.style.width = `${r.width + 12}px`;
    holeEl.style.height = `${r.height + 12}px`;
    positionPopover(r);
    popoverEl.style.visibility = 'visible';
  }));
}

function clearSpotlight() {
  if (overlayEl) overlayEl.style.display = 'none';
  if (holeEl) holeEl.style.display = 'none';
  if (popoverEl) popoverEl.style.display = 'none';
}

function waitForElement(selector, timeout = 4000) {
  return new Promise(resolve => {
    const existing = document.querySelector(selector);
    if (existing) return resolve(existing);
    const obs = new MutationObserver(() => {
      const el = document.querySelector(selector);
      if (el) { obs.disconnect(); resolve(el); }
    });
    obs.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => { obs.disconnect(); resolve(document.querySelector(selector)); }, timeout);
  });
}

function matchesPage(page) {
  const path = window.location.pathname;
  if (page === 'index.html') return path === '/' || path.endsWith('/') || path.endsWith('index.html');
  return path.endsWith(page);
}

// ── Tour state ───────────────────────────────────────────────────────────────

function getTourState() {
  try { return JSON.parse(sessionStorage.getItem('tour_active') || 'null'); } catch { return null; }
}
function setTourState(stepIndex, fromOffer) {
  sessionStorage.setItem('tour_active', JSON.stringify({ stepIndex, fromOffer: !!fromOffer }));
}

function tourPopoverHtml(step, idx) {
  return `
    <div class="tour-pop__title">${step.title}</div>
    <div class="tour-pop__body">${step.body}</div>
    <div class="tour-pop__footer">
      <span class="tour-pop__count">${idx + 1} of ${TOUR_STEPS.length}</span>
      <div class="tour-pop__actions">
        <button class="btn btn--ghost btn--sm" id="tourSkip">Skip</button>
        ${idx > 0 ? `<button class="btn btn--ghost btn--sm" id="tourBack">Back</button>` : ''}
        <button class="btn btn--primary btn--sm" id="tourNext">${idx === TOUR_STEPS.length - 1 ? 'Done' : 'Next →'}</button>
      </div>
    </div>
  `;
}

async function showTourStep(idx) {
  const step = TOUR_STEPS[idx];
  if (!step) return endTour('completed');
  const el = await waitForElement(step.selector);
  if (!el) { gotoStep(idx + 1); return; } // target missing on this page state — skip ahead
  const state = getTourState();
  setTourState(idx, state?.fromOffer);
  renderSpotlight(el, tourPopoverHtml(step, idx));

  document.getElementById('tourSkip')?.addEventListener('click', () => endTour('skipped'));
  document.getElementById('tourBack')?.addEventListener('click', () => gotoStep(idx - 1));
  document.getElementById('tourNext')?.addEventListener('click', () => {
    if (idx === TOUR_STEPS.length - 1) return endTour('completed');
    gotoStep(idx + 1);
  });
}

function gotoStep(idx) {
  const step = TOUR_STEPS[idx];
  if (!step) return endTour('completed');
  const state = getTourState();
  if (!matchesPage(step.page)) {
    setTourState(idx, state?.fromOffer);
    window.location.href = step.page;
    return;
  }
  showTourStep(idx);
}

function endTour(reason) {
  const state = getTourState();
  sessionStorage.removeItem('tour_active');
  clearSpotlight();
  if (state?.fromOffer && (reason === 'completed' || reason === 'skipped')) {
    localStorage.setItem('tour_offer_decision', reason === 'completed' ? 'accepted' : 'declined');
  }
}

export function startTour({ fromOffer = false } = {}) {
  disableExplainMode();
  setTourState(0, fromOffer);
  if (!matchesPage(TOUR_STEPS[0].page)) {
    window.location.href = TOUR_STEPS[0].page;
  } else {
    showTourStep(0);
  }
}

// Call on every page load (after nav renders) to continue a tour started on another page.
export function resumeTourIfActive() {
  const state = getTourState();
  if (!state) return;
  const step = TOUR_STEPS[state.stepIndex];
  if (!step || !matchesPage(step.page)) return; // not this page's turn yet
  showTourStep(state.stepIndex);
}

// ── First-load auto-offer ──────────────────────────────────────────────────────

function offerPopoverHtml() {
  return `
    <div class="tour-pop__title">New here?</div>
    <div class="tour-pop__body">Take a 60-second tour of how this all works.</div>
    <div class="tour-pop__footer">
      <div class="tour-pop__actions">
        <button class="btn btn--ghost btn--sm" id="offerNo">No thanks</button>
        <button class="btn btn--primary btn--sm" id="offerYes">Take the tour</button>
      </div>
    </div>
  `;
}

// Call once on index.html, after the catalog has rendered (so the first tour target exists).
export function maybeOfferTour() {
  if (localStorage.getItem('tour_offer_decision')) return;
  if (getTourState()) return;
  const btn = document.getElementById('helpNavBtn');
  if (!btn) return;
  renderSpotlight(btn, offerPopoverHtml(), { dim: false });

  document.getElementById('offerNo')?.addEventListener('click', () => {
    localStorage.setItem('tour_offer_decision', 'declined');
    clearSpotlight();
  });
  document.getElementById('offerYes')?.addEventListener('click', () => {
    clearSpotlight();
    startTour({ fromOffer: true });
  });
}

// ── Explain mode ───────────────────────────────────────────────────────────────

function explainModeOn() { return localStorage.getItem('help_mode') === 'on'; }

function updateHelpBtnState() {
  const btn = document.getElementById('helpNavBtn');
  if (btn) btn.classList.toggle('nav__link--active', explainModeOn());
}

export function enableExplainMode() {
  localStorage.setItem('help_mode', 'on');
  document.body.classList.add('help-mode');
  updateHelpBtnState();
}

export function disableExplainMode() {
  localStorage.removeItem('help_mode');
  document.body.classList.remove('help-mode');
  updateHelpBtnState();
  clearSpotlight();
}

function showExplainPopover(target) {
  const text = target.getAttribute(MARK);
  if (!text) return;
  renderSpotlight(target, `<div class="tour-pop__body">${text}</div>`, { dim: false, small: true });
}

let explainListenersWired = false;
function wireExplainListeners() {
  if (explainListenersWired) return;
  explainListenersWired = true;

  // Intercept clicks on tagged elements while explain mode is on, so tapping
  // "Start Exam" to learn what it does doesn't actually start an exam.
  document.addEventListener('click', e => {
    if (!explainModeOn()) return;
    const target = e.target.closest(`[${MARK}]`);
    if (!target) { clearSpotlight(); return; }
    e.preventDefault();
    e.stopPropagation();
    showExplainPopover(target);
  }, true);

  document.addEventListener('mouseover', e => {
    if (!explainModeOn()) return;
    const target = e.target.closest(`[${MARK}]`);
    if (target) showExplainPopover(target);
  });
  document.addEventListener('focusin', e => {
    if (!explainModeOn()) return;
    const target = e.target.closest(`[${MARK}]`);
    if (target) showExplainPopover(target);
  });
}

// ── Help menu (the `?` nav button) ─────────────────────────────────────────────

function chooserHtml() {
  return `
    <div class="tour-pop__title">How can we help?</div>
    <div class="tour-pop__footer">
      <div class="tour-pop__actions tour-pop__actions--stack">
        <button class="btn btn--primary btn--sm" id="chooserTour">🧭 Guided tour</button>
        <button class="btn btn--ghost btn--sm" id="chooserExplain">💡 Explain mode — hover anything</button>
      </div>
    </div>
  `;
}

function explainActiveHtml() {
  return `
    <div class="tour-pop__title">Explain mode is on</div>
    <div class="tour-pop__body">Hover or tap anything to see what it does.</div>
    <div class="tour-pop__footer">
      <div class="tour-pop__actions">
        <button class="btn btn--primary btn--sm" id="explainExit">Exit explain mode</button>
      </div>
    </div>
  `;
}

export function openHelpChooser() {
  const btn = document.getElementById('helpNavBtn');
  if (!btn) return;

  if (explainModeOn()) {
    renderSpotlight(btn, explainActiveHtml(), { dim: false });
    document.getElementById('explainExit')?.addEventListener('click', disableExplainMode);
    return;
  }

  renderSpotlight(btn, chooserHtml(), { dim: false });
  document.getElementById('chooserTour')?.addEventListener('click', () => {
    clearSpotlight();
    startTour({ fromOffer: false });
  });
  document.getElementById('chooserExplain')?.addEventListener('click', () => {
    clearSpotlight();
    enableExplainMode();
  });
}

// ── Init (call once per page, from nav.js) ─────────────────────────────────────

export function initTour() {
  if (explainModeOn()) document.body.classList.add('help-mode');
  updateHelpBtnState();
  wireExplainListeners();
  resumeTourIfActive();

  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if (getTourState()) endTour('skipped');
    else if (explainModeOn()) disableExplainMode();
    else clearSpotlight();
  });

  window.addEventListener('resize', () => {
    // Re-measure the current tour step's target on resize, if one is showing.
    const state = getTourState();
    if (!state) return;
    const step = TOUR_STEPS[state.stepIndex];
    if (step && matchesPage(step.page)) {
      const el = document.querySelector(step.selector);
      if (el) positionPopover(el.getBoundingClientRect());
    }
  });
}
