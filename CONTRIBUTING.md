# Contributing — Exam Content

This project is exam content first. The most valuable contributions are new mock exams, corrections to existing questions, and improvements to explanations.

---

## Quick start

```bash
git clone https://github.com/lilmuckers/databricks-exam-mocks.git
cd databricks-exam-mocks

# Validate an exam file
python3 scripts/validate.py --exam exams/data-engineer-associate/exam-01.json

# Validate everything
python3 scripts/validate.py
```

No build step, no npm, no dependencies beyond Python 3.

---

## Types of contribution

### 1. Fix an existing question

If a question has a wrong answer, misleading wording, a broken reference link, or an explanation that's vague or incorrect:

1. Find the file in `exams/<cert-id>/exam-NN.json`
2. Open a PR with just the questions you changed and a clear description of what was wrong and why the fix is correct
3. Link to official documentation that supports the change

Use the [Exam Question Issue](https://github.com/lilmuckers/databricks-exam-mocks/issues/new?template=exam_question_issue.md) template to flag a problem without fixing it yourself.

### 2. Add questions to an existing exam

Add new questions at the end of the `questions` array. Keep IDs sequential — if the last question is `q45`, the next is `q46`. Update `meta.totalQuestions` to match.

### 3. Add a new exam file

See [Adding a new exam](#adding-a-new-exam) below.

### 4. Add a new certification

See [Adding a new certification](#adding-a-new-certification) below.

---

## Adding a new exam

### Step 1 — check the catalog

Confirm the certification already exists in `exams/catalog.json`. If not, see [Adding a new certification](#adding-a-new-certification) first.

### Step 2 — determine the next exam number

```bash
ls exams/<cert-id>/
# exam-01.json  exam-02.json  exam-03.json → next is exam-04.json
```

### Step 3 — create the file

All exam files live at `exams/<cert-id>/exam-NN.json` with zero-padded numbers.

The file must have exactly two top-level keys — `meta` and `questions`. See `EXAM_GENERATION_GUIDE.md` Section 2–3 for the full `meta` schema.

```json
{
  "meta": {
    "id":                "dea-exam-06",
    "certification":     "data-engineer-associate",
    "certificationName": "Databricks Certified Data Engineer Associate",
    "title":             "DBX-DEA-6: Unity Catalog and Data Governance",
    "version":           "1.0",
    "timeLimit":         90,
    "passingScore":      70,
    "totalQuestions":    45,
    "domains": [
      { "id": "data-governance",   "name": "Data Governance",   "weight": 30 },
      { "id": "elt-processing",    "name": "ELT Processing",    "weight": 40 },
      { "id": "lakehouse-platform","name": "Lakehouse Platform", "weight": 30 }
    ],
    "difficulty": "medium",
    "status":     "available"
  },
  "questions": [ ... ]
}
```

### Step 4 — write the questions

Target **45–60 questions**. See [Question quality rules](#question-quality-rules) and `EXAM_GENERATION_GUIDE.md` for the complete spec.

### Step 5 — register the exam in the catalog

Open `exams/catalog.json` and add an entry to the cert's `exams` array:

```json
{
  "id":    "dea-exam-06",
  "file":  "exams/data-engineer-associate/exam-06.json",
  "title": "DBX-DEA-6: Unity Catalog and Data Governance"
}
```

### Step 6 — validate

```bash
python3 scripts/validate.py --exam exams/<cert-id>/exam-NN.json
```

All **errors** must be fixed before opening a PR. **Warnings** should be reviewed and addressed where possible — the most important warnings are about answer distribution and reference URL format.

### Step 7 — open a PR

Describe what certification the exam covers, what domains it focuses on, and how many questions it includes.

---

## Adding a new certification

1. Verify the certification is real and currently active (check the vendor's official website)
2. Open `exams/catalog.json` and add an entry to the `certifications` array — follow the structure of existing entries exactly
3. Confirm the cert's `platform` value matches an entry in the `platforms` array; add a new platform entry if needed
4. Create the directory `exams/<new-cert-id>/`
5. Add any domain IDs used by the new cert to the `domainGroups` section of `catalog.json` if they don't already exist — see `EXAM_GENERATION_GUIDE.md` Section 5.3
6. Run `python3 scripts/validate.py --catalog` to verify the catalog
7. Then follow [Adding a new exam](#adding-a-new-exam) to create the first exam file

---

## Question quality rules

These rules are enforced by the validator or reviewed in PRs:

### Structure
- Questions use IDs `q01`, `q02`, … in sequence — no gaps, no prefixes
- `type` is exactly `"single"` or `"multiple"` — never `"easy"`, `"hard"`, `"multi"`, etc.
- Multi-select stems must end with `(Select TWO)`, `(Select THREE)`, etc.
- Minimum 4 options (A–D), maximum 6 (A–F)

### Answer distribution
- No single option (A, B, C, D) should be the correct answer for more than **40%** of questions in a file
- If B is correct for 26 of 45 questions, rotate some answers by reordering the `options` array and updating `correct` to match

### Distractors
- Every wrong answer must be **plausible** to someone with partial knowledge — not obviously absurd
- Good distractors: a real API that does the wrong thing in this context, a common misconception, an approach that's valid elsewhere but not here
- Bad distractors: nonsense terms, completely unrelated technologies, obviously silly answers

**Forbidden option texts** (reveal the answer by elimination — never use these):
- "All of the above"
- "None of the above"
- "Both A and B"
- "All of these"
- "None of these"

### Explanations
Each option must have its own paragraph explaining **specifically** why it is right or wrong:

```
"**B** is correct because MERGE INTO ... performs upsert semantics ...\n\n**A** is incorrect because COPY INTO ... only inserts new data ...\n\n**C** is incorrect because ...\n\n**D** is incorrect because ...\n\n[Delta Lake MERGE INTO](https://docs.databricks.com/delta/delta-update.html)"
```

Do not write "**A** is incorrect because it is wrong" — state the specific technical reason.

Every explanation must end with a markdown documentation link: `[Page Title](https://docs.vendor.com/...)`.

### Reference field
The `reference` field on each question must be a **markdown link**, not a bare URL:

```json
"reference": "[Delta Lake MERGE INTO](https://docs.databricks.com/delta/delta-update.html)"
```

Not:
```json
"reference": "https://docs.databricks.com/delta/delta-update.html"
```

The reference URL should point to a page that is directly relevant to the question topic. Link to the specific docs page for the feature being tested, not a general index page.

### Difficulty distribution
Each exam should have approximately:
- 20–30% **easy** — direct recall of a single fact
- 40–55% **medium** — applying a concept in context
- 20–30% **hard** — synthesising multiple concepts, scenario-based troubleshooting

### Accuracy
- The marked correct answer must be unambiguously correct based on official vendor documentation
- If two options are both defensible, restructure the question or convert it to multi-select
- Version-sensitive facts (specific release numbers, deprecated features) should be avoided unless the certification explicitly tests them

---

## Validating your changes

Always run the validator before opening a PR:

```bash
# Single exam file
python3 scripts/validate.py --exam exams/<cert-id>/exam-NN.json

# All exams
python3 scripts/validate.py

# Catalog only
python3 scripts/validate.py --catalog
```

The validator checks:
- JSON validity and schema compliance
- `meta.totalQuestions` matches the actual question count
- Domain IDs exist in `catalog.json`
- Domain weights sum to 100
- No duplicate question IDs
- Answer distribution (>40% on one letter = warning)
- Difficulty distribution (<20% hard = warning)
- Forbidden options
- Multi-select stem suffix
- Explanation length
- Reference field format (bare URL = warning)

Errors block the PR. Warnings should be resolved where possible.

---

## Full specification

`EXAM_GENERATION_GUIDE.md` is the complete authoritative spec. It covers:
- The full `meta` object schema (Section 3)
- Every question field in detail (Section 6)
- The complete domain ID taxonomy (Section 5)
- Markdown formatting rules for stems, options, and explanations (Section 6.9)
- Worked examples of single-select and multi-select questions (Section 8)
- Exam title code prefixes for every supported certification (Section 10)
- A full pre-submission checklist (Section 11)
