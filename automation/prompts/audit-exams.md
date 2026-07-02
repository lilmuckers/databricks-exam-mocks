# Databricks Exam Mocks: Scheduled Exam Auditor

Read this file from the cloned repo before taking any other action.

---

## Objective

Review the three oldest (by `meta.last_audited` or git commit date) exam files
in the repo, fix any quality issues found, and open a pull request.

> **Status: stub** — full runbook to be written. The structure mirrors
> `generate-exams.md`. See `automation/README.md` for conventions.

---

## Validators to run

```bash
python3 scripts/validate.py --exam <path>
python3 scripts/check_links.py --exam <path> --check-links --fields reference --no-cache --only-bad
python3 scripts/check_semantic_quality.py --exam <path>
```

---

## Branch naming

`auto/audit-exams-YYYYMMDD-HHMM`

---

## Guardrails

- Never modify more than three exam files per run.
- Never force-push.
- Never open a new audit PR while an open `auto/audit-exams-*` PR has
  unaddressed review feedback.
