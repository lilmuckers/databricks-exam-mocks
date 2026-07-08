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

## Orchestration protocol

This runbook drives a **staged, multi-agent pipeline**. The orchestrator
(cron process) reads the full file. Sub-agents receive only their assigned
section plus the shared **Content rules** section.

| Step | Agent | Reasoning | Input | Output |
|------|-------|-----------|-------|--------|
| 0–3.5 | Orchestrator | — | repo state | cert selection, research, corpus index |
| 4 | Planning agent | **High** | research + corpus + prior chunk concepts + chunk range | 10-row ledger chunk |
| 4.5 | Parent | — | all ledger chunks | assembled `ledger.json` |
| 5 | Stem writer | **High / medium-high** | one ledger row | stem + correct answer + explanation |
| 6 | Distractor writer | **Low** (hard-constrained) | stem + correct answer + `target_misconception` | 3 distractors with "wrong because X" |
| 7 | JSON assembler | **Low** | all step 5+6 outputs | exam JSON file |
| 8 | Validator | **Low** | exam JSON | structured failure list, typed by category |
| 9 | Structural fixer | **Medium** | structural failures + exam JSON | corrected JSON; no wording changes |
| 10 | Semantic fixer | **High** | semantic failures + failing questions | rewritten questions → re-enters at step 5 |

Steps 5–6 run per question. Step 7 runs once per exam. Steps 8–10 iterate up
to **five times total** before escalating.

**Routing rule (step 8 output):** failures from `validate.py` and
`check_links.py` are **structural** — route to step 9. Failures from
`check_semantic_quality.py` and `check_reference_relevance.py` are **semantic**
— route to step 10, which re-enters the pipeline at step 5 for the affected
questions only.

**Anti-drift rule (step 9):** the structural fixer must not alter any question
stem, correct-answer text, or explanation wording unless the validator
specifically identifies that wording as malformed. It fixes schema, format,
link, and distribution failures only. Quietly rewriting high-reasoning output
to fit a pattern is a disqualifying failure.

**Session spawning — supervisor model:**

The parent (cron process) is a **pure supervisor**. Its only permitted actions
are:

- Read files from the repo and `/tmp/exam-run-${RUN_ID}/`
- Call `sessions_spawn` to start a child agent for one pipeline stage
- Poll for a child's output artifact (see paths below)
- Make routing decisions based on artifact contents
- Run `git` and `gh` CLI commands (branch, commit, push, PR)

**The parent must not:** generate question text, write exam JSON, call bash to
produce content, or perform any pipeline step (4–10) inline. There is no
fallback to inline generation. If `sessions_spawn` fails or a child times out,
write `{"status":"error","reason":"..."}` to the run directory and stop the
run. Do not attempt to recover by generating content in the parent.

Reasoning levels map to the `thinking` parameter:
- `thinking=high` — planning agent (step 4), stem writer (step 5), semantic
  fixer (step 10)
- `thinking=medium` — structural fixer (step 9)
- `thinking=low` — distractor writer (step 6), JSON assembler (step 7),
  validator (step 8)

**The first `sessions_spawn` call for each exam must be the first planning
agent chunk (step 4)** — it receives the corpus index, research, and the range
`q01–q10`, and produces `ledger-chunk-01.json`. Each subsequent chunk receives
the same research plus the list of concepts already planned in prior chunks.
After all chunks exist, the parent assembles them into `ledger.json` (no
subagent needed for assembly). Only after `ledger.json` exists does the parent
spawn stem-writer children.

**Hard rules for child sessions:**

1. **No whole-exam subagents.** Every child performs one pipeline stage for a
   bounded set of questions. A child that receives "generate exam for cert X"
   is malformed — reject the prompt and write a failure record instead.
2. **Batch sizes.** Stem writer spawns handle **3–5 questions each**. Distractor
   writer spawns handle **5–10 questions each**. Never process a full exam in
   one session.
3. **Sequential batches within a stage.** Spawn one batch, wait for its
   artifact, then spawn the next. Do not fire all batches for a stage at once.
   Never have more than **3 child sessions running simultaneously**.
3. **Every child writes a known artifact then stops immediately.** After
   writing the JSON artifact to its path, the child must produce no further
   output, no verification pass, no summary, and no additional tool calls.
   Writing the artifact is the final act — the session ends there.
4. **`sessions_spawn` is synchronous.** The parent call blocks until the child
   session ends. The parent reads the artifact file immediately after
   `sessions_spawn` returns. If the artifact is missing after the call returns,
   treat it as a failure: write `{"status":"error","stage":"..."}` to the run
   directory and stop. Do not retry or continue to the next stage.
