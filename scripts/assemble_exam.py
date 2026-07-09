#!/usr/bin/env python3
"""
Merge stem and distractor batch files into a final exam JSON.

Usage:
    python3 scripts/assemble_exam.py <run_dir> <cert_id> <output_path>

    run_dir     — /tmp/exam-run-<RUN_ID>/<cert-id>/
    cert_id     — e.g. snowpro-specialty-native-apps
    output_path — exams/<cert-id>/exam-NN.json

Contract (Step 5 stem writer output — fixed label ordering):
    Explanation always uses A = first correct answer, B = second correct (multi)
    or distractor_1 (single), etc. Labels are in predictable positions so this
    script can shuffle the final options and relabel the explanation atomically.

    stems-batch-*.json: [{id, domain, type, difficulty, stem,
                           correct_answer_text, explanation}, ...]

Contract (Step 6 distractor writer output — fixed option ordering, no shuffle):
    options array always: A = correct (first), B = correct_2 or distractor_1,
    C/D = remaining distractors. correct is always ["A"] or ["A","B"].
    This script shuffles and updates correct + explanation labels.

    distractors-batch-*.json: [{id, options, correct, reference}, ...]

Writes the merged exam to output_path and prints a JSON status line.
"""

import json
import re
import sys
import random
from pathlib import Path


def shuffle_and_relabel(options: list, correct: list, explanation: str):
    """
    Randomly shuffle option positions, update correct letters, and atomically
    relabel **X** patterns in the explanation to match the new positions.

    Input contract: options[i]["id"] == labels[i] (A, B, C, D in order).
    correct is the pre-shuffle correct letter(s), always starting from A.
    """
    labels = [o["id"] for o in options]
    texts = [o["text"] for o in options]

    # Build a shuffled permutation: perm[new_pos] = old_pos
    perm = list(range(len(options)))
    random.shuffle(perm)

    # New options: new position i gets text from old position perm[i]
    new_options = [{"id": labels[i], "text": texts[perm[i]]} for i in range(len(options))]

    # old_to_new[old_label] = new_label
    # Old label at position j is labels[j].
    # It ends up at new position i where perm[i] == j.
    old_to_new: dict[str, str] = {}
    for new_i, old_i in enumerate(perm):
        old_to_new[labels[old_i]] = labels[new_i]

    new_correct = sorted([old_to_new[c] for c in correct])

    # Relabel explanation atomically: replace **X** using null-byte tokens to
    # prevent A→C then C→X double-substitution.
    new_exp = explanation
    for old_id, new_id in old_to_new.items():
        new_exp = new_exp.replace(f"**{old_id}**", f"\x00{new_id}\x00")
    new_exp = re.sub(r"\x00([A-F])\x00", r"**\1**", new_exp)

    return new_options, new_correct, new_exp


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

        options, correct, explanation = shuffle_and_relabel(
            d["options"], d["correct"], s["explanation"]
        )

        questions.append({
            "id": qid,
            "domain": s["domain"],
            "type": s.get("type", "single"),
            "difficulty": s.get("difficulty", "medium"),
            "stem": s["stem"],
            "options": options,
            "correct": correct,
            "explanation": explanation,
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
