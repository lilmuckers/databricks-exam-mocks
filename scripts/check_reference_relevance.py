#!/usr/bin/env python3
"""
Reference relevance checker for exam JSON files.

Uses a local sentence-transformers embedding model to verify that each
question's reference URL contains content that actually supports the correct
answer. Catches cases where a reference is live and plausible but discusses
a different topic than the question tests.

Default mode — bi-encoder (all-MiniLM-L6-v2):
  For each question, a query is built from:
    stem + correct option text + correct-option explanation paragraph
  The reference page is fetched, cleaned, and split into overlapping word
  windows. Each window is embedded and compared against the query embedding
  using cosine similarity. The maximum similarity across all windows is used
  as the relevance score.

Cross-encoder mode (--cross-encoder flag):
  Uses cross-encoder/ms-marco-MiniLM-L-6-v2 instead. The query and each
  page chunk are encoded jointly in a single forward pass, giving full
  attention across both texts. Eliminates vocabulary bleed at the cost of
  being 10-20x slower. Scores are raw logits, not cosine similarities.

Usage:
    # Install dependencies first (one-time):
    pip install sentence-transformers requests beautifulsoup4 numpy

    # Basic check (WARN on low relevance, HARD FAIL only on very low):
    python3 scripts/check_reference_relevance.py --exam exams/<cert>/exam-NN.json

    # Strict mode — recommended for agent generation runs:
    python3 scripts/check_reference_relevance.py --exam exams/<cert>/exam-NN.json --strict

    # Cross-encoder mode — slower but more accurate, no vocabulary bleed:
    python3 scripts/check_reference_relevance.py --exam exams/<cert>/exam-NN.json --cross-encoder

    # Cross-encoder strict mode:
    python3 scripts/check_reference_relevance.py --exam exams/<cert>/exam-NN.json --cross-encoder --strict

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

    Typical scores with all-MiniLM-L6-v2 (bi-encoder):
      Well-matched reference:  0.30 – 0.65
      Same domain, wrong page: 0.18 – 0.35
      Completely wrong page:   0.05 – 0.20

    Typical scores with ms-marco-MiniLM-L-6-v2 (cross-encoder, logits):
      Clearly relevant:        > 5
      Somewhat relevant:       0 to 5
      Weak signal:            -5 to 0
      Clearly unrelated:      < -5

Model note:
    First run downloads the model to the sentence-transformers cache directory
    (usually ~/.cache/huggingface/). Subsequent runs use the cache.
    Bi-encoder (default): ~90 MB. Cross-encoder: ~66 MB.
"""

import argparse
import glob as glob_module
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional, Union

# ── SSL certificate fix (macOS) ────────────────────────────────────────────────
#
# huggingface_hub uses urllib internally to check for model updates. On macOS,
# Python's urllib does not trust the system certificate store, causing
# SSL: CERTIFICATE_VERIFY_FAILED even when the model is already cached.
# Point urllib at certifi's CA bundle (which requests already uses) to fix this.
# Must be set BEFORE sentence_transformers is imported (huggingface_hub
# initialises its HTTP client at import time). No-op on Linux/Windows.
try:
    import certifi as _certifi
    os.environ.setdefault("SSL_CERT_FILE", _certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _certifi.where())
except ImportError:
    pass  # certifi not installed separately; requests bundles its own copy

# ── Dependency check ───────────────────────────────────────────────────────────

try:
    import numpy as np
    import requests
    from bs4 import BeautifulSoup
    from sentence_transformers import CrossEncoder, SentenceTransformer
except ImportError as _import_err:
    print(
        f"Missing dependency: {_import_err}\n\n"
        "Install all required packages with:\n"
        "  pip install sentence-transformers requests beautifulsoup4 numpy\n\n"
        "The sentence-transformers model is downloaded on first use\n"
        "and cached locally — no API key or internet connection needed after that.",
        file=sys.stderr,
    )
    sys.exit(2)

# ── Bi-encoder constants ───────────────────────────────────────────────────────
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
MODEL_SIZE_NOTE: str = "~90 MB"

# Words per page chunk. Chunks are overlapping sliding windows over the page.
# Larger values capture more context; smaller values are more precise.
CHUNK_WORDS: int = 200

# Word overlap between consecutive chunks. Prevents relevant content at chunk
# boundaries from being split across two low-scoring chunks.
CHUNK_OVERLAP: int = 50

# Cosine similarity below this → HARD FAIL regardless of --strict flag.
# Reference is almost certainly discussing an unrelated topic.
HARD_FAIL_THRESHOLD: float = 0.15