5. **Strict child scope.** Each child prompt must state the exact question range
   (e.g., "process questions 1–5 only") and explicitly prohibit the child from
   running validators on the full exam or creating branches or PRs.
6. **No hard-coded topic key lookups.** Children derive all keys from the ledger
   row they receive. If a key is missing, write a structured failure record —
   do not crash or assume the key exists.

**Artifact paths (one run-directory per exam):**

```
/tmp/exam-run-${RUN_ID}/<exam-id>/
  research.json               ← parent writes one file per cert after step 3
  existing-concepts.json      ← parent writes corpus index after step 3.5
  ledger-chunk-NN.json        ← planning agent, one file per 10-question chunk
  ledger.json                 ← parent assembles all chunks (step 4.5)
  stems-batch-NN.json         ← stem writer, one file per batch of 3–5 questions
  distractors-batch-NN.json   ← distractor writer, one file per batch of 5–10
  exam-assembled.json         ← JSON assembler (step 7)
  validation.json             ← validator (step 8) — structured failure list
  structural-patch.json       ← structural fixer (step 9)
  semantic-patch-NN.json      ← semantic fixer (step 10), one file per iteration
  error.json                  ← written by parent on any unrecoverable failure
```

Parent reads each artifact and decides whether to proceed, retry, or escalate.
A run is only complete when the parent has read `exam-assembled.json` and
confirmed `validation.json` shows no failures — not when the last child exits.

---

## Known failure modes (read before generating anything)

Previous runs produced content that was rejected. The patterns to avoid:

- **Rotating project/workflow filler** — prepending irrelevant project names,
  city names, owner roles, and review windows to stems. Example of a rejected
  stem opening: `"Project Atlas runs from Dublin under the risk owner. The
  orders workflow reconciles quotes records during the 6:00 review window. The
  release note explicitly names policy replay rollout lineage, while the
  acceptance checklist covers assurance baseline redaction eligibility
  enrichment."` None of that context affects any answer. Every sentence in the
  stem must change the correct answer or eliminate at least one distractor —
  if it does neither, it must not exist.
- **Concept repetition via constraint rotation** — generating the same service
  or feature concept 2–3 times with different filler or a rotated
  `decisive_constraint` phrase. Each concept must appear exactly once across
  the exam. The corpus index (step 3.5) and ledger `not_a_variant_of` field
  enforce this — check both before accepting a row.
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
- **Stems that do not make sense to a human** — slot-filled identifiers,
  synthetic ticket numbers, and made-up asset names are not exam scenarios.
  Example of a rejected stem: `Case \`calibrate-orders-01\`: unapproved model;
  ticket OC001; asset forecasts_01. Required capability: \`claims_features_01\`.
  Which control fixes this?` — this is gibberish. Every stem must read as a
  coherent English sentence describing a real situation a practitioner could
  encounter.
- **Ledger or generation artifacts leaking into question text** — stems must
  never contain synthetic uniqueness markers, checkpoint markers, evidence
  bundles, rotating token lists, placeholder workspace objects, or text whose
  only purpose is to make automated similarity checks pass. Banned examples
  include phrases like `unique checkpoint marker`, `The evidence bundle for
  this question includes`, `distinct operational signals`, and
  `Workspace object ... has already been created` when the object is not a real
  product concept needed to answer the question.
- **Unrelated scenario splicing** — do not paste together two different
  scenarios and attach a random documentation title as the question. A stem
  must have one coherent decision point, and every sentence before the question
  must affect why the correct option is correct or why a distractor is wrong.
- **Documentation-title prompts** — stems such as `Which choice best uses
  <documentation page title> for <generic decision>?` are not acceptable unless
  the page title names the actual feature being configured in the scenario.
  The question should ask about the practitioner action, configuration, SQL
  construct, API call, or architecture choice — not about "using" a page title.

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
3. Generate a unique run ID and hold it constant for the entire run:
   ```bash
   RUN_ID=$(python3 -c "import uuid; print(uuid.uuid4().hex[:12])")
   ```
   All artifact paths for this run use `/tmp/exam-run-${RUN_ID}/<exam-id>/`.
   Never read from a `/tmp/exam-run-*/` directory created by a prior run.

Do not inspect PRs, select certifications, edit files, or run any command
until both files have been read and `RUN_ID` has been set.

---

## Step 1 — Check for open PRs requiring action

