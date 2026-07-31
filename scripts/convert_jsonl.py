"""Convert a JSONL answers file (external eval format) to the JSON array
format expected by main.py's --score argument.

Field mapping:
  question_id  →  id
  answer       →  answer  (main.py falls back to this if answer_b is absent)

Every question is kept, including failed/timed-out ones: those simply carry an
empty answer. This keeps the question in the scored set (it would otherwise be
dropped from a pairwise comparison if either side failed), so a model that
failed to answer is scored low instead of having the question silently skipped.

Usage:
  python scripts/convert_jsonl.py input.jsonl [output.json]

If output path is omitted, it is derived by replacing the .jsonl extension
with .json in the same directory.
"""

import json
import re
import sys
from pathlib import Path


def _sort_key(qid) -> int:
    # Order by the numeric part of the id (e.g. "C15" -> 15) so the output is
    # Q1..Q35 instead of file order, matching export_sheets.py.
    n = re.sub(r"\D", "", str(qid))
    return int(n) if n else 0


def convert(src: Path, dst: Path) -> int:
    entries = []
    n_failed = 0
    with open(src, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("status") != "ok":
                n_failed += 1
            # Keep the entry regardless of status; a non-"ok" entry has an empty
            # answer so it scores low rather than vanishing from the comparison.
            entries.append(
                {
                    "id": obj["question_id"],
                    "question": obj.get("question", ""),
                    "answer": obj.get("answer", "") or "",
                }
            )

    entries.sort(key=lambda e: _sort_key(e["id"]))

    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    if n_failed:
        print(
            f"  ({n_failed} failed/empty answer(s) kept with blank answer)",
            file=sys.stderr,
        )
    return len(entries)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} input.jsonl [output.json]", file=sys.stderr)
        sys.exit(1)

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) >= 3 else src.with_suffix(".json")

    if not src.exists():
        print(f"[error] File not found: {src}", file=sys.stderr)
        sys.exit(1)

    n = convert(src, dst)
    print(f"Converted {n} entries: {src} → {dst}")


if __name__ == "__main__":
    main()
