#!/usr/bin/env python3
"""
Find, validate, and optionally fix URLs in exam JSON files.

Each URL found is classified as:
  bare       — a plain https://... string not inside a markdown link
  markdown   — already wrapped as [Title](https://...)

Usage
-----
  # Report all links (no HTTP checks)
  python3 scripts/check_links.py

  # Also resolve every URL and flag bad ones
  python3 scripts/check_links.py --check-links

  # Preview what --fix-bare would change (no writes)
  python3 scripts/check_links.py --fix-bare --dry-run

  # Convert bare URLs to markdown links in-place
  python3 scripts/check_links.py --fix-bare --fix

  # Scan a single file
  python3 scripts/check_links.py --exam exams/data-engineer-associate/exam-01.json --check-links

  # Only show bad or bare links, write JSON report to file
  python3 scripts/check_links.py --check-links --only-bad --output report.json --format json

  # More parallel workers and longer timeout
  python3 scripts/check_links.py --check-links --workers 16 --timeout 15

  # Show cache stats
  python3 scripts/check_links.py --cache-stats

  # Clear entire cache
  python3 scripts/check_links.py --clear-cache

  # Clear only Snowflake entries from cache
  python3 scripts/check_links.py --clear-cache-domain docs.snowflake.com

  # Use a custom cache file and 3-day TTL
  python3 scripts/check_links.py --check-links --cache-file /tmp/mylinks.json --cache-ttl 3

  # Run without using or writing to the cache
  python3 scripts/check_links.py --check-links --no-cache

  # Scan specific exam files (one or more)
  python3 scripts/check_links.py --exam exams/snowpro-core/exam-01.json exams/snowpro-core/exam-02.json --check-links

  # Check a single file without touching the cache at all
  python3 scripts/check_links.py --exam exams/data-engineer-associate/exam-01.json --check-links --no-cache
"""

import argparse
import datetime
import glob
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

DEFAULT_CACHE_FILE = '.link-cache.json'
DEFAULT_CACHE_TTL  = 7  # days

# ── URL cache ──────────────────────────────────────────────────────────────────

class URLCache:
    """Persistent URL resolution cache backed by a JSON file."""

    def __init__(self):
        self._data = {}   # url → {status, title, final_url, error, checked_at}
        self._lock = threading.Lock()
        self._dirty = False

    def load(self, path):
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self._data = json.load(f)
                print(f'Loaded {len(self._data)} cached URL(s) from {path}', file=sys.stderr)
            except Exception as e:
                print(f'Warning: could not read cache {path}: {e}', file=sys.stderr)
                self._data = {}

    def save(self, path):
        if not self._dirty:
            return
        try:
            with open(path, 'w') as f:
                json.dump(self._data, f, indent=2)
            print(f'Cache saved to {path} ({len(self._data)} entries)', file=sys.stderr)
        except Exception as e:
            print(f'Warning: could not write cache {path}: {e}', file=sys.stderr)

    def get(self, url, ttl_days):
        """Return cached entry dict if present and not expired, else None."""
        entry = self._data.get(url)
        if not entry:
            return None
        checked_at = entry.get('checked_at', '')
        if checked_at:
            try:
                age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(checked_at)
                if age.days >= ttl_days:
                    return None  # expired
            except Exception:
                return None
        return entry

    def set(self, url, status, title, final_url, error):
        entry = {
            'status':     status,
            'title':      title,
            'final_url':  final_url,
            'error':      error,
            'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        with self._lock:
            self._data[url] = entry
            self._dirty = True

    def clear_all(self):
        count = len(self._data)
        self._data.clear()
        self._dirty = True
        return count

    def clear_domain(self, domain):
        to_remove = [u for u in self._data if f'://{domain}' in u or f'.{domain}/' in u
                     or u.startswith(f'https://{domain}') or u.startswith(f'http://{domain}')]
        for u in to_remove:
            del self._data[u]
        if to_remove:
            self._dirty = True
        return len(to_remove)

    def stats(self):
        domains = {}
        for url in self._data:
            try:
                from urllib.parse import urlparse
                d = urlparse(url).netloc
            except Exception:
                d = 'unknown'
            domains[d] = domains.get(d, 0) + 1
        return len(self._data), domains


# ── Regex ──────────────────────────────────────────────────────────────────────

RE_MARKDOWN_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^\s)]+)\)')
RE_BARE_URL      = re.compile(r'(?<!\()https?://[^\s)"\'>,\]]+')

FIELDS_TO_SCAN = ('explanation', 'reference')

