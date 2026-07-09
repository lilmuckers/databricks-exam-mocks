#!/usr/bin/env python3
"""
Migrate all exam JSON files from v1 schema to v2 schema.

v1: question has top-level correct[], explanation (combined), type, options[{id,text}]
v2: question has options[{id, text, correct, explanation}]; correct/explanation removed
    from question level; type retained (derivable from correct count but kept for compat)

Option IDs: qNNaN (e.g. q01a1, q01a2) — letter index preserved (A→a1, B→a2, ...).

Usage:
    python3 scripts/migrate_v2_schema.py --dry-run    # report only, no writes
    python3 scripts/migrate_v2_schema.py --write      # migrate in place
    python3 scripts/migrate_v2_schema.py --exam path  # single file
    python3 scripts/migrate_v2_schema.py --cert name  # single cert dir

Exit code 0 even with flagged questions (those need manual follow-up).
"""

import json
import re
import sys
import glob
import argparse
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
EXAM_GLOB = str(ROOT / "exams" / "*" / "exam-*.json")

LETTER_TO_IDX = {c: i for i, c in enumerate("ABCDEF")}


# ── Explanation parsing ──────────────────────────────────────────────────────

def strip_verdict(text: str) -> str:
    """Strip leading 'is correct/incorrect because ' verdict clause if present."""
    # "is correct because ..." or "is incorrect because ..." at very start
    m = re.match(
        r"^is (?:correct|incorrect|wrong|not correct)(?:\s+because\s+|\s*[—–:]\s*)(.+)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if m:
        rest = m.group(1).strip()
        return rest[0].upper() + rest[1:] if rest else text
    # "Correct — ..." or "Incorrect: ..."
    m = re.match(
        r"^(?:correct|incorrect|wrong)\s*[—–:.-]\s*(.+)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if m:
        rest = m.group(1).strip()
        return rest[0].upper() + rest[1:] if rest else text
    return text


def correctness_from_text(text: str) -> bool | None:
    """Return True/False/None based on verdict language in the paragraph body."""
    t = text.lower()
    # Wrong signals
    if re.search(r"\bis (?:incorrect|wrong|not correct)\b", t):
        return False
    if re.search(r"^(?:incorrect|wrong)\b", t):
        return False
    # Correct signals
    if re.search(r"\bis correct\b", t):
        return True
    if re.search(r"^correct\b", t):
        return True
    return None


def parse_explanation(explanation: str, options: list, correct_letters: list) -> dict:
    """
    Parse a combined v1 explanation into per-option explanation strings.

    Returns:
        {
          "A": "explanation text for A",
          "B": "explanation text for B",
          ...
        }
    And a style: "per_option" | "mixed" | "single_block" | "multi_combined"
    """
    paragraphs = [p.strip() for p in explanation.split("\n\n") if p.strip()]
    option_letters = [o["id"] for o in options]

    letter_map: dict[str, str] = {}
    multi_combined_text: str | None = None

    for p in paragraphs:
        # Skip bare markdown doc links: [Title](https://...)
        if re.match(r"^\[.+?\]\(https?://", p):
            continue

        # Multi-combined: **A and B** are correct ...
        mc = re.match(r"^\*\*([A-F])\s+and\s+([A-F])\*\*\s*(.*)", p, re.IGNORECASE | re.DOTALL)
        if mc:
            la, lb, body = mc.group(1).upper(), mc.group(2).upper(), mc.group(3).strip()
            cleaned = strip_verdict(body)
            letter_map[la] = cleaned
            letter_map[lb] = cleaned
            multi_combined_text = cleaned
            continue

        # Per-option: **X** body text
        m = re.match(r"^\*\*([A-F])\*\*\s*(.*)", p, re.IGNORECASE | re.DOTALL)
        if m:
            letter = m.group(1).upper()
            body = m.group(2).strip()
            cleaned = strip_verdict(body)
            letter_map[letter] = cleaned
            continue

    # Classify style
    found = set(letter_map.keys())
    all_letters = set(option_letters)

    if multi_combined_text and len(found) <= 2:
        style = "multi_combined"
    elif found >= all_letters:
        style = "per_option"
    elif found:
        style = "mixed"
    else:
        style = "single_block"

    # Fill missing options
    if style == "single_block":
        # Put the whole explanation on correct options; leave others empty
        full_text = " ".join(
            p for p in paragraphs
            if not re.match(r"^\[.+?\]\(https?://", p)
        )
        for letter in option_letters:
            if letter in correct_letters:
                letter_map[letter] = full_text
            else:
                letter_map[letter] = ""
    elif style == "mixed":
        # Fill missing with empty
        for letter in option_letters:
            if letter not in letter_map:
                letter_map[letter] = ""

    return letter_map, style


# ── Question migration ───────────────────────────────────────────────────────

def migrate_question(q: dict) -> tuple[dict, str, list[str]]:
    """
    Convert a v1 question to v2 format.

    Returns (new_question, style, warnings)
    """
    warnings = []
    qid = q["id"]
    correct_letters = q.get("correct", [])
    options_v1 = q.get("options", [])
    explanation = q.get("explanation", "")

    letter_map, style = parse_explanation(explanation, options_v1, correct_letters)

    # Validate: derived correctness should match declared correct[]
    derived_correct = [
        letter for letter, text in letter_map.items()
        if correctness_from_text(text) is True
    ]
    # Only warn if we got signals and they conflict
    if derived_correct and set(derived_correct) != set(correct_letters):
        warnings.append(
            f"correctness mismatch: declared={correct_letters} "
            f"derived={sorted(derived_correct)}"
        )

    # Build v2 options
    new_options = []
    for opt in options_v1:
        letter = opt["id"]
        idx = LETTER_TO_IDX.get(letter, ord(letter) - ord("A"))
        opt_id = f"{qid}a{idx + 1}"
        opt_explanation = letter_map.get(letter, "")
        is_correct = letter in correct_letters

        if not opt_explanation and style != "per_option":
            warnings.append(f"option {letter}: no explanation extracted ({style})")

        new_options.append({
            "id": opt_id,
            "text": opt["text"],
            "correct": is_correct,
            "explanation": opt_explanation,
        })

    new_q = {
        "id": qid,
        "domain": q["domain"],
        "type": q.get("type", "single"),
        "difficulty": q.get("difficulty", "medium"),
        "stem": q["stem"],
        "options": new_options,
        "reference": q.get("reference", ""),
    }

    return new_q, style, warnings


# ── File-level migration ─────────────────────────────────────────────────────

def migrate_file(path: Path, write: bool, stats: dict) -> list[str]:
    """Migrate one exam file. Returns list of warning strings."""
    data = json.loads(path.read_text())
    questions_v1 = data.get("questions", [])

    new_questions = []
    file_warnings = []

    for q in questions_v1:
        # Skip already-migrated questions (options have 'correct' bool)
        if questions_v1 and isinstance(q.get("options", [{}])[0].get("correct"), bool):
            stats["already_migrated"] += 1
            new_questions.append(q)
            continue

        new_q, style, warns = migrate_question(q)
        new_questions.append(new_q)
        stats[style] += 1
        stats["total"] += 1

        for w in warns:
            msg = f"  {path.parent.name}/{path.name} {q['id']}: {w}"
            file_warnings.append(msg)
            stats["warnings"] += 1

    if write:
        data["questions"] = new_questions
        path.write_text(json.dumps(data, indent=2) + "\n")

    return file_warnings


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    mode.add_argument("--write", action="store_true", help="Migrate in place")
    parser.add_argument("--exam", metavar="PATH", help="Single exam file")
    parser.add_argument("--cert", metavar="NAME", help="Single cert directory")
    args = parser.parse_args()

    write = args.write

    if args.exam:
        files = [Path(args.exam)]
    elif args.cert:
        files = sorted(Path(ROOT / "exams" / args.cert).glob("exam-*.json"))
    else:
        files = sorted(Path(ROOT).glob("exams/*/exam-*.json"))

    stats = defaultdict(int)
    all_warnings = []

    for f in files:
        warns = migrate_file(f, write, stats)
        all_warnings.extend(warns)

    # ── Report ────────────────────────────────────────────────────────────────
    print(f"\n{'DRY RUN — ' if not write else ''}Migration report")
    print(f"  Files processed  : {len(files)}")
    print(f"  Total questions  : {stats['total']}")
    print(f"  Already migrated : {stats['already_migrated']}")
    print()
    print("  Explanation style breakdown:")
    for style in ("per_option", "mixed", "single_block", "multi_combined"):
        n = stats[style]
        pct = 100 * n // max(stats["total"], 1)
        print(f"    {style:<20}: {n:>5}  ({pct}%)")
    print()
    print(f"  Warnings         : {stats['warnings']}")

    if all_warnings:
        print("\n  Warning details (options with empty or mismatched explanations):")
        for w in all_warnings[:50]:
            print(w)
        if len(all_warnings) > 50:
            print(f"  ... and {len(all_warnings) - 50} more")

    if not write:
        print("\n  Run with --write to apply changes.")


if __name__ == "__main__":
    main()
