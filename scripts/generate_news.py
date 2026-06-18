#!/usr/bin/env python3
"""
Generate news.json from git history of exam files.
Lists the last 12 new or updated exam JSON files.

Usage:
    python3 scripts/generate_news.py
"""
import subprocess
import json
import os
import re
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IGNORE_FILES = {'catalog.json', 'hints.json'}


def run_git(*args):
    r = subprocess.run(
        ['git'] + list(args),
        capture_output=True, text=True, cwd=ROOT
    )
    return r.stdout


def parse_log():
    """Return list of dicts with type/examFile/hash/date/message, newest first."""
    output = run_git(
        'log',
        '--name-status',
        '--diff-filter=AM',
        '--pretty=format:COMMIT|||%H|||%aI|||%s',
        '--',
        'exams/'
    )

    items = []
    current = None

    for line in output.splitlines():
        line = line.rstrip()
        if line.startswith('COMMIT|||'):
            parts = line.split('|||', 3)
            current = {
                'hash': parts[1],
                'date': parts[2],
                'message': parts[3] if len(parts) > 3 else ''
            }
        elif current and line:
            m = re.match(r'^([AM])\t(.+\.json)$', line)
            if m:
                status, filepath = m.group(1), m.group(2)
                if os.path.basename(filepath) in IGNORE_FILES:
                    continue
                # Only exam files: exams/<cert>/<name>.json (exactly 3 path parts)
                parts = filepath.split('/')
                if len(parts) != 3 or parts[0] != 'exams':
                    continue
                items.append({
                    'type': 'new' if status == 'A' else 'update',
                    'examFile': filepath,
                    'hash': current['hash'],
                    'date': current['date'],
                    'message': current['message'],
                })

    return items


def load_catalog():
    path = os.path.join(ROOT, 'exams', 'catalog.json')
    with open(path) as f:
        return json.load(f)


def get_cert_for_exam(catalog, exam_file):
    norm = exam_file.lstrip('/')
    for cert in catalog.get('certifications', []):
        for entry in cert.get('exams', []):
            entry_file = entry if isinstance(entry, str) else entry.get('file', '')
            if entry_file.lstrip('/') == norm:
                return cert
    return None


def get_exam_meta(exam_file):
    """Return (title, id) from the exam JSON, falling back to filename-derived values."""
    path = os.path.join(ROOT, exam_file)
    try:
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            meta = data.get('meta', {})
            title = meta.get('title')
            exam_id = meta.get('id')
            if title and exam_id:
                return title, exam_id
    except Exception:
        pass
    # Fallback: derive from filename
    name = os.path.basename(exam_file).replace('.json', '')
    title = name.replace('-', ' ').title()
    if name.startswith('exam-'):
        num = name[5:].lstrip('0') or '1'
        title = f'Exam {num}'
    return title, name


def format_date_iso(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return iso_str


def main():
    items = parse_log()
    catalog = load_catalog()

    # Deduplicate: keep only the most recent event per exam file
    seen = set()
    news_items = []

    for item in items:
        if item['examFile'] in seen:
            continue
        seen.add(item['examFile'])

        cert = get_cert_for_exam(catalog, item['examFile'])
        if not cert:
            print(f'  Warning: no cert found for {item["examFile"]}, skipping')
            continue

        exam_title, exam_id = get_exam_meta(item['examFile'])
        news_items.append({
            'type': item['type'],
            'examFile': item['examFile'],
            'examId': exam_id,
            'certId': cert['id'],
            'certName': cert['name'],
            'certShortName': cert.get('shortName', cert['name']),
            'badge': cert.get('badge', '?'),
            'color': cert.get('color', '#666'),
            'examTitle': exam_title,
            'date': format_date_iso(item['date']),
            'commitHash': item['hash'][:7],
            'commitMessage': item['message'],
        })

        if len(news_items) >= 12:
            break

    news = {
        'generated': datetime.now(timezone.utc).isoformat(),
        'items': news_items,
    }

    out_path = os.path.join(ROOT, 'news.json')
    with open(out_path, 'w') as f:
        json.dump(news, f, indent=2)

    print(f'Generated news.json with {len(news_items)} items')
    for item in news_items:
        print(f'  [{item["type"]:6}] {item["examFile"]} ({item["date"][:10]})')


if __name__ == '__main__':
    main()
