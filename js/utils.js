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

export function buildExamKey(certId, examId) {
  if (!examId) return '';
  if (examId.includes('::')) return examId;
  return certId ? `${certId}::${examId}` : examId;
}

export function resultStorageKey(examKey) {
  return `result_${examKey}`;
}

export function resultQuestionsStorageKey(examKey) {
  return `result_questions_${examKey}`;
}

export function sessionStorageKey(examKey) {
  return `session_${examKey}`;
}

export function legacyExamIdFromFile(file) {
  return (file || '').split('/').pop()?.replace(/\.json$/i, '') || '';
}

export function getExamMetadata(file, examData) {
  const meta = examData?.meta || {};
  const legacyId = legacyExamIdFromFile(file);
  return {
    file,
    id: meta.id || legacyId,
    legacyId,
    title: meta.title || legacyId,
    questionCount: examData?.questions?.length ?? meta.totalQuestions ?? 0,
    difficulty: meta.difficulty || 'medium',
    status: meta.status || 'available',
    timeLimit: meta.timeLimit ?? null,
    passingScore: meta.passingScore ?? null,
    certification: meta.certification || ''
  };
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

export async function loadExamMetadata(file) {
  const examData = await loadJSON(file);
  return getExamMetadata(file, examData);
}

export async function hydrateCatalog(catalog) {
  const certifications = await Promise.all(
    (catalog.certifications || []).map(async cert => ({
      ...cert,
      exams: await Promise.all(
        (cert.exams || []).map(async examEntry => {
          const file = typeof examEntry === 'string' ? examEntry : examEntry?.file;
          return loadExamMetadata(file);
        })
      )
    }))
  );

  return { ...catalog, certifications };
}

function migrateStorageRecord(oldKey, newKey, transformValue = value => value) {
  if (!oldKey || !newKey || oldKey === newKey) return;

  try {
    const current = localStorage.getItem(newKey);
    const legacy = localStorage.getItem(oldKey);
    if (current || !legacy) return;

    const parsed = JSON.parse(legacy);
    localStorage.setItem(newKey, JSON.stringify(transformValue(parsed)));
    localStorage.removeItem(oldKey);
  } catch {}
}

export function migrateLegacyExamStorage(certifications) {
  for (const cert of certifications || []) {
    for (const exam of cert.exams || []) {
      const legacyKey = buildExamKey(cert.id, exam.legacyId);
      const examKey = buildExamKey(cert.id, exam.id);
      if (!legacyKey || legacyKey === examKey) continue;

      migrateStorageRecord(resultStorageKey(legacyKey), resultStorageKey(examKey), value => ({
        ...value,
        certId: cert.id,
        examId: exam.id,
        examKey
      }));
      migrateStorageRecord(
        resultQuestionsStorageKey(legacyKey),
        resultQuestionsStorageKey(examKey)
      );
      migrateStorageRecord(sessionStorageKey(legacyKey), sessionStorageKey(examKey));
    }
  }
}

let _afterSaveHook = null;
export function onAfterSave(fn) { _afterSaveHook = fn; }

export function saveState(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
  try { _afterSaveHook?.(); } catch {}
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