# Cosine similarity below this → WARNING (or HARD FAIL in --strict mode).
# In --strict mode (recommended for agent runs) this becomes the HARD FAIL bar.
WARN_THRESHOLD: float = 0.30

# ── Cross-encoder constants ────────────────────────────────────────────────────
#
# Used only when --cross-encoder is passed. Scores are logits, not cosine
# similarities — thresholds and chunk sizes differ from the bi-encoder.

# ms-marco-MiniLM-L-6-v2: ~66 MB. Upgrade to L-12-v2 (~130 MB) for better accuracy.
XE_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
XE_MODEL_SIZE_NOTE: str = "~66 MB"

# Smaller chunks than bi-encoder: 512-token joint limit (query + chunk combined).
XE_CHUNK_WORDS: int = 120
XE_CHUNK_OVERLAP: int = 30

# Pre-filter: score only the top-K chunks by keyword overlap before running
# cross-encoder inference. Reduces forward passes from O(all_chunks) to O(top_k).
# Set to None to score all chunks (accurate but slow on large pages).
XE_TOP_K_CHUNKS: Optional[int] = 20

# Cross-encoder logit thresholds (NOT cosine similarities):
#   ms-marco-MiniLM-L-6-v2 typical ranges:
#     Highly relevant:     > 5
#     Somewhat relevant:   0 to 5
#     Weak signal:        -5 to 0
#     Clearly unrelated:  < -5
XE_HARD_FAIL_THRESHOLD: float = -5.0
XE_WARN_THRESHOLD: float = 0.0

# ── Shared constants ───────────────────────────────────────────────────────────

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

def chunk_text(text: str, chunk_words: int, chunk_overlap: int) -> list[str]:
    """Split text into overlapping word-count windows."""
    words = text.split()[:MAX_PAGE_WORDS]
    if not words:
        return []
    step = max(1, chunk_words - chunk_overlap)
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + chunk_words]))
        i += step
    return chunks


def select_chunks(chunks: list[str], query: str, top_k: Optional[int]) -> list[str]:
    """
    Pre-filter chunks by keyword overlap to reduce cross-encoder inference calls.
    Returns top_k chunks by shared word count, or all chunks if top_k is None.
    """
    if top_k is None or len(chunks) <= top_k:
        return chunks
    query_words = set(query.lower().split())
    scored = sorted(
        chunks,
        key=lambda c: len(set(c.lower().split()) & query_words),
        reverse=True,
    )
    return scored[:top_k]


def extract_url(reference: str) -> str:
    """Extract URL from markdown [title](url) or return as-is."""
    m = re.search(r"\(([^)]+)\)", reference)
    return m.group(1).strip() if m else reference.strip()


def build_query(question: dict) -> str:
    """
    Build the embedding query for a question.

    Uses stem + correct option text + correct-option explanation.
    The correct-option explanation is the strongest signal for what
    the reference page needs to contain.
    """
    stem = question.get("stem", "")
    options = question.get("options", [])
    correct_opts = [opt for opt in options if opt.get("correct") is True]

    correct_texts = [opt.get("text", "") for opt in correct_opts]
    correct_explanations = [
        opt.get("explanation", "").strip()
        for opt in correct_opts
        if opt.get("explanation", "").strip()
    ]

    parts = [stem]
    if correct_texts:
        parts.append("Correct answer: " + "; ".join(correct_texts))
    if correct_explanations:
        parts.extend(correct_explanations)

    return "\n\n".join(filter(None, parts))


# ── Per-question check ─────────────────────────────────────────────────────────

