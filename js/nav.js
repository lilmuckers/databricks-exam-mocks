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
const ICON_BUG = `<svg class="nav__link-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 2.27A10 10 0 0 1 12 2a10 10 0 0 1 3 .27"/><path d="M9 22a10 10 0 0 1-7-9.5"/><path d="M15 22a10 10 0 0 0 7-9.5"/><path d="M2 12h4"/><path d="M18 12h4"/><path d="M9 7.5V8a3 3 0 0 0 6 0v-.5"/><ellipse cx="12" cy="14" rx="4" ry="5"/><path d="M7.5 10 4 8"/><path d="M16.5 10 20 8"/></svg>`;

const GITHUB_REPO = 'https://github.com/lilmuckers/databricks-exam-mocks';

function currentPageName() {
  const path = window.location.pathname;
  if (path.includes('exam.html')) return 'Exam';
  if (path.includes('review.html')) return 'Review';
  if (path.includes('profile.html')) return 'My Progress';
  if (path.includes('quicktest.html')) return 'Quick Test';
  return 'Home';
}

function buildBugReportUrl() {
  const page = currentPageName();
  const body = [
    `**Page affected:** ${page}`,
    `**URL:** ${window.location.href}`,
    `**Browser:** ${navigator.userAgent}`,
    '',
    '**What functionality is broken?**',
    '<!-- Describe what you were trying to do and what went wrong -->',
    '',
    '',
    '**Steps to reproduce**',
    '1.',
    '2.',
    '3.',
    '',
    '**Expected behaviour**',
    '',
    '',
    '**Actual behaviour**',
    '<!-- Include any error messages or screenshots if possible -->',
    '',
    '',
    `**Device**`,
    `- Type: ${/Mobi|Android/i.test(navigator.userAgent) ? 'Mobile' : 'Desktop'}`,
    `- Installed as PWA: ${window.matchMedia('(display-mode: standalone)').matches ? 'Yes' : 'No'}`,
  ].join('\n');

  const params = new URLSearchParams({ labels: 'bug', title: `Bug on ${page}`, body });
  return `${GITHUB_REPO}/issues/new?${params}`;
}

export function buildExamIssueUrl({ cert = '', exam = '', question = '', context = 'Exam' } = {}) {
  const body = [
    `**Certification:** ${cert}`,
    `**Exam number:** ${exam}`,
    `**Question number:** ${question}`,
    `**Reported from:** ${context}`,
    '',
    '**Type of issue** (check all that apply)',
    '- [ ] The marked correct answer is wrong',
    '- [ ] A wrong answer could also be correct',
    '- [ ] The question is misleading or ambiguous',
    '- [ ] The explanation is incorrect or incomplete',
    '- [ ] The explanation contradicts the marked answer',
    '- [ ] Typo or formatting error',
    '- [ ] Other',
    '',
    '**Describe the problem**',
    '',
    '',
    '**Supporting reference** (optional)',
    '',
  ].join('\n');

  const title = `Question issue: ${cert} ${exam} ${question}`.trim();
  const params = new URLSearchParams({ labels: 'exam-content', title, body });
  return `${GITHUB_REPO}/issues/new?${params}`;
}

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
    <a href="${buildBugReportUrl()}" class="nav__link nav__bug-btn" id="bugReportBtn" title="Report a bug" aria-label="Report a bug" target="_blank" rel="noopener noreferrer">
      ${ICON_BUG}
      <span class="nav__link-text">Report Bug</span>
    </a>
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
