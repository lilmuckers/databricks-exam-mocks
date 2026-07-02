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
| `EXAM_GENERATION_GUIDE.md` | Authoritative style guide for exam content |
| `scripts/validate.py` | Structural/schema validator |
| `scripts/check_links.py` | Live reference URL liveness checker |
| `scripts/check_semantic_quality.py` | Template and boilerplate detector |
| `scripts/check_reference_relevance.py` | Embedding-based reference content relevance checker |
| `automation/prompts/generate-exams.md` | Agent runbook for scheduled exam generation |
| `automation/prompts/audit-exams.md` | Agent runbook for scheduled exam auditing |

Deployments are automatic: push to `main` → GitHub Actions → GitHub Pages.

---

## Content quality

Every question has:
- A scenario-based stem describing a realistic problem a practitioner could encounter
- Four plausible options — wrong answers are wrong for specific, different technical reasons
- Per-option explanations stating exactly why each choice is right or wrong
- A markdown link to official documentation that directly supports the correct answer

### Validators

All four validators must pass before any exam content is merged. Run them in order:

```bash
# 1. Structural validation — schema, field presence, forbidden options, format rules
python3 scripts/validate.py --exam exams/<cert-id>/exam-NN.json

# 2. Live link check — every reference URL must resolve to a real page
python3 scripts/check_links.py --exam exams/<cert-id>/exam-NN.json \
  --check-links --fields reference --no-cache --only-bad

# 3. Semantic quality — detects template generation, boilerplate, recycled content
python3 scripts/check_semantic_quality.py --exam exams/<cert-id>/exam-NN.json

# 4. Reference relevance — embedding similarity between question and reference page content
#    Requires: pip install sentence-transformers requests beautifulsoup4 numpy
#    First run downloads the embedding model (~90 MB, cached after that)
python3 scripts/check_reference_relevance.py --exam exams/<cert-id>/exam-NN.json --strict
```

**validate.py** enforces: correct answer distribution, forbidden option phrases, per-option explanation format, reference field as a markdown link, difficulty distribution.

**check_semantic_quality.py** enforces: no placeholder stems, no meta-filler multi-select options, no boilerplate wrong-option explanations, no recycled option text, no near-duplicate stems, no industry-rotation duplicates, no gameable answer distribution, no overused reference URLs. All thresholds are named constants at the top of the file.

**check_reference_relevance.py** embeds each question's stem + correct answer + explanation and compares it against chunked content of the reference page using cosine similarity. Flags questions where the reference page does not appear to discuss the concept tested. Use `--warn-only --glob "exams/**/*.json"` to calibrate thresholds across the full corpus.

---

## Automation

Exam generation and auditing is handled by a scheduled agent (OpenClaw/GPT-5.5) running against runbooks in `automation/prompts/`. The runbooks are read from the cloned repo at runtime — the on-disk version is always authoritative.

| Runbook | What it does |
|---|---|
| `automation/prompts/generate-exams.md` | Creates three new mock exams per run, selects certs by coverage gap, builds a per-question authorship ledger, enforces all four validators, opens a PR |
| `automation/prompts/audit-exams.md` | Reviews the three oldest exams by audit timestamp, verifies question count against official cert spec, fixes accuracy/format/reference issues, opens or updates a PR |

Both runbooks include:
- **Escalation rule** — after two rejected review rounds for the same systemic failure, the agent posts a blocker comment and stops rather than continuing to patch
- **Known failure modes** — named, with examples, so the agent can self-identify before generating
- **All four validators mandatory** — no "equivalent" manual check accepted; scripts must exit 0

---

## License

MIT
