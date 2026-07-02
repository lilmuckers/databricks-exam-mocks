#!/usr/bin/env python3
"""
EXPERIMENTAL VARIANT — Cross-encoder reference relevance checker.

Uses a cross-encoder (ms-marco-MiniLM-L-6-v2) instead of a bi-encoder.

Key architectural difference from baseline and BGE variants:
  Bi-encoder (baseline/BGE):
    encode(query) → vector A
    encode(chunk) → vector B
    score = cosine(A, B)
    Pro: chunks can be pre-embedded and cached
    Con: independent encodings miss interaction between query and passage

  Cross-encoder:
    encode(query + chunk together) → relevance score
    Pro: full attention across both texts — eliminates vocabulary bleed
    Con: must run inference per (query, chunk) pair — no caching
         40 questions × 40 chunks = 1600 forward passes per exam

This approach is most similar to how a human would assess relevance — it
reads both the question and the page content together rather than comparing
independent summaries.

Scores are raw logits (not cosine similarities). Thresholds are different:
  ms-marco models: > 0 = somewhat relevant, > 5 = clearly relevant,
                   < -3 = likely unrelated, < -7 = clearly unrelated

Usage:
    pip install sentence-transformers requests beautifulsoup4
    python3 scripts/check_reference_relevance_crossencoder.py --exam exams/<cert>/exam-NN.json
    python3 scripts/check_reference_relevance_crossencoder.py --exam ... --strict

Expect this to be 10-20× slower than the bi-encoder variants for large exams.
Use scripts/compare_relevance_models.py to compare all three on the same exam.

Exit codes: 0 pass, 1 hard failure, 2 missing deps.
"""

import argparse
import glob as glob_module
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import requests
    from bs4 import BeautifulSoup
    from sentence_transformers import CrossEncoder
except ImportError as _e:
    print(
        f"Missing dependency: {_e}\n"
        "Install with:\n"
        "  pip install sentence-transformers requests beautifulsoup4",
        file=sys.stderr,
    )
    sys.exit(2)

# ── Constants ──────────────────────────────────────────────────────────────────

# MiniLM cross-encoder (~66 MB). Upgrade to L-12-v2 (~130 MB) for better accuracy.
MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
MODEL_SIZE_NOTE: str = "~66 MB"

# Chunk size. Smaller than bi-encoder variants because cross-encoders have a
# 512-token input limit (query + chunk combined). Reduce CHUNK_WORDS if you
# see truncation warnings.
CHUNK_WORDS: int = 120
CHUNK_OVERLAP: int = 30
MAX_PAGE_WORDS: int = 8000
REQUEST_TIMEOUT: int = 15
FETCH_DELAY: float = 0.5

# Top-K chunks to score. Scoring all chunks is slow; pre-filtering by simple
# keyword overlap or taking every Nth chunk is an alternative.
# Set to None to score all chunks (accurate but slow on large pages).
TOP_K_CHUNKS: Optional[int] = 20

# Cross-encoder logit thresholds. These are NOT cosine similarities.
# ms-marco-MiniLM-L-6-v2 typical ranges:
#   Highly relevant:     > 5
#   Somewhat relevant:   0 to 5
#   Weak signal:        -5 to 0
#   Clearly unrelated:  < -5
# Calibrate by running --warn-only across known-good exams.
HARD_FAIL_THRESHOLD: float = -5.0
WARN_THRESHOLD: float = 0.0

# ── Page fetching ──────────────────────────────────────────────────────────────

_page_cache: dict[str, Optional[str]] = {}


def fetch_page_text(url: str) -> Optional[str]:
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
        text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True)).strip()
        _page_cache[url] = text
        time.sleep(FETCH_DELAY)
        return text
    except Exception:
        _page_cache[url] = None
        return None


def chunk_text(text: str) -> list[str]:
    words = text.split()[:MAX_PAGE_WORDS]
    step = max(1, CHUNK_WORDS - CHUNK_OVERLAP)
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + CHUNK_WORDS]))
        i += step
    return chunks or [text]


def extract_url(reference: str) -> str:
    m = re.search(r"\(([^)]+)\)", reference)
    return m.group(1).strip() if m else reference.strip()


