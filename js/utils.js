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
    certification: meta.certification || '',
    domains: (meta.domains || []).map(d => typeof d === 'string' ? d : d?.id).filter(Boolean)
  };
}

// Full markdown → HTML for stems and explanations.
// Supports: fenced code blocks, inline code, bold, italic, links, ul/ol lists, paragraphs.
// Links must be https?:// and open in a new tab.
export function processMarkdown(text) {
  if (!text) return '';

  const MARK = '\x02';
  const saved = [];
  function save(html) { const i = saved.length; saved.push(html); return `${MARK}${i}${MARK}`; }

  // 1. Extract fenced code blocks (content HTML-escaped during extraction)
  text = text.replace(/```(\w+)?\n?([\s\S]*?)```/g, (_, _lang, code) =>
    save(`<pre><code>${escapeHtml(code.trim())}</code></pre>`)
  );

  // 2. Extract inline code
  text = text.replace(/`([^`\n]+)`/g, (_, code) =>
    save(`<code>${escapeHtml(code)}</code>`)
  );

  // 3. HTML-escape remaining text (MARK chars are \x02, safe from escapeHtml)
  text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // 4. Links — https?:// only, open in new tab with noopener
  text = text.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)\n]+)\)/g, (_, label, url) =>
    save(`<a href="${url.replace(/"/g, '%22')}" target="_blank" rel="noopener noreferrer">${label}</a>`)
  );

  // 5. Insert line breaks before per-option sentences in multi-answer explanations.
  // Bold labels:  ". **B** is" → ".\n**B** is"
  // Plain labels: ". B is correct/incorrect/wrong" → ".\nB is correct/incorrect/wrong"
  text = text.replace(/([.!?])\s+(\*\*[A-D]\*\*\s)/g, '$1\n$2');
  text = text.replace(/([.!?])\s+([A-D]\s+is\s+(?:correct|incorrect|wrong|right)\b)/g, '$1\n$2');

  // 6. Inline emphasis — only **bold** is safe in technical content.
  // Single * and _ are too common in identifiers/code to use for italic.
  text = text.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');

  // 6. Block-level: gather list items, then paragraph-wrap remaining lines
  const lines = text.split('\n');
  const out = [];
  let listType = null, listItems = [];

  function flushList() {
    if (!listItems.length) return;
    out.push(`<${listType}>${listItems.map(t => `<li>${t}</li>`).join('')}</${listType}>`);
    listItems = []; listType = null;
  }

  for (const line of lines) {
    const ulM = line.match(/^[-*]\s+(.+)$/);
    const olM = line.match(/^\d+\.\s+(.+)$/);
    if (ulM) {
      if (listType === 'ol') flushList();
      listType = 'ul'; listItems.push(ulM[1]);
    } else if (olM) {
      if (listType === 'ul') flushList();
      listType = 'ol'; listItems.push(olM[1]);
    } else {
      flushList();
      out.push(line.trim() === '' ? '' : line);
    }
  }
  flushList();

  // 7. Wrap text segments in <p>, leave block elements bare
  const html = out.join('\n')
    .split(/\n{2,}/)
    .map(seg => {
      seg = seg.trim();
      if (!seg) return '';
      if (/^<(?:ul|ol|pre|div|h[1-6])[\s>]/.test(seg)) return seg;
      return `<p>${seg.replace(/\n/g, '<br>')}</p>`;
    })
    .filter(Boolean)
    .join('\n');

  // 8. Restore saved fragments
  return html.replace(new RegExp(`${MARK}(\\d+)${MARK}`, 'g'), (_, i) => saved[+i]);
}

// Inline-only markdown for option text — bold, italic, inline code. No links, no block.
export function processInlineMarkdown(text) {
  if (!text) return '';

  const MARK = '\x02';
  const saved = [];
  function save(html) { const i = saved.length; saved.push(html); return `${MARK}${i}${MARK}`; }

  text = text.replace(/`([^`\n]+)`/g, (_, code) =>
    save(`<code>${escapeHtml(code)}</code>`)
  );
  // Links before HTML escaping so URL isn't mangled
  text = text.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)\n]+)\)/g, (_, label, url) =>
    save(`<a href="${url.replace(/"/g, '%22')}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`)
  );
  text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  // Only **bold** — single * and _ are unsafe in identifiers/code contexts
  text = text.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');
  return text.replace(new RegExp(`${MARK}(\\d+)${MARK}`, 'g'), (_, i) => saved[+i]);
}

// Backward-compat alias
export const processCodeBlocks = processMarkdown;

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
