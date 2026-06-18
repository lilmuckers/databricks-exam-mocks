// Shared site navigation component.
// Call initNav({ active }) to inject <nav> at top of body and wire theme toggle.
// active: 'home' | 'profile' | '' (no active state)
// Index-specific extras (progressSummary, refreshBtn) are added by index.html into
// the #navSpacer and before #themeToggle after calling initNav.

import { initTheme, toggleTheme } from './theme.js';

const ICON_QT = `<svg class="nav__link-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`;
const ICON_EXAMS = `<svg class="nav__link-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`;
const ICON_PROFILE = `<svg class="nav__link-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
const ICON_NEWS = `<svg class="nav__link-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`;

export function initNav({ active = '' } = {}) {
  const homeActive = active === 'home' ? ' nav__link--active' : '';
  const profileActive = active === 'profile' ? ' nav__link--active' : '';

  const nav = document.createElement('nav');
  nav.className = 'nav';
  nav.innerHTML = `
    <a href="index.html" class="nav__logo" style="text-decoration:none">
      <div class="nav__logo-icon">DB</div>
      <span class="nav__logo-text">Data Exam Prep</span>
    </a>
    <div class="nav__spacer" id="navSpacer"></div>
    <button class="nav__link" id="qtNavBtn" title="Quick Test" aria-label="Quick Test">
      ${ICON_QT}
      <span class="nav__link-text">Quick Test</span>
    </button>
    <a href="index.html" class="nav__link${homeActive}" title="Exams" aria-label="Exams">
      ${ICON_EXAMS}
      <span class="nav__link-text">Exams</span>
    </a>
    <a href="profile.html" class="nav__link${profileActive}" title="My Progress" aria-label="My Progress">
      ${ICON_PROFILE}
      <span class="nav__link-text">My Progress</span>
    </a>
    <button class="nav__link nav__news-btn" id="newsNavBtn" title="What's New" aria-label="What's New">
      ${ICON_NEWS}
      <span class="nav__link-text">What's New</span>
      <span class="nav__news-badge" style="display:none"></span>
    </button>
    <button class="theme-toggle" id="themeToggle" title="Toggle theme"></button>
  `;

  document.body.prepend(nav);
  initTheme();

  document.getElementById('qtNavBtn').addEventListener('click', () => {
    if (typeof window.openQtModal === 'function') window.openQtModal();
    else window.location.href = 'index.html';
  });

  document.getElementById('newsNavBtn').addEventListener('click', () => {
    if (typeof window.openNewsModal === 'function') window.openNewsModal();
    else window.location.href = 'index.html';
  });

  document.getElementById('themeToggle').addEventListener('click', toggleTheme);

  return nav;
}
