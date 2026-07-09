#!/usr/bin/env python3
"""
Merge stem and distractor batch files into a final exam JSON.

Usage:
    python3 scripts/assemble_exam.py <run_dir> <cert_id> <output_path>

    run_dir     — /tmp/exam-run-<RUN_ID>/<cert-id>/
    cert_id     — e.g. snowpro-specialty-native-apps
    output_path — exams/<cert-id>/exam-NN.json

Reads:
    <run_dir>/stems-batch-*.json       (produced by Step 5 stem writer)
    <run_dir>/distractors-batch-*.json (produced by Step 6 distractor writer)

Each stems-batch file is a JSON array of objects with fields:
    id, domain, type, difficulty, stem, correct_answer_text, explanation

Each distractors-batch file is a JSON array of objects with fields:
    id, options ([{id, text}, ...] — all 4 options including correct),
    correct ([letter, ...]), reference

Writes the merged exam to output_path and prints a JSON status line.
"""

import json
import sys
from pathlib import Path


def main(run_dir: str, cert_id: str, output_path: str) -> None:
    run_path = Path(run_dir)

    stems: dict = {}
    for f in sorted(run_path.glob("stems-batch-*.json")):
        for row in json.loads(f.read_text()):
            stems[row["id"]] = row

    distractors: dict = {}
    for f in sorted(run_path.glob("distractors-batch-*.json")):
        for row in json.loads(f.read_text()):
            distractors[row["id"]] = row

    if not stems:
        print(json.dumps({"status": "error", "reason": "no stems-batch-*.json found"}))
        sys.exit(1)

    missing_distractors = [qid for qid in stems if qid not in distractors]
    if missing_distractors:
        print(json.dumps({
            "status": "error",
            "reason": f"missing distractors for: {missing_distractors}",
        }))
        sys.exit(1)

    questions = []
    for qid in sorted(stems.keys(), key=lambda x: int(x[1:])):
        s = stems[qid]
        d = distractors[qid]
        questions.append({
            "id": qid,
            "domain": s["domain"],
            "type": s.get("type", "single"),
            "difficulty": s.get("difficulty", "medium"),
            "stem": s["stem"],
            "options": d["options"],
            "correct": d["correct"],
            "explanation": s["explanation"],
            "reference": d["reference"],
        })

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"questions": questions}, indent=2))
    print(json.dumps({"status": "ok", "path": output_path, "question_count": len(questions)}))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <run_dir> <cert_id> <output_path>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
