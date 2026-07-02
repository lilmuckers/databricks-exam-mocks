# Databricks Exam Mocks: Scheduled Exam Generator

Read this file from the cloned repo before taking any other action. The version
on disk is authoritative — if your session context, memory, or cron payload
conflicts with this file, this file wins.

---

## Objective

Create three new mock exams, push them on a branch, and open one pull request
for human review. The PR will be reviewed against the quality bar in
`EXAM_GENERATION_GUIDE.md` and this prompt. Exams that fail that bar will be
rejected and you will be asked to regenerate.

---

## Known failure modes (read before generating anything)

Previous runs produced content that was rejected. The patterns to avoid:

- **Scenario pool rotation** — writing N base scenarios then repeating them
  with industry prefixes ("retail", "healthcare", "logistics"). A question is
  not unique because it says "healthcare" instead of "retail".
- **Question count averaging** — defaulting to 40 or 60 questions because
  other repo exams use that count. Every certification has a specific official
  question count. Find it from the vendor. If you cannot verify it, say so
  explicitly — do not guess or average.
- **Injected irrelevant context** — appending a sentence about a failed canary,
  a compliance requirement, or stakeholder reporting that has no effect on the
  correct answer.
- **Meta-filler multi-select options** — one of the two correct answers that is
  always correct because it restates the question: "Use the documented X
  workflow rather than an unrelated feature" or "Configure the related Y
  capability for the stated workload". These test nothing.
- **Boilerplate wrong-option explanations** — "it applies a related service
  feature in a way the documentation does not support", "it targets storage
  rather than the decision point", "it handles an adjacent use case". These
  are not technical explanations.
- **Reference URL overuse** — one URL reused for an entire domain regardless
  of what each question is actually about.
- **Self-certified quality passes** — running "mental" equivalents of the
  semantic check and claiming pass. The semantic check script must be run and
  must exit 0.
- **Stems that do not make sense to a human** — slot-filled identifiers, synthetic
  ticket numbers, and made-up asset names are not exam scenarios. Example of a
  rejected stem: `Case \`calibrate-orders-01\`: unapproved model; ticket OC001;
  asset forecasts_01. Required capability: \`claims_features_01\`. Which control
  fixes this?` — this is gibberish to a human reader. Every stem must read as
  a coherent English sentence describing a real situation a practitioner could
  encounter.

If you recognise yourself producing any of these patterns, stop and regenerate
from a new ledger rather than patching words.

---

## Escalation rule

If a generated-exam PR has received `CHANGES_REQUESTED` on **two or more
review rounds** for the same systemic failure category, do **not** push another
cosmetic patch. Post a PR comment explaining that you cannot meet the quality
bar for this batch, recommend the PR be closed, and stop the run without
creating new exam content. A human will review the generation approach before
the next attempt.

---

## Step 0 — Read live files first

Before any repo work:

1. Read `automation/prompts/generate-exams.md` from the cloned repo (this
   file). Treat it as the active runbook.
2. Read `EXAM_GENERATION_GUIDE.md` from the same branch. It is the
   authoritative style guide. Follow it for every question, explanation, and
   reference field.

Do not inspect PRs, select certifications, edit files, or run any command
until both files have been read.

---

## Step 1 — Check for open PRs requiring action

Use the GitHub CLI to list open PRs from this automation (branches matching
`auto/batch-exams-*` or `auto/audit-exams-*`).

**If an open generated-exam PR has `CHANGES_REQUESTED`:**
- Check out the PR branch and pull latest.
- Read every review comment in full.
- Apply the requested fixes — see the "Per-question authorship discipline"
  section below for how to do this properly.
- Rerun all three validation scripts (validate, check_links, check_semantic_quality).
- Push a follow-up commit and comment on the PR summarising what was fixed.
- Do not create a new batch in the same run.

**If no open PR needs attention:** proceed to Step 2.

---

## Step 2 — Select certifications

1. Read `exams/catalog.json`. Skip any entry with `"retired": true`.
2. Count existing mock exam files for each certification.
3. Group certifications by provider and estimate repo coverage per provider.
4. Apply weighted random selection:
   - Base weight: `1 / (existing_mock_count + 1)`
   - Apply a provider-balance multiplier that boosts underrepresented providers
