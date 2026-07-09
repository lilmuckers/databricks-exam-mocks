#!/usr/bin/env python3
"""
Exam JSON validator — checks all exam files and catalog.json against the
schemas defined in schemas/exam.schema.json and schemas/catalog.schema.json.

Usage:
    python3 scripts/validate.py              # validate everything
    python3 scripts/validate.py --catalog    # catalog only
    python3 scripts/validate.py --exam path  # single exam file
    python3 scripts/validate.py --fix        # auto-fix known safe issues
    python3 scripts/validate.py --json       # output results as JSON

No external dependencies required — uses only Python stdlib.
Optionally uses jsonschema if installed: pip install jsonschema
"""

import sys
import os
import json
import re
import glob
import argparse
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(ROOT, "exams", "catalog.json")
EXAM_SCHEMA_PATH = os.path.join(ROOT, "schemas", "exam.schema.json")
CATALOG_SCHEMA_PATH = os.path.join(ROOT, "schemas", "catalog.schema.json")

SEVERITY_ERROR = "error"
SEVERITY_WARN  = "warning"

# ── Colour output ──────────────────────────────────────────────────────────────
USE_COLOR = sys.stdout.isatty()
RED    = "\033[31m" if USE_COLOR else ""
YELLOW = "\033[33m" if USE_COLOR else ""
GREEN  = "\033[32m" if USE_COLOR else ""
CYAN   = "\033[36m" if USE_COLOR else ""
BOLD   = "\033[1m"  if USE_COLOR else ""
RESET  = "\033[0m"  if USE_COLOR else ""


class Issue:
    __slots__ = ("severity", "file", "path", "message")

    def __init__(self, severity, file, path, message):
        self.severity = severity
        self.file = file
        self.path = path
        self.message = message

    def __str__(self):
        color = RED if self.severity == SEVERITY_ERROR else YELLOW
        label = f"{color}{self.severity.upper()}{RESET}"
        loc = f"{CYAN}{self.file}{RESET}" + (f" [{self.path}]" if self.path else "")
        return f"  {label}  {loc}\n        {self.message}"

    def to_dict(self):
        return {"severity": self.severity, "file": self.file,
                "path": self.path, "message": self.message}


