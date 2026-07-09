// GitHub Gist sync — pull-merge-push on every write, 60s idle poll
// Token stays in localStorage only — never written to the Gist itself.

import { migrateV1Results } from './utils.js';

const DEFAULT_FILENAME  = 'data-exam-prep-state.json';
const FILENAME_KEY      = 'gist_filename';
const TOKEN_KEY         = 'gist_token';
const GIST_ID_KEY       = 'gist_id';
const LAST_SYNCED_KEY   = 'gist_last_synced';
const LOCAL_UPDATED_KEY = 'gist_local_updated';

const TOMBSTONE_TTL_MS  = 30 * 24 * 60 * 60 * 1000; // 30 days

// ── Getters / setters ─────────────────────────────────────────────────────────

export function getFilename()  { return localStorage.getItem(FILENAME_KEY)  || DEFAULT_FILENAME; }
export function getToken()     { return localStorage.getItem(TOKEN_KEY)      || ''; }
export function getGistId()    { return localStorage.getItem(GIST_ID_KEY)   || ''; }
export function isConfigured() { return !!getToken(); }
export function getLastSynced() {
  const v = localStorage.getItem(LAST_SYNCED_KEY);
  return v ? parseInt(v, 10) : null;
}

export function saveToken(token)   { localStorage.setItem(TOKEN_KEY, token.trim()); }

export function saveFilename(name) {
  const next = name?.trim() || DEFAULT_FILENAME;
  if (next !== getFilename()) {
    // Filename changed → cached gist ID is for the old file; invalidate it.
    localStorage.removeItem(GIST_ID_KEY);
  }
  if (next === DEFAULT_FILENAME) localStorage.removeItem(FILENAME_KEY);
  else localStorage.setItem(FILENAME_KEY, next);
}

export function touchLocalUpdated() {
  localStorage.setItem(LOCAL_UPDATED_KEY, new Date().toISOString());
}

export function clearConfig() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(GIST_ID_KEY);
  localStorage.removeItem(LAST_SYNCED_KEY);
  localStorage.removeItem(FILENAME_KEY);
  localStorage.removeItem(LOCAL_UPDATED_KEY);
  stopIdlePoll();
}

// Write a tombstone for a deleted result so mergeState() won't restore it from Gist.
// The tombstone stays in localStorage under the same key as the result, with _deleted: true
// and a deletedAt timestamp. Any subsequent result saved for the same key will overwrite
// the tombstone naturally (completedAt > deletedAt → result wins in merge).
export function markResultDeleted(resultKey) {
  localStorage.setItem(resultKey, JSON.stringify({ _deleted: true, deletedAt: new Date().toISOString() }));
  localStorage.removeItem(resultKey.replace(/^result_/, 'result_questions_'));
}

// ── Internal helpers ──────────────────────────────────────────────────────────

function authHeaders() {
  return {
    Authorization: `Bearer ${getToken()}`,
    'Content-Type': 'application/json',
    Accept: 'application/vnd.github.v3+json'
  };
}

// Resolve gist ID: local cache → search up to 3 pages of user's gists by filename.
async function resolveGistId() {
  const cached = localStorage.getItem(GIST_ID_KEY);
  if (cached) return cached;

  const filename = getFilename();
  try {
    for (let page = 1; page <= 3; page++) {
      const res = await fetch(
        `https://api.github.com/gists?per_page=100&page=${page}`,
        { headers: authHeaders() }
      );
      if (!res.ok) break;
      const gists = await res.json();
      if (!gists.length) break;
      const found = gists.find(g => g.files?.[filename]);
      if (found) { localStorage.setItem(GIST_ID_KEY, found.id); return found.id; }
      if (gists.length < 100) break;
    }
  } catch {}
  return null;
}

// ── State collection ──────────────────────────────────────────────────────────

function collectState() {
  const state = {};
  const now = Date.now();

  for (const key of Object.keys(localStorage)) {
    if (key === 'quicktest_history') {
      try { state[key] = JSON.parse(localStorage.getItem(key)); } catch {}
      continue;
    }
    if (key.startsWith('result_questions_quicktest::')) {
      try { state[key] = JSON.parse(localStorage.getItem(key)); } catch {}
      continue;
    }
    if (key.startsWith('result_questions_')) continue; // re-derivable from exam JSON

    if (key.startsWith('result_quicktest::')) {
      try { state[key] = JSON.parse(localStorage.getItem(key)); } catch {}
    } else if (key.startsWith('result_')) {
      try {
        const full = JSON.parse(localStorage.getItem(key));
        if (full._deleted) {
          // Tombstone: propagate to Gist so other devices honour the deletion.
          // Prune tombstones older than 30 days — they've had time to propagate.
          const age = now - new Date(full.deletedAt || 0).getTime();
          if (age >= TOMBSTONE_TTL_MS) {
            localStorage.removeItem(key); // clean up stale tombstone
          } else {
            state[key] = { _deleted: true, deletedAt: full.deletedAt };
          }
        } else {
          state[key] = {
            certId:      full.certId,
            examId:      full.examId,
            completedAt: full.completedAt,
            percentage:  full.percentage,
            passed:      full.passed,
            correct:     full.correct,
            total:       full.total,
            timeTaken:   full.timeTaken,
            answers:     full.answers
          };
        }
      } catch {}
    } else if (key.startsWith('session_')) {
      try { state[key] = JSON.parse(localStorage.getItem(key)); } catch {}
    }
  }
  return state;
}

