#!/usr/bin/env python3
"""
Semantic quality checker for exam JSON files.

Catches template-generated, boilerplate, and low-quality content that the
structural validator (validate.py) does not detect — things like recycled
option text, placeholder stems, boilerplate explanations, meta-filler
multi-select answers, industry-prefix rotation, and reference URL overuse.

Usage:
    python3 scripts/check_semantic_quality.py --exam exams/<cert>/exam-NN.json
    python3 scripts/check_semantic_quality.py --exam exams/<cert>/exam-01.json exams/<cert>/exam-02.json
    python3 scripts/check_semantic_quality.py --glob "exams/aws-*/*.json"
    python3 scripts/check_semantic_quality.py --exam exams/<cert>/exam-NN.json --warn-only

Exit codes:
    0  — all checks passed (or --warn-only)
    1  — one or more HARD FAIL criteria violated
"""

import argparse
import glob as glob_module
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ── Tuneable thresholds ────────────────────────────────────────────────────────
#
# All numeric thresholds live here so they can be adjusted without hunting
# through function bodies. Each constant documents:
#   - what it controls
#   - why it was set to this value
#   - what to consider if you raise or lower it

# How many times an identical option text may appear across different questions
# before it is flagged as recycled boilerplate.
#   Raise if you see false positives on short, legitimately-repeated option
#   phrases (e.g., "Enable versioning on the S3 bucket" used 5× across a
#   large storage-focused exam where it is always wrong for different reasons).
#   Lower if you want stricter uniqueness across options.
OPTION_TEXT_REPEAT_MAX: int = 5

# Minimum fraction of questions that must have a unique primary reference URL.
# E.g., 0.30 means a 75-question exam needs ≥23 distinct URLs.
#   Calibrated against:
#     - agent failure pattern: 10–12 unique URLs for 50–75 questions (13–24%)
#     - acceptable human-authored exam: ~18 unique URLs for 45 questions (40%)
#   Lower to 0.20 if legitimate domain-specialist exams keep tripping this.
#   Raise toward 0.50 once generation quality improves.
REF_URL_UNIQUE_RATIO_MIN: float = 0.30

# Maximum times a single reference URL may appear across the exam.
# Using the same broad overview page for every question in a domain is the
# failure pattern; a page appearing 3–6× on a foundational topic is normal.
#   Calibrated against agent failure: 7–12× reuse of a single overview page.
#   Raise if a legitimately narrow cert (e.g., single-product deep-dive)
#   has fewer than 8 distinct concept pages worth linking.
REF_URL_MAX_APPEARANCES: int = 8

# Jaccard similarity threshold for flagging near-duplicate stems AFTER stripping
# industry/domain words (retail, healthcare, logistics, …).
# 0.65 = two stems share 65%+ of their vocabulary → probably the same question.
#   Lower (e.g., 0.55) for stricter uniqueness; raises false-positive risk on
#   questions that legitimately share many technical terms (e.g., two questions
#   both about "batch inference job timeout on a GPU cluster").
#   Raise (e.g., 0.75) if you see too many false positives on dense-tech stems.
STEM_DUPLICATE_JACCARD: float = 0.65

# Jaccard similarity threshold used specifically for INDUSTRY-ROTATION detection.
# Applied AFTER stripping both industry words AND the leading persona/intro phrase
# ("A retail team is deploying…" → "deploying…"). Set slightly higher than
# STEM_DUPLICATE_JACCARD because the aggressive prefix-stripping already does
# more normalisation, so residual similarity is a stronger signal.
#   Lower toward STEM_DUPLICATE_JACCARD if rotation detection misses variants.
#   Raise if legitimate questions with stripped-down short stems collide.
INDUSTRY_ROTATION_JACCARD: float = 0.72

# Maximum fraction of single-select questions that may share the same correct
# answer letter (A/B/C/D). 0.45 = no letter may be correct more than 45% of
# the time. Agent failure pattern: answer A for 100% of single-select questions.
#   Lower (e.g., 0.40) for stricter distribution requirements.
#   Raise (e.g., 0.50) only if the cert's own official exam is known to have
#   an unusual distribution.
SINGLE_SELECT_DOMINANCE_MAX: float = 0.45

