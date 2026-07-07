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

## Orchestration protocol

This runbook drives a **staged, multi-agent pipeline**. The orchestrator (cron
process) reads the full file. Sub-agents receive only their assigned section.

| Step | Agent | Reasoning | Input | Output |
|------|-------|-----------|-------|--------|
| 0–2 | Orchestrator | — | repo state | exam selection |
| 3 | Research agent | **Medium** | `guideUrl` + vendor pages | official spec per cert |
| 4 | Audit analyst | **High** | full exam JSON (all questions) | `findings.json` per exam |
| 4.5 | Orchestrator | — | `findings.json` | scope gate decision |
| 5 | Triage agent | **Medium** | `findings.json` | routed fix plan per question |
| 6a | Full rewriter | **High** | flagged question + research context | rewritten question → step 6b |
| 6b | Distractor writer | **Low** (hard-constrained) | stem + correct answer + misconception | 3 distractors with specific wrong reasons |
| 6c | Partial fixer | **Medium** | flagged question + `affected_fields` | corrected fields only — anti-drift applies |
| 6d | Structural fixer | **Low** | schema/format failures | field-only corrections |
| 7 | Assembler | **Low** | all fixed + passing questions | updated exam JSON |
| 8 | Validator | **Low** | exam JSON path | structured failure list, typed by category |
| 9 | Structural repair | **Medium** | structural failures + exam JSON | corrected JSON — anti-drift applies |
| 10 | Semantic repair | **High** | semantic failures + failing questions | rewritten questions → re-enters at step 6a |
| 11 | Orchestrator | — | clean exam JSON | metadata update |
| 12 | Orchestrator | — | all changed files | commit, push, PR |

Steps 4–7 run per exam. Steps 8–10 iterate up to **five times total** per exam
before escalating. The distractor writer (6b) is only invoked when a full
rewriter (6a) produces a new stem — partial fixes skip 6b entirely.

**Routing rule (step 8 output):** failures from `validate.py` and
`check_links.py` are **structural** — route to step 9. Failures from
`check_semantic_quality.py` and `check_reference_relevance.py` are **semantic**
— route to step 10, which re-enters at step 6a for the affected questions only.

**Anti-drift rule (steps 6c, 9):** partial and structural fixers must not alter
any question stem, correct-answer text, or explanation wording unless the
failure message explicitly identifies that field as malformed. Fix only the
fields listed in `affected_fields`. Quietly rewriting high-reasoning output is
a disqualifying failure.

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

Use the GitHub CLI to list open PRs whose branch name matches `auto/audit-exams-*`.

**Do not act on `auto/batch-exams-*` PRs.** Those branches are owned by the
generate runbook (`automation/prompts/generate-exams.md`). If you see an open
batch PR with `CHANGES_REQUESTED`, ignore it and proceed to Step 2 as normal.

**If an open `auto/audit-exams-*` PR has `CHANGES_REQUESTED`:**
- Check out the PR branch and pull latest.
- Read every review comment in full.
- Apply the requested fixes across all affected exam files.
- Rerun all four validation scripts on every changed file.
- Push a follow-up commit and comment on the PR summarising what was fixed.
- Do not select a fresh set of exams in the same run.

**If an open `auto/audit-exams-*` PR is awaiting review (last activity was a
commit push, not a `CHANGES_REQUESTED` review):**
- Do not touch that PR.
- Proceed to Step 2 to select a fresh set of exams, but treat the exam files
  already in the awaiting PR as if they have today's date as their
  `meta.last_audited` value. This prevents re-selecting them before the pending
  PR is merged.

Detect "awaiting review" with:
```bash
gh pr view <number> --json reviewDecision --jq '.reviewDecision'
# returns: null / "REVIEW_REQUIRED" → awaiting review
# returns: "CHANGES_REQUESTED"       → needs fixes
# returns: "APPROVED"                → approved (treat same as awaiting, skip)
```