Use the GitHub CLI to list open PRs whose branch name matches `auto/batch-exams-*`.

**Do not act on `auto/audit-exams-*` PRs.** Those branches are owned by the
audit runbook (`automation/prompts/audit-exams.md`). If you see an open audit
PR with `CHANGES_REQUESTED`, ignore it and proceed to Step 2 as normal.

**If an open `auto/batch-exams-*` PR has `CHANGES_REQUESTED`:**
- Check out the PR branch and pull latest.
- Read every review comment in full.
- Apply the requested fixes — see the **Content rules** section below for how
  to do this properly.
- Rerun all four validation scripts (validate, check_links, check_semantic_quality,
  check_reference_relevance).
- Push a follow-up commit and comment on the PR summarising what was fixed.
- Do not create a new batch in the same run.

**If an open `auto/batch-exams-*` PR is awaiting review (last activity was a
commit push, not a `CHANGES_REQUESTED` review):**
- Do not touch that PR.
- Proceed to Step 2 to select a fresh set of certifications, but treat the
  certifications already covered in the awaiting PR as if they have one
  additional mock exam (i.e., increase their `existing_mock_count` by 1 in the
  weight calculation). This prevents double-selecting the same cert before the
  pending PR is merged.
- Open a new `auto/batch-exams-*` PR for the new batch on a new branch.

Detect "awaiting review" with:
```bash
gh pr view <number> --json reviewDecision --jq '.reviewDecision'
# returns: null / "REVIEW_REQUIRED" → awaiting review
# returns: "CHANGES_REQUESTED"       → needs fixes
# returns: "APPROVED"                → approved (treat same as awaiting, skip)
```

**If no open `auto/batch-exams-*` PR exists:** proceed to Step 2 normally.

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

1. Read `examDetails.guideUrl` from the cert's entry in `exams/catalog.json`.
   Open that URL. This is the **preferred authoritative exam guide**.
2. Attempt to record the following **directly from the guide page**, each with
   its source URL:
   - official question count
   - time limit
   - passing score
   - domains/objectives and their weights
   - difficulty level and candidate profile
3. **If the guide page is inaccessible, gated, or does not expose exam facts:**
   fall back to the `examDetails` values already present in `catalog.json`
   (question count, time limit, passing score, format). Treat those values as
   the working source of truth. Document the fallback in the PR body — do not
   stop the run.
4. **If both the guide page and `catalog.json` examDetails are missing or
   incomplete for a cert:** skip that cert, select the next candidate from
   Step 2's weighted list, and note the substitution in the PR body.
5. Cross-check catalog values against reputable wider-web sources where
   possible (certification study guides, official learning paths).
6. **GUIDE WINS rule:** if the live guide page contradicts `catalog.json`,
   this prompt, or existing repo exams on any factual point (question count,
   domain name, domain weight, passing score), the live guide wins. Document
   the contradiction in the PR body and follow the guide.
7. **HARD CHECK — question count:** the exam you generate must contain exactly
   the verified official question count from whichever source was used (guide
   page or catalog fallback). Do not interpolate from repo averages or round to
   a convenient number. If sources genuinely conflict, document and use the
   most authoritative figure available.
8. **Write a per-cert research file** to
   `/tmp/exam-run-${RUN_ID}/<exam-id>/research.json` containing exactly the
   verified facts for that cert (question count, time limit, passing score,
   domains, syllabus). One file per cert — do not write a shared array across
   all three certs. Child agents read this file directly with no filtering.

---

## Step 3.5 — Build concept corpus index

Before planning any questions, extract the concepts already covered by existing
exams for each selected certification. This prevents the planning agent from
repeating concepts that are already well-tested.

```bash
python3 - <<'EOF'
import json, glob, sys

cert_id = sys.argv[1]  # e.g. "aws-ml-engineer-associate"
concepts = []
for path in sorted(glob.glob(f"exams/{cert_id}/exam-*.json")):
    d = json.load(open(path))
    for q in d.get("questions", []):
        stem = q.get("stem", "")[:120]
        domain = q.get("domain", "")
        concepts.append({"file": path.split("/")[-1], "domain": domain, "stem_preview": stem})

print(json.dumps(concepts, indent=2))
EOF
python3 - aws-ml-engineer-associate  # replace with actual cert id
```

Pass the resulting concept list to the planning agent in step 4 as
`existing_concepts`. The planning agent must not produce a ledger row whose
concept duplicates an entry in `existing_concepts`.

---