// ── Merge: gist → localStorage ────────────────────────────────────────────────
// Returns true if any local key was updated.

function mergeState(gistState) {
  if (!gistState || typeof gistState !== 'object') return false;
  let changed = false;
  const imported = new Set();
  const now = Date.now();

  // result_ keys: last-write wins using whichever timestamp is newer —
  // completedAt for real results, deletedAt for tombstones.
  // A newer tombstone beats an older result (deletion wins).
  // A newer result beats an older tombstone (re-take wins).
  for (const [key, gistVal] of Object.entries(gistState)) {
    if (!key.startsWith('result_') || key.startsWith('result_questions_')) continue;

    // Skip stale tombstones from Gist — no need to import a deletion that old
    if (gistVal._deleted) {
      const age = now - new Date(gistVal.deletedAt || 0).getTime();
      if (age >= TOMBSTONE_TTL_MS) continue;
    }

    const gistTs = gistVal._deleted
      ? new Date(gistVal.deletedAt  || 0).getTime()
      : new Date(gistVal.completedAt || 0).getTime();

    const localRaw = localStorage.getItem(key);
    if (!localRaw) {
      // Nothing local — import whatever the Gist has (result or tombstone)
      localStorage.setItem(key, JSON.stringify(gistVal));
      if (!gistVal._deleted) imported.add(key);
      changed = true;
    } else {
      try {
        const local = JSON.parse(localRaw);
        const localTs = local._deleted
          ? new Date(local.deletedAt  || 0).getTime()
          : new Date(local.completedAt || 0).getTime();
        if (gistTs > localTs) {
          localStorage.setItem(key, JSON.stringify(gistVal));
          if (!gistVal._deleted) imported.add(key);
          changed = true;
        }
      } catch {}
    }
  }

  // For each result imported from gist, also bring in its questions snapshot
  for (const resultKey of imported) {
    const qKey = `result_questions_${resultKey.slice('result_'.length)}`;
    const gistQ = gistState[qKey];
    if (gistQ !== undefined) localStorage.setItem(qKey, JSON.stringify(gistQ));
  }

  // session_ keys: never overwrite — in-progress work on THIS device wins

  // quicktest_history: union by id, keep newest per id, cap 50
  const gistQtHistory = gistState['quicktest_history'];
  if (Array.isArray(gistQtHistory) && gistQtHistory.length) {
    let local = [];
    try { local = JSON.parse(localStorage.getItem('quicktest_history') || '[]'); } catch {}
    const byId = new Map();
    for (const item of [...local, ...gistQtHistory]) {
      const ex = byId.get(item.id);
      if (!ex || new Date(item.date) > new Date(ex.date)) byId.set(item.id, item);
    }
    const merged = [...byId.values()].sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 50);
    const same = JSON.stringify(local.map(i => i.id).sort()) === JSON.stringify(merged.map(i => i.id).sort());
    if (!same) { localStorage.setItem('quicktest_history', JSON.stringify(merged)); changed = true; }
  }

  return changed;
}

// ── Core API ──────────────────────────────────────────────────────────────────

// Pull gist → merge into localStorage.
// Returns { changed: bool, error: string|null }
export async function syncFromGist() {
  if (!isConfigured()) return { changed: false, error: null };

  const gistId = await resolveGistId();
  if (!gistId) return { changed: false, error: null };

  try {
    const res = await fetch(`https://api.github.com/gists/${gistId}`, {
      headers: authHeaders()
    });
    if (res.status === 401) return { changed: false, error: 'invalid_token' };
    if (res.status === 404) {
      localStorage.removeItem(GIST_ID_KEY);
      return { changed: false, error: null };
    }
    if (!res.ok) return { changed: false, error: `http_${res.status}` };

    const gist   = await res.json();
    const raw    = gist.files?.[getFilename()]?.content;
    if (!raw) return { changed: false, error: null };

    const { state } = JSON.parse(raw);
    const changed = mergeState(state);
    if (changed) migrateV1Results();
    return { changed, error: null };
  } catch (e) {
    return { changed: false, error: e.message };
  }
}