def build_query(question: dict) -> str:
    stem = question.get("stem", "")
    correct_ids = set(question.get("correct", []))
    correct_texts = [
        opt.get("text", "") for opt in question.get("options", [])
        if opt.get("id") in correct_ids
    ]
    correct_paras = [
        p.strip() for p in question.get("explanation", "").split("\n\n")
        if re.match(r"\*\*([A-Z])\*\*", p.strip())
        and re.match(r"\*\*([A-Z])\*\*", p.strip()).group(1) in correct_ids
    ]
    parts = [stem]
    if correct_texts:
        parts.append("Correct: " + "; ".join(correct_texts))
    parts.extend(correct_paras)
    return " ".join(filter(None, parts))  # single string, not paragraphs (512 token limit)


def select_chunks(chunks: list[str], query: str, top_k: Optional[int]) -> list[str]:
    """
    Pre-filter chunks by simple keyword overlap to reduce cross-encoder calls.
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


# ── Per-question check ─────────────────────────────────────────────────────────

def check_question(
    question: dict, model: CrossEncoder
) -> tuple[str, Optional[float], str]:
    url = extract_url(question.get("reference", ""))
    if not url or not url.startswith("http"):
        return "skip", None, "no valid URL"

    page_text = fetch_page_text(url)
    if page_text is None:
        return "skip", None, "could not fetch page"
    if len(page_text.split()) < 30:
        return "skip", None, "page too short"

    query = build_query(question)
    if not query.strip():
        return "skip", None, "could not build query"

    chunks = chunk_text(page_text)
    candidate_chunks = select_chunks(chunks, query, TOP_K_CHUNKS)

    pairs = [(query, chunk) for chunk in candidate_chunks]
    scores = model.predict(pairs)
    max_score = float(max(scores))

    if max_score < HARD_FAIL_THRESHOLD:
        return "fail", max_score, (
            f"score {max_score:.2f} < hard-fail {HARD_FAIL_THRESHOLD} — "
            "page appears unrelated"
        )
    if max_score < WARN_THRESHOLD:
        return "warn", max_score, (
            f"score {max_score:.2f} < warn {WARN_THRESHOLD} — "
            "page may not support the answer"
        )
    return "pass", max_score, f"score {max_score:.2f}"


def run_checks(
    exam_path: Path, model: CrossEncoder, strict: bool
) -> tuple[list[str], list[str]]:
    with exam_path.open() as f:
        questions = json.load(f).get("questions", [])
    if not questions:
        return [f"No questions in {exam_path}"], []

    print(
        f"  Scoring {len(questions)} questions × up to {TOP_K_CHUNKS or 'all'} "
        f"chunks each (cross-encoder — this takes a while)…"
    )

    hard_failures, warnings = [], []
    for q in questions:
        status, score, msg = check_question(q, model)
        qid = q.get("id", "?")
        ref = q.get("reference", "")[:60]
        line = f"[{qid}] {msg}  ref: {ref!r}"
        if status == "fail":
            hard_failures.append(f"HARD FAIL — {line}")
        elif status == "warn":
            (hard_failures if strict else warnings).append(
                f"{'LOW RELEVANCE (strict)' if strict else 'LOW RELEVANCE'} — {line}"
            )
        elif status == "skip":
            warnings.append(f"SKIP — {line}")
    return hard_failures, warnings


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Cross-encoder reference relevance checker ({MODEL_NAME}).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--exam", nargs="+", metavar="PATH")
    group.add_argument("--glob", metavar="PATTERN")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--warn-only", action="store_true")
    args = parser.parse_args()

    paths = (
        [Path(p) for p in sorted(glob_module.glob(args.glob, recursive=True))]
        if args.glob else [Path(p) for p in args.exam]
    )
    for p in paths:
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            sys.exit(1)

    print(f"Loading {MODEL_NAME} ({MODEL_SIZE_NOTE}, downloads on first run)…")
    try:
        model = CrossEncoder(MODEL_NAME)
    except Exception as e:
        print(f"ERROR loading model: {e}", file=sys.stderr)
        sys.exit(2)
    print(f"Model ready. Mode: {'strict' if args.strict else 'default'}\n")

    any_failures = False
    for path in paths:
        print(f"\n{'─'*64}\n  {path}\n{'─'*64}")
        hard_failures, warnings_list = run_checks(path, model, strict=args.strict)
        if warnings_list:
            print(f"\n  ⚠  {len(warnings_list)} WARNING(S):\n")
            for w in warnings_list:
                print(f"    {w}")
        if hard_failures:
            any_failures = True
            print(f"\n  ✗ {len(hard_failures)} HARD FAILURE(S):\n")
            for f in hard_failures:
                print(f"    {f}")
        elif not warnings_list:
            print("  ✓ All checks passed.")

    print()
    if any_failures and not args.warn_only:
        print("Reference relevance check FAILED (cross-encoder variant).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
