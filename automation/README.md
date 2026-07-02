# Automation

Agent runbooks for scheduled automation against this repo. Each prompt is a
self-contained Markdown file that an agent runtime (currently OpenClaw/GPT-5.5)
reads after cloning the repo.

## Structure

```
automation/
  prompts/
    generate-exams.md   — scheduled exam generation (3 new exams per run)
    audit-exams.md      — scheduled exam audit (quality pass on oldest exams)
```

## How prompts are used

1. The cron runner checks out this repo
2. It reads the prompt file from `automation/prompts/<name>.md`
3. The prompt is the authoritative runbook — the runner's own system prompt
   is minimal ("read and follow `automation/prompts/<name>.md`")
4. All validation scripts referenced in prompts live in `scripts/`

## Adding a new automation prompt

- Create `automation/prompts/<name>.md`
- Reference only scripts that exist in `scripts/`
- Test the prompt manually before wiring it to a cron schedule
- Update this README with the new entry

## Validation scripts used by agents

| Script | Purpose |
|--------|---------|
| `scripts/validate.py` | Structural/schema validation |
| `scripts/check_links.py` | Live reference URL liveness check |
| `scripts/check_semantic_quality.py` | Template/boilerplate detection |
| `scripts/check_reference_relevance.py` | Embedding-based reference content relevance |

Agents must run all four validators and fix every finding before opening a PR.

`check_reference_relevance.py` requires extra dependencies:
```
pip install sentence-transformers requests beautifulsoup4 numpy
```

**Modes:**

| Flag | Model | Size | Speed | Use when |
|------|-------|------|-------|----------|
| _(none)_ | all-MiniLM-L6-v2 (bi-encoder) | ~90 MB | fast | agent pipeline default |
| `--cross-encoder` | cross-encoder/ms-marco-MiniLM-L-6-v2 | ~66 MB | 10-20× slower | deep audit, spot-checking suspect questions |

The bi-encoder encodes query and page chunks independently and compares via
cosine similarity. The cross-encoder encodes both together in a single forward
pass (full attention), eliminating vocabulary bleed — it distinguishes "Delta
Lake overview page" from "page that answers this specific Delta question" where
the bi-encoder cannot. Scores are logits (not cosine), so thresholds differ.

**Agent pipeline:** use the default bi-encoder with `--strict`. Fast enough for
full-exam runs before opening a PR.

**Manual investigation:** add `--cross-encoder` when the bi-encoder passes but
something looks off, or to spot-check exams with many questions pointing at the
same broad reference URL.

Run `--warn-only --glob "exams/**/*.json"` to calibrate thresholds against the
full exam corpus before tightening `HARD_FAIL_THRESHOLD` or `WARN_THRESHOLD`
(or `XE_HARD_FAIL_THRESHOLD` / `XE_WARN_THRESHOLD` for cross-encoder mode).

**Model selection:** `--model <name>` overrides the model for whichever mode is
active. Bi-encoder upgrade: `all-mpnet-base-v2` (~420 MB, better accuracy).
Cross-encoder upgrade: `cross-encoder/ms-marco-MiniLM-L-12-v2` (~130 MB).

**Experimental variant scripts** (not used by agents — for calibration only):
- `scripts/check_reference_relevance_bge.py` — BGE large bi-encoder variant
- `scripts/check_reference_relevance_crossencoder.py` — standalone cross-encoder
- `scripts/compare_relevance_models.py` — side-by-side score table across all three

Calibration finding: BGE adds no discrimination over MiniLM on this corpus
(0 flags across 45 human-authored questions). Cross-encoder detects broad
reference pages (intro/index URLs reused across many questions) that bi-encoders
miss due to vocabulary overlap. Use MiniLM in the pipeline; reach for
`--cross-encoder` for targeted investigation.