def check_question(
    question: dict,
    model: Union["SentenceTransformer", "CrossEncoder"],
    use_cross_encoder: bool,
) -> tuple[str, Optional[float], str]:
    """
    Returns (status, score, message).
      status: "pass" | "warn" | "fail" | "skip"
      score:  relevance score (cosine similarity or logit), or None if skipped
    """
    url = extract_url(question.get("reference", ""))

    if not url or not url.startswith("http"):
        return "skip", None, "no valid URL in reference field"

    page_text = fetch_page_text(url)
    if page_text is None:
        return "skip", None, "could not fetch page (check_links.py should flag this)"

    words = page_text.split()
    if len(words) < 30:
        return "skip", None, f"page text too short to embed ({len(words)} words)"

    query = build_query(question)
    if not query.strip():
        return "skip", None, "could not build query — question missing stem/answer"

    if use_cross_encoder:
        chunks = chunk_text(page_text, XE_CHUNK_WORDS, XE_CHUNK_OVERLAP)
        candidate_chunks = select_chunks(chunks, query, XE_TOP_K_CHUNKS)
        # Cross-encoder needs a flat query string (512-token joint limit)
        flat_query = " ".join(query.split())
        pairs = [(flat_query, chunk) for chunk in candidate_chunks]
        scores = model.predict(pairs)
        score = float(max(scores))

        hard_threshold = XE_HARD_FAIL_THRESHOLD
        warn_threshold = XE_WARN_THRESHOLD
        score_fmt = f"{score:.2f}"
    else:
        chunks = chunk_text(page_text, CHUNK_WORDS, CHUNK_OVERLAP)
        query_vec = model.encode(query, normalize_embeddings=True)
        chunk_vecs = model.encode(
            chunks, normalize_embeddings=True, show_progress_bar=False
        )
        # Both already L2-normalised — dot product = cosine similarity
        score = float(np.max(np.array(chunk_vecs) @ query_vec))

        hard_threshold = HARD_FAIL_THRESHOLD
        warn_threshold = WARN_THRESHOLD
        score_fmt = f"{score:.4f}"

    if score < hard_threshold:
        return "fail", score, (
            f"score {score_fmt} < hard-fail threshold {hard_threshold} — "
            "reference page appears unrelated to the question"
        )
    if score < warn_threshold:
        return "warn", score, (
            f"score {score_fmt} < warn threshold {warn_threshold} — "
            "reference page may not directly support the correct answer"
        )
    return "pass", score, f"score {score_fmt}"


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_checks(
    exam_path: Path,
    model: Union["SentenceTransformer", "CrossEncoder"],
    strict: bool,
    use_cross_encoder: bool,
) -> tuple[list[str], list[str]]:
    """Returns (hard_failures, warnings)."""
    with exam_path.open() as f:
        exam = json.load(f)
    questions = exam.get("questions", [])

    if not questions:
        return [f"No questions found in {exam_path}"], []

    if use_cross_encoder:
        print(
            f"  Scoring {len(questions)} questions × up to "
            f"{XE_TOP_K_CHUNKS or 'all'} chunks each "
            f"(cross-encoder — expect 10-20× slower than bi-encoder)…"
        )

    hard_failures: list[str] = []
    warnings: list[str] = []

    for question in questions:
        status, score, msg = check_question(question, model, use_cross_encoder)
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
        "--cross-encoder",
        action="store_true",
        help=(
            f"Use the cross-encoder model ({XE_MODEL_NAME}, {XE_MODEL_SIZE_NOTE}) "
            "instead of the default bi-encoder. Encodes query and page chunk jointly "
            "for full attention — eliminates vocabulary bleed at 10-20x the compute "
            "cost. Scores are logits (not cosine similarities); thresholds differ."
        ),
    )
    parser.add_argument(
        "--model",
        metavar="MODEL",
        help=(
            "Override the model name. With --cross-encoder, overrides the cross-encoder "
            f"model (default: {XE_MODEL_NAME}). Without it, overrides the bi-encoder "
            f"model (default: {MODEL_NAME})."
        ),
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

    use_cross_encoder = args.cross_encoder
    if use_cross_encoder:
        model_name = args.model or XE_MODEL_NAME
        size_note = XE_MODEL_SIZE_NOTE if not args.model else "size varies"
        mode_desc = "cross-encoder"
    else:
        model_name = args.model or MODEL_NAME
        size_note = MODEL_SIZE_NOTE if not args.model else "size varies"
        mode_desc = "bi-encoder"

    mode_label = "strict" if args.strict else "default"
    print(
        f"Loading {mode_desc} model '{model_name}' "
        f"(downloads {size_note} on first run, then cached)…"
    )
    try:
        # Try local cache first — avoids a network round-trip to HuggingFace Hub
        # that fails on macOS due to SSL certificate verification issues with urllib.
        # Falls back to normal (network) load if the model is not yet cached.
        if use_cross_encoder:
            try:
                model = CrossEncoder(model_name, local_files_only=True)
            except Exception:
                model = CrossEncoder(model_name)
        else:
            try:
                model = SentenceTransformer(model_name, local_files_only=True)
            except Exception:
                model = SentenceTransformer(model_name)
    except Exception as e:
        print(f"ERROR: Could not load model '{model_name}': {e}", file=sys.stderr)
        sys.exit(2)
    print(f"Model ready. Mode: {mode_desc}, {mode_label}.\n")

    any_failures = False
    for path in paths:
        print(f"\n{'─'*64}")
        print(f"  {path}")
        print(f"{'─'*64}")

        hard_failures, warnings_list = run_checks(
            path, model, strict=args.strict, use_cross_encoder=use_cross_encoder
        )

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
                f"Reference relevance check FAILED [{mode_desc}, {mode_label} mode]. "
                "Fix or replace flagged references before opening a PR.\n"
                "Run with --warn-only for informational output.",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
