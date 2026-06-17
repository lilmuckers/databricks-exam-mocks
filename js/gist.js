// GitHub Gist sync — persists all exam state to a secret gist
// Gist is discovered by filename across devices — no gist ID needs to be shared

const FILENAME = 'data-exam-prep-state.json';
const TOKEN_KEY = 'gist_token';
const GIST_ID_KEY = 'gist_id';       // local cache only — re-discovered on new devices
const LAST_PUSHED_KEY = 'gist_last_pushed';

// Keys to sync: results and sessions, NOT gist_token/gist_id themselves
const SYNC_PREFIXES = ['result_', 'session_'];

export function getToken() { return localStorage.getItem(TOKEN_KEY) || ''; }
export function getGistId() { return localStorage.getItem(GIST_ID_KEY) || ''; }
export function isConfigured() { return !!getToken(); }
export function getLastPushed() {
  const v = localStorage.getItem(LAST_PUSHED_KEY);
  return v ? parseInt(v, 10) : null;
}

export function saveToken(token) { localStorage.setItem(TOKEN_KEY, token.trim()); }

export function clearConfig() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(GIST_ID_KEY);
  localStorage.removeItem(LAST_PUSHED_KEY);
}

function authHeaders() {
  return {
    Authorization: `Bearer ${getToken()}`,
    'Content-Type': 'application/json',
    Accept: 'application/vnd.github.v3+json'
  };
}

// Resolve gist ID: use local cache, otherwise search the user's gists by filename.
// Searches up to 3 pages (300 gists) to handle large accounts.
async function resolveGistId() {
  const cached = localStorage.getItem(GIST_ID_KEY);
  if (cached) return cached;

  try {
    for (let page = 1; page <= 3; page++) {
      const res = await fetch(
        `https://api.github.com/gists?per_page=100&page=${page}`,
        { headers: authHeaders() }
      );
      if (!res.ok) break;
      const gists = await res.json();
      if (!gists.length) break;
      const found = gists.find(g => g.files && g.files[FILENAME]);
      if (found) {
        localStorage.setItem(GIST_ID_KEY, found.id);
        return found.id;
      }
      if (gists.length < 100) break; // no more pages
    }
  } catch {}
  return null;
}

function collectState() {
  const state = {};
  for (const key of Object.keys(localStorage)) {
    // Full question objects — served from JSON files, never sync to gist
    if (key.startsWith('result_questions_')) continue;

    if (key.startsWith('result_')) {
      try {
        const full = JSON.parse(localStorage.getItem(key));
        // Only sync discrete answer data — drop derived/display fields
        state[key] = {
          certId: full.certId,
          examId: full.examId,
          completedAt: full.completedAt,
          percentage: full.percentage,
          passed: full.passed,
          correct: full.correct,
          total: full.total,
          timeTaken: full.timeTaken,
          answers: full.answers   // { qId: [optionId, ...] }
        };
      } catch {}
    } else if (key.startsWith('session_')) {
      try { state[key] = JSON.parse(localStorage.getItem(key)); } catch {}
    }
  }
  return state;
}

// Smart merge: result keys merged by completedAt; questions follow their result;
// session keys are never overwritten (in-progress work on THIS device wins).
function mergeState(gistState) {
  if (!gistState || typeof gistState !== 'object') return false;
  let changed = false;
  const gistResultsApplied = new Set();

  // 1. Merge result_ keys by completedAt timestamp
  for (const [key, gistVal] of Object.entries(gistState)) {
    if (!key.startsWith('result_') || key.startsWith('result_questions_')) continue;

    const localRaw = localStorage.getItem(key);
    if (!localRaw) {
      localStorage.setItem(key, JSON.stringify(gistVal));
      gistResultsApplied.add(key);
      changed = true;
    } else {
      try {
        const local = JSON.parse(localRaw);
        if ((gistVal.completedAt || 0) > (local.completedAt || 0)) {
          localStorage.setItem(key, JSON.stringify(gistVal));
          gistResultsApplied.add(key);
          changed = true;
        }
      } catch {}
    }
  }

  // 2. For each result imported from gist, also import its questions snapshot
  for (const resultKey of gistResultsApplied) {
    const qKey = `result_questions_${resultKey.slice('result_'.length)}`;
    const gistQ = gistState[qKey];
    if (gistQ !== undefined) {
      localStorage.setItem(qKey, JSON.stringify(gistQ));
    }
  }

  // session_ keys intentionally skipped — never overwrite in-progress work

  return changed;
}

// Pull from gist → merge into localStorage
// Returns { changed: bool, error: string|null }
export async function syncFromGist() {
  const token = getToken();
  if (!token) return { changed: false, error: null };

  const gistId = await resolveGistId();
  if (!gistId) return { changed: false, error: null }; // no gist exists yet, nothing to pull

  try {
    const res = await fetch(`https://api.github.com/gists/${gistId}`, {
      headers: authHeaders()
    });
    if (res.status === 401) return { changed: false, error: 'invalid_token' };
    if (res.status === 404) {
      // Stale cached ID (gist deleted) — clear so next push creates a fresh one
      localStorage.removeItem(GIST_ID_KEY);
      return { changed: false, error: null };
    }
    if (!res.ok) return { changed: false, error: `http_${res.status}` };

    const gist = await res.json();
    const raw = gist.files?.[FILENAME]?.content;
    if (!raw) return { changed: false, error: null };

    const { state } = JSON.parse(raw);
    const changed = mergeState(state);
    return { changed, error: null };
  } catch (e) {
    return { changed: false, error: e.message };
  }
}

// Push full local state → gist (create if none found)
// Returns { ok: bool, error: string|null }
export async function pushToGist() {
  const token = getToken();
  if (!token) return { ok: false, error: 'no_token' };

  const payload = JSON.stringify({
    version: 1,
    lastUpdated: new Date().toISOString(),
    state: collectState()
  }, null, 2);

  let gistId = await resolveGistId();

  try {
    let res;

    if (gistId) {
      res = await fetch(`https://api.github.com/gists/${gistId}`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ files: { [FILENAME]: { content: payload } } })
      });
      if (res.status === 404) {
        // Stale cached ID — clear and fall through to create
        localStorage.removeItem(GIST_ID_KEY);
        gistId = null;
      }
    }

    if (!gistId) {
      res = await fetch('https://api.github.com/gists', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          description: 'Data Exam Prep — synced progress',
          public: false,
          files: { [FILENAME]: { content: payload } }
        })
      });
    }

    if (res.status === 401) return { ok: false, error: 'invalid_token' };
    if (!res.ok) return { ok: false, error: `http_${res.status}` };

    const gist = await res.json();
    localStorage.setItem(GIST_ID_KEY, gist.id); // cache (or re-cache after create)
    localStorage.setItem(LAST_PUSHED_KEY, Date.now().toString());
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

// Debounced push — call after any state write
let _pushTimer = null;
export function schedulePush(delayMs = 2500) {
  clearTimeout(_pushTimer);
  _pushTimer = setTimeout(async () => {
    const result = await pushToGist();
    if (!result.ok) console.warn('[gist] push failed:', result.error);
  }, delayMs);
}

// When connectivity is restored: pull any remote changes then flush pending writes.
// Dispatches 'gist:synced' with { changed: true } if local state was updated.
if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    if (!isConfigured()) return;
    syncFromGist()
      .then(result => {
        if (result.changed) {
          window.dispatchEvent(new CustomEvent('gist:synced', { detail: { changed: true } }));
        }
        schedulePush(0); // flush any writes queued while offline
      })
      .catch(() => {});
  });
}