# ── Data structures ────────────────────────────────────────────────────────────

class Finding:
    __slots__ = ('file', 'qid', 'field', 'url', 'kind', 'title',
                 'http_status', 'final_url', 'error')

    def __init__(self, file, qid, field, url, kind, title=''):
        self.file        = file
        self.qid         = qid
        self.field       = field
        self.url         = url
        self.kind        = kind   # 'bare' | 'markdown'
        self.title       = title  # existing title for markdown links
        self.http_status = None
        self.final_url   = None
        self.error       = None

    def status_label(self):
        if self.http_status is None:
            return 'unchecked'
        if self.http_status == 200:
            return 'OK'
        if self.http_status == 301 or self.http_status == 302:
            return f'REDIRECT→{self.final_url}'
        return str(self.http_status)

    def is_bad(self):
        return self.http_status is not None and self.http_status not in (200, 301, 302)


# ── HTML title parser ──────────────────────────────────────────────────────────

class _TitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_title = False
        self.title = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'title':
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def _fetch_page_title(url, timeout):
    """GET the URL and return (status_code, final_url, page_title)."""
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (exam-link-checker)'})
    try:
        with urlopen(req, timeout=timeout) as resp:
            final_url = resp.url
            status    = resp.status
            content_type = resp.headers.get('Content-Type', '')
            if 'html' not in content_type:
                return status, final_url, ''
            html = resp.read(32768).decode('utf-8', errors='replace')
            parser = _TitleParser()
            parser.feed(html)
            title = parser.title.strip()
            # Strip trailing site name (e.g. " | Snowflake Documentation")
            title = re.sub(r'\s*[|–—]\s*(Snowflake|Databricks|Apache Spark|MLflow|AWS|Google Cloud|Microsoft).*$', '', title, flags=re.IGNORECASE).strip()
            return status, final_url, title
    except HTTPError as e:
        return e.code, url, ''
    except URLError as e:
        raise


def check_url(finding, timeout, fetch_title=False, cache=None, cache_ttl=DEFAULT_CACHE_TTL):
    """Resolve finding.url. Mutates finding in-place. Uses cache when provided."""
    url = finding.url

    # Check cache first
    if cache is not None:
        cached = cache.get(url, cache_ttl)
        if cached is not None:
            finding.http_status = cached.get('status', 0)
            finding.final_url   = cached.get('final_url')
            finding.error       = cached.get('error')
            if fetch_title and cached.get('title'):
                finding.title = cached['title']
            return  # served from cache

    try:
        status, final_url, title = _fetch_page_title(url, timeout)
        finding.http_status = status
        finding.final_url   = final_url if final_url != url else None
        if fetch_title and title:
            finding.title = title
        if cache is not None:
            cache.set(url, status, title, finding.final_url, None)
    except URLError as e:
        finding.http_status = 0
        finding.error       = str(e.reason)
        if cache is not None:
            cache.set(url, 0, '', None, str(e.reason))
    except Exception as e:
        finding.http_status = 0
        finding.error       = str(e)
        if cache is not None:
            cache.set(url, 0, '', None, str(e))


# ── Extraction ─────────────────────────────────────────────────────────────────

def extract_findings_from_text(text, file, qid, field):
    """Return list of Finding objects found in a text value."""
    findings = []
    # Consume markdown links first so we don't double-count their URLs
    consumed = set()
    for m in RE_MARKDOWN_LINK.finditer(text):
        title, url = m.group(1), m.group(2)
        consumed.add(m.start())
        findings.append(Finding(file, qid, field, url, 'markdown', title))

    # Bare URLs: skip if they appear inside a markdown link construct
    # Build set of char ranges that are inside markdown links
    md_ranges = [(m.start(), m.end()) for m in RE_MARKDOWN_LINK.finditer(text)]

    def inside_md(pos):
        return any(s <= pos < e for s, e in md_ranges)

    for m in RE_BARE_URL.finditer(text):
        if not inside_md(m.start()):
            findings.append(Finding(file, qid, field, m.group(0), 'bare'))

    return findings


def extract_findings_from_exam(path, fields=FIELDS_TO_SCAN):
    """Parse one exam JSON file and return all URL findings."""
    findings = []
    with open(path) as f:
        data = json.load(f)
    for q in data.get('questions', []):
        qid = q.get('id', '?')
        for field in fields:
            val = q.get(field, '')
            if isinstance(val, str):
                findings.extend(extract_findings_from_text(val, path, qid, field))
    return findings, data


# ── Fix: bare URL → markdown ───────────────────────────────────────────────────

