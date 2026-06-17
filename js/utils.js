// Shared utilities

export function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function processCodeBlocks(text) {
  // Convert triple-backtick code blocks to <pre><code>
  text = text.replace(/```(\w+)?\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code>${escapeHtml(code.trim())}</code></pre>`
  );
  // Convert inline code
  text = text.replace(/`([^`]+)`/g, (_, code) =>
    `<code>${escapeHtml(code)}</code>`
  );
  return text;
}

export function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.json();
}

export function saveState(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
}

export function loadState(key, fallback = null) {
  try {
    const v = localStorage.getItem(key);
    return v ? JSON.parse(v) : fallback;
  } catch { return fallback; }
}

export function clearState(key) {
  try { localStorage.removeItem(key); } catch {}
}

export function scoreColor(pct) {
  if (pct >= 80) return '#22c55e';
  if (pct >= 70) return '#f59e0b';
  return '#ef4444';
}

export function showToast(msg, duration = 2500) {
  let t = document.querySelector('.toast');
  if (!t) {
    t = document.createElement('div');
    t.className = 'toast';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('show'), duration);
}
