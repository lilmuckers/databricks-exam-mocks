#!/usr/bin/env python3
"""
Reference relevance checker for exam JSON files.

Uses a local sentence-transformers embedding model to verify that each
question's reference URL contains content that actually supports the correct
answer. Catches cases where a reference is live and plausible but discusses
a different topic than the question tests.

How it works:
  For each question, a query is built from:
    stem + correct option text + correct-option explanation paragraph
  The reference page is fetched, cleaned, and split into overlapping word
  windows. Each window is embedded and compared against the query embedding
  using cosine similarity. The maximum similarity across all windows is used
  as the relevance score.

Usage:
    # Install dependencies first (one-time):
    pip install sentence-transformers requests beautifulsoup4 numpy

    # Basic check (WARN on low relevance, HARD FAIL only on very low):
    python3 scripts/check_reference_relevance.py --exam exams/<cert>/exam-NN.json

    # Strict mode — recommended for agent generation runs:
    python3 scripts/check_reference_relevance.py --exam exams/<cert>/exam-NN.json --strict

    # Calibration — run across known-good exams to establish baseline scores:
    python3 scripts/check_reference_relevance.py --glob "exams/**/*.json" --warn-only

    # Multiple files:
    python3 scripts/check_reference_relevance.py --exam exam-01.json exam-02.json

Exit codes:
    0  — all checks passed (or --warn-only mode)
    1  — one or more HARD FAILUREs
    2  — required Python dependencies not installed

Threshold calibration:
    First run this with --warn-only across human-authored exams to see the
    baseline score distribution. Set HARD_FAIL_THRESHOLD comfortably below
    the minimum observed on known-good questions. Set WARN_THRESHOLD below
    the expected normal range for well-matched references.

    Typical scores with all-MiniLM-L6-v2:
      Well-matched reference:  0.30 – 0.65
      Same domain, wrong page: 0.18 – 0.35
      Completely wrong page:   0.05 – 0.20

Model note:
    First run downloads the model (~90 MB) to the sentence-transformers cache
    directory (usually ~/.cache/huggingface/). Subsequent runs use the cache.
"""

import argparse
import glob as glob_module
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

# ── Dependency check ───────────────────────────────────────────────────────────

try:
    import numpy as np
    import requests
    from bs4 import BeautifulSoup
    from sentence_transformers import SentenceTransformer
except ImportError as _import_err:
    print(
        f"Missing dependency: {_import_err}\n\n"
        "Install all required packages with:\n"
        "  pip install sentence-transformers requests beautifulsoup4 numpy\n\n"
        "The sentence-transformers model (~90 MB) is downloaded on first use\n"
        "and cached locally — no API key or internet connection needed after that.",
        file=sys.stderr,
    )
    sys.exit(2)

# ── Tuneable constants ─────────────────────────────────────────────────────────
#
# Calibrate HARD_FAIL_THRESHOLD and WARN_THRESHOLD by running with --warn-only
# across a set of known-good human-authored exams and inspecting the score
# distribution. Thresholds should sit below the minimum observed good score
# with comfortable margin.

# Local embedding model to use. all-MiniLM-L6-v2 is a good default:
#   - ~90 MB download, runs on CPU, ~50 ms per embedding
#   - Good balance of speed and semantic quality for technical content
# Upgrade to all-mpnet-base-v2 (~420 MB) for better accuracy at slower speed.
MODEL_NAME: str = "all-MiniLM-L6-v2"

# Words per page chunk. Chunks are overlapping sliding windows over the page.
# Larger values capture more context; smaller values are more precise.
CHUNK_WORDS: int = 200

# Word overlap between consecutive chunks. Prevents relevant content at chunk
# boundaries from being split across two low-scoring chunks.
CHUNK_OVERLAP: int = 50

# Cosine similarity below this → HARD FAIL regardless of --strict flag.
# Reference is almost certainly discussing an unrelated topic.
# Lower this if you see false positives on known-good narrow-topic questions.
HARD_FAIL_THRESHOLD: float = 0.15

