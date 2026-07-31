"""Export benchmark JSON outputs to the Google Sheets scoring workbook.

Standalone companion to main.py — reads the JSON files main.py produces and
pushes them into the existing Google Spreadsheet, replacing the manual
copy-paste. Two sub-commands:

  responses  one tab per model, three runs side-by-side
             (Questions # | First Run | Second Run | Third Run)
  scoring    the full pairwise comparison + scoring detail
             (Questions # | Model A | Answer A | Model B | Answer B |
              Verdict | Reason | Score A | Reason Score A | Score B | Reason Score B)

Setup (one-time):
  1. Create a GCP project, enable the Google Sheets API.
  2. Create a service account, download its JSON key.
  3. Share the target spreadsheet with the service-account email (Editor).
     If the workbook only exists as .xlsx, upload it to Drive and
     "Open as Google Sheets" once to get its ID (from the URL).
  4. In .env set:
       GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/key.json
       GOOGLE_SHEET_ID=<spreadsheet id from the sheet URL>

Tabs are named after the exported content — "<model name> Responses" for
`responses`, the score file's name for `scoring`. Use --title to pick any
other name, or --temp to prefix a temperature label ("Temp 0 - ...") when
comparing runs across temperatures.

Examples:
  python scripts/export_sheets.py responses --name "My Fine-tune" \
      --first output/answers-first-run.json \
      --second output/answers-second-run.json \
      --third output/answers-third-run.json --dry-run

  python scripts/export_sheets.py scoring \
      --file output/score-gen2-vs-base.json \
      --model-a "Base" --model-b "Gen 2"
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

# Only the named tabs below are ever created/overwritten; every other sheet in
# the workbook (Overview / Rules / Info / Score) is left untouched.
RESPONSES_HEADER = ["Questions #", "First Run", "Second Run", "Third Run"]
SCORING_HEADER = [
    "Questions #",
    "Model A",
    "Answer A",
    "Model B",
    "Answer B",
    "Verdict",
    "Verdict Normal",
    "Verdict Normal Score",
    "Verdict Swapped",
    "Verdict Swapped Score",
    "Avg Pref Score",
    "Reason",
    "Score A",
    "Reason Score A",
    "Score B",
    "Reason Score B",
]


# --- helpers copied from main.py (kept local so importing this file never runs
# --- main.py's top-level argparse / benchmark) -----------------------------
def clean_answer(text) -> str:
    if not text:
        return ""
    return re.sub(r"<\|channel>.*?<channel\|>", "", str(text), flags=re.DOTALL).strip()


def norm_id(x) -> str:
    # Numeric part only: "A1" -> "1", "D16" -> "16" (ids are globally numbered
    # 1..25 across sections, so this yields Q1..Q25 matching the template).
    return re.sub(r"\D", "", str(x))


def question_label(qid) -> str:
    n = norm_id(qid)
    return f"Q{n}" if n else str(qid)


def sort_key(qid) -> int:
    n = norm_id(qid)
    return int(n) if n else 0


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# --- row builders ----------------------------------------------------------
def build_responses_rows(name: str, first, second, third) -> list:
    """Align three plain-answer files by question id into one 4-column table."""
    runs = [first, second, third]
    answers = {}  # qid -> [run0, run1, run2]
    for run_idx, data in enumerate(runs):
        for item in data:
            qid = item["id"]
            text = clean_answer(item.get("answer_b", item.get("answer", "")))
            answers.setdefault(qid, ["", "", ""])[run_idx] = text

    rows = [[name, "", "", ""], list(RESPONSES_HEADER)]
    for qid in sorted(answers, key=sort_key):
        a = answers[qid]
        rows.append([question_label(qid), a[0], a[1], a[2]])
    return rows


def build_summary_block(entries, model_a, model_b) -> list:
    """main.py-style aggregate stats over the compared entries."""
    verdicts = [e.get("verdict", "") for e in entries]
    a_wins = sum(1 for v in verdicts if v in ("A>>B", "A>B"))
    b_wins = sum(1 for v in verdicts if v in ("B>>A", "B>A"))
    ties = sum(1 for v in verdicts if v == "A=B")
    unknown = sum(1 for v in verdicts if v == "unknown")
    scores_a = [
        e["score_a"] for e in entries if isinstance(e.get("score_a"), (int, float))
    ]
    scores_b = [
        e["score_b"] for e in entries if isinstance(e.get("score_b"), (int, float))
    ]
    avg_a = round(sum(scores_a) / len(scores_a), 2) if scores_a else ""
    avg_b = round(sum(scores_b) / len(scores_b), 2) if scores_b else ""
    ma = model_a or (entries[0].get("source_answer_a", "") if entries else "")
    mb = model_b or (entries[0].get("source_answer_b", "") if entries else "")
    return [
        ["Summary"],
        ["Model A", ma],
        ["Model B", mb],
        ["A wins (A>>B + A>B)", a_wins],
        ["B wins (B>>A + B>A)", b_wins],
        ["Ties (A=B)", ties],
        ["Unknown", unknown],
        ["Total compared", len(verdicts)],
        [f"Avg Score A (/10, n={len(scores_a)})", avg_a],
        [f"Avg Score B (/10, n={len(scores_b)})", avg_b],
    ]


def build_scoring_rows(title, files, model_a, model_b, include_summary=True) -> list:
    """Stack one or more score-mode files into the A–K detail table,
    optionally preceded by an aggregate summary block."""
    entries = sorted(
        [e for data in files for e in data],
        key=lambda e: sort_key(e.get("id", "")),
    )
    rows = [[title]]
    if include_summary:
        rows.extend(build_summary_block(entries, model_a, model_b))
        rows.append([])  # blank separator before the detail table
    rows.append(list(SCORING_HEADER))
    for e in entries:
        ans_a = e.get("answer_a_clean") or clean_answer(e.get("answer_a", ""))
        ans_b = e.get("answer_b_clean") or clean_answer(e.get("answer_b", ""))
        rows.append(
            [
                question_label(e.get("id", "")),
                model_a or e.get("source_answer_a", ""),
                ans_a,
                model_b or e.get("source_answer_b", ""),
                ans_b,
                e.get("verdict", ""),
                e.get("verdict_normal", ""),
                _cell(e.get("verdict_normal_score")),
                e.get("verdict_swapped", ""),
                _cell(e.get("verdict_swapped_score")),
                _cell(e.get("avg_score")),
                e.get("reason", ""),
                _cell(e.get("score_a")),
                e.get("score_a_reason", ""),
                _cell(e.get("score_b")),
                e.get("score_b_reason", ""),
            ]
        )
    return rows


def _cell(v):
    # None -> blank; numbers/strings pass through. Sheets accepts mixed types.
    return "" if v is None else v


# --- Google Sheets I/O (gspread imported lazily so --dry-run / --help need
# --- neither the package nor credentials) ----------------------------------
def get_sheet():
    import gspread  # noqa: PLC0415  (lazy import by design)

    key_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    if not key_file:
        sys.exit("[error] GOOGLE_SERVICE_ACCOUNT_FILE not set (check your .env).")
    if not Path(key_file).is_file():
        sys.exit(f"[error] service-account key not found: {key_file}")
    if not sheet_id:
        sys.exit("[error] GOOGLE_SHEET_ID not set (check your .env).")
    gc = gspread.service_account(filename=key_file)
    return gc.open_by_key(sheet_id)


def _pad(rows: list) -> list:
    """Make all rows the same width so we never leave stale cells behind."""
    width = max((len(r) for r in rows), default=1)
    return [list(r) + [""] * (width - len(r)) for r in rows]


def _last_data_row(values: list) -> int:
    """1-based index of the last row containing any non-empty cell (0 if none)."""
    last = 0
    for i, row in enumerate(values, start=1):
        if any(str(c).strip() for c in row):
            last = i
    return last


def write_tab(sh, title: str, rows: list, mode: str) -> None:
    # mode: "create" (write only if the tab is new/empty — never clobbers),
    # "replace" (clear the whole tab then write), or "append" (write below the
    # existing data). Only the single tab named `title` is ever read or written;
    # all other sheets in the workbook are untouched.
    import gspread  # noqa: PLC0415

    n_cols = len(rows[0]) if rows else 12
    try:
        ws = sh.worksheet(title)
        existing = ws.get_all_values()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(
            title=title, rows=max(100, len(rows) + 10), cols=max(12, n_cols)
        )
        ws.update(values=rows, range_name="A1")
        print(f"  created tab '{title}' and wrote {len(rows)} rows")
        return

    last = _last_data_row(existing)

    if mode == "append":
        start = last + 2 if last else 1  # leave one blank separator row
        ws.update(values=rows, range_name=f"A{start}")
        print(
            f"  appended {len(rows)} rows to '{title}' at row {start} "
            f"(kept existing data through row {last})"
        )
        return

    if mode == "replace":
        ws.clear()
        ws.update(values=rows, range_name="A1")
        print(f"  replaced '{title}': cleared {last} existing rows, wrote {len(rows)}")
        return

    # mode == "create": refuse to overwrite a tab that already has data
    if last:
        sys.exit(
            f"[abort] tab '{title}' already has data (through row {last}); nothing changed.\n"
            f"        Re-run with --append to add below it, or --replace to overwrite the tab."
        )
    ws.update(values=rows, range_name="A1")
    print(f"  wrote {len(rows)} rows to empty tab '{title}'")


def emit(title: str, rows: list, dry_run: bool, mode: str) -> None:
    rows = _pad(rows)
    if dry_run:
        print(f"[dry-run] tab: {title}  (write mode: {mode})")
        print(f"  total rows: {len(rows)}")
        for r in rows[:8]:
            print("    " + str([str(c)[:45] for c in r]))
        if len(rows) > 8:
            print("    ...")
        return
    sh = get_sheet()
    write_tab(sh, title, rows, mode)
    print(f"[done] {title}")


# --- CLI -------------------------------------------------------------------
def _resolve_mode(args, allow_append: bool) -> str:
    if allow_append and getattr(args, "append", False):
        return "append"
    if getattr(args, "replace", False):
        return "replace"
    return "create"


def resolve_title(args, base: str) -> str:
    """Tab title: --title wins outright; otherwise the content-derived base,
    prefixed with the optional temperature label so exports at different
    temperatures land in separate tabs instead of stacking into one."""
    if args.title:
        return args.title
    return f"Temp {args.temp} - {base}" if args.temp is not None else base


def cmd_responses(args) -> None:
    first = load_json(args.first)
    second = load_json(args.second)
    third = load_json(args.third)
    title = resolve_title(args, f"{args.name} Responses")
    rows = build_responses_rows(args.name, first, second, third)
    emit(title, rows, args.dry_run, _resolve_mode(args, allow_append=False))


def cmd_scoring(args) -> None:
    files = [load_json(p) for p in args.file]
    title = resolve_title(args, args.file[0].stem)
    rows = build_scoring_rows(
        title, files, args.model_a, args.model_b, include_summary=not args.no_summary
    )
    emit(title, rows, args.dry_run, _resolve_mode(args, allow_append=True))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export benchmark JSON to the Google Sheets scoring workbook.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_resp = sub.add_parser(
        "responses", help="one tab per model with three runs side-by-side"
    )
    p_resp.add_argument(
        "--temp",
        default=None,
        help='optional temperature label; prefixes the tab name ("Temp 0 - ...")',
    )
    p_resp.add_argument("--title", default=None, help="override tab title")
    p_resp.add_argument(
        "--name", required=True, help='model display name, e.g. "Gemma R64 Gen 2"'
    )
    p_resp.add_argument("--first", type=Path, required=True, metavar="FILE")
    p_resp.add_argument("--second", type=Path, required=True, metavar="FILE")
    p_resp.add_argument("--third", type=Path, required=True, metavar="FILE")
    p_resp.add_argument(
        "--replace",
        action="store_true",
        help="overwrite the tab if it already has data",
    )
    p_resp.add_argument(
        "--dry-run", action="store_true", help="print rows, do not write"
    )
    p_resp.set_defaults(func=cmd_responses)

    p_score = sub.add_parser(
        "scoring", help="the Scoring Detailed Results tab (columns A-K)"
    )
    p_score.add_argument(
        "--temp",
        default=None,
        help='optional temperature label; prefixes the tab name ("Temp 0 - ...")',
    )
    p_score.add_argument(
        "--file",
        type=Path,
        nargs="+",
        required=True,
        metavar="FILE",
        help="one or more score-mode JSON files (rows are stacked)",
    )
    p_score.add_argument(
        "--model-a", default=None, help="override Model A name (else source_answer_a)"
    )
    p_score.add_argument(
        "--model-b", default=None, help="override Model B name (else source_answer_b)"
    )
    p_score.add_argument("--title", default=None, help="override tab title")
    p_score.add_argument(
        "--no-summary", action="store_true", help="omit the aggregate summary block"
    )
    score_mode = p_score.add_mutually_exclusive_group()
    score_mode.add_argument(
        "--replace", action="store_true", help="clear the tab and rewrite it"
    )
    score_mode.add_argument(
        "--append",
        action="store_true",
        help="add below existing data, preserving prior tables in the tab",
    )
    p_score.add_argument(
        "--dry-run", action="store_true", help="print rows, do not write"
    )
    p_score.set_defaults(func=cmd_scoring)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
