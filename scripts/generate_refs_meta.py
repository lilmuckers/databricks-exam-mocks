#!/usr/bin/env python3
"""
Generate/update references-meta.json by fetching page metadata via Microlink API.

Only stores successful Microlink responses — failed/rate-limited URLs are skipped
so the file builds incrementally across multiple builds as the daily limit resets.

Uses .link-cache.json (from check_links.py) to skip URLs already known to be
broken, so Microlink quota is not spent on dead links.

Usage
-----
  # Print sorted, deduped list of reference URLs (for CI cache key)
  python3 scripts/generate_refs_meta.py --list-urls

  # Fetch metadata for new/stale URLs
  python3 scripts/generate_refs_meta.py --fetch

  # Custom paths, TTL, and rate
  python3 scripts/generate_refs_meta.py --fetch \\
      --meta-file references-meta.json \\
      --link-cache .link-cache.json \\
      --ttl 30 --delay 1.2

  # Preview what would be fetched without calling the API
  python3 scripts/generate_refs_meta.py --fetch --dry-run
"""

import argparse
import datetime
import glob
import json
import os
import re
import sys
import time
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

MICROLINK_API   = 'https://api.microlink.io'
META_FILE       = 'references-meta.json'
LINK_CACHE_FILE = '.link-cache.json'
DEFAULT_TTL     = 30   # days before re-fetching a cached entry

RE_MARKDOWN_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^\s)]+)\)')
RE_BARE_URL      = re.compile(r'(?<!\()https?://[^\s)"\'>,\]]+')


# ── URL extraction ─────────────────────────────────────────────────────────────

def extract_reference_urls(exam_files):
    """Return sorted, deduped set of URLs from all exam reference fields."""
    urls = set()
    for path in exam_files:
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue
        for q in data.get('questions', []):
            ref = q.get('reference', '')
            if not isinstance(ref, str) or not ref.strip():
                continue
            # Markdown link — extract URL
            m = RE_MARKDOWN_LINK.search(ref)
            if m:
                urls.add(m.group(2))
                continue
            # Bare URL
            m = RE_BARE_URL.search(ref)
            if m:
                urls.add(m.group(0))
    return sorted(urls)


def find_exam_files(pattern='exams/**/*.json'):
    return [f for f in glob.glob(pattern, recursive=True) if 'catalog' not in f]


# ── Link cache (from check_links.py) ──────────────────────────────────────────

