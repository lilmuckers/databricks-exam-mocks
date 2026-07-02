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
| `scripts/check_links.py` | Live reference URL checking |
| `scripts/check_semantic_quality.py` | Template/boilerplate detection |