## Step 4 — Planning agent (high reasoning)

The parent spawns one planning agent per **10-question chunk**, sequentially.
Each chunk agent receives:
- `/tmp/exam-run-${RUN_ID}/<exam-id>/research.json` — cert-specific research
  written by the parent after step 3 (one file per cert, no filtering needed)
- `/tmp/exam-run-${RUN_ID}/<exam-id>/existing-concepts.json` — corpus index
  written by the parent after step 3.5
- The question ID range for this chunk (e.g., `q01–q10`, `q11–q20`)
- `prior_planned_concepts`: the `concept` values from all chunks completed so
  far (empty list for the first chunk)

**This agent produces:** a 10-row (or fewer for the last chunk) ledger chunk
written to `/tmp/exam-run-${RUN_ID}/<exam-id>/ledger-chunk-NN.json`.

After all chunks complete, the parent concatenates them into `ledger.json` and
writes a copy to `automation/ledgers/<cert-id>-exam-NN-ledger.json`. No
subagent is needed for assembly — the parent does this directly.

Each chunk agent must not write stems, distractors, or exam JSON.

### Ledger format

Each row is a JSON object. Write the full array to file:

```json
[
  {
    "id": "q01",
    "domain": "preparing-data",
    "concept": "SageMaker Processing job for data transformation",
    "scenario": "An ML engineer must run a PySpark cleaning script on a 500 GB raw S3 dataset and write the output to a separate S3 prefix before training begins.",
    "decisive_constraint": "The job output must be logged and reproducible for audit.",
    "target_misconception": "Candidates confuse Processing jobs (arbitrary managed compute) with Batch Transform (inference-only) or Data Wrangler (visual GUI, not scriptable at scale).",
    "correct_answer": "Run a SageMaker Processing job using ProcessingInput/Output channels.",
    "distractor_1": "Use Batch Transform — wrong because Batch Transform runs model inference, not arbitrary data transformation scripts.",
    "distractor_2": "Use a real-time endpoint — wrong because endpoints serve live predictions, not offline ETL workloads.",
    "distractor_3": "Register the raw CSV as a model package — wrong because model packages store model artifacts, not input datasets.",
    "reference_url": "https://docs.aws.amazon.com/sagemaker/latest/dg/processing-job.html",
    "not_a_variant_of": "No prior question in this exam or in existing_concepts covers Processing job setup."
  }
]
```

### Ledger quality gates (apply before handing off to step 5)

- **Concept uniqueness:** no `concept` value may duplicate or closely paraphrase
  any entry in `existing_concepts` (from step 3.5) or `prior_planned_concepts`
  (from earlier chunks in this run) or any earlier row in this chunk. Each
  concept must appear exactly once across the whole exam.
- **Scenario specificity:** `scenario` must be one concrete sentence naming a
  specific service, feature, metric, or constraint. "A team needs to process
  data" is not acceptable. "An engineer must clean a 500 GB Parquet dataset
  stored in S3 before training" is acceptable.
- **Decisive constraint is specific:** `decisive_constraint` must reference an
  actual property of the scenario (an audit requirement, a latency threshold,
  a governance rule). Generic phrases like "the decision can be reproduced from
  logged inputs and outputs" are not acceptable — they do not distinguish this
  question from any other.
- **Distractors are wrong for different reasons:** the three `distractor_*`
  fields must each name a different service or misunderstanding and state
  "wrong because X" for a distinct technical reason.
- **`target_misconception` is specific:** it must name the exact conceptual
  confusion the question exploits — not "candidates may not know this feature".
- **No constraint rotation:** the three `decisive_constraint` phrases across
  the ledger must not be a mechanical rotation of 2–3 boilerplate sentences.
- **Reference URL diversity:** no single URL may appear more than 4 times.
- **Answer letter distribution:** aim for roughly equal distribution across A/B/C/D
  within this chunk. The parent checks the full distribution on the assembled
  `ledger.json` before spawning stem writers — if any letter exceeds 45% of
  all single-select questions, the parent adjusts the affected rows before assembly.
- **Row count:** exactly 10 rows, or the remainder for the final chunk (e.g.,
  5 rows if the exam has 65 questions and this is chunk 7).

Write the chunk to its artifact path once it passes all gates above. The
parent proceeds to the next chunk after reading the artifact. Stem writers
(step 5) are not spawned until the parent has assembled the full `ledger.json`
from all chunks.

---

## Step 5 — Stem writer (high / medium-high reasoning)

**This agent receives:** a single ledger row (one JSON object from step 4).