def load_link_cache(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def is_known_bad(url, link_cache):
    """True if check_links.py already confirmed this URL is broken."""
    entry = link_cache.get(url)
    if not entry:
        return False
    status = entry.get('status')
    if status is None:
        return False
    # 200, 301, 302 = reachable. Anything else = bad.
    return status not in (200, 301, 302)


# ── Microlink fetch ────────────────────────────────────────────────────────────

def fetch_microlink(url, timeout=20):
    """
    Call Microlink API for `url`.
    Returns (data_dict, rate_limited).
    data_dict is None if the call failed or Microlink returned status != 'success'.
    rate_limited is True if the API returned 429.
    """
    api_url = f'{MICROLINK_API}?url={quote_plus(url)}'
    req = Request(api_url, headers={
        'User-Agent': 'Mozilla/5.0 (exam-ref-meta-fetcher)',
        'Accept': 'application/json',
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode('utf-8', errors='replace'))
            if body.get('status') == 'success':
                d = body.get('data', {})
                return {
                    'title':       d.get('title') or '',
                    'description': d.get('description') or '',
                    'image':       (d.get('image') or {}).get('url') or '',
                    'logo':        (d.get('logo') or {}).get('url') or '',
                    'url':         d.get('url') or url,
                }, False
            return None, False
    except HTTPError as e:
        if e.code == 429:
            return None, True   # rate limited
        return None, False
    except (URLError, Exception):
        return None, False


# ── Meta store ─────────────────────────────────────────────────────────────────

def load_meta(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def save_meta(meta, path):
    with open(path, 'w') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        f.write('\n')


def is_stale(entry, ttl_days):
    fetched_at = entry.get('fetched_at', '')
    if not fetched_at:
        return True
    try:
        age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(fetched_at)
        return age.days >= ttl_days
    except Exception:
        return True


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='Fetch Microlink metadata for exam reference URLs.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument('--list-urls', action='store_true',
                    help='Print sorted, deduped reference URLs to stdout and exit '
                         '(used to generate a hash for CI cache key)')
    ap.add_argument('--fetch', action='store_true',
                    help='Fetch Microlink metadata for new/stale URLs')
    ap.add_argument('--dry-run', action='store_true',
                    help='Show what would be fetched without calling the API')
    ap.add_argument('--meta-file', default=META_FILE,
                    help=f'Path to metadata store (default: {META_FILE})')
    ap.add_argument('--link-cache', default=LINK_CACHE_FILE,
                    help=f'Path to check_links.py cache for filtering bad URLs '
                         f'(default: {LINK_CACHE_FILE})')
    ap.add_argument('--glob', default='exams/**/*.json',
                    help='Glob pattern for exam files (default: exams/**/*.json)')
    ap.add_argument('--ttl', type=int, default=DEFAULT_TTL,
                    help=f'Days before re-fetching a cached entry (default: {DEFAULT_TTL})')
    ap.add_argument('--delay', type=float, default=1.0,
                    help='Seconds between Microlink requests (default: 1.0)')
    ap.add_argument('--timeout', type=int, default=20,
                    help='HTTP timeout per Microlink request in seconds (default: 20)')
    ap.add_argument('--max-fetch', type=int, default=0,
                    help='Stop after this many live API calls (0 = unlimited, useful for daily limit)')
    args = ap.parse_args()

    if not args.list_urls and not args.fetch:
        ap.error('Specify --list-urls or --fetch')

    exam_files = find_exam_files(args.glob)
    all_urls   = extract_reference_urls(exam_files)

    # ── --list-urls ──
    if args.list_urls:
        for url in all_urls:
            print(url)
        return

    # ── --fetch ──
    meta       = load_meta(args.meta_file)
    link_cache = load_link_cache(args.link_cache)

    # Classify each URL
    to_fetch   = []
    skip_bad   = []
    skip_fresh = []

    for url in all_urls:
        if is_known_bad(url, link_cache):
            skip_bad.append(url)
        elif url in meta and not is_stale(meta[url], args.ttl):
            skip_fresh.append(url)
        else:
            to_fetch.append(url)

    print(f'Reference URLs : {len(all_urls)}', file=sys.stderr)
    print(f'  Already fresh: {len(skip_fresh)}', file=sys.stderr)
    print(f'  Known bad    : {len(skip_bad)} (skipped — from check_links cache)', file=sys.stderr)
    print(f'  To fetch     : {len(to_fetch)}', file=sys.stderr)
    if args.max_fetch and len(to_fetch) > args.max_fetch:
        print(f'  (capped at {args.max_fetch} per --max-fetch)', file=sys.stderr)

    if not to_fetch:
        print('Nothing to fetch.', file=sys.stderr)
        return

    if args.dry_run:
        print('\n[DRY-RUN] Would fetch metadata for:', file=sys.stderr)
        for url in to_fetch[:args.max_fetch or len(to_fetch)]:
            print(f'  {url}', file=sys.stderr)
        return

    # Fetch
    fetched = 0
    saved   = 0
    rate_limited = False

    for url in to_fetch:
        if args.max_fetch and fetched >= args.max_fetch:
            print(f'\nReached --max-fetch limit of {args.max_fetch}. Remaining URLs will be fetched on next run.', file=sys.stderr)
            break
        if rate_limited:
            print('\nRate limited by Microlink — stopping. Remaining URLs will retry next build.', file=sys.stderr)
            break

        print(f'  [{fetched+1}/{len(to_fetch)}] {url}', end='  ', file=sys.stderr)
        data, hit_limit = fetch_microlink(url, timeout=args.timeout)
        fetched += 1

        if hit_limit:
            print('RATE LIMITED', file=sys.stderr)
            rate_limited = True
            continue

        if data:
            data['fetched_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            # Record the HTTP status from check_links cache so the renderer can
            # skip metadata for pages that are unreachable (404 etc.)
            cached_status = link_cache.get(url, {}).get('status')
            if cached_status:
                data['http_status'] = cached_status
            meta[url] = data
            saved += 1
            title = (data.get('title') or '')[:60]
            print(f'OK  "{title}"', file=sys.stderr)
        else:
            print('no data (Microlink error — will retry next build)', file=sys.stderr)
            # Do NOT save — entry stays absent so next build retries

        if fetched < len(to_fetch) and not rate_limited:
            time.sleep(args.delay)

    if saved:
        save_meta(meta, args.meta_file)
        print(f'\nSaved {saved} new/updated entries to {args.meta_file} ({len(meta)} total)', file=sys.stderr)
    else:
        print('\nNo new entries to save.', file=sys.stderr)

    if skip_bad:
        print(f'\nSkipped {len(skip_bad)} known-bad URL(s) (run check_links.py --check-links to update their status):', file=sys.stderr)
        for url in skip_bad[:10]:
            status = link_cache.get(url, {}).get('status', '?')
            print(f'  HTTP {status}  {url}', file=sys.stderr)
        if len(skip_bad) > 10:
            print(f'  ... and {len(skip_bad) - 10} more', file=sys.stderr)


if __name__ == '__main__':
    main()