def _sub_bare_urls(text, url_to_title):
    """Replace bare URLs in text with [Title](url) using url_to_title map."""
    def replacer(m):
        url = m.group(0)
        title = url_to_title.get(url, '')
        if title:
            return f'[{title}]({url})'
        return url  # no title available, leave as-is

    # Only replace if not already inside a markdown link
    md_ranges = [(m.start(), m.end()) for m in RE_MARKDOWN_LINK.finditer(text)]

    def inside_md(pos):
        return any(s <= pos < e for s, e in md_ranges)

    result = []
    last = 0
    for m in RE_BARE_URL.finditer(text):
        if not inside_md(m.start()):
            result.append(text[last:m.start()])
            url = m.group(0)
            title = url_to_title.get(url, '')
            result.append(f'[{title}]({url})' if title else url)
            last = m.end()
        else:
            pass
    result.append(text[last:])
    return ''.join(result)


def apply_fixes(path, findings_with_titles):
    """Rewrite exam JSON replacing bare URLs that have resolved titles."""
    url_to_title = {f.url: f.title for f in findings_with_titles
                    if f.kind == 'bare' and f.title}
    if not url_to_title:
        return False

    with open(path) as fp:
        data = json.load(fp)

    changed = False
    for q in data.get('questions', []):
        for field in FIELDS_TO_SCAN:
            val = q.get(field, '')
            if isinstance(val, str):
                new_val = _sub_bare_urls(val, url_to_title)
                if new_val != val:
                    q[field] = new_val
                    changed = True

    if changed:
        with open(path, 'w') as fp:
            json.dump(data, fp, indent=2, ensure_ascii=False)
            fp.write('\n')

    return changed


# ── Report ─────────────────────────────────────────────────────────────────────

def print_text_report(findings, show_only_bad=False, show_only_bare=False, quiet=False):
    counts = {'bare': 0, 'markdown': 0, 'bad': 0, 'ok': 0, 'unchecked': 0}
    rows = []

    for f in findings:
        is_bad  = f.is_bad()
        is_bare = f.kind == 'bare'

        counts[f.kind] += 1
        if f.http_status == 200:
            counts['ok'] += 1
        elif f.http_status is None:
            counts['unchecked'] += 1
        elif is_bad:
            counts['bad'] += 1

        if show_only_bad and not is_bad:
            continue
        if show_only_bare and not is_bare:
            continue

        status = f.status_label()
        rows.append((f.file, f.qid, f.field, f.kind, status, f.url, f.title, f.error))

    if not rows or quiet:
        if not rows and not quiet:
            print('No findings match the current filters.')
    else:
        # Column widths
        col_file   = min(50, max((len(r[0]) for r in rows), default=4))
        col_qid    = max(4,  max((len(r[1]) for r in rows), default=4))
        col_field  = max(8,  max((len(r[2]) for r in rows), default=8))
        col_kind   = 8
        col_status = max(9,  max((len(r[4]) for r in rows), default=9))

        hdr = f"{'FILE':<{col_file}}  {'QID':<{col_qid}}  {'FIELD':<{col_field}}  {'KIND':<{col_kind}}  {'STATUS':<{col_status}}  URL"
        print(hdr)
        print('-' * min(160, len(hdr) + 40))

        for file, qid, field, kind, status, url, title, error in rows:
            short_file = file[-col_file:] if len(file) > col_file else file
            marker = '✗' if status not in ('OK', 'unchecked') else (' ' if status == 'OK' else '?')
            note = f' [{title}]' if title and kind == 'markdown' else ''
            err  = f' ({error})' if error else ''
            print(f"{short_file:<{col_file}}  {qid:<{col_qid}}  {field:<{col_field}}  {kind:<{col_kind}}  {marker} {status:<{col_status}}  {url}{note}{err}")

    print()
    print('Summary:')
    print(f"  Total URLs found : {len(findings)}")
    print(f"  Markdown links   : {counts['markdown']}")
    print(f"  Bare URLs        : {counts['bare']}")
    if counts['ok'] + counts['bad'] > 0:
        print(f"  Resolved OK      : {counts['ok']}")
        print(f"  Bad / unreachable: {counts['bad']}")
    if counts['unchecked'] > 0:
        print(f"  Unchecked        : {counts['unchecked']}  (run with --check-links to resolve)")


