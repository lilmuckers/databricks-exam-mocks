# Data Exam Prep

A free, offline-capable PWA for practising cloud data certification exams. No account required, no ads, no paywalls.

**Live site → [dbx.patrick-mckinley.com](https://dbx.patrick-mckinley.com/)**

---

## What it does

- **Timed, scored mock exams** that mirror real certification formats — question count, time limit, and pass threshold per cert
- **Instant explanations** for every option on every question, with links to official documentation
- **Post-exam review** with correct/incorrect/missed highlighting and per-domain breakdown
- **Quick Test** — random cross-certification questions, good for daily revision
- **My Progress** — tracks every attempt, score history, and pass/fail per exam
- **Gist sync** — optional GitHub Gist sync keeps progress in sync across devices (PAT stays in your browser only)
- **Offline-first** — service worker caches all content after first load; works on a plane
- **Installable PWA** — add to home screen on iOS or Android for a native-app feel
- **Dark mode** — follows system preference, toggleable in the nav bar
- **Report issues** — flag incorrect questions directly from within the exam or review page; pre-populates a GitHub issue with the cert, exam, and question ID

---

## Supported certifications

129 mock exams · 6,504 practice questions across 41 certifications

### Databricks (8 certs · 1,835 questions)

| Certification | Mock Exams | Questions |
|---|---|---|
| Certified Data Engineer Professional | 6 | 359 |
| Certified Data Engineer Associate | 5 | 225 |
| Certified Data Analyst Associate | 6 | 260 |
| Certified Generative AI Engineer Associate | 5 | 220 |
| Certified Machine Learning Professional | 3 | 180 |
| Certified Machine Learning Associate | 4 | 180 |
| Certified Associate Developer for Apache Spark | 5 | 276 |
| Certified Context Engineer Associate | 3 | 135 |

### Snowflake (11 certs · 2,455 questions)

| Certification | Mock Exams | Questions |
|---|---|---|
| SnowPro Core | 5 | 500 |
| SnowPro Advanced: Data Engineer | 7 | 380 |
| SnowPro Advanced: Administrator | 6 | 365 |
| SnowPro Advanced: Architect | 4 | 260 |
| SnowPro Advanced: Data Scientist | 4 | 264 |
| SnowPro Advanced: Data Analyst | 3 | 145 |
| SnowPro Advanced: Security Engineer | 3 | 145 |
| SnowPro Specialty: Snowpark | 4 | 160 |
| SnowPro Specialty: Gen AI | 2 | 80 |
| SnowPro Specialty: Native Apps | 1 | 55 |
| SnowPro Associate: Platform | 2 | 105 |

### Microsoft (7 certs · 570 questions)

| Certification | Mock Exams | Questions |
|---|---|---|
| Power BI Data Analyst Associate (PL-300) | 4 | 160 |
| Fabric Analytics Engineer Associate (DP-600) | 2 | 120 |
| Fabric Data Engineer Associate (DP-700) | 2 | 90 |
| Azure AI Apps and Agents Developer Associate (AI-103) | 3 | 120 |
| Azure MLOps Engineer Associate (AI-300) | 2 | 80 |
| Azure Data Engineer Associate (DP-203) | — | coming soon |
| Azure AI Engineer Associate (AI-102) | — | coming soon |

### AWS (5 certs · 330 questions)

| Certification | Mock Exams | Questions |
|---|---|---|
| Certified Data Engineer – Associate | 2 | 80 |
| Certified Machine Learning Engineer – Associate | 3 | 120 |
| Certified Generative AI Developer – Professional | 3 | 130 |
| Certified AI Practitioner | — | coming soon |
| Certified Machine Learning – Specialty | — | coming soon |

### Google Cloud (3 certs · 360 questions)

| Certification | Mock Exams | Questions |
|---|---|---|
| Professional Data Engineer | 3 | 120 |
| Professional Machine Learning Engineer | 3 | 120 |
| Associate Data Practitioner | 3 | 120 |

### Tableau (2 certs · 305 questions)

| Certification | Mock Exams | Questions |
|---|---|---|
| Tableau Desktop Foundations | 5 | 225 |
| Tableau Certified Data Analyst | 2 | 80 |

### Sigma Computing (2 certs · 315 questions)

| Certification | Mock Exams | Questions |
|---|---|---|
| Sigma Certified Developer | 3 | 135 |
| Sigma Analytics Engineer | 4 | 180 |

### Anthropic (1 cert · 145 questions)

| Certification | Mock Exams | Questions |
|---|---|---|
| Claude Certified Architect – Foundations | 3 | 145 |

### OpenAI (1 cert · 185 questions)

| Certification | Mock Exams | Questions |
|---|---|---|
| OpenAI Certified: AI Foundations | 4 | 185 |

---

## How to use

1. Open [dbx.patrick-mckinley.com](https://dbx.patrick-mckinley.com/)
2. Pick a certification from the home page
3. Start any mock exam — choose timed or untimed mode
4. After submitting, review every question with full per-option explanations
5. Track your scores in **My Progress**

**Installing as a PWA:** in your browser, tap "Add to Home Screen" (iOS) or look for the install prompt in the address bar (Chrome/Android). The app works fully offline after the first load.

**Syncing progress across devices:** go to **My Progress → Sync**, paste a GitHub Personal Access Token with `gist` scope, and connect. Your results are saved to a private Gist and merged on every other device automatically. The token never leaves your browser.

---

## Reporting a problem

Found a wrong answer, a misleading question, or a broken explanation?

- **From within any exam or review page** — click the **⚑ Report** button next to the question. It opens a pre-filled GitHub issue with the cert, exam, and question ID already populated.
- **General bug** — click **Report Bug** in the nav bar. It pre-fills the page, URL, browser, and device info.
- **Directly** — open an issue at [github.com/lilmuckers/databricks-exam-mocks/issues](https://github.com/lilmuckers/databricks-exam-mocks/issues) and pick a template.

---

## Tech

Pure HTML, CSS, and JavaScript — no framework, no build step, no npm.

| File | Role |
|---|---|
| `index.html` | Home page — cert browser, search, platform filters |
| `exam.html` | Exam-taking UI with timer, flagging, keyboard shortcuts |
| `review.html` | Post-exam review with score breakdown and explanations |
| `profile.html` | Progress tracking and Gist sync settings |
| `quicktest.html` | Random cross-cert quick test |
| `sw.js` | Service worker — offline-first caching |
| `exams/catalog.json` | Master registry of all certs and exams |
| `exams/<cert-id>/exam-NN.json` | Individual exam question sets |
| `scripts/validate.py` | Exam JSON validator — run before any PR |
| `EXAM_GENERATION_GUIDE.md` | Style guide for exam content |

Deployments are automatic: push to `main` → GitHub Actions → GitHub Pages.

---

## Content quality

Every question has:
- A scenario-based stem describing a realistic problem
- Four plausible options — wrong answers are wrong for a specific technical reason, not obviously absurd
- Per-option explanations stating exactly why each choice is right or wrong
- A markdown link to the relevant official documentation

The validator (`scripts/validate.py`) enforces:
- Answer distribution — no single option correct >40% of questions per exam
- Forbidden options — "All of the above", "None of the above", "Both A and B" are banned
- Explanation format — per-option paragraphs with bold labels (`**A**`, `**B**`, etc.)
- Reference field — must be a markdown link to live documentation, not a bare URL
- Difficulty distribution — at least 20% hard questions per exam

---

## License

MIT