**If no open `auto/audit-exams-*` PR exists:** proceed to Step 2 normally.

---

## Step 2 — Select exams to audit

1. Always branch from `main`. Do not base new audit work on a pending or
   awaiting-review audit branch — start clean.
2. Enumerate all `exams/*/exam-*.json` files on `main`.
3. For each file, determine its effective audit timestamp:
   1. Prefer `meta.last_audited` when present.
   2. Otherwise use `git log -1 --format=%ct -- <path>`.
   3. If git history is unavailable, fall back to filesystem mtime and note it.
4. For any exam file that appears in an open awaiting-review audit PR, treat its
   effective timestamp as today's date (so it sorts to the end and is not
   re-selected).
5. Sort ascending and select the three oldest.
6. Do not select any file already in an open awaiting-review or
   CHANGES_REQUESTED audit PR.

---

## Step 3 — Research each selected certification (medium reasoning)

For each exam selected:

1. Read `examDetails.guideUrl` from the cert's entry in `exams/catalog.json`.
   Open that URL. This is the **authoritative exam guide** — it defines the
   official question count, domain weights, time limit, passing score, and
   candidate profile for this certification.
2. Record the following **directly from the guide page**, each with its source
   URL:
   - official question count
   - time limit
   - passing score
   - domains/objectives and their weights
   - difficulty level and candidate profile
3. Cross-check against the repo's catalog metadata and reputable wider-web
   sources.
4. **GUIDE WINS rule:** if anything in this prompt, in `exams/catalog.json`
   (syllabus, question counts, domain names), or in the existing exam file
   contradicts what the official guide at `guideUrl` says, the guide wins.
   Document the contradiction in the PR body and follow the guide, not the
   conflicting source.
5. If sources conflict other than the guide, prefer the most current
   certification-specific official source. Document any unresolved conflict in
   the PR body.
6. **HARD CHECK — question count:** the audited exam must contain exactly the
   certification's verified official question count after the audit is complete.
   If the existing exam has the wrong count (too many or too few), correct it —
   add missing questions or remove excess ones. Do not preserve a wrong count
   because it was already in the file. If you genuinely cannot determine the
   official count, state that explicitly in the PR body rather than defaulting.
7. Build an audit blueprint: expected question count, domain distribution, and
   difficulty mix. Compare the existing exam against it before beginning step 4.

---

## Step 4 — Audit analyst (high reasoning)

**This agent receives:** the full exam JSON for one exam (all questions).

**This agent produces:** a structured `findings.json` for that exam — a
complete per-question diagnosis **before any edits are made**.

The analyst reads every question from start to finish before writing any
findings. This single-pass read enables systemic pattern detection that is
impossible when reading and fixing are interleaved.

### What the analyst looks for

For every question, assess:

**Accuracy**
- Is the keyed answer correct against current documentation?
- Does the explanation correctly explain why each option is right or wrong?
- Does the reference URL page directly support the correct answer?

**Certification fit**
- Is this question appropriate for the cert's scope, level, and candidate
  profile established in step 3?

**Question quality**
- Does the stem describe a concrete, real-world scenario a practitioner could
  encounter?
- Does every sentence in the stem change the correct answer or eliminate at
  least one distractor? If not, that sentence is dead weight.
- Are distractors plausible, wrong for distinct reasons, and non-recycled?

**Stem pathologies** (check each question, then also check as a batch)
- Rotating project/workflow filler (irrelevant project names, city names,
  stakeholder reports that have no effect on the answer)
- Slot-filled identifiers, synthetic ticket numbers, made-up asset names
- Meta-filler multi-select option (one correct answer restates the question)
- Boilerplate wrong-option explanation (no specific service, feature, or
  constraint named)
- Console/app URL used as `reference` instead of a documentation page
- Reference URL overuse (same URL on more than 4 questions in a domain)

**Systemic patterns** (recorded at the exam level, not per-question)
- Concept repetition: same service or feature concept tested in 2+ questions
  with only surface variation
