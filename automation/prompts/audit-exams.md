# Databricks Exam Mocks: Scheduled Exam Auditor

Read this file from the cloned repo before taking any other action. The version
on disk is authoritative — if your session context, memory, or cron payload
conflicts with this file, this file wins.

---

## Objective

Review the three oldest eligible exam files in the repo, fix any quality issues
found, stamp each with a fresh `meta.last_audited` value, and open or update a
single pull request for human review.

---

## Known failure modes (read before auditing anything)

- **Question count defaulting** — accepting an exam's existing question count
  without verifying it against the official certification spec. An exam that
  was generated with 40 questions when the cert requires 75 must be corrected,
  not preserved. Independently verify every audited exam's official question
  count from the vendor before deciding whether the count is correct.
- **Spot-fixing** — finding one broken reference or one bad explanation and
  fixing only that occurrence. The audit scope is the whole file. If you find
  a class of issue, search for every instance in that exam and fix them all.
- **Self-certified quality passes** — mentally running the semantic check and
  claiming pass. The script must be run and must exit 0.
- **Console URL references** — using provider app/console URLs (e.g.
  `platform.claude.com`, AWS Console login pages) as `reference` values.
  References must point to documentation, not app interfaces.
- **Soft rewrites** — cosmetically changing template-generated exams word by
  word instead of regenerating the affected questions from scratch. If an exam
  is built from a recycled scenario pool, rewrite the affected questions fully.
- **Stems that do not make sense to a human** — a stem is not a scenario if it
  contains slot-filled identifiers, synthetic ticket numbers, or made-up asset
  names in place of real technical context. This PR will be reviewed by a human.
  Every stem, option, and explanation must read as coherent, meaningful English
  to a practitioner who has never seen the exam before.
- **Injected irrelevant context** — stems that append a sentence about a failed
  canary, a compliance requirement, or stakeholder reporting that has no effect
  on the correct answer. Every sentence in a stem must change the answer or
  eliminate at least one distractor. If it does neither, cut it.
- **Meta-filler multi-select options** — a correct answer that is always correct
  because it restates the question: "Use the documented X workflow rather than
  an unrelated feature" or "Configure the related Y capability for the stated
  workload". These test nothing and must be replaced with independently
  verifiable correct answers.
- **Boilerplate wrong-option explanations** — "it applies a related service
  feature in a way the documentation does not support", "it targets storage
  rather than the decision point", "it handles an adjacent use case". These
  are not technical explanations and must be rewritten to name the specific
  service, feature, API, or constraint and explain precisely why it fails.
- **Reference URL overuse** — one URL reused across an entire domain regardless
  of what each question tests. If more than 4 questions share the same
  reference URL, replace the extras with more specific documentation pages.

---

## Escalation rule

If an audit PR has received `CHANGES_REQUESTED` on **two or more review
rounds** for the same systemic failure category, do **not** push another
cosmetic patch. Post a PR comment explaining that you cannot meet the quality
bar for this batch, recommend the PR be closed, and stop the run. A human will
review the audit approach before the next attempt.

---

## Step 0 — Read live files first

Before any repo work:

1. Read `automation/prompts/audit-exams.md` from the cloned repo (this file).
   Treat it as the active runbook.
2. Read `EXAM_GENERATION_GUIDE.md` from the same branch. It is the
   authoritative quality standard for all exam content.

Do not inspect PRs, select exams, edit files, or run any command until both
files have been read.

---

## Step 1 — Check for open audit PRs requiring action

Use the GitHub CLI to list open PRs from this automation (branches matching
`auto/audit-exams-*`).

**If an open audit PR has `CHANGES_REQUESTED`:**
- Check out the PR branch and pull latest.
- Read every review comment in full.
- Apply the requested fixes across all affected exam files.
- Rerun all four validation scripts on every changed file.
- Push a follow-up commit and comment on the PR summarising what was fixed.
- Do not select a fresh set of exams in the same run.

**If no open audit PR needs attention:** proceed to Step 2.

---

## Step 2 — Select exams to audit

1. Determine the working base branch: use the most recently updated open audit
   PR branch if one exists; otherwise use `main`.
2. Enumerate all `exams/*/exam-*.json` files.
3. For each file, determine its effective audit timestamp:
   1. Prefer `meta.last_audited` when present.
   2. Otherwise use `git log -1 --format=%ct -- <path>`.
   3. If git history is unavailable, fall back to filesystem mtime and note it.
4. Sort ascending and select the three oldest.
5. Do not select a file that is currently changed on the open audit branch.

---

## Step 3 — Research each selected certification

For each exam selected:

1. Find the official certification page and current exam guide from the vendor.
2. Record the following, **each with its source URL**:
   - official question count
   - time limit
   - passing score
   - domains/objectives and their weights
   - difficulty level and candidate profile
3. Cross-check against the repo's catalog metadata and reputable wider-web
   sources.
