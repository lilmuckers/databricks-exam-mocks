#!/usr/bin/env python3
"""
Merge stem and distractor batch files into a final v2 exam JSON.

Usage:
    python3 scripts/assemble_exam.py <run_dir> <cert_id> <output_path>

    run_dir     — /tmp/exam-run-<RUN_ID>/<cert-id>/
    cert_id     — e.g. snowpro-specialty-native-apps
    output_path — exams/<cert-id>/exam-NN.json

Contract (Step 5 stem writer output — fixed label ordering):
    option_explanations keyed by letter (A = first correct, B = second correct
    or distractor_1, C/D = remaining). Explanations are per-option; no combined
    explanation string needed.

    stems-batch-*.json: [{id, domain, type, difficulty, stem,
                           correct_answer_text, option_explanations:{A:..., B:..., ...}}, ...]

Contract (Step 6 distractor writer output — fixed option ordering, no shuffle):
    options array always: A = correct (first), B = correct_2 or distractor_1,
    C/D = remaining distractors. correct is always ["A"] or ["A","B"].
    No explanation field — explanations come from stems-batch.

    distractors-batch-*.json: [{id, options:[{id,text},...], correct:["A"], reference}, ...]

Assembly:
    For each question: merge option_explanations with option texts, set correct
    booleans, shuffle the option objects for display variety, assign stable v2
    IDs (q01a1, q01a2, ...). No label rewriting needed.

Writes the merged exam to output_path and prints a JSON status line.
"""

import json
import random
import sys
from pathlib import Path


def assemble_question(qid: str, stems_row: dict, distractors_row: dict) -> list:
    """
    Merge stem writer + distractor writer outputs into v2 option list.

    Returns list of {id, text, correct, explanation} objects with stable IDs
    assigned after shuffling.
    """
    option_explanations: dict = stems_row.get("option_explanations", {})
    options_v1: list = distractors_row["options"]
    correct_letters: set = set(distractors_row["correct"])

    # Build option objects pairing text + explanation + correctness
    raw_options = []
    for opt in options_v1:
        letter = opt["id"]
        raw_options.append({
            "text": opt["text"],
            "correct": letter in correct_letters,
            "explanation": option_explanations.get(letter, ""),
        })

    # Shuffle for display variety — explanations travel with their option,
    # so no label rewriting is needed
    random.shuffle(raw_options)

    # Assign stable v2 IDs based on shuffled position
    return [
        {"id": f"{qid}a{i + 1}", **opt}
        for i, opt in enumerate(raw_options)
    ]


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

        options = assemble_question(qid, s, d)

        questions.append({
            "id": qid,
            "domain": s["domain"],
            "type": s.get("type", "single"),
            "difficulty": s.get("difficulty", "medium"),
            "stem": s["stem"],
            "options": options,
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