- Answer-letter bias: one letter is correct in >45% of single-select questions
- Scenario pool rotation: same base scenario repeated with industry prefix
  changes

### Findings report format

Write one `findings.json` per exam at
`automation/ledgers/<cert-id>-audit-findings.json`:

```json
{
  "exam_path": "exams/aws-ml-engineer-associate/exam-03.json",
  "systemic_issues": [
    {
      "pattern": "rotating_filler",
      "affected_qids": ["q01","q03","q07"],
      "action": "full_rewrite_all"
    },
    {
      "pattern": "answer_distribution_bias",
      "affected_qids": ["q01","q04","q09","q11","q15"],
      "dominant_letter": "C",
      "action": "reshuffle"
    }
  ],
  "questions": [
    {
      "qid": "q01",
      "verdict": "full_rewrite",
      "reason": "Correct answer is factually wrong — explanation states VACUUM removes transaction log files, but VACUUM only removes unreferenced data files",
      "affected_fields": ["stem", "correct", "explanation"],
      "reference_issue": null
    },
    {
      "qid": "q07",
      "verdict": "partial_fix",
      "reason": "Explanation for option B is boilerplate; stem and correct answer valid",
      "affected_fields": ["explanation"],
      "reference_issue": null
    },
    {
      "qid": "q12",
      "verdict": "structural",
      "reason": "reference is a bare URL, not a markdown link",
      "affected_fields": ["reference"],
      "reference_issue": "format_only"
    },
    {
      "qid": "q22",
      "verdict": "pass",
      "reason": null,
      "affected_fields": [],
      "reference_issue": null
    }
  ]
}
```

**Verdict values:**
- `full_rewrite` — stem, correct answer, or explanation is wrong, misleading,
  or so degraded it cannot be patched. Routes to step 6a.
- `partial_fix` — stem and correct answer are sound; only specific named fields
  need fixing. Routes to step 6c with the `affected_fields` list.
- `structural` — schema, format, or reference URL issue only. Routes to step 6d.
- `pass` — question meets quality bar; no changes needed.

Do not make any edits to the exam JSON during this step. Produce the findings
report, then stop.

---

## Step 4.5 — Scope gate

The orchestrator reads the findings report before any fixing begins.

**If more than 50% of questions in an exam are marked `full_rewrite`:** this
exam needs regeneration, not patching. Post a PR comment explaining the scope
and recommend the exam be regenerated via the generation runbook
(`automation/prompts/generate-exams.md`). Do not proceed with step 5 for that
exam. Still audit the other two selected exams normally.

**If a `systemic_issues` entry with `action: full_rewrite_all` covers more
questions than are already marked individual `full_rewrite`:** promote those
questions to `full_rewrite` before passing findings to the triage agent. The
systemic flag takes precedence over per-question optimism.

---

## Step 5 — Triage agent (medium reasoning)

**This agent receives:** the `findings.json` for one exam.

**This agent produces:** a fix plan that groups questions into work queues:

- `rewrite_queue` — questions with verdict `full_rewrite`, ordered so that
  concept-adjacent questions are rewritten together for consistency.
- `partial_queue` — questions with verdict `partial_fix`, each with their
  `affected_fields` list. Only those fields may be touched.
- `structural_queue` — questions with verdict `structural`, routed directly
  to step 6d.

Also identify and record:
- Whether any `rewrite_queue` questions share a domain (so the full rewriter
  avoids producing duplicate concepts).
- Whether the `systemic_issues` `answer_distribution_bias` entry requires
  reshuffling after all other fixes (the assembler does this last).

---

## Step 6a — Full rewriter (high reasoning)

**This agent receives:** one `full_rewrite` question, the cert research from
step 3, the fix reason from findings, and the list of concepts already covered
in the exam (to avoid duplication).

**This agent produces:** a new stem, correct answer, and explanation. It must:

1. Preserve `id`, `domain`, and `difficulty` unless the findings report flags
   those fields as wrong.
2. Write a concrete scenario stem: named service, specific constraint,
   observable symptom or measurable tradeoff. No generic "a team needs to
   decide".
3. Every sentence in the stem must change the correct answer or eliminate at
   least one distractor.
4. Write the correct answer as a complete, standalone sentence.
5. Write the explanation with one `\n\n`-separated paragraph per option, each
   starting with a bold label (`**A**`, `**B**`, etc.). Wrong-option paragraphs
   must name the specific service, feature, API, or constraint and explain
   precisely why it fails — no boilerplate.
6. Verify the reference URL: open the page and find the specific passage that
   supports the correct answer. Replace the reference if no direct support exists.
7. Pass output to step 6b (distractor writer) before assembly.

**Multi-select independence check:** for every `multiple`-type question, write:
> "A candidate who knows [Concept A] but not [Concept B] will select [option X]
> correctly but miss [option Y] because ___."
If you cannot fill the blank with a specific technical reason, rewrite both
correct answers to test separable knowledge.

---

## Step 6b — Distractor writer (low reasoning)

**This agent receives:** the stem, correct answer, and explanation from step 6a,
plus the `target_misconception` (derived from the fix reason in findings).

**This agent must not alter** the stem, correct answer, or explanation.

Produce three distractors. Each must:
1. Be a plausible wrong answer for a candidate who holds the target misconception.
2. State "wrong because X" — one specific technical reason it fails in this
   scenario.

Distractors must be wrong for **different** reasons. Do not produce two
distractors stating the same failure mode in different words. Do not recycle
distractor text from other questions in the exam.

---

## Step 6c — Partial fixer (medium reasoning)

**This agent receives:** one `partial_fix` question and its `affected_fields`
list.

**Anti-drift rule:** fix only the fields listed in `affected_fields`. Do not
touch the stem, correct answer, or any explanation paragraph not explicitly
flagged. Even if a non-flagged field looks improvable, leave it unchanged.

Permitted actions per field type:
- `explanation` (specific paragraph): rewrite only the boilerplate paragraph,
  naming the actual service, feature, API, or constraint with the precise
  failure reason.
- `reference`: replace with a page that directly supports the correct answer.
- `options` (specific option): rewrite the flagged option text only.

After fixing, return the question with only the listed fields changed.

---

## Step 6d — Structural fixer (low reasoning)

**This agent receives:** questions with verdict `structural` from the triage
plan.

Fix only schema and format issues:
- Reformat `reference` as a markdown link.
- Replace console/app URLs with documentation URLs.
- Add missing required schema fields.
- Reword a specific option that contains a forbidden phrase.

Do not touch stems, explanations, or correct answers. Report which fields
were changed.

---

## Step 7 — Assembler (low reasoning)

**This agent receives:** all fixed questions (from steps 6a–6d) plus the
original passing questions from the findings report.

**This agent must not alter** any question wording, explanation, or answer
content. Its only task is to merge the fixed questions back into the original
exam JSON structure, apply any answer-distribution reshuffling flagged in the
systemic issues, and write the updated file.

For large exams (more than 25 questions), pause after merging every 25
questions and run `python3 scripts/check_semantic_quality.py --exam <path>
--warn-only` on progress so far. Address any HARD FAILUREs before continuing.

After assembly, report the file path.

---

## Step 8 — Validation and routing (low reasoning)

**This agent receives:** the assembled exam JSON path.

Run the four validators in order:

```bash
# 0. Install embedding dependencies if not already present (one-time):
pip install sentence-transformers requests beautifulsoup4 numpy

# 1. Structural
python3 scripts/validate.py --exam exams/<cert>/exam-NN.json

# 2. Live links
python3 scripts/check_links.py \
  --exam exams/<cert>/exam-NN.json \
  --check-links --fields reference --no-cache --only-bad

# 3. Semantic quality
python3 scripts/check_semantic_quality.py --exam exams/<cert>/exam-NN.json

# 4. Reference relevance
python3 scripts/check_reference_relevance.py \
  --exam exams/<cert>/exam-NN.json --strict
```