5. Select up to three distinct certifications from different providers where
   possible. Do not select all three from the same provider unless scarcity
   math overwhelmingly justifies it.

---

## Step 3 — Research each certification

For each selected certification:

1. Find the official certification page and exam guide from the vendor.
2. Record the following, **each with its source URL**:
   - official question count
   - time limit
   - passing score
   - domains/objectives and their weights
   - difficulty level and candidate profile
3. Cross-check against the repo's catalog metadata and reputable wider-web
   sources (certification study guides, official learning paths).
4. If sources conflict, prefer the most current certification-specific official
   source. Document any unresolved conflict in the PR body.
5. **HARD CHECK — question count:** the exam you generate must contain exactly
   the certification's verified official question count. Do not interpolate from
   repo averages. Do not round to a convenient number. If official sources
   disagree, document the conflict and use the most authoritative source. If
   you genuinely cannot determine the count from any source, state that
   explicitly in the PR body and use the best-supported number — do not
   silently default to a round number.

---

## Step 4 — Build the per-question authorship ledger

**This step is mandatory. Write the ledger to a file before producing any JSON.**

For every planned question, write a row containing:

| Field | Content |
|-------|---------|
| `id` | Planned question ID (q01, q02, …) |
| `domain` | Domain/objective from official syllabus |
| `concept` | Specific skill or feature being tested |
| `scenario` | One-sentence unique real-world situation |
| `decisive_constraint` | The fact that makes one answer correct and eliminates distractors |
| `correct_answer` | Which option(s) will be correct |
| `distractor_A/B/C` | Three plausible wrong answers, each wrong for a *different specific reason* |
| `reference_url` | The specific documentation URL for this concept |
| `not_a_variant_of` | ID(s) of any earlier question that touches the same service — and one sentence explaining why this is genuinely different |

Also record at the top of the ledger:

| Field | Content |
|-------|---------|
| `verified_question_count` | Official count and the source URL used to verify it |
| `domain_distribution` | Planned question count per domain matching official weights |

**After writing the full ledger, review it before writing JSON:**

- If any two rows share the same `scenario` base (even with different industry
  words), delete one and write a new row.
- If any two rows have the same `decisive_constraint`, rewrite one.
- If the same `reference_url` appears more than 4 times, replace the extras
  with more specific URLs.
- If any `correct_answer` letter appears in more than 45% of rows, reshuffle.
- Confirm total row count matches `verified_question_count`.

Only proceed to JSON once the ledger is clean.

---

## Step 5 — Draft questions in batches of 15

**Hard batch limit: generate a maximum of 15 questions, then stop.**

After every 15 questions:

1. Run `python3 scripts/check_semantic_quality.py --exam <path>` on the
   partial file (save progress to a temp file or the final path).
2. Report the output inline.
3. Fix every HARD FAILURE before continuing to the next 15.
4. Do not proceed to the next batch until the script exits 0 for the current
   batch.

Draft each question independently from its ledger row. Do not:
- Copy a stem and swap one word
- Share an option set across two questions
- Use the same explanation skeleton

### Multi-select independence check

For every `multiple`-type question, before finalising it, write this sentence
in your working notes:

> "A candidate who knows [Concept A] but not [Concept B] will select
> [option X] correctly but miss [option Y] because ___."

If you cannot fill the blank with a specific technical reason, the question
fails. Rewrite it so both correct answers are independently testable.

---

## Step 6 — Per-question content rules

Every question must have:

- **A concrete scenario stem** — named service, named feature, observable
  symptom, specific error, architectural constraint, or measurable tradeoff.
  No "a team needs to make a design decision about X".
- **Additional context that matters** — any extra sentence in the stem must
  change the correct answer or eliminate at least one distractor. If it does
  neither, cut it.
- **Four distinct, plausible distractors** — wrong for *different* specific
  reasons, not recycled from another question, not obviously absurd.
- **Explanation format** — one `\n\n`-separated paragraph per option, each
  starting with a bold label: `**A** ...\n\n**B** ...\n\n**C** ...\n\n**D** ...`
- **Wrong-option explanations that name specifics** — state the actual
  service, feature, API, or constraint in the option and explain precisely
  why it fails this scenario. "It applies a related feature in a way the
  documentation does not support" is not acceptable.
- **A topic-specific reference URL** — the documentation page that directly
  covers this question's concept. Not a provider landing page. Not the same
  URL as the previous five questions.

