# Data Exam Prep — Claude Code Project Context

## What This Is

A pure HTML/CSS/JS PWA for multi-certification exam practice. No build step, no framework, no bundler. Deployed to GitHub Pages via `.github/workflows/deploy.yml`.

Live site served from the repo root. Service worker (`sw.js`) provides offline-first caching.

## Mandatory Behaviours

- **Always commit and push to GitHub after every code change.** No confirmation needed — just stage, commit with a descriptive message, and `git push`.
- **Never persist the GitHub personal access token anywhere other than the user's browser localStorage.** The token is used for Gist sync — it must never be written into any Gist, file, or commit.

## Tech Stack

- Pure HTML + CSS + JS (ES modules via `<script type="module">`)
- No build step, no npm, no bundler
- Service worker (`sw.js`) — cache version string is `CACHE_VERSION = 'vN'`. **Bump this on every deploy** to bust stale caches
- GitHub Pages deployment via `/.github/workflows/deploy.yml`
- `news.json` is generated at deploy time by `scripts/generate_news.py`

## Key Files

| File | Role |
|------|------|
| `index.html` | Home page — cert browser, news modal, quick actions |
| `exam.html` | Exam taking UI |
| `review.html` | Post-exam review with explanations |
| `profile.html` | My Progress — results, sync, filter pills |
| `quicktest.html` | Random cross-cert quick test |
| `js/utils.js` | `processMarkdown`, `processInlineMarkdown`, `showToast`, shared helpers |
| `js/nav.js` | Top nav bar rendered by all pages |
| `js/gist.js` | GitHub Gist sync for cross-device progress |
| `sw.js` | Service worker — cache-first, offline fallback |
| `exams/catalog.json` | Master cert + exam registry |
| `EXAM_GENERATION_GUIDE.md` | Authoritative style guide for exam JSON generation |
| `scripts/generate_news.py` | Generates `news.json` from git history (run at deploy time) |
| `scripts/fix_exams.py` | Bulk formatting fixer for exam JSON files |

## Exam JSON Structure

All exams live at `exams/<cert-id>/exam-NN.json`. Every question:

```json
{
  "id": "q01",
  "domain": "lakehouse-platform",
  "type": "single",
  "difficulty": "medium",
  "stem": "Scenario text.\n\nWhat is the result?",
  "options": [
    { "id": "A", "text": "Option text" },
    { "id": "B", "text": "Option text" }
  ],
  "correct": ["B"],
  "explanation": "**B** is correct because...\n\n**A** is incorrect because...\n\n[Doc Title](https://...)",
  "reference": "[Doc Title](https://docs.example.com/...)"
}
```

Key rules (see `EXAM_GENERATION_GUIDE.md` for full spec):
- Explanation: each option is its own `\n\n`-separated paragraph with bold label (`**A**`)
- Stem: `\n\n` before/after code blocks; use bullet lists for metrics/observations
- Multi-select stems must end with `(Select TWO)` / `(Select THREE)`
- Forbidden options: "All of the above", "None of the above", "Both A and B"
- Every explanation ends with a markdown doc link: `[Title](https://...)`
- `reference` field must also be a markdown link: `[Title](https://...)` — not a bare URL

Validate with: `python3 scripts/validate.py --exam exams/<cert-id>/exam-NN.json`

## Markdown Rendering

`processMarkdown` in `js/utils.js` handles:
- Fenced code blocks, inline code
- `**bold**` only (no italic — single `*`/`_` unsafe in technical content)
- `[label](https://url)` links (new tab, noopener)
- Lists, paragraphs, `<br>` for single newlines
- Auto-inserts `<br>` before `**[A-D]**` and `[A-D] is correct/incorrect/wrong` patterns

`processInlineMarkdown` is for option text (same but no block elements).

## Service Worker Notes

The SW aggressively caches all shell pages. After editing any HTML/CSS/JS:
- Bump `CACHE_VERSION` in `sw.js`
- In the preview browser, clear SW cache: `navigator.serviceWorker.getRegistrations().then(rs=>Promise.all(rs.map(r=>r.unregister()))).then(()=>caches.keys()).then(ks=>Promise.all(ks.map(k=>caches.delete(k)))).then(()=>location.reload(true))`

## GitHub Gist Sync

User's GitHub PAT is stored in `localStorage` under a key. It's used to create/update a secret Gist with exam results. The token **never** leaves the browser — never write it to files, commits, or Gist content.

## Deployment

Push to `main` → GitHub Actions runs `scripts/generate_news.py` → uploads to GitHub Pages. No manual deploy step needed.

## Cert Families

| Family | Cert dirs |
|--------|-----------|
| Databricks | `data-engineer-associate`, `data-engineer-professional`, `data-analyst-associate`, `spark-developer-associate`, `machine-learning-associate`, `machine-learning-professional`, `generative-ai-engineer-associate`, `context-engineer-associate` |
| Snowflake | `snowpro-core`, `snowpro-advanced-*`, `snowpro-associate-platform`, `snowpro-specialty-*` |
| AWS | `aws-data-engineer-associate` |
| GCP | `gcp-professional-data-engineer` |
| Microsoft | `powerbi-data-analyst`, `fabric-analytics-engineer`, `fabric-data-engineer-associate` |
| Sigma | `sigma-certified-developer`, `sigma-analytics-engineer` |
| Tableau | `tableau-desktop-foundations` |