def print_json_report(findings):
    out = []
    for f in findings:
        out.append({
            'file':        f.file,
            'question_id': f.qid,
            'field':       f.field,
            'url':         f.url,
            'kind':        f.kind,
            'title':       f.title,
            'http_status': f.http_status,
            'final_url':   f.final_url,
            'error':       f.error,
        })
    print(json.dumps(out, indent=2))


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='Find, validate, and optionally fix URLs in exam JSON files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Target selection
    sel = ap.add_mutually_exclusive_group()
    sel.add_argument('--exam', metavar='PATH', nargs='+',
                     help='One or more specific exam JSON files to scan '
                          '(e.g. --exam exams/foo/exam-01.json exams/foo/exam-02.json)')
    sel.add_argument('--glob', metavar='PATTERN', default='exams/**/*.json',
                     help='Glob pattern for exam files (default: exams/**/*.json)')

    # Actions
    ap.add_argument('--check-links', action='store_true',
                    help='Resolve every URL via HTTP and report status codes')
    ap.add_argument('--fix-bare', action='store_true',
                    help='Convert bare URLs to [Title](url) markdown links '
                         '(requires --fix to actually write, or use --dry-run to preview)')
    ap.add_argument('--fix', action='store_true',
                    help='Write changes to disk (without this, nothing is modified)')
    ap.add_argument('--dry-run', action='store_true',
                    help='Print what would be changed without modifying any files')

    # Filters
    ap.add_argument('--only-bad',  action='store_true',
                    help='Report only URLs that returned non-200 / failed to resolve')
    ap.add_argument('--only-bare', action='store_true',
                    help='Report only bare (unwrapped) URLs')

    # HTTP tuning
    ap.add_argument('--workers', type=int, default=8,
                    help='Parallel HTTP workers (default: 8)')
    ap.add_argument('--timeout', type=int, default=12,
                    help='HTTP timeout in seconds per URL (default: 12)')
    ap.add_argument('--delay',   type=float, default=0.1,
                    help='Seconds to wait between requests per worker (default: 0.1)')

    # Cache
    ap.add_argument('--cache-file', metavar='PATH', default=DEFAULT_CACHE_FILE,
                    help=f'Path to URL result cache file (default: {DEFAULT_CACHE_FILE})')
    ap.add_argument('--cache-ttl', type=int, default=DEFAULT_CACHE_TTL,
                    help=f'Days before a cached result expires (default: {DEFAULT_CACHE_TTL})')
    ap.add_argument('--no-cache', action='store_true',
                    help='Skip cache entirely — do not read, write, or create the cache file. '
                         'All URLs are checked live regardless of previous results.')
    ap.add_argument('--clear-cache', action='store_true',
                    help='Clear ALL entries from the cache file then exit')
    ap.add_argument('--clear-cache-domain', metavar='DOMAIN',
                    help='Clear all cache entries for DOMAIN (e.g. docs.snowflake.com) then exit')
    ap.add_argument('--cache-stats', action='store_true',
                    help='Print cache statistics then exit')

    # Output
    ap.add_argument('--output', metavar='FILE',
                    help='Write report to this file instead of stdout')
    ap.add_argument('--format', choices=['text', 'json'], default='text',
                    help='Report format: text (default) or json')
    ap.add_argument('--quiet', action='store_true',
                    help='Suppress the per-URL report; only print the summary (useful in CI)')
    ap.add_argument('--fields', metavar='FIELD,...', default=','.join(FIELDS_TO_SCAN),
                    help=f'Comma-separated fields to scan (default: {",".join(FIELDS_TO_SCAN)})')

    args = ap.parse_args()

    # ── Cache setup ──
    cache = URLCache()
    if not args.no_cache:
        cache.load(args.cache_file)

    # Early-exit cache operations
    if args.cache_stats:
        total, domains = cache.stats()
        print(f'Cache file : {args.cache_file}')
        print(f'Total entries: {total}')
        if domains:
            print('Entries by domain:')
            for d, n in sorted(domains.items(), key=lambda x: -x[1]):
                print(f'  {n:5d}  {d}')
        sys.exit(0)

    if args.clear_cache:
        n = cache.clear_all()
        cache.save(args.cache_file)
        print(f'Cleared {n} entries from {args.cache_file}')
        sys.exit(0)

    if args.clear_cache_domain:
        n = cache.clear_domain(args.clear_cache_domain)
        cache.save(args.cache_file)
        print(f'Cleared {n} entries for domain "{args.clear_cache_domain}" from {args.cache_file}')
        sys.exit(0)

    # Override scanned fields if caller passed --fields
    scanned_fields = tuple(f.strip() for f in args.fields.split(','))

    # --fix-bare needs either --fix or --dry-run
    if args.fix_bare and not args.fix and not args.dry_run:
        ap.error('--fix-bare requires --fix (to write) or --dry-run (to preview)')

    # --fix-bare without --check-links still needs HTTP to get page titles
    need_http = args.check_links or args.fix_bare

    # ── Collect files ──
    if args.exam:
        files = args.exam  # list of one or more explicit paths
    else:
        files = sorted(glob.glob(args.glob, recursive=True))
        files = [f for f in files if 'catalog' not in f]

    if not files:
        print('No files found.', file=sys.stderr)
        sys.exit(1)

    print(f'Scanning {len(files)} file(s)…', file=sys.stderr)

    # ── Extract findings ──
    all_findings = []
    file_data_map = {}
    for path in files:
        try:
            findings, data = extract_findings_from_exam(path, scanned_fields)
            all_findings.extend(findings)
            file_data_map[path] = data
        except Exception as e:
            print(f'  ERROR reading {path}: {e}', file=sys.stderr)

    print(f'Found {len(all_findings)} URL(s) across {len(files)} file(s).', file=sys.stderr)

    # ── HTTP resolution ──
    if need_http and all_findings:
        print(f'Resolving URLs with {args.workers} worker(s), timeout={args.timeout}s…', file=sys.stderr)
        unique_urls = {}
        for f in all_findings:
            unique_urls.setdefault(f.url, []).append(f)

        print(f'  {len(unique_urls)} unique URL(s) to check.', file=sys.stderr)

        active_cache = None if args.no_cache else cache

        # Count how many will actually need a live fetch (not cached)
        uncached = sum(
            1 for url in unique_urls
            if active_cache is None or active_cache.get(url, args.cache_ttl) is None
        )
        cached_count = len(unique_urls) - uncached
        if cached_count:
            print(f'  {cached_count} URL(s) served from cache, {uncached} need live fetch.', file=sys.stderr)

        def _worker(url, findings_for_url):
            time.sleep(args.delay)
            check_url(findings_for_url[0], args.timeout,
                      fetch_title=args.fix_bare,
                      cache=active_cache,
                      cache_ttl=args.cache_ttl)
            return url, findings_for_url[0]

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_worker, url, fs): url
                       for url, fs in unique_urls.items()}
            done = 0
            for fut in as_completed(futures):
                done += 1
                if done % 20 == 0 or done == len(futures):
                    print(f'  {done}/{len(futures)} checked…', file=sys.stderr)
                url, rep = fut.result()
                # Copy results to all findings that share this URL
                for f in unique_urls[url]:
                    f.http_status = rep.http_status
                    f.final_url   = rep.final_url
                    f.error       = rep.error
                    if args.fix_bare and rep.title and f.kind == 'bare':
                        f.title = rep.title

        # Persist cache after all HTTP work is done
        if not args.no_cache:
            cache.save(args.cache_file)

    # ── Apply fixes ──
    if args.fix_bare:
        files_changed = []
        bare_with_title = [f for f in all_findings if f.kind == 'bare' and f.title]
        if not bare_with_title:
            print('No bare URLs have resolved titles — nothing to fix.', file=sys.stderr)
        else:
            by_file = {}
            for f in bare_with_title:
                by_file.setdefault(f.file, []).append(f)

            for path, file_findings in by_file.items():
                if args.dry_run:
                    print(f'\n[DRY-RUN] Would update {path}:', file=sys.stderr)
                    for f in file_findings:
                        print(f'  {f.qid} {f.field}: {f.url}  →  [{f.title}]({f.url})', file=sys.stderr)
                elif args.fix:
                    changed = apply_fixes(path, file_findings)
                    if changed:
                        files_changed.append(path)
                        print(f'  Updated {path}', file=sys.stderr)

            if args.fix and files_changed:
                print(f'\nUpdated {len(files_changed)} file(s).', file=sys.stderr)

    # ── Redirect output ──
    if args.output:
        sys.stdout = open(args.output, 'w')

    # ── Report ──
    if args.quiet:
        # Summary only — don't print per-URL rows
        print_text_report(all_findings,
                          show_only_bad=True,   # still show bad ones even in quiet mode
                          show_only_bare=False,
                          quiet=True)
    elif args.format == 'json':
        print_json_report(all_findings)
    else:
        print_text_report(all_findings,
                          show_only_bad=args.only_bad,
                          show_only_bare=args.only_bare)

    if args.output:
        sys.stdout.close()
        sys.stdout = sys.__stdout__
        print(f'Report written to {args.output}', file=sys.stderr)


if __name__ == '__main__':
    main()