### Human readability test

This PR will be reviewed by a human. Before finalising each question, read
it as a human candidate would — cold, without knowing it was generated:

- Does the stem describe a situation a real practitioner could encounter?
- Do the options make sense as distinct, plausible choices within that situation?
- Does the explanation teach something, or does it just assert that an answer
  is correct?

If any of those answers is "no", rewrite before moving on. A question that
only passes a script check but would confuse a human reviewer will be rejected.

### Reference content verification

For each question, after writing it:

1. Open the `reference` URL.
2. Find the specific passage, table, or code example on that page that
   supports the correct answer.
3. If you cannot find direct support on that page, either fix the answer or
   replace the reference with a page that does support it.
4. If uncertain, double-check and triple-check before accepting. Do not keep
   a reference that only loosely relates to the question's concept.

`check_links.py` only confirms the URL is live. Reference *content*
verification is your responsibility and cannot be automated.

### Using existing exams as format reference

You may read existing exams in the repo to understand expected wording style,
scenario depth, explanation length, and option format. However:

- Do not derive questions from existing ones. A question is too similar if a
  student who has already studied an existing exam would recognise the scenario
  or the decisive constraint.
- The new exam must be genuinely useful to someone who has already done every
  other exam for that certification in the repo. Enough variation is required
  for it to test different knowledge.

---

## Step 7 — Run all three validators

Run these commands in order after completing all questions. Fix every finding
before proceeding to the next command.

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

Do not open a PR if any command exits non-zero.

---

## Step 8 — Update catalog.json

Add the new exam path to the `exams` array for each chosen certification in
`exams/catalog.json`. Run `python3 scripts/validate.py --catalog` to confirm.

---

## Step 9 — Commit, push, open PR

```bash
git checkout -b auto/batch-exams-YYYYMMDD
git add exams/<cert-1>/exam-NN.json exams/<cert-2>/exam-NN.json exams/<cert-3>/exam-NN.json exams/catalog.json
git commit -m "Add generated mock exams for <cert-1>, <cert-2>, <cert-3>"
git push origin auto/batch-exams-YYYYMMDD
gh pr create --title "Add scheduled mock exams for <cert-1>, <cert-2>, <cert-3>" --body "..."
```

**PR body must include:**

- Chosen certifications and their existing mock counts at selection time
- For each certification: the verified official question count, the source URL
  used to verify it, and any conflict between sources
- Research basis for each: sources used for syllabus, topic weights, difficulty
- Final question count, domain distribution, and difficulty blueprint per exam
- Confidence rating (high / medium / low) per exam and reasons for lower
  confidence
- Confirmation that all three validators passed (validate.py, check_links.py,
  check_semantic_quality.py)
- Confirmation of semantic quality: no duplicate/near-duplicate stems, no
  scenario-pool rotation, no industry-prefix rotation, no injected irrelevant
  context, no meta-filler multi-select answers, non-gameable answer
  distribution, per-option explanation format, specific wrong-option
  explanations, topic-specific reference URLs
- Confirmation of human readability: every stem describes a real situation a
  practitioner could encounter; every option is a distinct, plausible choice;
  every explanation teaches the underlying concept
- Confirmation of reference content verification: for each question the correct
  answer is directly supported by content on the linked reference page — not
  merely that the page is live

---

## Guardrails

- Never force-push.
- Never start a new batch while an open generated-exam PR has unaddressed
  review feedback.
- Never mirror existing exam quirks that conflict with `EXAM_GENERATION_GUIDE.md`.
- Never modify existing exam content (except `catalog.json`).
- If `check_semantic_quality.py` exits non-zero after three regeneration
  attempts on the same exam, do not push. Post a blocker comment on the
  existing PR and stop the run.
- If the selected certification is marked `"retired": true`, re-roll.
- If a PR for the same certification was already opened today, re-roll.

---

## Output

Return a concise run summary including:

- Confirmation that this prompt file and `EXAM_GENERATION_GUIDE.md` were
  read from the cloned repo before any other action
- Whether this run addressed an existing PR or created a new batch
- Certifications chosen and their prior mock counts
- For each certification: verified question count and source URL
- File paths created
- Branch name and PR URL
- Confidence ratings and reasons for any low confidence
- Confirmation that all three validators passed
- Any blockers or assumptions
