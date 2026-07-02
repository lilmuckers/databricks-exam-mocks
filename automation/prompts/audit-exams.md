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
- Rerun all three validation scripts on every changed file.
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

## Step 6 — Run all three validators on every changed file

Run these commands in order per exam. Fix every finding before the next
command.

```bash
# 1. Structural validation
python3 scripts/validate.py --exam exams/<cert>/exam-NN.json

# 2. Live reference link check (no cache — must be live)
python3 scripts/check_links.py \
  --exam exams/<cert>/exam-NN.json \
  --check-links --fields reference --no-cache --only-bad

# 3. Semantic quality check (must exit 0)
python3 scripts/check_semantic_quality.py --exam exams/<cert>/exam-NN.json
```

Do not open or update a PR if any command exits non-zero.

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
- Confirmation all three validators passed (validate.py, check_links.py,
  check_semantic_quality.py)
- Confirmation of semantic quality: per-option explanation formatting, no
  console/app URL references, no recycled scenario pool, no recycled
  distractors, non-gameable answer distribution

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
- Confirmation all three validators passed
- Any blockers or assumptions
