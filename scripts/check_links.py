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
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

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


def check_url(finding, timeout, fetch_title=False):
    """Resolve finding.url. Mutates finding in-place."""
    url = finding.url
    try:
        status, final_url, title = _fetch_page_title(url, timeout)
        finding.http_status = status
        finding.final_url   = final_url if final_url != url else None
        if fetch_title and title:
            finding.title = title
    except URLError as e:
        finding.http_status = 0
        finding.error       = str(e.reason)
    except Exception as e:
        finding.http_status = 0
        finding.error       = str(e)


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

def print_text_report(findings, show_only_bad=False, show_only_bare=False):
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

    if not rows:
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
    sel.add_argument('--exam',  metavar='PATH',
                     help='Scan a single exam JSON file')
    sel.add_argument('--glob',  metavar='PATTERN', default='exams/**/*.json',
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

    # Output
    ap.add_argument('--output', metavar='FILE',
                    help='Write report to this file instead of stdout')
    ap.add_argument('--format', choices=['text', 'json'], default='text',
                    help='Report format: text (default) or json')
    ap.add_argument('--fields', metavar='FIELD,...', default=','.join(FIELDS_TO_SCAN),
                    help=f'Comma-separated fields to scan (default: {",".join(FIELDS_TO_SCAN)})')

    args = ap.parse_args()

    # Override scanned fields if caller passed --fields
    scanned_fields = tuple(f.strip() for f in args.fields.split(','))

    # --fix-bare needs either --fix or --dry-run
    if args.fix_bare and not args.fix and not args.dry_run:
        ap.error('--fix-bare requires --fix (to write) or --dry-run (to preview)')

    # --fix-bare without --check-links still needs HTTP to get page titles
    need_http = args.check_links or args.fix_bare

    # ── Collect files ──
    if args.exam:
        files = [args.exam]
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

        resolved = {}
        def _worker(url, findings_for_url):
            time.sleep(args.delay)
            # Use the first finding as a representative; we'll copy results to others
            check_url(findings_for_url[0], args.timeout, fetch_title=args.fix_bare)
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
    if args.format == 'json':
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
