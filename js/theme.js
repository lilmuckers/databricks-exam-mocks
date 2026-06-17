// Theme management — dark / light / system
// Call initTheme() on page load, applyThemeToggle(buttonEl) to wire a button.

export function getEffectiveTheme() {
  const saved = localStorage.getItem('theme');
  if (saved === 'dark' || saved === 'light') return saved;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  updateToggleIcon(theme);
}

export function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || getEffectiveTheme();
  setTheme(current === 'dark' ? 'light' : 'dark');
}

export function initTheme() {
  const theme = getEffectiveTheme();
  document.documentElement.setAttribute('data-theme', theme);
  // Update icon once DOM is ready
  requestAnimationFrame(() => updateToggleIcon(theme));
}

export function updateToggleIcon(theme) {
  document.querySelectorAll('.theme-toggle').forEach(btn => {
    btn.textContent = theme === 'dark' ? '☀️' : '🌙';
    btn.title = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
  });
}