4. If sources conflict, prefer the most current certification-specific official
   source. Document any unresolved conflict in the PR body.
5. **HARD CHECK — question count:** the audited exam must contain exactly the
   certification's verified official question count after the audit is complete.
   If the existing exam has the wrong count (too many or too few), correct it —
   add missing questions or remove excess ones. Do not preserve a wrong count
   because it was already in the file. If you genuinely cannot determine the
   official count, state that explicitly in the PR body rather than defaulting.
6. Build an audit blueprint: expected question count, domain distribution, and
   difficulty mix. Compare the existing exam against it before beginning edits.

---

## Step 4 — Audit each exam

The audit scope is the **whole exam file**, not only lines touched by the first
obvious fix. If you find a class of issue, search every question for the same
pattern.

For every question in each selected exam, check:

### Accuracy
- Verify the keyed answer and explanation against current documentation.
- Replace or rewrite any question whose answer is wrong, outdated, weakly
  supported, or depends on a hidden assumption.
- **Reference content verification:** for each question, open the `reference`
  URL and find the specific passage, table, or code example that supports the
  correct answer. If you cannot find direct support on that page, fix the
  answer or replace the reference. `check_links.py` only confirms the URL is
  live — reference *content* verification is your responsibility. If uncertain,
  double-check and triple-check before accepting.

### Certification fit
- Confirm the question is appropriate for the cert's scope and level.
- Remove questions that belong to a different certification or are below/above
  the expected difficulty.

### Question quality
- Fix unclear, vague, or misleading stems.
- Detect template/mechanical sets: repeated stem frames, concepts repeated with
  only option order changed, predictable answer-key patterns. If an exam is
  built from a small recycled scenario pool, rewrite the affected questions
  from scratch — do not cosmetically patch.
- Every question must be a concrete scenario or precise conceptual test with
  named services, observable symptoms, specific constraints, or measurable
  tradeoffs causally relevant to the answer.
- **Stem context rule:** every sentence in a stem must change the correct answer
  or eliminate at least one distractor. If a sentence does neither, cut it.
  Do not preserve injected context (failed canaries, stakeholder reports,
  compliance mentions) that has no bearing on the answer.
- **Answer distribution:** check the `correct` field distribution across all
  single-select questions. If any single letter appears as the correct answer
  in more than 45% of single-select questions, reshuffle affected questions
  so each option letter appears in roughly equal proportions. Do not rely only
  on the `--warn-only` checkpoint — verify and fix distribution explicitly.
- **Multi-select independence check:** for every `multiple`-type question you
  rewrite or leave unchanged, verify that both correct answers are independently
  testable. Write this sentence in your working notes before finalising:
  > "A candidate who knows [Concept A] but not [Concept B] will select
  > [option X] correctly but miss [option Y] because ___."
  If you cannot fill the blank with a specific technical reason, rewrite the
  question so both answers test different, separable knowledge.
- **Human readability test:** read each question as a human candidate would —
  cold, without knowing it was generated. Does the stem describe a situation a
  real practitioner could encounter? Do the options make sense as distinct,
  plausible choices? Does the explanation teach something? If any answer is
  "no", rewrite. A question that passes the scripts but would confuse a human
  reviewer must be fixed.
- **Variation from existing exams:** you may read other exams for that
  certification to understand expected format and wording. However, rewritten
  questions must not be so similar to existing questions that a student who
  has already studied the other exams gains no new knowledge. Ensure enough
  variation for each audited exam to be independently useful.

### Distractor quality
- Wrong answers must be plausible and wrong for different, specific reasons.
- No joke answers, obviously impossible options, or trivially dismissible
  distractors.
- No recycled distractor text across questions.

### Reference quality
- Every `reference` must be a live URL pointing to real documentation.
- The page must be relevant to the specific concept tested — not a broad
  landing page or product home.
- **HARD CHECK:** provider console/app URLs are not documentation references.
  `platform.claude.com`, AWS Console login pages, and equivalent app interfaces
  must be replaced with `docs.*` or equivalent official documentation URLs.
- If many questions in a domain share one broad source, find more specific
  documentation pages for each individual concept.

### Explanation format
- One `\n\n`-separated paragraph per option, each starting with a bold label:
  `**A** ...\n\n**B** ...\n\n**C** ...\n\n**D** ...`
- Multi-select explanations must address each option independently.
- Wrong-option paragraphs must name the specific service, feature, API, or
  constraint and explain precisely why it fails — no generic boilerplate.

### Schema conformity
- Keep the file structure valid per the guide.
- Preserve question IDs unless there is a compelling reason to change them.

### Large exam checkpoint
For exams with more than 25 questions, pause after every 25 questions and run
`python3 scripts/check_semantic_quality.py --exam <path> --warn-only` on
progress so far. Address any HARD FAILUREs before continuing.

---

## Step 5 — Update metadata

For each audited exam:

- Set `meta.last_audited` to today's date in `YYYY-MM-DD` format.
- Set `meta.totalQuestions` to the actual question count in the file, which
  must match the verified official question count from Step 3.
- If substantive content or metadata changed, increment `meta.version` by 0.1.
- Do not bump `meta.version` for a `last_audited`-only refresh.
- If `meta.last_audited` is not present in the schema or validator, update the
  schema, validation logic, and docs in the same branch so the field is
  first-class rather than ad hoc.

---

## Step 6 — Run all four validators on every changed file

Run these commands in order per exam. Fix every finding before the next
command.

```bash
# 0. Install embedding dependencies if not already present (one-time):
pip install sentence-transformers requests beautifulsoup4 numpy

# 1. Structural validation
python3 scripts/validate.py --exam exams/<cert>/exam-NN.json

# 2. Live reference link check (no cache — must be live)
python3 scripts/check_links.py \
  --exam exams/<cert>/exam-NN.json \
  --check-links --fields reference --no-cache --only-bad

# 3. Semantic quality check (must exit 0)
python3 scripts/check_semantic_quality.py --exam exams/<cert>/exam-NN.json

# 4. Reference relevance check — verifies page content supports the answer
#    First run downloads the embedding model (~90 MB, cached after that).
python3 scripts/check_reference_relevance.py \
  --exam exams/<cert>/exam-NN.json \
  --strict
```

Do not open or update a PR if any command exits non-zero.

**If check_reference_relevance.py flags a question:**
- Open the reference URL and read the page yourself.
- If the page genuinely does not discuss the concept tested, replace the
  reference with a page that does, or fix the question's answer and explanation.
- If the page does support the answer but scored low (technical content that
  uses different vocabulary than the question), that is a signal that the
  question's wording may be too abstract — consider making the stem and
  correct-answer explanation more specific so the terminology aligns.
- Do not change the threshold to make the question pass. Fix the reference
  or the question.

---

## Step 7 — Commit, push, open or update PR

```bash
# New audit run:
git checkout -b auto/audit-exams-YYYYMMDD-HHMM
# or reuse the existing open audit branch:
git checkout auto/audit-exams-<existing>

git add exams/<cert-1>/exam-NN.json exams/<cert-2>/exam-NN.json exams/<cert-3>/exam-NN.json
git commit -m "Audit <cert-1>, <cert-2>, <cert-3> exams"
git push origin <branch>
```

If reusing an existing open audit PR, leave the original PR body intact and add
this run's summary as a new PR comment.

**PR body (or comment when updating) must include:**

- Three audited exam paths
- Why each was selected (source of the audit timestamp used)
- For each exam: verified official question count, source URL used, and whether
  the count in the file was correct or had to be changed
- What changed in each exam (or confirmation that only `meta.last_audited` was
  refreshed)
- Domain distribution and difficulty mix before/after, if changed
- References replaced and why
- Version bumps made
- `last_audited` values written
- Any source conflicts or assumptions
- Confirmation all four validators passed (validate.py, check_links.py,
  check_semantic_quality.py, check_reference_relevance.py --strict)
- Confirmation of semantic quality: no duplicate/near-duplicate stems, no
  recycled scenario pool, no industry-prefix rotation, no injected irrelevant
  context, no meta-filler multi-select answers, non-gameable answer
  distribution, per-option explanation format, specific wrong-option
  explanations (naming the actual service/feature/constraint), topic-specific
  reference URLs, no console/app URL references
- Confirmation of human readability: every stem describes a real situation a
  practitioner could encounter; every option is a distinct, plausible choice;
  every explanation teaches the underlying concept
- Confirmation of reference content verification: for each question the correct
  answer is directly supported by content on the linked reference page — not
  merely that the page is live

---

## Guardrails

- Never force-push.
- Never start a new audit PR while an open audit PR has unaddressed review
  feedback.
- Do not create new exam files in this run.
- Do not limit fixes to validator failures — fix guide violations even when
  validate.py passes.
- Large rewrites are allowed when an exam is mechanically templated, gameable,
  or broadly non-compliant. Preserve file path and question IDs where
  reasonable, but prioritise quality over minimal diff size.
- If one of the three selected exams needs no substantive changes, still update
  `meta.last_audited` so it is not immediately re-selected, and note in the PR
  that no content changes were needed.
- Never modify existing exams other than the three selected ones (except
  `catalog.json` if a schema change requires it).

---

## Output

Return a concise run summary including:

- Confirmation that this prompt file and `EXAM_GENERATION_GUIDE.md` were read
  from the cloned repo before any other action
- Whether this run addressed an existing PR or audited a fresh set
- Audited exam paths and audit timestamp source for each
- For each exam: verified question count, source URL, and whether count was
  correct or corrected
- Which exams received substantive changes vs. `last_audited`-only refresh
- Version bumps and `last_audited` values written
- Branch name and PR URL
- Confirmation all four validators passed
- Any blockers or assumptions