Produce a structured failure list:

```json
[
  {
    "qid": "q07",
    "check": "check_reference_relevance",
    "category": "semantic",
    "message": "score 0.21 below 0.30 threshold — reference page does not discuss the concept tested"
  },
  {
    "qid": "q12",
    "check": "validate",
    "category": "structural",
    "message": "reference field is a bare URL, not a markdown link"
  }
]
```

**Routing:**
- `"category": "structural"` (validate.py failures, check_links.py failures,
  answer-distribution failures) → step 9.
- `"category": "semantic"` (duplicate stems, boilerplate explanations,
  low reference relevance scores) → step 10.

If the failure list is empty, all validators passed — proceed to step 11.

If this is iteration 5 and failures remain, stop. Post a PR comment listing
the unresolved failures and stop the run without committing.

---

## Step 9 — Structural repair (medium reasoning)

**This agent receives:** the structural failure list and the exam JSON.

**Anti-drift rule:** fix only the fields identified in each failure item. Do
not modify any question's `stem`, `explanation`, or correct-answer text unless
the failure message explicitly identifies that field as malformed.

Permitted fixes:
- `reference` field: reformat or replace with a live documentation URL.
- Answer-letter distribution: reshuffle option ordering and update `correct`
  letter — do not change option text.
- Schema fields: add missing required fields.
- Forbidden option phrases: reword only the specific option flagged.

Return the corrected exam JSON to step 8 for re-validation.

---

## Step 10 — Semantic repair (high reasoning)

**This agent receives:** the semantic failure list and the full text of each
failing question.

For each failing question:

1. Read the failure message. Understand the specific quality failure.
2. Rewrite the question from scratch — new scenario, new options, same domain
   and concept.
3. Apply the full rewriter discipline from step 6a.
4. Return the rewritten question to step 6b (distractor writer), then step 7
   (assembler), before re-entering step 8.

Do not patch individual words. A cosmetic rewrite produces the same failure on
the next iteration.

---

## Step 11 — Update metadata

For each audited exam:

- Set `meta.last_audited` to today's date in `YYYY-MM-DD` format.
- Set `meta.totalQuestions` to the actual question count in the file, which
  must match the verified official question count from step 3.
- If substantive content or metadata changed, increment `meta.version` by 0.1.
- Do not bump `meta.version` for a `last_audited`-only refresh.
- If `meta.last_audited` is not present in the schema or validator, update the
  schema, validation logic, and docs in the same branch so the field is
  first-class rather than ad hoc.

---

## Step 12 — Commit, push, open or update PR

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
- Any guide-wins contradictions found (prompt vs. guide, catalog vs. guide)
- Findings summary per exam: verdict counts (full_rewrite / partial_fix /
  structural / pass) and whether the scope gate triggered
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
- **The official guide (`examDetails.guideUrl`) overrides everything.** If the
  guide contradicts this prompt, the catalog syllabus, or the existing exam on
  any factual point (question count, domain name, domain weight, passing score),
  follow the guide and document the discrepancy in the PR body.

---

## Output

Return a concise run summary including:

- Confirmation that this prompt file and `EXAM_GENERATION_GUIDE.md` were read
  from the cloned repo before any other action
- Whether this run addressed an existing PR or audited a fresh set
- Audited exam paths and audit timestamp source for each
- For each exam: verified question count, source URL, and whether count was
  correct or corrected
- Findings summary per exam: verdict counts (full_rewrite / partial_fix /
  structural / pass)
- Which exams hit the scope gate (if any)
- Which exams received substantive changes vs. `last_audited`-only refresh
- Version bumps and `last_audited` values written
- Branch name and PR URL
- Confirmation all four validators passed
- Any blockers or assumptions