**This agent produces:** the `stem`, `correct_answer_text` (full sentence, not
a letter), and `explanation` fields for that question.

### Instructions

1. Read the ledger row. The `scenario` sentence is your starting point — expand
   it into a stem that gives a candidate exactly the information they need to
   select the correct answer, and no more. Do not add sentences that do not
   affect the answer.
2. Use `target_misconception` to frame the scenario around the specific
   conceptual confusion being tested. The situation should make the wrong
   options feel plausible to a candidate who holds that misconception.
3. Write the correct answer as a complete, standalone sentence.
4. Write the explanation. One `\n\n`-separated paragraph per option, each
   starting with a bold option label (`**A**`, `**B**`, etc.). For each option:
   - Correct option: explain the mechanism that makes it correct, naming the
     specific service, API, or behaviour.
   - Wrong options: name the specific reason this option fails in this scenario.
     "It applies a related feature in a way the documentation does not support"
     is not acceptable.
5. End the explanation with a markdown link to `reference_url`.

### Multi-select independence check

For every `multiple`-type question, before finalising, write this sentence:

> "A candidate who knows [Concept A] but not [Concept B] will select
> [option X] correctly but miss [option Y] because ___."

If you cannot fill the blank with a specific technical reason, the question
fails. Rewrite it so both correct answers are independently testable.

### Reference content verification

After writing the explanation:

1. Open the `reference_url`.
2. Find the specific passage, table, or code example on that page that supports
   the correct answer.
3. If you cannot find direct support, either fix the answer or replace the
   reference with a page that does support it.
4. `check_links.py` only confirms the URL is live — reference *content*
   verification is this agent's responsibility.

---

## Step 6 — Distractor writer (low reasoning)

**This agent receives:** the fixed stem, the fixed correct answer text, the
fixed explanation from step 5, and the `target_misconception` from the ledger
row.

**This agent must not alter** the stem, correct answer, or explanation under
any circumstances. Its only task is to produce three distractors.

### Instructions

For each distractor:

1. State the option text (a plausible wrong answer a candidate holding the
   `target_misconception` might choose).
2. State "wrong because X" — a single specific technical reason this option
   fails in this scenario.

Distractors must be wrong for **different** reasons. Do not produce two
distractors that are wrong for the same reason stated in different words.

Do not recycle distractor text from other questions in the ledger or from
existing exams.

---

## Step 7 — JSON assembler (low reasoning)

**This agent receives:** the stem, correct answer, explanation, and distractors
for all questions in the exam.

**This agent must not alter** any question wording, explanation text, or answer
content. Its only task is to serialise the inputs into a valid exam JSON file
at the correct path (`exams/<cert-id>/exam-NN.json`).

Follow the JSON schema in `EXAM_GENERATION_GUIDE.md` exactly. Write the file
and report the path.

---

## Step 8 — Validation and routing

**This agent receives:** the exam JSON path.

Run the four validators in order:

```bash
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

After running, produce a **structured failure list** in this format:

```json
[
  {
    "qid": "q03",
    "check": "check_semantic_quality",
    "category": "semantic",
    "message": "boilerplate wrong-option explanation in option B"
  },
  {
    "qid": "q17",
    "check": "validate",
    "category": "structural",
    "message": "reference field is a bare URL, not a markdown link"
  }
]
```

**Routing:**
- Items with `"category": "structural"` → send to **step 9** (structural fixer).
  Includes: validate.py failures, check_links.py failures, answer-distribution
  failures from check_semantic_quality.py.
- Items with `"category": "semantic"` → send to **step 10** (semantic fixer).
  Includes: duplicate/near-duplicate stems, boilerplate explanations, recycled
  options, low reference relevance scores.

If the failure list is empty, all validators passed — proceed to step 11.

If this is iteration 5 and failures remain, do not iterate further. Post a PR
comment listing the unresolved failures and stop the run.

---

## Step 9 — Structural fixer (medium reasoning)

**This agent receives:** the structural failure list and the exam JSON.

**Anti-drift rule:** fix only the fields identified in each failure item. Do
not modify any question's `stem`, `explanation`, or correct-answer text unless
the failure message explicitly identifies that field as malformed. Quietly
rewriting high-reasoning output to match a pattern is a disqualifying failure.

Permitted fixes:
- `reference` field: reformat as markdown link, or replace with a live URL
- Answer letter distribution: reshuffle option ordering and update `correct`
  letter — do not change option text
- Schema fields: add missing required fields with correct values
- Forbidden option phrases: reword only the specific option flagged

After fixing, report which fields were changed and return the corrected JSON
to step 8 for re-validation.

---

## Step 10 — Semantic fixer (high reasoning)

**This agent receives:** the semantic failure list and the full text of each
failing question.

For each failing question:

1. Read the failure message carefully.
2. Read the original ledger row for that question.
3. Rewrite the question from scratch using the ledger row — new scenario
   sentence, new options, same concept and reference URL.
4. Apply the full stem-writer discipline from step 5.
5. Return the rewritten question to step 6 (distractor writer), then step 7
   (JSON assembler), before re-entering step 8.

Do not patch individual words. A cosmetic rewrite produces the same failure on
the next iteration.

---

## Content rules (shared reference)

All stem-writing and distractor-writing agents must follow these rules. The
orchestrator should pass this section to steps 5 and 6 as part of their
context.

Every question must have:

- **A concrete scenario stem** — named service, named feature, observable
  symptom, specific error, architectural constraint, or measurable tradeoff.
  No "a team needs to make a design decision about X".
- **Context that matters** — every sentence before the question mark must
  change the correct answer or eliminate at least one distractor. If it does
  neither, remove it.
- **Four distinct, plausible distractors** — wrong for *different* specific
  reasons, not recycled from another question, not obviously absurd.
- **Explanation format** — one `\n\n`-separated paragraph per option, each
  starting with a bold label: `**A** ...\n\n**B** ...\n\n**C** ...\n\n**D** ...`
- **Wrong-option explanations that name specifics** — state the actual
  service, feature, API, or constraint and explain precisely why it fails.
- **A topic-specific reference URL** — the documentation page that directly
  covers this question's concept. Not a provider landing page. Not the same
  URL as the previous five questions.

### Human readability test

This PR will be reviewed by a human. Before finalising each question:

- Does the stem describe a situation a real practitioner could encounter?
- Do the options make sense as distinct, plausible choices within that
  situation?
- Does the explanation teach something, or does it just assert that an answer
  is correct?

If any of those answers is "no", rewrite before moving on.

---

## Step 11 — Update catalog.json

Add the new exam path to the `exams` array for each chosen certification in
`exams/catalog.json`. Run `python3 scripts/validate.py --catalog` to confirm.

---

## Step 12 — Commit, push, open PR

```bash
git checkout -b auto/batch-exams-YYYYMMDD
git add exams/<cert-1>/exam-NN.json exams/<cert-2>/exam-NN.json exams/<cert-3>/exam-NN.json exams/catalog.json
git commit -m "Add generated mock exams for <cert-1>, <cert-2>, <cert-3>"
git push origin auto/batch-exams-YYYYMMDD
gh pr create --title "Add scheduled mock exams for <cert-1>, <cert-2>, <cert-3>" --body "..."
```

**PR body must include:**

- Chosen certifications and their existing mock counts at selection time
- For each certification: verified official question count, source URL, any
  conflict between sources
- Research basis: sources used for syllabus, topic weights, difficulty
- Final question count, domain distribution, and difficulty blueprint per exam
- Confidence rating (high / medium / low) per exam and reasons for lower
  confidence
- Confirmation that all four validators passed
- Confirmation of semantic quality: no duplicate/near-duplicate stems, no
  scenario-pool rotation, no rotating filler, no concept repetition, no
  injected irrelevant context, no meta-filler multi-select answers,
  non-gameable answer distribution, per-option explanation format, specific
  wrong-option explanations, topic-specific reference URLs
- Confirmation of human readability: every stem describes a real situation a
  practitioner could encounter; every option is a distinct, plausible choice;
  every explanation teaches the underlying concept
- Confirmation of reference content verification: for each question the correct
  answer is directly supported by content on the linked reference page

---

## Guardrails

- Never force-push.
- Never start a new batch while an open generated-exam PR has unaddressed
  review feedback.
- Never mirror existing exam quirks that conflict with `EXAM_GENERATION_GUIDE.md`.
- Never modify existing exam content (except `catalog.json`).
- If the selected certification is marked `"retired": true`, re-roll.
- If a PR for the same certification was already opened today, re-roll.
- **The official guide (`examDetails.guideUrl`) overrides everything.** If
  the guide contradicts this prompt, the catalog syllabus, or existing repo
  exams on any factual point (question count, domain name, domain weight,
  passing score), follow the guide and document the discrepancy in the PR body.

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
- Confirmation that all four validators passed
- Any blockers or assumptions