# Minimum number of multi-select questions required before the combination-
# dominance check runs. With very few multi-select questions the sample is too
# small to distinguish a skewed distribution from random chance.
#   Raise if you want the check to require an even larger sample before firing.
#   Lower (e.g., 5) if small exams are hiding combination issues.
MULTI_SELECT_MIN_QUESTIONS: int = 8

# Maximum fraction of multi-select questions that may share the same correct
# answer COMBINATION (e.g., always [A, C]). Agent failure pattern: 100% of
# multi-select questions answered [A, C].
#   Calibrated to pass human-authored exams where small multi-select counts
#   (5–7 questions) can legitimately have 60%+ coincidence by chance.
#   Lower (e.g., 0.60) once exams routinely have 10+ multi-select questions.
MULTI_SELECT_COMBO_DOMINANCE_MAX: float = 0.70

# How many questions must share a near-identical wrong-option explanation
# paragraph before it is flagged as boilerplate (beyond the known-pattern
# checks). This catches novel boilerplate the regex list doesn't know about yet.
#   Lower (e.g., 3) for stricter uniqueness; raises false-positive risk on
#   short, naturally-recurring technical phrases.
#   Raise (e.g., 8) if you see false positives on dense terminology that
#   legitimately recurs across wrong-option explanations.
WRONG_OPTION_REPEAT_MIN: int = 5

# Number of leading characters from a wrong-option explanation paragraph used
# as the de-duplication fingerprint. Longer = more specific match; shorter =
# catches more variations of the same boilerplate opener.
#   Lower (e.g., 60) to catch boilerplate that diverges quickly after the
#   opening sentence. Raise (e.g., 150) to require more overlap before flagging.
WRONG_OPTION_FINGERPRINT_CHARS: int = 100

# ── Hard-fail patterns ─────────────────────────────────────────────────────────

PLACEHOLDER_STEM_PATTERNS = [
    (r"project team needs to make a certification.aligned design decision",
     "certification-aligned design decision template"),
    (r"needs to make .{0,40} decision about .{0,60}\. What is the BEST",
     "topic-swap stem template"),
    (r"What is the BEST choice\?$",
     "generic 'What is the BEST choice?' stem ending"),
    (r"certification.aligned",
     "'certification-aligned' placeholder phrase"),
    (r"make a .{0,30}design decision",
     "generic 'make a design decision' stem"),
    # Slot-filled case/ticket template: "Case `action-noun-NN`: symptom; ticket OCNNN; asset noun_NN."
    (r"^Case `[a-z]+-[a-z]+-\d+`\s*:",
     "slot-filled 'Case `action-noun-NN`:' stem template"),
    (r"ticket OC\d{3,}",
     "synthetic ticket reference (OC\\d+) — not a real certification scenario"),
    (r"Required capability:\s*`[a-z_]+_\d+`",
     "slot-filled 'Required capability: `noun_NN`' placeholder"),
]

META_FILLER_CORRECT_OPTION_PATTERNS = [
    (r"documented .{0,40} workflow rather than an? unrelated",
     "tautological 'documented workflow' meta-filler"),
    (r"configure the related .{0,60} capability for the (stated|specified|described) workload",
     "tautological 'configure related capability' meta-filler"),
    (r"use the managed .{0,50} capability .{0,30} (then validate|validate it)",
     "tautological 'use managed capability' meta-filler"),
    (r"rather than an? unrelated (feature|service|tool|capability)",
     "'rather than an unrelated feature' meta-filler"),
    (r"^use the documented",
     "'use the documented' meta-filler prefix"),
]

BOILERPLATE_EXPLANATION_PATTERNS = [
    (r"changes a requirement in the scenario",
     "'changes a requirement' boilerplate"),
    (r"applies a related service feature in a way that the documentation does not support",
     "boilerplate wrong-option explanation"),
    (r"in a way (the|that) documentation does not support for this use case",
     "'documentation does not support' boilerplate"),
    (r"targets storage.{0,20}(ingestion|monitoring).{0,30}rather than the decision point",
     "'targets storage rather than decision point' boilerplate"),
    (r"handles an adjacent use case but would not produce the requested",
     "'handles adjacent use case' boilerplate"),
    (r"solves a different lifecycle step and does not satisfy the stated",
     "'different lifecycle step' boilerplate"),
    (r"bypasses the managed feature that provides the required behavior",
     "'bypasses managed feature' boilerplate"),
    (r"conflicts with the governance or latency constraint described in the scenario",
     "'conflicts with governance/latency constraint' boilerplate"),
    (r"In this scenario, choosing .{0,80} would not meet the required behavior",
     "'would not meet required behavior' boilerplate sentence"),
    (r"it (is|would be) (not|incorrect|wrong) because it (changes|applies|targets|handles|solves|bypasses|conflicts)",
     "generic 'it is wrong because it...' boilerplate"),
]