// Push merged local state to gist (create if none exists).
// Returns { ok: bool, error: string|null }
export async function pushToGist() {
  if (!isConfigured()) return { ok: false, error: 'no_token' };

  const filename = getFilename();
  const payload  = JSON.stringify({
    version:      1,
    lastUpdated:  new Date().toISOString(),
    localUpdated: localStorage.getItem(LOCAL_UPDATED_KEY) || new Date().toISOString(),
    state:        collectState()
  }, null, 2);

  let gistId = await resolveGistId();

  try {
    let res;

    if (gistId) {
      res = await fetch(`https://api.github.com/gists/${gistId}`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ files: { [filename]: { content: payload } } })
      });
      if (res.status === 404) {
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
          files: { [filename]: { content: payload } }
        })
      });
    }

    if (res.status === 401) return { ok: false, error: 'invalid_token' };
    if (!res.ok)            return { ok: false, error: `http_${res.status}` };

    const gist = await res.json();
    localStorage.setItem(GIST_ID_KEY, gist.id);
    localStorage.setItem(LAST_SYNCED_KEY, Date.now().toString());
    return { ok: true, error: null };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

// Full sync cycle: pull → merge → push → dispatch event if changed.
// This is the canonical operation called on every state write.
// Returns { ok: bool, changed: bool, error: string|null }
export async function syncAndPush() {
  if (!isConfigured()) return { ok: false, changed: false, error: 'no_token' };

  const pull = await syncFromGist();
  if (pull.error === 'invalid_token') return { ok: false, changed: false, error: 'invalid_token' };

  const push = await pushToGist();

  if (pull.changed) {
    window.dispatchEvent(new CustomEvent('gist:synced', { detail: { changed: true } }));
  }

  return { ok: push.ok, changed: pull.changed, error: push.error || pull.error || null };
}

// Force-write an empty state to the gist — bypasses merge.
// Used by "Clear All Results & Sessions".
// Returns { ok: bool, error: string|null }
export async function clearAndPushEmpty() {
  if (!isConfigured()) return { ok: false, error: 'no_token' };

  const filename = getFilename();
  const payload  = JSON.stringify({
    version:      1,
    lastUpdated:  new Date().toISOString(),
    localUpdated: new Date().toISOString(),
    state:        {}
  }, null, 2);

  let gistId = await resolveGistId();

  try {
    let res;

    if (gistId) {
      res = await fetch(`https://api.github.com/gists/${gistId}`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ files: { [filename]: { content: payload } } })
      });
      if (res.status === 404) { localStorage.removeItem(GIST_ID_KEY); gistId = null; }
    }

    if (!gistId) {
      res = await fetch('https://api.github.com/gists', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          description: 'Data Exam Prep — synced progress',
          public: false,
          files: { [filename]: { content: payload } }
        })
      });
    }

    if (res.status === 401) return { ok: false, error: 'invalid_token' };
    if (!res.ok)            return { ok: false, error: `http_${res.status}` };

    const gist = await res.json();
    localStorage.setItem(GIST_ID_KEY, gist.id);
    localStorage.setItem(LAST_SYNCED_KEY, Date.now().toString());
    return { ok: true, error: null };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

// ── Debounced write trigger ───────────────────────────────────────────────────
// Call after any localStorage state write. Marks local state dirty then
// performs a full pull-merge-push cycle after the debounce window.

let _pushTimer = null;
export function schedulePush(delayMs = 2500) {
  touchLocalUpdated();
  clearTimeout(_pushTimer);
  _pushTimer = setTimeout(async () => {
    const result = await syncAndPush();
    if (!result.ok) console.warn('[gist] sync failed:', result.error);
  }, delayMs);
}

// ── Idle polling ──────────────────────────────────────────────────────────────
// Checks for remote changes every 60 s when the app is open but not writing.

let _pollTimer = null;

export function startIdlePoll() {
  stopIdlePoll();
  if (!isConfigured()) return;
  _pollTimer = setInterval(async () => {
    if (!isConfigured()) { stopIdlePoll(); return; }
    try {
      const { changed, error } = await syncFromGist();
      if (error) return;
      if (changed) {
        await pushToGist(); // write merged state back so the gist reflects the union
        window.dispatchEvent(new CustomEvent('gist:synced', { detail: { changed: true } }));
      }
    } catch {}
  }, 60_000);
}

export function stopIdlePoll() {
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
}

// ── Connectivity recovery ─────────────────────────────────────────────────────
if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    if (!isConfigured()) return;
    syncAndPush()
      .then(({ changed }) => {
        if (changed) window.dispatchEvent(new CustomEvent('gist:synced', { detail: { changed: true } }));
      })
      .catch(() => {});
  });
}