# Cosine similarity below this → WARNING (or HARD FAIL in --strict mode).
# Reference may be in the right domain but not the right subtopic.
# In --strict mode (recommended for agent runs) this becomes the HARD FAIL bar.
# Raise this to enforce stricter reference specificity; lower if legitimate
# deep-technical references consistently score below it.
WARN_THRESHOLD: float = 0.30

# HTTP request timeout in seconds.
REQUEST_TIMEOUT: int = 15

# Maximum words to embed from a page. Caps compute on very large documentation
# pages. Content beyond this limit is ignored.
MAX_PAGE_WORDS: int = 8000

# Seconds to sleep between page fetches. Avoids rate-limiting on doc servers.
FETCH_DELAY: float = 0.5

# ── Page fetching ──────────────────────────────────────────────────────────────

_page_cache: dict[str, Optional[str]] = {}


def fetch_page_text(url: str) -> Optional[str]:
    """Fetch a URL and return cleaned text. Returns None on any error."""
    if url in _page_cache:
        return _page_cache[url]

    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; exam-ref-check/1.0)"},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        _page_cache[url] = text
        time.sleep(FETCH_DELAY)
        return text
    except Exception:
        _page_cache[url] = None
        return None


# ── Text processing ────────────────────────────────────────────────────────────

def chunk_text(text: str) -> list[str]:
    """Split text into overlapping word-count windows."""
    words = text.split()[:MAX_PAGE_WORDS]
    if not words:
        return []
    step = max(1, CHUNK_WORDS - CHUNK_OVERLAP)
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + CHUNK_WORDS]))
        i += step
    return chunks


def extract_url(reference: str) -> str:
    """Extract URL from markdown [title](url) or return as-is."""
    m = re.search(r"\(([^)]+)\)", reference)
    return m.group(1).strip() if m else reference.strip()


def build_query(question: dict) -> str:
    """
    Build the embedding query for a question.

    Uses stem + correct option text + correct-option explanation paragraph.
    The explanation paragraph for the correct answer is the strongest signal
    for what the reference page needs to contain.
    """
    stem = question.get("stem", "")
    correct_ids = set(question.get("correct", []))
    options = question.get("options", [])

    correct_texts = [
        opt.get("text", "") for opt in options if opt.get("id") in correct_ids
    ]

    explanation = question.get("explanation", "")
    correct_paras = []
    for para in explanation.split("\n\n"):
        m = re.match(r"\*\*([A-Z])\*\*", para.strip())
        if m and m.group(1) in correct_ids:
            correct_paras.append(para.strip())

    parts = [stem]
    if correct_texts:
        parts.append("Correct answer: " + "; ".join(correct_texts))
    if correct_paras:
        parts.extend(correct_paras)

    return "\n\n".join(filter(None, parts))


# ── Similarity ─────────────────────────────────────────────────────────────────

def max_cosine_similarity(
    query_vec: "np.ndarray", chunk_vecs: "np.ndarray"
) -> float:
    """Return the maximum cosine similarity between query and any chunk."""
    # Both query_vec and chunk_vecs are already L2-normalised by encode().
    # Dot product of normalised vectors = cosine similarity.
    sims = chunk_vecs @ query_vec
    return float(np.max(sims))


# ── Per-question check ─────────────────────────────────────────────────────────

