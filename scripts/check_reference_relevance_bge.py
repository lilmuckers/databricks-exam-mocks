#!/usr/bin/env python3
"""
EXPERIMENTAL VARIANT — BGE bi-encoder reference relevance checker.

Replaces all-MiniLM-L6-v2 with BAAI/bge-large-en-v1.5 (~300 MB).

Key difference from the baseline:
  BGE uses an asymmetric instruction prefix on the QUERY side only:
    query  → "Represent this sentence for searching relevant passages: {text}"
    chunks → no prefix (raw text)

  This frames the task as retrieval explicitly, which BGE was fine-tuned for.
  MiniLM treats query and passage symmetrically.

Usage:
    pip install sentence-transformers requests beautifulsoup4 numpy
    python3 scripts/check_reference_relevance_bge.py --exam exams/<cert>/exam-NN.json
    python3 scripts/check_reference_relevance_bge.py --exam ... --strict
    python3 scripts/check_reference_relevance_bge.py --exam ... --warn-only

Use scripts/compare_relevance_models.py to compare this against the baseline
and the cross-encoder variant on the same exam.

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
    import numpy as np
    import requests
    from bs4 import BeautifulSoup
    from sentence_transformers import SentenceTransformer
except ImportError as _e:
    print(
        f"Missing dependency: {_e}\n"
        "Install with:\n"
        "  pip install sentence-transformers requests beautifulsoup4 numpy",
        file=sys.stderr,
    )
    sys.exit(2)

# ── Constants ──────────────────────────────────────────────────────────────────

MODEL_NAME: str = "BAAI/bge-large-en-v1.5"
MODEL_SIZE_NOTE: str = "~300 MB"

# BGE instruction prefix applied to the query only.
# Do NOT apply to document chunks — BGE uses asymmetric encoding.
BGE_QUERY_PREFIX: str = "Represent this sentence for searching relevant passages: "

CHUNK_WORDS: int = 200
CHUNK_OVERLAP: int = 50
MAX_PAGE_WORDS: int = 8000
REQUEST_TIMEOUT: int = 15
FETCH_DELAY: float = 0.5

# Thresholds for BGE scores.
# BGE scores with instruction prefix tend to be higher than MiniLM — calibrate
# by running --warn-only across known-good exams.
# Starting point: MiniLM baseline thresholds + 0.05 (BGE generally scores higher).
HARD_FAIL_THRESHOLD: float = 0.20
WARN_THRESHOLD: float = 0.35

# ── Page fetching (identical to baseline) ─────────────────────────────────────

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


# ── BGE-specific encoding ──────────────────────────────────────────────────────

def encode_query(model: SentenceTransformer, query: str) -> "np.ndarray":
    """Encode query WITH the BGE instruction prefix."""
    prefixed = BGE_QUERY_PREFIX + query
    return model.encode(prefixed, normalize_embeddings=True)


def encode_chunks(model: SentenceTransformer, chunks: list[str]) -> "np.ndarray":
    """Encode document chunks WITHOUT prefix (BGE asymmetric)."""
    return model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)


# ── Per-question check ─────────────────────────────────────────────────────────

def check_question(
    question: dict, model: SentenceTransformer
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
    query_vec = encode_query(model, query)
    chunk_vecs = encode_chunks(model, chunks)

    score = float(np.max(np.array(chunk_vecs) @ query_vec))

    if score < HARD_FAIL_THRESHOLD:
        return "fail", score, (
            f"score {score:.3f} < hard-fail {HARD_FAIL_THRESHOLD} — "
            "page appears unrelated"
        )
    if score < WARN_THRESHOLD:
        return "warn", score, (
            f"score {score:.3f} < warn {WARN_THRESHOLD} — "
            "page may not support the answer"
        )
    return "pass", score, f"score {score:.3f}"


def run_checks(
    exam_path: Path, model: SentenceTransformer, strict: bool
) -> tuple[list[str], list[str]]:
    with exam_path.open() as f:
        questions = json.load(f).get("questions", [])
    if not questions:
        return [f"No questions in {exam_path}"], []

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
        description=f"BGE-variant reference relevance checker ({MODEL_NAME}).",
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
        model = SentenceTransformer(MODEL_NAME)
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
        print("Reference relevance check FAILED (BGE variant).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