class Validator:
    def __init__(self):
        self.issues: list[Issue] = []
        self.catalog = None
        self.known_platform_ids: set[str] = set()
        self.known_domain_ids: set[str] = set()
        self.fix_mode = False

    def err(self, file, path, msg):
        self.issues.append(Issue(SEVERITY_ERROR, file, path, msg))

    def warn(self, file, path, msg):
        self.issues.append(Issue(SEVERITY_WARN, file, path, msg))

    # ── Catalog validation ─────────────────────────────────────────────────────

    def validate_catalog(self):
        rel = os.path.relpath(CATALOG_PATH, ROOT)

        try:
            with open(CATALOG_PATH) as f:
                self.catalog = json.load(f)
        except FileNotFoundError:
            self.err(rel, "", f"catalog.json not found at {CATALOG_PATH}")
            return
        except json.JSONDecodeError as e:
            self.err(rel, "", f"JSON parse error: {e}")
            return

        c = self.catalog

        # ── Top-level required keys ──
        for key in ("platforms", "domainGroups", "certifications"):
            if key not in c:
                self.err(rel, "", f"Missing required top-level key: '{key}'")

        # ── Platforms ──
        seen_platform_ids = set()
        for i, p in enumerate(c.get("platforms", [])):
            path = f"platforms[{i}]"
            pid = p.get("id", "")
            if not pid:
                self.err(rel, path, "Missing 'id'")
            elif not re.match(r'^[a-z][a-z0-9-]+$', pid):
                self.err(rel, path, f"id '{pid}' must be kebab-case")
            if pid in seen_platform_ids:
                self.err(rel, path, f"Duplicate platform id '{pid}'")
            seen_platform_ids.add(pid)
            color = p.get("color", "")
            if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
                self.err(rel, path, f"color '{color}' must be a 6-digit hex color like #FF3621")
            for field in ("name", "logo"):
                if not p.get(field):
                    self.err(rel, path, f"Missing required field '{field}'")
        self.known_platform_ids = seen_platform_ids

        # ── Domain groups ──
        seen_group_ids = set()
        seen_domain_ids = set()
        for i, g in enumerate(c.get("domainGroups", [])):
            path = f"domainGroups[{i}]"
            gid = g.get("id", "")
            if not gid:
                self.err(rel, path, "Missing 'id'")
            elif not re.match(r'^[a-z][a-z0-9-]+$', gid):
                self.err(rel, path, f"id '{gid}' must be kebab-case")
            if gid in seen_group_ids:
                self.err(rel, path, f"Duplicate domainGroup id '{gid}'")
            seen_group_ids.add(gid)

            for field in ("name", "icon", "color"):
                if not g.get(field):
                    self.err(rel, path, f"Missing required field '{field}'")
            color = g.get("color", "")
            if color and not re.match(r'^#[0-9A-Fa-f]{6}$', color):
                self.err(rel, path, f"color '{color}' must be a 6-digit hex color")

            for j, did in enumerate(g.get("domains", [])):
                dpath = f"{path}.domains[{j}]"
                if not re.match(r'^[a-z][a-z0-9-]+$', did):
                    self.err(rel, dpath, f"Domain id '{did}' must be kebab-case")
                if did in seen_domain_ids:
                    self.err(rel, dpath, f"Domain id '{did}' appears in multiple groups")
                seen_domain_ids.add(did)

            if not g.get("domains"):
                self.warn(rel, path, f"domainGroup '{gid}' has no domain IDs")

        self.known_domain_ids = seen_domain_ids

        # ── Certifications ──
        seen_cert_ids = set()
        for i, cert in enumerate(c.get("certifications", [])):
            path = f"certifications[{i}]"
            cid = cert.get("id", "")
            if not cid:
                self.err(rel, path, "Missing 'id'")
                continue

            if cid in seen_cert_ids:
                self.err(rel, path, f"Duplicate cert id '{cid}'")
            seen_cert_ids.add(cid)

            # Platform reference
            plat = cert.get("platform", "")
            if plat not in self.known_platform_ids:
                self.err(rel, path, f"platform '{plat}' not in platforms list")

            # Required string fields
            for field in ("name", "shortName", "badge", "description"):
                if not cert.get(field):
                    self.err(rel, path, f"Missing required field '{field}'")

            # Color
            color = cert.get("color", "")
            if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
                self.err(rel, path, f"color '{color}' must be a 6-digit hex color")

            # Badge format
            badge = cert.get("badge", "")
            if badge and not re.match(r'^[A-Z0-9-]{2,8}$', badge):
                self.err(rel, path, f"badge '{badge}' must be 2-8 uppercase alphanumeric chars")

            # examDetails
            ed = cert.get("examDetails", {})
            if not ed:
                self.err(rel, path, "Missing 'examDetails'")
            else:
                for field, lo, hi in [("questions", 40, 100), ("timeLimit", 30, 180), ("passingScore", 60, 80)]:
                    v = ed.get(field)
                    if v is None:
                        self.err(rel, f"{path}.examDetails", f"Missing '{field}'")
                    elif not isinstance(v, int) or not (lo <= v <= hi):
                        self.err(rel, f"{path}.examDetails", f"'{field}' must be int {lo}–{hi}, got {v!r}")

            # Syllabus
            if not cert.get("syllabus"):
                self.warn(rel, path, f"cert '{cid}' has no syllabus — AI generators need this to produce accurate questions")

            # Exam file paths
            exams = cert.get("exams", [])
            expected_pattern = re.compile(r'^exams/[a-z][a-z0-9-]+/exam-[0-9]+\.json$')
            for j, epath in enumerate(exams):
                epath_full = os.path.join(ROOT, epath)
                if not expected_pattern.match(epath):
                    self.err(rel, f"{path}.exams[{j}]", f"path '{epath}' doesn't match pattern exams/<cert-id>/exam-NN.json")
                if not os.path.exists(epath_full):
                    self.err(rel, f"{path}.exams[{j}]", f"file not found: {epath}")

            # retired consistency
            if cert.get("retired") and not cert.get("retiredDate"):
                self.warn(rel, path, f"cert '{cid}' has retired=true but no retiredDate")

    # ── Exam file validation ───────────────────────────────────────────────────

    def validate_exam(self, filepath: str):
        rel = os.path.relpath(filepath, ROOT)

        try:
            with open(filepath) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.err(rel, "", f"JSON parse error: {e}")
            return

        # ── meta ──
        if "meta" not in data:
            self.err(rel, "", "Missing top-level 'meta' key")
            return
        if "questions" not in data:
            self.err(rel, "", "Missing top-level 'questions' key")
            return

        extra_keys = set(data.keys()) - {"meta", "questions"}
        if extra_keys:
            self.warn(rel, "", f"Unexpected top-level keys: {sorted(extra_keys)}")

        meta = data["meta"]
        self._validate_meta(rel, meta, filepath)

        questions = data["questions"]
        if not isinstance(questions, list):
            self.err(rel, "questions", "Must be an array")
            return

        if len(questions) < 40:
            self.err(rel, "questions", f"Only {len(questions)} questions — minimum is 40")
        elif len(questions) > 100:
            self.err(rel, "questions", f"{len(questions)} questions — maximum is 100")

        # totalQuestions consistency
        total = meta.get("totalQuestions")
        if isinstance(total, int) and total != len(questions):
            self.err(rel, "meta.totalQuestions",
                     f"totalQuestions={total} but found {len(questions)} questions in array")

        # Validate each question
        seen_ids = set()
        meta_domain_ids = {d["id"] for d in meta.get("domains", []) if isinstance(d, dict)}
        for i, q in enumerate(questions):
            self._validate_question(rel, i, q, seen_ids, meta_domain_ids)

        # Difficulty distribution
        if questions:
            diff_counts = Counter(q.get("difficulty") for q in questions if isinstance(q, dict))
            total_q = sum(diff_counts.values())
            hard_pct = (diff_counts.get("hard", 0) / total_q * 100) if total_q else 0
            easy_pct = (diff_counts.get("easy", 0) / total_q * 100) if total_q else 0
            if hard_pct < 10:
                self.warn(rel, "questions", f"Only {hard_pct:.0f}% hard questions — target ≥20%")
            if easy_pct < 10:
                self.warn(rel, "questions", f"Only {easy_pct:.0f}% easy questions — target ≥20%")

    def _validate_meta(self, rel, meta, filepath):
        required = ["id", "certification", "certificationName", "title", "version",
                    "timeLimit", "passingScore", "totalQuestions", "domains", "difficulty", "status"]
        for field in required:
            if field not in meta:
                self.err(rel, f"meta.{field}", f"Missing required field '{field}'")

        # id pattern
        mid = meta.get("id", "")
        if mid and not re.match(r'^[a-z][a-z0-9-]+-exam-[0-9]{2}$', mid):
            self.err(rel, "meta.id", f"id '{mid}' must match pattern <cert-code>-exam-NN, e.g. 'dea-exam-01'")

        # title pattern
        title = meta.get("title", "")
        if title and not re.match(r'^[A-Z][A-Z0-9-]+-[0-9]+: .{5,}$', title):
            self.err(rel, "meta.title",
                     f"title '{title}' must match '<CODE>-N: Description', e.g. 'DBX-DEA-1: Lakehouse Fundamentals'")

        # version
        ver = meta.get("version", "")
        if ver and not re.match(r'^[0-9]+\.[0-9]+$', str(ver)):
            self.err(rel, "meta.version", f"version '{ver}' must be like '1.0'")

        # Numeric ranges
        for field, lo, hi in [("timeLimit", 30, 180), ("passingScore", 60, 80), ("totalQuestions", 40, 100)]:
            v = meta.get(field)
            if v is not None and (not isinstance(v, int) or not (lo <= v <= hi)):
                self.err(rel, f"meta.{field}", f"Must be int {lo}–{hi}, got {v!r}")

        # Enums
        if meta.get("difficulty") not in ("easy", "medium", "hard"):
            self.err(rel, "meta.difficulty",
                     f"Must be 'easy', 'medium', or 'hard', got {meta.get('difficulty')!r}")
        if meta.get("status") not in ("available", "coming-soon", "archived"):
            self.err(rel, "meta.status",
                     f"Must be 'available', 'coming-soon', or 'archived', got {meta.get('status')!r}")

        # domains
        domains = meta.get("domains", [])
        if not isinstance(domains, list) or len(domains) < 2:
            self.err(rel, "meta.domains", "Must be an array with at least 2 items")
        else:
            weight_sum = 0
            seen_domain_ids = set()
            for j, d in enumerate(domains):
                dpath = f"meta.domains[{j}]"
                if not isinstance(d, dict):
                    self.err(rel, dpath, "Must be an object with id, name, weight")
                    continue
                did = d.get("id", "")
                if not re.match(r'^[a-z][a-z0-9-]+$', did):
                    self.err(rel, dpath, f"id '{did}' must be kebab-case")
                if did in seen_domain_ids:
                    self.err(rel, dpath, f"Duplicate domain id '{did}'")
                seen_domain_ids.add(did)

                # Cross-reference: must exist in catalog domainGroups
                if self.known_domain_ids and did and did not in self.known_domain_ids:
                    self.err(rel, dpath,
                             f"Domain id '{did}' not found in catalog.json domainGroups — "
                             "add it to the most relevant group before using it in an exam")

                w = d.get("weight")
                if not isinstance(w, int) or w < 1 or w > 60:
                    self.err(rel, dpath, f"weight must be int 1–60, got {w!r}")
                else:
                    weight_sum += w

            if weight_sum != 100:
                self.err(rel, "meta.domains",
                         f"Domain weights sum to {weight_sum} — must equal exactly 100")

    def _validate_question(self, rel, idx, q, seen_ids, meta_domain_ids):
        path = f"questions[{idx}]"
        if not isinstance(q, dict):
            self.err(rel, path, "Question must be an object")
            return

        # Required fields (schema v2: correct/explanation moved to options[])
        required = ["id", "domain", "type", "difficulty", "stem", "options", "reference"]
        for field in required:
            if field not in q:
                self.err(rel, f"{path}.{field}", f"Missing required field '{field}'")

        # id
        qid = q.get("id", "")
        if qid:
            if not re.match(r'^q[0-9]{2,3}$', qid):
                self.err(rel, f"{path}.id", f"id '{qid}' must match q01, q02, … q999")
            if qid in seen_ids:
                self.err(rel, f"{path}.id", f"Duplicate question id '{qid}'")
            seen_ids.add(qid)

        # domain
        domain = q.get("domain", "")
        if domain:
            if not re.match(r'^[a-z][a-z0-9-]+$', domain):
                self.err(rel, f"{path}.domain", f"domain '{domain}' must be kebab-case")
            if self.known_domain_ids and domain not in self.known_domain_ids:
                self.err(rel, f"{path}.domain",
                         f"domain '{domain}' not in catalog.json domainGroups — "
                         "add it to the appropriate group first")
            if meta_domain_ids and domain not in meta_domain_ids:
                self.err(rel, f"{path}.domain",
                         f"domain '{domain}' not in meta.domains — add it there with a weight")

        # type
        qtype = q.get("type")
        if qtype not in ("single", "multiple"):
            self.err(rel, f"{path}.type",
                     f"type must be 'single' or 'multiple', got {qtype!r} — "
                     "('easy'/'hard' in type field is a common AI generation mistake)")

        # difficulty
        if q.get("difficulty") not in ("easy", "medium", "hard"):
            self.err(rel, f"{path}.difficulty",
                     f"difficulty must be 'easy', 'medium', or 'hard', got {q.get('difficulty')!r}")

        # stem
        stem = q.get("stem", "")
        if len(stem) < 20:
            self.err(rel, f"{path}.stem", f"stem too short ({len(stem)} chars) — minimum 20")
        if qtype == "multiple" and not re.search(r'\(select|choose|pick', stem, re.IGNORECASE):
            self.warn(rel, f"{path}.stem",
                      "Multiple-select stem should include '(Select TWO)' / '(Choose THREE)' etc.")

        # options (schema v2: each option carries correct bool + explanation)
        options = q.get("options", [])
        if not isinstance(options, list) or not (4 <= len(options) <= 6):
            self.err(rel, f"{path}.options",
                     f"Must have 4–6 options, got {len(options) if isinstance(options, list) else 'non-array'}")
        else:
            seen_opt_ids = []
            correct_count = 0
            qid = q.get("id", f"q{idx+1:02d}")
            for k, opt in enumerate(options):
                opath = f"{path}.options[{k}]"
                if not isinstance(opt, dict):
                    self.err(rel, opath, "Option must be an object"); continue

                # id: schema v2 format qNNaN
                oid = opt.get("id", "")
                expected_id = f"{qid}a{k+1}"
                if not re.match(r'^q[0-9]{2,3}a[0-9]+$', oid):
                    self.err(rel, opath,
                             f"Option id '{oid}' must match schema v2 format (e.g. '{expected_id}')")
                if oid in seen_opt_ids:
                    self.err(rel, opath, f"Duplicate option id '{oid}'")
                seen_opt_ids.append(oid)

                text = opt.get("text", "")
                if not text:
                    self.err(rel, opath, "Missing 'text'")

                # correct flag
                if "correct" not in opt:
                    self.err(rel, opath, "Missing 'correct' (boolean) — schema v2 requires per-option correctness flag")
                elif not isinstance(opt.get("correct"), bool):
                    self.err(rel, opath, f"'correct' must be boolean, got {type(opt.get('correct')).__name__}")
                elif opt["correct"]:
                    correct_count += 1

                # Anti-patterns in option text
                bad_phrases = ["all of the above", "none of the above", "both a and b",
                               "all the above", "none of these"]
                for phrase in bad_phrases:
                    if phrase in text.lower():
                        self.err(rel, opath,
                                 f"Option text contains banned phrase '{phrase}' — use specific answer choices")

            # Correct count vs type consistency
            if correct_count == 0:
                self.err(rel, f"{path}.options", "No option has correct=true — every question needs at least one correct answer")
            if qtype == "single" and correct_count != 1:
                self.err(rel, f"{path}.options",
                         f"type='single' must have exactly 1 correct option, got {correct_count}")
            elif qtype == "multiple" and correct_count < 2:
                self.err(rel, f"{path}.options",
                         f"type='multiple' must have ≥2 correct options, got {correct_count}")

        # reference
        ref = q.get("reference", "")
        if not ref:
            self.warn(rel, f"{path}.reference", "Missing 'reference' — every question should cite a doc section or concept")
        elif re.match(r'^https?://', ref):
            self.warn(rel, f"{path}.reference", f"'reference' is a bare URL — use markdown link format: [Title](url)")
        elif not re.match(r'^\[.+\]\(https?://.+\)$', ref.strip()):
            self.warn(rel, f"{path}.reference", f"'reference' should be a markdown link: [Title](url)")

    # ── Full-suite validation ──────────────────────────────────────────────────

    def validate_all(self):
        self.validate_catalog()

        # Find all exam files
        pattern = os.path.join(ROOT, "exams", "**", "exam-*.json")
        exam_files = sorted(glob.glob(pattern, recursive=True))

        if not exam_files:
            self.warn("exams/", "", "No exam files found matching exams/**/exam-*.json")

        for filepath in exam_files:
            self.validate_exam(filepath)

    # ── Auto-fix ───────────────────────────────────────────────────────────────

    def autofix(self):
        """
        Auto-fix safe, deterministic issues:
        - type field set to 'easy'/'hard'/'medium' instead of 'single'/'multiple'
        - type='single' but multiple correct answers → change to 'multiple'
        - question id prefix like 'e1-q01' or 'e2-q01' → strip to 'q01'
        - multiple-select question missing '(Select N)' in stem → append it
        """
        pattern = os.path.join(ROOT, "exams", "**", "exam-*.json")
        exam_files = sorted(glob.glob(pattern, recursive=True))
        fixed_files = []
        COUNT_WORDS = {2: "TWO", 3: "THREE", 4: "FOUR"}

        for filepath in exam_files:
            rel = os.path.relpath(filepath, ROOT)
            try:
                with open(filepath) as f:
                    data = json.load(f)
            except Exception:
                continue

            changed = False
            for q in data.get("questions", []):
                qid = q.get("id", "")

                # Fix prefixed question IDs: e1-q01 → q01, e2-q03 → q03
                clean_id = re.sub(r'^e[0-9]+-', '', qid)
                if clean_id != qid and re.match(r'^q[0-9]{2,3}$', clean_id):
                    print(f"  FIX  {rel} {qid}: id '{qid}' → '{clean_id}'")
                    q["id"] = clean_id
                    changed = True

                # Fix type field containing difficulty value
                if q.get("type") in ("easy", "hard", "medium"):
                    old = q["type"]
                    q["type"] = "single"
                    print(f"  FIX  {rel} {q['id']}: type '{old}' → 'single'")
                    changed = True

                # Fix single with multiple correct options (schema v2: count from options[].correct)
                correct_opts = [o for o in q.get("options", []) if isinstance(o.get("correct"), bool) and o["correct"]]
                if q.get("type") == "single" and len(correct_opts) > 1:
                    q["type"] = "multiple"
                    print(f"  FIX  {rel} {q['id']}: type 'single' → 'multiple' ({len(correct_opts)} correct options)")
                    changed = True

                # Fix dict-format options: {"A": "text"} → [{id:"A", text:"text"}]
                if isinstance(q.get("options"), dict):
                    q["options"] = [{"id": k, "text": v} for k, v in sorted(q["options"].items())]
                    print(f"  FIX  {rel} {q.get('id','?')}: options dict → array")
                    changed = True

                # Add (Select N) to multiple-select stems that are missing it
                if q.get("type") == "multiple":
                    stem = q.get("stem", "")
                    n = len([o for o in q.get("options", []) if isinstance(o.get("correct"), bool) and o["correct"]])
                    if n >= 2 and not re.search(r'\(select|choose|pick', stem, re.IGNORECASE):
                        word = COUNT_WORDS.get(n, str(n))
                        q["stem"] = stem.rstrip() + f" (Select {word})"
                        print(f"  FIX  {rel} {q['id']}: appended '(Select {word})' to multi-select stem")
                        changed = True

            if changed:
                with open(filepath, "w") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                fixed_files.append(filepath)

        # Fix meta.domains to cover all domain IDs used in questions
        for filepath in exam_files:
            rel = os.path.relpath(filepath, ROOT)
            try:
                with open(filepath) as f:
                    data = json.load(f)
            except Exception:
                continue

            meta = data.get("meta", {})
            questions = data.get("questions", [])
            if not meta or not questions:
                continue

            meta_domain_ids = {d["id"] for d in meta.get("domains", []) if isinstance(d, dict)}
            # Count questions per domain
            q_domain_counts = Counter(
                q["domain"] for q in questions if isinstance(q, dict) and "domain" in q
            )
            missing = {d for d in q_domain_counts if d not in meta_domain_ids}
            if not missing:
                continue

            # Recompute weights from question counts
            total_qs = len(questions)
            all_domains = set(q_domain_counts.keys()) | meta_domain_ids
            new_domains = []
            for did in sorted(all_domains):
                count = q_domain_counts.get(did, 0)
                raw_weight = round(count / total_qs * 100)
                existing = next((d for d in meta.get("domains", []) if isinstance(d, dict) and d.get("id") == did), None)
                name = existing.get("name", did.replace("-", " ").title()) if existing else did.replace("-", " ").title()
                new_domains.append({"id": did, "name": name, "weight": max(1, raw_weight)})

            # Normalise weights to exactly 100
            total_weight = sum(d["weight"] for d in new_domains)
            if total_weight != 100:
                delta = 100 - total_weight
                new_domains[-1]["weight"] = max(1, new_domains[-1]["weight"] + delta)

            meta["domains"] = sorted(new_domains, key=lambda d: d["id"])
            data["meta"] = meta
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            print(f"  FIX  {rel}: meta.domains updated to include {sorted(missing)}")
            if filepath not in fixed_files:
                fixed_files.append(filepath)

        return fixed_files

    # ── Reporting ──────────────────────────────────────────────────────────────

    def summary(self, json_output=False):
        errors = [i for i in self.issues if i.severity == SEVERITY_ERROR]
        warnings = [i for i in self.issues if i.severity == SEVERITY_WARN]

        if json_output:
            print(json.dumps({
                "errors": len(errors),
                "warnings": len(warnings),
                "issues": [i.to_dict() for i in self.issues]
            }, indent=2))
            return len(errors) > 0

        if not self.issues:
            print(f"\n{GREEN}{BOLD}✓ All checks passed.{RESET}\n")
            return False

        # Group by file
        by_file = defaultdict(list)
        for issue in self.issues:
            by_file[issue.file].append(issue)

        for file, file_issues in sorted(by_file.items()):
            file_errors = sum(1 for i in file_issues if i.severity == SEVERITY_ERROR)
            file_warns = sum(1 for i in file_issues if i.severity == SEVERITY_WARN)
            summary_parts = []
            if file_errors:
                summary_parts.append(f"{RED}{file_errors} error{'s' if file_errors != 1 else ''}{RESET}")
            if file_warns:
                summary_parts.append(f"{YELLOW}{file_warns} warning{'s' if file_warns != 1 else ''}{RESET}")
            print(f"\n{BOLD}{file}{RESET}  ({', '.join(summary_parts)})")
            for issue in file_issues:
                print(str(issue))

        print()
        total_label = []
        if errors:
            total_label.append(f"{RED}{BOLD}{len(errors)} error{'s' if len(errors) != 1 else ''}{RESET}")
        if warnings:
            total_label.append(f"{YELLOW}{len(warnings)} warning{'s' if len(warnings) != 1 else ''}{RESET}")
        print(f"Total: {', '.join(total_label)}")

        if errors:
            print(f"\n{RED}Validation FAILED — fix errors before committing.{RESET}\n")
        else:
            print(f"\n{YELLOW}Validation passed with warnings.{RESET}\n")

        return len(errors) > 0


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Validate exam JSON files against schemas.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--catalog", action="store_true", help="Validate catalog.json only")
    group.add_argument("--exam", metavar="PATH", help="Validate a single exam file")
    parser.add_argument("--fix", action="store_true",
                        help="Auto-fix known safe issues (wrong type field, single+multi-correct)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    v = Validator()

    if args.fix:
        print(f"{BOLD}Auto-fixing known issues…{RESET}")
        fixed = v.autofix()
        if fixed:
            print(f"\n{GREEN}Fixed {len(fixed)} file(s). Re-running validation…{RESET}\n")
        else:
            print("Nothing to fix.\n")

    if args.catalog:
        v.validate_catalog()
    elif args.exam:
        v.validate_catalog()          # need catalog for domain cross-references
        v.validate_exam(os.path.abspath(args.exam))
    else:
        v.validate_all()

    had_errors = v.summary(json_output=args.json)
    sys.exit(1 if had_errors else 0)


if __name__ == "__main__":
    main()