def check_question(
    question: dict,
    model: "SentenceTransformer",
) -> tuple[str, Optional[float], str]:
    """
    Returns (status, score, message).
      status: "pass" | "warn" | "fail" | "skip"
      score:  max cosine similarity, or None if page could not be processed
    """
    url = extract_url(question.get("reference", ""))
    qid = question.get("id", "?")

    if not url or not url.startswith("http"):
        return "skip", None, "no valid URL in reference field"

    page_text = fetch_page_text(url)
    if page_text is None:
        return "skip", None, f"could not fetch page (check_links.py should flag this)"

    words = page_text.split()
    if len(words) < 30:
        return "skip", None, f"page text too short to embed ({len(words)} words)"

    query = build_query(question)
    if not query.strip():
        return "skip", None, "could not build query — question missing stem/answer"

    chunks = chunk_text(page_text)

    query_vec = model.encode(query, normalize_embeddings=True)
    chunk_vecs = model.encode(
        chunks, normalize_embeddings=True, show_progress_bar=False
    )

    score = max_cosine_similarity(query_vec, np.array(chunk_vecs))

    if score < HARD_FAIL_THRESHOLD:
        return "fail", score, (
            f"score {score:.3f} < hard-fail threshold {HARD_FAIL_THRESHOLD} — "
            "reference page appears unrelated to the question"
        )
    if score < WARN_THRESHOLD:
        return "warn", score, (
            f"score {score:.3f} < warn threshold {WARN_THRESHOLD} — "
            "reference page may not directly support the correct answer"
        )
    return "pass", score, f"score {score:.3f}"


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_checks(
    exam_path: Path,
    model: "SentenceTransformer",
    strict: bool,
) -> tuple[list[str], list[str]]:
    """Returns (hard_failures, warnings)."""
    with exam_path.open() as f:
        exam = json.load(f)
    questions = exam.get("questions", [])

    if not questions:
        return [f"No questions found in {exam_path}"], []

    hard_failures: list[str] = []
    warnings: list[str] = []

    for question in questions:
        status, score, msg = check_question(question, model)
        qid = question.get("id", "?")
        ref_preview = question.get("reference", "")[:70]

        line = f"[{qid}] {msg}  ref: {ref_preview!r}"

        if status == "fail":
            hard_failures.append(f"HARD FAIL — {line}")
        elif status == "warn":
            if strict:
                hard_failures.append(f"LOW RELEVANCE (strict) — {line}")
            else:
                warnings.append(f"LOW RELEVANCE — {line}")
        elif status == "skip":
            warnings.append(f"SKIP — {line}")
        # "pass" is silent

    return hard_failures, warnings


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reference relevance checker using local sentence embeddings.",
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
        help='Glob pattern, e.g. "exams/aws-*/*.json"',
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Treat LOW RELEVANCE warnings as HARD FAILUREs. "
            "Recommended for agent generation and audit runs."
        ),
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Print all findings but always exit 0. Use for calibration runs.",
    )
    parser.add_argument(
        "--model",
        default=MODEL_NAME,
        metavar="MODEL",
        help=f"Sentence-transformers model name (default: {MODEL_NAME})",
    )
    args = parser.parse_args()

    if args.glob:
        paths = [Path(p) for p in sorted(glob_module.glob(args.glob, recursive=True))]
        if not paths:
            print(f"ERROR: No files matched: {args.glob}", file=sys.stderr)
            sys.exit(1)
    else:
        paths = [Path(p) for p in args.exam]

    for path in paths:
        if not path.exists():
            print(f"ERROR: File not found: {path}", file=sys.stderr)
            sys.exit(1)

    mode_label = "strict" if args.strict else "default"
    print(
        f"Loading model '{args.model}' (downloads ~90 MB on first run, "
        f"then cached)…"
    )
    try:
        model = SentenceTransformer(args.model)
    except Exception as e:
        print(f"ERROR: Could not load model '{args.model}': {e}", file=sys.stderr)
        sys.exit(2)
    print(f"Model ready. Running in {mode_label} mode.\n")

    any_failures = False
    for path in paths:
        print(f"\n{'─'*64}")
        print(f"  {path}")
        print(f"{'─'*64}")

        hard_failures, warnings_list = run_checks(path, model, strict=args.strict)

        if warnings_list:
            print(f"\n  ⚠  {len(warnings_list)} WARNING(S):\n")
            for w in warnings_list:
                print(f"    {w}")

        if hard_failures:
            any_failures = True
            print(f"\n  ✗ {len(hard_failures)} HARD FAILURE(S):\n")
            for failure in hard_failures:
                print(f"    {failure}")
        elif not warnings_list:
            print("  ✓ All reference relevance checks passed.")

    print()
    if any_failures:
        if args.warn_only:
            print("(warn-only mode — failures reported but exiting 0)")
        else:
            print(
                f"Reference relevance check FAILED [{mode_label} mode]. "
                "Fix or replace flagged references before opening a PR.\n"
                "Run with --warn-only for informational output.",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
