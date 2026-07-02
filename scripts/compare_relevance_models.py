#!/usr/bin/env python3
"""
EXPERIMENTAL — Compare all three reference relevance approaches side-by-side.

Runs MiniLM (baseline), BGE, and cross-encoder against the same exam and
prints a per-question score table so you can see where models agree or
diverge, and calibrate thresholds.

Models used:
  minilm   — all-MiniLM-L6-v2        (~90 MB)   cosine similarity
  bge      — BAAI/bge-large-en-v1.5  (~300 MB)  cosine similarity (w/ prefix)
  xenc     — cross-encoder/ms-marco-MiniLM-L-6-v2 (~66 MB)  logit score

Usage:
    pip install sentence-transformers requests beautifulsoup4 numpy

    # Compare all three on one exam:
    python3 scripts/compare_relevance_models.py --exam exams/<cert>/exam-NN.json

    # Skip slow cross-encoder:
    python3 scripts/compare_relevance_models.py --exam ... --no-crossencoder

    # Output CSV for analysis:
    python3 scripts/compare_relevance_models.py --exam ... --csv > scores.csv

    # Only load one model (useful for quick calibration of a single model):
    python3 scripts/compare_relevance_models.py --exam ... --only minilm

Exit codes: 0 always (comparison tool, not a gate).
"""

import argparse
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
    from sentence_transformers import CrossEncoder, SentenceTransformer
except ImportError as _e:
    print(
        f"Missing dependency: {_e}\n"
        "Install with:\n"
        "  pip install sentence-transformers requests beautifulsoup4 numpy",
        file=sys.stderr,
    )
    sys.exit(2)

# ── Model config ───────────────────────────────────────────────────────────────

MODELS = {
    "minilm": {
        "name": "all-MiniLM-L6-v2",
        "type": "biencoder",
        "size": "~90 MB",
        "query_prefix": "",
        "hard_fail": 0.15,
        "warn": 0.30,
        "chunk_words": 200,
    },
    "bge": {
        "name": "BAAI/bge-large-en-v1.5",
        "type": "biencoder",
        "size": "~300 MB",
        "query_prefix": "Represent this sentence for searching relevant passages: ",
        "hard_fail": 0.20,
        "warn": 0.35,
        "chunk_words": 200,
    },
    "xenc": {
        "name": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "type": "crossencoder",
        "size": "~66 MB",
        "query_prefix": "",
        "hard_fail": -5.0,
        "warn": 0.0,
        "chunk_words": 120,  # smaller due to 512 token joint limit
    },
}

CHUNK_OVERLAP: int = 30
MAX_PAGE_WORDS: int = 8000
REQUEST_TIMEOUT: int = 15
FETCH_DELAY: float = 0.5
CROSSENCODER_TOP_K: int = 20

# ── Shared helpers ─────────────────────────────────────────────────────────────

_page_cache: dict[str, Optional[str]] = {}


def fetch_page_text(url: str) -> Optional[str]:
    if url in _page_cache:
        return _page_cache[url]
    try:
        resp = requests.get(
            url, timeout=REQUEST_TIMEOUT,
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


def chunk_text(text: str, chunk_words: int) -> list[str]:
    words = text.split()[:MAX_PAGE_WORDS]
    step = max(1, chunk_words - CHUNK_OVERLAP)
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + chunk_words]))
        i += step
    return chunks or [text]


def extract_url(reference: str) -> str:
    m = re.search(r"\(([^)]+)\)", reference)
    return m.group(1).strip() if m else reference.strip()


def build_query(question: dict, join_char: str = "\n\n") -> str:
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
    return join_char.join(filter(None, parts))


def keyword_top_k(chunks: list[str], query: str, k: int) -> list[str]:
    query_words = set(query.lower().split())
    return sorted(
        chunks,
        key=lambda c: len(set(c.lower().split()) & query_words),
        reverse=True,
    )[:k]


# ── Scoring per model ──────────────────────────────────────────────────────────

def score_biencoder(
    model: SentenceTransformer,
    question: dict,
    page_text: str,
    cfg: dict,
) -> float:
    query_raw = build_query(question)
    query = cfg["query_prefix"] + query_raw
    chunks = chunk_text(page_text, cfg["chunk_words"])
    q_vec = model.encode(query, normalize_embeddings=True)
    c_vecs = model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)
    return float(np.max(np.array(c_vecs) @ q_vec))


def score_crossencoder(
    model: CrossEncoder,
    question: dict,
    page_text: str,
    cfg: dict,
) -> float:
    query = build_query(question, join_char=" ")
    chunks = chunk_text(page_text, cfg["chunk_words"])
    candidates = keyword_top_k(chunks, query, CROSSENCODER_TOP_K)
    scores = model.predict([(query, c) for c in candidates])
    return float(max(scores))