# Industry/domain words stripped when checking for near-duplicate stems
INDUSTRY_RE = re.compile(
    r"\b(retail|healthcare|health.care|media|manufacturing|education|legal|"
    r"travel|gaming|logistics|financial|banking|insurance|pharmaceutical|"
    r"ecommerce|e.commerce|government|enterprise|startup|airline|telecom|"
    r"energy|automotive|real.estate|hospitality|agriculture|nonprofit|"
    r"clinical|research|compliance|regulated|production|mid.size|large)\b",
    re.IGNORECASE,
)

# Persona/intro phrases to strip for rotation detection
INTRO_RE = re.compile(
    r"^(a|an)\s+\S+\s+(team|company|organization|engineer|developer|analyst|"
    r"architect|project|lead|manager|scientist|consultant)\s+(is|needs|wants|"
    r"has|must|plans to|is building|is deploying|needs to|seeks to|would like to)\s+",
    re.IGNORECASE,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def extract_url(reference: str) -> str:
    """Extract raw URL from markdown [title](url) or return as-is."""
    m = re.search(r"\(([^)]+)\)", reference)
    return m.group(1).strip() if m else reference.strip()


def normalize_stem(stem: str) -> str:
    """Normalise for similarity comparison — strip industry words + punctuation."""
    s = INDUSTRY_RE.sub(" ", stem.lower())
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def strip_intro(stem: str) -> str:
    """Strip leading 'A <industry> <persona> is/needs...' intro phrase."""
    s = INDUSTRY_RE.sub(" ", stem.lower())
    s = INTRO_RE.sub("", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokenize(text: str) -> set:
    return set(text.lower().split())


def jaccard(a: str, b: str) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# ── Individual checks ──────────────────────────────────────────────────────────

def check_placeholder_stems(questions: list) -> list:
    failures = []
    for q in questions:
        stem = q.get("stem", "")
        for pat, label in PLACEHOLDER_STEM_PATTERNS:
            if re.search(pat, stem, re.IGNORECASE | re.DOTALL):
                failures.append(f"[{q['id']}] {label} in stem")
                break  # one failure per question
    return failures


def check_meta_filler_correct_options(questions: list) -> list:
    """Correct options that are tautological meta-fillers."""
    failures = []
    for q in questions:
        correct_ids = set(q.get("correct", []))
        for opt in q.get("options", []):
            if opt["id"] not in correct_ids:
                continue
            text = opt.get("text", "")
            for pat, label in META_FILLER_CORRECT_OPTION_PATTERNS:
                if re.search(pat, text, re.IGNORECASE):
                    failures.append(
                        f"[{q['id']}] Correct option {opt['id']} is a {label}: "
                        f"{text[:80]!r}"
                    )
                    break
    return failures


def check_boilerplate_explanations(questions: list) -> list:
    """Boilerplate wrong-option explanation phrases."""
    failures = []
    seen_per_question: dict[str, set] = {}
    for q in questions:
        explanation = q.get("explanation", "")
        matched_labels = set()
        for pat, label in BOILERPLATE_EXPLANATION_PATTERNS:
            if re.search(pat, explanation, re.IGNORECASE):
                matched_labels.add(label)
        if matched_labels:
            failures.append(
                f"[{q['id']}] Boilerplate explanation phrase(s): "
                + "; ".join(sorted(matched_labels))
            )
    return failures


def check_option_text_repetition(questions: list) -> list:
    """Option texts that appear verbatim across too many questions."""
    counter: Counter = Counter()
    locations: dict = defaultdict(list)
    for q in questions:
        for opt in q.get("options", []):
            text = opt.get("text", "").strip()
            counter[text] += 1
            locations[text].append(f"{q['id']}/{opt['id']}")

    failures = []
    for text, count in counter.most_common():
        if count < OPTION_TEXT_REPEAT_MAX:
            break
        sample = ", ".join(locations[text][:5])
        failures.append(
            f"Option text appears {count}× (max {OPTION_TEXT_REPEAT_MAX}): "
            f"{text[:70]!r}  [e.g. {sample}]"
        )
    return failures


def check_reference_urls(questions: list) -> list:
    """
    Fail if unique URL ratio < REF_URL_UNIQUE_RATIO_MIN or any URL appears
    more than REF_URL_MAX_APPEARANCES times.
    """
    raw_urls = [extract_url(q.get("reference", "")) for q in questions]
    url_counter = Counter(raw_urls)
    unique_count = len(url_counter)
    total = len(questions)

    failures = []
    ratio = unique_count / total if total else 1.0
    if ratio < REF_URL_UNIQUE_RATIO_MIN:
        failures.append(
            f"Reference URL diversity too low: {unique_count} unique URLs "
            f"for {total} questions ({ratio:.0%}, minimum {REF_URL_UNIQUE_RATIO_MIN:.0%})"
        )
    for url, count in url_counter.most_common():
        if count <= REF_URL_MAX_APPEARANCES:
            break
        failures.append(
            f"Reference URL appears {count}× (max {REF_URL_MAX_APPEARANCES}): {url}"
        )
    return failures


def check_near_duplicate_stems(questions: list) -> list:
    """Pairs of stems with high Jaccard similarity after normalisation."""
    normalised = [(q["id"], normalize_stem(q.get("stem", ""))) for q in questions]
    failures = []
    for i, (qid_a, norm_a) in enumerate(normalised):
        for qid_b, norm_b in normalised[:i]:
            score = jaccard(norm_a, norm_b)
            if score >= STEM_DUPLICATE_JACCARD:
                failures.append(
                    f"Near-duplicate stems ({score:.0%} similarity after "
                    f"stripping industry words): {qid_b} ↔ {qid_a}"
                )
    return failures


def check_industry_rotation(questions: list) -> list:
    """
    Stems that are the same underlying scenario with only an industry/persona
    prefix swapped — detected by stripping the intro phrase before comparing.
    """
    stripped = [(q["id"], strip_intro(q.get("stem", ""))) for q in questions]
    failures = []
    for i, (qid_a, s_a) in enumerate(stripped):
        for qid_b, s_b in stripped[:i]:
            if not s_a or not s_b:
                continue
            score = jaccard(s_a, s_b)
            if score >= INDUSTRY_ROTATION_JACCARD:
                failures.append(
                    f"Industry-rotation duplicate ({score:.0%} match after "
                    f"stripping intro phrase): {qid_b} ↔ {qid_a}"
                )
    return failures


def check_answer_distribution(questions: list) -> list:
    """Single-select answer letter must not dominate; multi-select combos must vary."""
    failures = []

    single = [q for q in questions if q.get("type") == "single"]
    if single:
        counter: Counter = Counter()
        for q in single:
            for ans in q.get("correct", []):
                counter[ans] += 1
        total = len(single)
        for letter, count in counter.most_common():
            if count / total > SINGLE_SELECT_DOMINANCE_MAX:
                failures.append(
                    f"Answer position '{letter}' dominates single-select: "
                    f"{count}/{total} ({count/total:.0%}) — max {SINGLE_SELECT_DOMINANCE_MAX:.0%}"
                )

    multi = [q for q in questions if q.get("type") == "multiple"]
    if len(multi) >= MULTI_SELECT_MIN_QUESTIONS:
        combo_counter: Counter = Counter(
            tuple(sorted(q.get("correct", []))) for q in multi
        )
        most_common_combo, most_common_count = combo_counter.most_common(1)[0]
        if most_common_count / len(multi) > MULTI_SELECT_COMBO_DOMINANCE_MAX:
            failures.append(
                f"Multi-select answer combination {most_common_combo} dominates: "
                f"{most_common_count}/{len(multi)} ({most_common_count/len(multi):.0%}) — max {MULTI_SELECT_COMBO_DOMINANCE_MAX:.0%}"
            )
    return failures


def check_explanation_format(questions: list) -> list:
    """Every option must have a \\n\\n-separated paragraph with bold label in the explanation."""
    failures = []
    for q in questions:
        explanation = q.get("explanation", "")
        for opt in q.get("options", []):
            label = opt["id"]
            if not re.search(rf"\*\*{re.escape(label)}\*\*", explanation):
                failures.append(
                    f"[{q['id']}] Explanation missing bold label **{label}**"
                )
    # Check that explanation uses \n\n paragraph breaks (at least one)
    for q in questions:
        if "\n\n" not in q.get("explanation", ""):
            failures.append(
                f"[{q['id']}] Explanation has no \\n\\n paragraph breaks "
                f"(options must be separated by blank lines)"
            )
    return failures


def check_wrong_option_specificity(questions: list) -> list:
    """
    Wrong-option explanations must not be identical or near-identical across
    different questions. Flags when the same explanation sentence appears in
    many questions (indicator of template boilerplate even when the known
    boilerplate patterns aren't matched).
    """
    # Extract per-option explanation paragraphs
    sentence_counter: Counter = Counter()
    sentence_locations: dict = defaultdict(list)

    for q in questions:
        explanation = q.get("explanation", "")
        correct_ids = set(q.get("correct", []))
        # Split by \n\n to get per-option blocks
        paragraphs = [p.strip() for p in explanation.split("\n\n") if p.strip()]
        for para in paragraphs:
            # Only look at wrong-option paragraphs
            first_label = re.match(r"\*\*([A-Z])\*\*", para)
            if not first_label:
                continue
            if first_label.group(1) in correct_ids:
                continue
            fingerprint = re.sub(r"\s+", " ", para[:WRONG_OPTION_FINGERPRINT_CHARS].lower())
            sentence_counter[fingerprint] += 1
            sentence_locations[fingerprint].append(q["id"])

    failures = []
    for fingerprint, count in sentence_counter.most_common():
        if count < WRONG_OPTION_REPEAT_MIN:
            break
        sample = ", ".join(sentence_locations[fingerprint][:4])
        failures.append(
            f"Wrong-option explanation paragraph identical/near-identical "
            f"across {count} questions: {fingerprint[:80]!r}  [e.g. {sample}]"
        )
    return failures


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_checks(exam_path: Path) -> tuple[list, list]:
    """Returns (hard_failures, warnings)."""
    with exam_path.open() as f:
        exam = json.load(f)
    questions = exam.get("questions", [])

    if not questions:
        return [f"No questions found in {exam_path}"], []

    hard_failures: list[str] = []

    hard_failures += check_placeholder_stems(questions)
    hard_failures += check_meta_filler_correct_options(questions)
    hard_failures += check_boilerplate_explanations(questions)
    hard_failures += check_option_text_repetition(questions)
    hard_failures += check_reference_urls(questions)
    hard_failures += check_near_duplicate_stems(questions)
    hard_failures += check_industry_rotation(questions)
    hard_failures += check_answer_distribution(questions)
    hard_failures += check_explanation_format(questions)
    hard_failures += check_wrong_option_specificity(questions)

    return hard_failures, []


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Semantic quality checker for exam JSON files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--exam",
        nargs="+",
        metavar="PATH",
        help="One or more exam JSON files to check",
    )
    group.add_argument(
        "--glob",
        metavar="PATTERN",
        help='Glob pattern for exam files, e.g. "exams/aws-*/*.json"',
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Print failures but exit 0 (informational runs only)",
    )
    args = parser.parse_args()

    if args.glob:
        paths = [Path(p) for p in sorted(glob_module.glob(args.glob))]
        if not paths:
            print(f"ERROR: No files matched glob pattern: {args.glob}", file=sys.stderr)
            sys.exit(1)
    else:
        paths = [Path(p) for p in args.exam]

    any_failures = False
    for path in paths:
        if not path.exists():
            print(f"ERROR: File not found: {path}", file=sys.stderr)
            sys.exit(1)

        print(f"\n{'─'*64}")
        print(f"  {path}")
        print(f"{'─'*64}")

        hard_failures, warnings = run_checks(path)

        if hard_failures:
            any_failures = True
            print(f"\n  ✗ {len(hard_failures)} HARD FAILURE(S):\n")
            for f in hard_failures:
                print(f"    {f}")
        else:
            print("  ✓ All semantic quality checks passed.")

    print()
    if any_failures:
        if args.warn_only:
            print("(warn-only mode — failures reported but exiting 0)")
        else:
            print(
                "Semantic quality check FAILED. Fix all HARD FAILURES before "
                "opening a PR.\nRun with --warn-only for informational output.",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