def flag(score: float, cfg: dict) -> str:
    if score < cfg["hard_fail"]:
        return "FAIL"
    if score < cfg["warn"]:
        return "warn"
    return "ok  "


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare MiniLM / BGE / cross-encoder relevance scores per question.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--exam", required=True, metavar="PATH")
    parser.add_argument(
        "--no-crossencoder", action="store_true",
        help="Skip the cross-encoder (faster, but no xenc column)"
    )
    parser.add_argument(
        "--only", choices=["minilm", "bge", "xenc"],
        help="Load and run only one model"
    )
    parser.add_argument(
        "--csv", action="store_true",
        help="Output CSV instead of aligned table (pipe to file for analysis)"
    )
    args = parser.parse_args()

    path = Path(args.exam)
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)

    with path.open() as f:
        questions = json.load(f).get("questions", [])
    if not questions:
        print("No questions found.", file=sys.stderr)
        sys.exit(1)

    # Decide which models to load
    run_keys = (
        [args.only] if args.only
        else ([k for k in ["minilm", "bge"] if not args.no_crossencoder or k != "xenc"]
              + ([] if args.no_crossencoder else ["xenc"]))
    )
    if not args.only and not args.no_crossencoder:
        run_keys = ["minilm", "bge", "xenc"]
    elif not args.only:
        run_keys = ["minilm", "bge"]

    loaded: dict = {}
    for key in run_keys:
        cfg = MODELS[key]
        print(f"Loading {key}: {cfg['name']} ({cfg['size']})…")
        try:
            if cfg["type"] == "biencoder":
                loaded[key] = SentenceTransformer(cfg["name"])
            else:
                loaded[key] = CrossEncoder(cfg["name"])
        except Exception as e:
            print(f"ERROR loading {key}: {e}", file=sys.stderr)
            sys.exit(2)
    print(f"\nScoring {len(questions)} questions from {path}\n")

    # Header
    col_keys = [k for k in ["minilm", "bge", "xenc"] if k in loaded]
    if args.csv:
        print("qid,url," + ",".join(f"{k}_score,{k}_flag" for k in col_keys))
    else:
        header = f"{'qid':<6}  " + "  ".join(f"{k:<14}" for k in col_keys) + "  url"
        print(header)
        print("─" * min(len(header) + 60, 120))

    # Per-question scoring
    for q in questions:
        qid = q.get("id", "?")
        url = extract_url(q.get("reference", ""))
        page_text = fetch_page_text(url) if url.startswith("http") else None

        row: dict[str, tuple[Optional[float], str]] = {}
        for key in col_keys:
            if page_text is None or len(page_text.split()) < 30:
                row[key] = (None, "skip")
                continue
            cfg = MODELS[key]
            try:
                if cfg["type"] == "biencoder":
                    score = score_biencoder(loaded[key], q, page_text, cfg)
                else:
                    score = score_crossencoder(loaded[key], q, page_text, cfg)
                row[key] = (score, flag(score, cfg))
            except Exception as e:
                row[key] = (None, f"err:{e!s:.20}")

        if args.csv:
            parts = [qid, url]
            for key in col_keys:
                score, flg = row[key]
                parts += [f"{score:.4f}" if score is not None else "NA", flg.strip()]
            print(",".join(parts))
        else:
            cells = []
            for key in col_keys:
                score, flg = row[key]
                val = f"{score:.4f}" if score is not None else "  NA  "
                cells.append(f"{flg} {val}".ljust(14))
            url_preview = url[:50] if url else "(no url)"
            print(f"{qid:<6}  " + "  ".join(cells) + f"  {url_preview}")

    # Summary: agreement stats
    if not args.csv and len(col_keys) > 1:
        print("\n" + "─" * 60)
        print("Agreement summary (questions where models disagree on flag):\n")
        disagreements = 0
        for q in questions:
            qid = q.get("id", "?")
            url = extract_url(q.get("reference", ""))
            page_text = fetch_page_text(url) if url.startswith("http") else None
            flags = set()
            for key in col_keys:
                if page_text is None or len(page_text.split()) < 30:
                    continue
                cfg = MODELS[key]
                try:
                    if cfg["type"] == "biencoder":
                        score = score_biencoder(loaded[key], q, page_text, cfg)
                    else:
                        score = score_crossencoder(loaded[key], q, page_text, cfg)
                    flags.add(flag(score, cfg).strip())
                except Exception:
                    pass
            if len(flags) > 1:
                disagreements += 1
                print(f"  [{qid}] flags differ: {flags}")
        if disagreements == 0:
            print("  All models agree on every question.")
        else:
            print(f"\n  {disagreements}/{len(questions)} questions have disagreeing flags.")
        print()


if __name__ == "__main__":
    main()
