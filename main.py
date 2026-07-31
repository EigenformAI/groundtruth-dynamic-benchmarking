"""Evaluate a fine-tuned (LoRA) Gemma model against a baseline on a fixed question set, using an LLM judge. See README.md for usage and docs/runpod.md for preparing the vLLM server on RunPod."""

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from prompts import PROMPT_PREFERENCE, PROMPT_SCORING

load_dotenv(override=True)

parser = argparse.ArgumentParser()
parser.add_argument(
    "--explore",
    action="store_true",
    help="use @explore before each question (opencode mode only)",
)
parser.add_argument(
    "--mode",
    choices=["opencode", "api"],
    default="opencode",
    help="mode to use (default: opencode)",
)
parser.add_argument(
    "--score",
    type=Path,
    nargs=2,
    metavar=("FILE_A", "FILE_B"),
    help="pairwise and pointwise compare two already-generated answer files: --score A.json B.json",
)
parser.add_argument(
    "--output",
    type=Path,
    default=Path("output/answers.json"),
    metavar="FILE",
    help="output file (default: output/answers.json)",
)
parser.add_argument(
    "--workers",
    type=int,
    default=1,
    metavar="N",
    help="number of questions to process concurrently (default: 1 = sequential). "
    "Each worker opens its own opencode process / API request against the same "
    "vLLM server. Keep modest (3-5) to avoid exhausting GPU KV-cache.",
)
RUBRICS_CONFIG = Path(__file__).parent / "configs" / "rubrics.json"
try:
    with open(RUBRICS_CONFIG) as f:
        RUBRIC_REGISTRY = {r["key"]: r for r in json.load(f)}
except (OSError, ValueError, KeyError, TypeError) as e:
    sys.exit(f"[error] cannot read {RUBRICS_CONFIG}: {e}")

parser.add_argument(
    "--rubric",
    default="example",
    metavar="KEY|FILE",
    help="grading key: a key from configs/rubrics.json "
    f"({', '.join(RUBRIC_REGISTRY)}) or a path to a rubric JSON file "
    "(default: example)",
)
parser.add_argument(
    "--check-rubric",
    action="store_true",
    help="validate the --rubric file and exit, without running anything. "
    "start_eval.sh calls this right after the rubric is chosen, so a bad "
    "rubric is caught before any prompts or GPU pods.",
)
parser.add_argument(
    "--no-flex",
    action="store_true",
    help="disable the OpenRouter flex service tier for the judge "
    "(faster / fewer 429s, but ~2x the cost)",
)
parser.add_argument(
    "--ids",
    nargs="+",
    metavar="ID",
    help="only process these question ids (matches exact id or its number, "
    'e.g. --ids 15 C16 "A1"); default: all questions',
)
parser.add_argument(
    "--api-url",
    default=os.getenv("VLLM_API_URL", ""),
    metavar="URL",
    help="vLLM chat-completions endpoint for --mode api (default: $VLLM_API_URL). "
    "start_eval.sh passes the freshly created RunPod pod's URL automatically.",
)
parser.add_argument(
    "--api-key",
    default=os.getenv("VLLM_API_KEY", ""),
    metavar="KEY",
    help="vLLM API key for --mode api, paired with --api-url (default: $VLLM_API_KEY)",
)
args = parser.parse_args()

if args.mode == "api" and not args.api_url:
    parser.error("--mode api requires --api-url (or VLLM_API_URL in .env)")

if args.score:
    for p in args.score:
        if not p.is_file():
            parser.error(f"--score file not found: {p}")

# None = standard tier (key omitted from the request); "flex" = discounted tier.
SERVICE_TIER = None if args.no_flex else "flex"

OUTPUT_FILE = args.output
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
# Failed generations (empty / thinking-only / leaked tokens) go here instead of the main output, so they're not scored and get retried on the next run.
ERROR_FILE = OUTPUT_FILE.parent / (OUTPUT_FILE.stem + ".errors.json")
# Per-question raw opencode event streams (one .jsonl per id). Scoped by the output file's stem so a 3-run batch (…-first-run / -second-run / -third-run) keeps separate subfolders instead of overwriting each other's transcripts.
TRANSCRIPTS_DIR = OUTPUT_FILE.parent / "transcripts" / OUTPUT_FILE.stem
# A registry key resolves to its entry; anything else is treated as a path, so an unregistered rubric can still be run directly.
RUBRIC_ENTRY = RUBRIC_REGISTRY.get(args.rubric, {})
ANSWER_KEY_FILE = Path(RUBRIC_ENTRY.get("file", args.rubric))
if not ANSWER_KEY_FILE.is_file():
    sys.exit(
        f"[error] rubric not found: {args.rubric}. Use a key from "
        f"{RUBRICS_CONFIG.name} ({', '.join(RUBRIC_REGISTRY)}) "
        "or a path to a rubric JSON file."
    )

# Opencode settings
# Alias vLLM serves the model under, whichever model that is; must match ADAPTER_NAME in start_eval.sh.
OPENCODE_MODEL = "vllm/benchmark"
# Passed to `opencode run --dir` so the model can explore the source documents for this rubric. A rubric with no project_dir runs without --dir.
PROJECT_DIR = RUBRIC_ENTRY.get("project_dir")

# API settings
API_URL = args.api_url
API_KEY = args.api_key
API_MODEL = "benchmark"

# Scoring settings (OpenRouter)
SCORE_API_URL = "https://openrouter.ai/api/v1/chat/completions"
SCORE_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
SCORE_MODEL = "openai/gpt-5.5"

JUDGE_USAGE = {"cost": 0.0, "prompt_tokens": 0, "completion_tokens": 0, "calls": 0}


def _accumulate_usage(data: dict) -> None:
    usage = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return
    JUDGE_USAGE["calls"] += 1
    JUDGE_USAGE["cost"] += usage.get("cost", 0) or 0
    JUDGE_USAGE["prompt_tokens"] += usage.get("prompt_tokens", 0) or 0
    JUDGE_USAGE["completion_tokens"] += usage.get("completion_tokens", 0) or 0


def fetch_model_pricing(model_id: str):
    """Return (prompt_price, completion_price) per token for `model_id` from OpenRouter's /models endpoint, or (None, None) if unavailable. Fetched live so the estimate tracks any price change."""
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=15)
        resp.raise_for_status()
        for m in resp.json().get("data", []):
            if m.get("id") == model_id:
                p = m.get("pricing", {})
                return float(p.get("prompt", 0)), float(p.get("completion", 0))
    except (requests.RequestException, ValueError, KeyError, TypeError):
        pass
    return None, None


def print_cost_estimate(n_questions: int) -> None:
    """Pre-run ballpark: 4 judge calls/question (2 verdict + 2 score), with
    rough per-call token averages, priced at live OpenRouter rates."""
    calls = n_questions * 4
    in_price, out_price = fetch_model_pricing(SCORE_MODEL)
    if in_price is None:
        print(
            f"[estimate] {n_questions} questions x 4 = {calls} judge calls "
            "(live pricing unavailable)"
        )
        return
    avg_in, avg_out = 2000, 1200  # rough per-call averages (incl. reasoning)
    std = calls * (avg_in * in_price + avg_out * out_price)
    print(
        f"[estimate] {SCORE_MODEL}: ${in_price * 1e6:.2f}/M in, "
        f"${out_price * 1e6:.2f}/M out (live)"
    )
    print(
        f"[estimate] {n_questions} questions x 4 calls = {calls} calls "
        f"(~{avg_in} in + {avg_out} out tok each)"
    )
    print(
        f"[estimate] rough cost: ~${std:.2f} standard | ~${std / 2:.2f} flex "
        "(actual billed shown at end)"
    )


OPENCODE_TIMEOUT = 300  # seconds per attempt


def exit_if_unauthorized(exc):
    resp = getattr(exc, "response", None)
    if resp is not None and resp.status_code == 401:
        print(
            "[fatal] 401 Unauthorized — check API key (OPENROUTER_API_KEY / vLLM key). Stopping.",
            file=sys.stderr,
        )
        sys.exit(1)


def check_service_tier():
    try:
        payload = {
            "model": SCORE_MODEL,
            "max_tokens": 16,
            "messages": [{"role": "user", "content": "Hi"}],
        }
        if SERVICE_TIER:
            payload["service_tier"] = SERVICE_TIER
        response = requests.post(
            SCORE_API_URL,
            headers={
                "Authorization": f"Bearer {SCORE_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        tier = response.json().get("service_tier", "unknown")
        print(f"Service tier: {tier}")
    except Exception as e:
        exit_if_unauthorized(e)
        print(f"[tier check error] {e}", file=sys.stderr)


_THOUGHT_BLOCK_RE = re.compile(r"<\|channel>.*?<channel\|>", re.DOTALL)
_LEAKED_TOKEN_RE = re.compile(
    r"<\|turn>(?:model|user)?|<turn\|>|<\|channel>|<channel\|>"
)
_REFUSAL_RE = re.compile(
    r"I('m| am) sorry|I('m| am) unable|I cannot|I can't|I apologize|"
    r"I don't have access|I do not have access|cannot (read|access|open|process)",
    re.IGNORECASE,
)
MIN_ANSWER_CHARS = 20  # shorter than this after cleaning = truncated/failed


def clean_answer(text: str) -> str:
    # Non-destructive: recovers the real answer by stripping leaked control tokens ("<|turn>model", "<|channel>thought<channel|>", ...). The raw answer is kept separately; this is only used for the judge input and failure detection.
    t = _THOUGHT_BLOCK_RE.sub("", text or "")
    t = _LEAKED_TOKEN_RE.sub("", t)
    return t.strip()


def is_failed_answer(text: str) -> bool:
    # Failed only when no usable answer remains AFTER cleaning: empty / a tiny truncated fragment (e.g. "que"), or a degenerate space-less blob (leaked system prompt), or a refusal/apology ("I am sorry, I cannot read..."). A real answer buried under control tokens is NOT a failure.
    cleaned = clean_answer(text or "")
    if len(cleaned) < MIN_ANSWER_CHARS:
        return True
    if _REFUSAL_RE.search(cleaned):
        return True
    return cleaned.count(" ") / len(cleaned) < 0.02  # almost no spaces = degenerate


def norm_id(x) -> str:
    return re.sub(r"\D", "", str(x))


def ask_opencode(question, retries=3):
    prompt = f"@explore {question}" if args.explore else question
    last_raw = ""
    last_error = ""
    for attempt in range(1, retries + 1):
        cmd = ["opencode", "run", "-m", OPENCODE_MODEL]
        if PROJECT_DIR:
            cmd += ["--dir", PROJECT_DIR]
        cmd += ["--dangerously-skip-permissions", "--format", "json", prompt]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
        )
        texts = []
        raw_lines = []
        error_msgs = []

        def _read():
            for line in proc.stdout:
                raw_lines.append(line)  # keep the full raw event stream
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                    event_type = obj.get("type")
                    if event_type == "text":
                        texts.append(obj["part"]["text"])
                    elif event_type == "tool_use":
                        tool = obj["part"].get("tool", "")
                        print(f"  [tool] {tool}", flush=True)
                    elif event_type == "error":
                        err = obj.get("error") or {}
                        data = err.get("data") or {}
                        msg = data.get("message") or err.get("name") or "unknown"
                        ref = data.get("ref")
                        error_msgs.append(f"{msg} (ref {ref})" if ref else msg)
                        print(f"  [opencode error] {error_msgs[-1]}", file=sys.stderr)
                except Exception:
                    pass

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        start = time.time()
        while t.is_alive():
            t.join(timeout=10)
            if t.is_alive():
                elapsed = int(time.time() - start)
                if elapsed >= OPENCODE_TIMEOUT:
                    proc.kill()
                    print(
                        f"  [timeout] opencode timed out after {OPENCODE_TIMEOUT}s",
                        file=sys.stderr,
                    )
                    break
                print(f"  [waiting] {elapsed}s...", flush=True)
        else:
            proc.wait()

        result = "".join(texts).strip()
        last_raw = "".join(raw_lines)
        if error_msgs:
            last_error = error_msgs[-1]
        cleaned = clean_answer(result)
        if cleaned:
            return result, last_raw, ""
        if result and not cleaned:
            print(
                f"  [retry {attempt}/{retries}] only thinking tokens returned (no answer), retrying...",
                flush=True,
            )
        else:
            print(
                f"  [retry {attempt}/{retries}] opencode returned empty, retrying...",
                flush=True,
            )
        time.sleep(2)
    print(
        f"  [failed] opencode returned empty after {retries} attempts"
        + (f" (last error: {last_error})" if last_error else ""),
        file=sys.stderr,
    )
    return "", last_raw, last_error


def write_transcript(qid, raw_output) -> None:
    """Save the raw opencode event stream for one question to
    transcripts/<id>.jsonl next to the output file (mirrors the wa pipeline)."""
    if not raw_output:
        return
    try:
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(TRANSCRIPTS_DIR / f"{qid}.jsonl", "w", encoding="utf-8") as f:
            f.write(raw_output)
    except OSError as e:
        print(f"  [transcript] failed to write {qid}: {e}", file=sys.stderr)


def extract_clean_text(raw: dict) -> str:
    try:
        message = raw["choices"][0]["message"]
        content = message.get("content")
        if content:
            return content.strip()
        reasoning = message.get("reasoning")
        if reasoning:
            return reasoning.strip()
        return ""
    except (KeyError, IndexError, TypeError):
        return ""


def ask_api(question) -> str:
    try:
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": API_MODEL,
                "messages": [{"role": "user", "content": question}],
                "temperature": 0.0,
                "top_p": 1.0,
            },
            timeout=120,
        )
        response.raise_for_status()
        return extract_clean_text(response.json())
    except requests.HTTPError as e:
        exit_if_unauthorized(e)
        body = e.response.text if e.response is not None else str(e)
        print(f"  [HTTP error] {body}", file=sys.stderr)
        return ""
    except requests.RequestException as e:
        print(f"  [request error] {e}", file=sys.stderr)
        return ""


def call_judge_api(
    prompt_text: str, expect_pattern: str = None, retries: int = 4
) -> str:
    last_text = None
    response = None
    for attempt in range(1, retries + 1):
        try:
            payload = {
                "model": SCORE_MODEL,
                "max_tokens": 4096,
                "temperature": 0,
                "top_p": 1,
                "reasoning": {"effort": "medium"},
                "usage": {"include": True},
                "messages": [{"role": "user", "content": prompt_text}],
            }
            if SERVICE_TIER:
                payload["service_tier"] = SERVICE_TIER
            response = requests.post(
                SCORE_API_URL,
                headers={
                    "Authorization": f"Bearer {SCORE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=180,
            )
            if response.status_code == 200:
                data = response.json()
                _accumulate_usage(data)
                choices = data.get("choices") if isinstance(data, dict) else None
                if choices:
                    last_text = choices[0]["message"]["content"].strip()
                    if expect_pattern is None or re.search(expect_pattern, last_text):
                        return last_text
                    print(
                        f"  [judge retry {attempt}/{retries}] response missing expected token",
                        file=sys.stderr,
                    )
                else:
                    # 200 but no choices (e.g. OpenRouter returned an error body)
                    print(
                        f"  [judge retry {attempt}/{retries}] 200 but no choices: {response.text[:120]}",
                        file=sys.stderr,
                    )
            else:
                print(
                    f"  [judge retry {attempt}/{retries}] {response.status_code}: {response.text[:120]}",
                    file=sys.stderr,
                )
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ) as e:
            print(f"  [judge retry {attempt}/{retries}] {e}", file=sys.stderr)
            response = None
        time.sleep(min(2**attempt, 15))

    if response is not None and response.status_code != 200:
        response.raise_for_status()  # persistent non-200 -> HTTPError (401 handled by caller)
    if last_text is not None:
        return last_text
    raise RuntimeError(f"judge failed after {retries} retries")


def compare_answers(
    question: str, answer_key_data: dict, answer_a: str, answer_b: str
) -> dict:
    """Judge answer_a vs answer_b, correcting for LLM position bias.

    An LLM judge tends to favor whichever answer it sees first, regardless
    of quality. To cancel that out, the judge is asked twice — once as
    (A, B) and once as (B, A) — and the two verdicts are averaged (see
    score_map / score_map_swapped below, and avg_score's thresholds). If
    both orderings agree, the verdict is confident; if they disagree, it
    nets toward "A=B".
    """
    model_answer = answer_key_data.get("model_answer", "")
    principle = answer_key_data.get("principle", "")

    # Run 1: (A vs B)
    prompt_normal = PROMPT_PREFERENCE.format(
        question=question,
        model_answer=model_answer,
        principle=principle,
        transliteration_variants=variants_for(answer_key_data),
        answer_a=clean_answer(answer_a),
        answer_b=clean_answer(answer_b),
    )

    # Run 2: Swapped (B vs A)
    prompt_swapped = PROMPT_PREFERENCE.format(
        question=question,
        model_answer=model_answer,
        principle=principle,
        transliteration_variants=variants_for(answer_key_data),
        answer_a=clean_answer(answer_b),
        answer_b=clean_answer(answer_a),
    )

    verdict_pattern = r"\[\[([AB][><=]{1,2}[AB])\]\]"
    try:
        text_normal = call_judge_api(prompt_normal, expect_pattern=verdict_pattern)
        text_swapped = call_judge_api(prompt_swapped, expect_pattern=verdict_pattern)

        match_normal = re.search(verdict_pattern, text_normal)
        match_swapped = re.search(verdict_pattern, text_swapped)

        v_normal = match_normal.group(1) if match_normal else "unknown"
        v_swapped = match_swapped.group(1) if match_swapped else "unknown"

        if "unknown" in (v_normal, v_swapped):
            print(
                f"  [warn] verdict unparseable (normal={v_normal}, swapped={v_swapped})",
                file=sys.stderr,
            )
            return {
                "verdict": "unknown",
                "reason": f"--- RUN NORMAL ---\n{text_normal}\n\n--- RUN SWAPPED ---\n{text_swapped}",
                "verdict_normal": v_normal,
                "verdict_swapped": v_swapped,
            }

        score_map = {"A>>B": 2, "A>B": 1, "A=B": 0, "B>A": -1, "B>>A": -2}
        score_map_swapped = {"A>>B": -2, "A>B": -1, "A=B": 0, "B>A": 1, "B>>A": 2}

        val_normal = score_map.get(v_normal, 0)
        val_swapped = score_map_swapped.get(v_swapped, 0)
        avg_score = (val_normal + val_swapped) / 2

        if avg_score >= 1.5:
            final_verdict = "A>>B"
        elif avg_score >= 0.5:
            final_verdict = "A>B"
        elif avg_score <= -1.5:
            final_verdict = "B>>A"
        elif avg_score <= -0.5:
            final_verdict = "B>A"
        else:
            final_verdict = "A=B"

        return {
            "verdict": final_verdict,
            "reason": f"--- RUN NORMAL ---\n{text_normal}\n\n--- RUN SWAPPED ---\n{text_swapped}",
            "verdict_normal": v_normal,
            "verdict_normal_score": val_normal,
            "verdict_swapped": v_swapped,
            "verdict_swapped_score": val_swapped,
            "avg_score": avg_score,
        }
    except Exception as e:
        exit_if_unauthorized(e)
        print(f"  [compare error] {e}", file=sys.stderr)
        return {"verdict": "unknown", "reason": str(e)}


def format_components(components: list) -> str:
    lines = []
    for c in components or []:
        gate = " [GATE]" if c.get("is_gate") else ""
        lines.append(
            f"- {c.get('id', '')} ({c.get('points', '?')} pts){gate}: {c.get('credit_if', '')}"
        )
    return "\n".join(lines)


def format_gate(gate: dict) -> str:
    """Render the gate object as prompt text. The schema requires at least one
    concrete fail example per gate; those are what stop the judge waving through
    a plausible adjacent answer, so they go into the prompt with the condition."""
    gate = gate or {}
    fail_examples = gate.get("fail_examples") or []
    if not fail_examples:
        return gate.get("pass_condition", "")
    examples = "\n".join(f"  - {e}" for e in fail_examples)
    return (
        f"{gate.get('pass_condition', '')}\n"
        f"Answers that FAIL this gate (score 0):\n{examples}"
    )


def format_distractors(distractors) -> str:
    if not distractors:
        return "(none)"
    if isinstance(distractors, list):
        return "\n".join(f"- {d}" for d in distractors)
    return str(distractors)


def format_transliteration(variants) -> str:
    lines = []
    for v in variants or []:
        lines.append(f"- {v.get('canonical', '')} = {v.get('accepted_variants', '')}")
    return "\n".join(lines) if lines else "(none)"


def variants_for(answer_key_data: dict) -> str:
    """Accepted variants are split between a corpus-wide table and per-question
    entries; the judge needs both for the question in front of it."""
    return format_transliteration(
        GLOBAL_VARIANTS + (answer_key_data.get("accepted_variants") or [])
    )


def format_marking_rules_block(scoring_model: dict) -> str:
    """Global marking policy is carried as scoring_model flags rather than free
    text, so turn the flags that change grader behaviour back into rules."""
    sm = scoring_model or {}
    rules = []
    if sm.get("positive_marking_after_gate"):
        rules.append(
            "Award credit positively once the gate passes. Do not deduct for "
            "omissions, style, or unrelated errors."
        )
    if sm.get("integer_scores_only"):
        rules.append("Scores are whole numbers only. No half or fractional marks.")
    if sm.get("holistic_bands") is False:
        rules.append(
            "Do not use holistic performance bands. Award only the defined components."
        )
    if not rules:
        return ""
    return "## Additional Marking Rules\n" + "\n".join(f"- {r}" for r in rules) + "\n\n"


def extract_judge_json(text: str):
    """Pull the judge's result object out of its response. The prompt asks for
    a fenced ```json block at the end, but tolerate a bare object too."""
    candidates = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text or "", re.DOTALL)
    if not candidates:
        start, end = (text or "").find("{"), (text or "").rfind("}")
        if start != -1 and end > start:
            candidates = [text[start : end + 1]]
    for cand in reversed(candidates):  # last block wins: the verdict comes last
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            continue
    return None


def validate_judge_result(obj: dict, rubric_components: list) -> str:
    """Check the judge JSON against the grader output contract (SKILL.md,
    'Grader Output Contract'): every rubric component reported once with its
    rubric maximum, awarded within range, total = sum of awarded, and a failed
    gate zeroing everything. Returns "" when valid, else what is wrong — the
    problem string goes back into a retry, so the judge can self-correct."""
    if not isinstance(obj.get("gate_passed"), bool):
        return "gate_passed missing or not a boolean"
    comps = obj.get("components")
    if not isinstance(comps, list) or not comps:
        return "components missing or empty"
    expected = {c.get("id"): c.get("points") for c in rubric_components}
    awarded_by_id = {}
    for c in comps:
        cid = c.get("id")
        if cid not in expected:
            return f"unknown component id {cid!r}"
        if cid in awarded_by_id:
            return f"duplicate component id {cid!r}"
        awarded, maximum = c.get("awarded"), c.get("maximum")
        if not isinstance(awarded, int) or not isinstance(maximum, int):
            return f"{cid}: awarded/maximum must be whole numbers"
        if maximum != expected[cid]:
            return f"{cid}: maximum {maximum} != rubric points {expected[cid]}"
        if not 0 <= awarded <= maximum:
            return f"{cid}: awarded {awarded} outside 0..{maximum}"
        awarded_by_id[cid] = awarded
    missing = set(expected) - set(awarded_by_id)
    if missing:
        return f"missing component(s): {', '.join(sorted(missing))}"
    total = obj.get("total")
    if not isinstance(total, int):
        return "total missing or not a whole number"
    if not obj["gate_passed"]:
        if total != 0 or any(v != 0 for v in awarded_by_id.values()):
            return "gate failed but total/awarded are not all zero"
    elif total != sum(awarded_by_id.values()):
        return f"total {total} != sum of awarded {sum(awarded_by_id.values())}"
    return ""


JUDGE_JSON_RETRIES = 3  # full re-asks when the judge's JSON breaks the contract


def score_answer(question: str, answer_key_data: dict, answer: str) -> dict:
    prompt = PROMPT_SCORING.format(
        gate_criteria=format_gate(answer_key_data.get("gate")),
        components_guide=format_components(answer_key_data.get("components", [])),
        required_keywords=", ".join(answer_key_data.get("required_concepts") or []),
        bonus_keywords=", ".join(answer_key_data.get("indicative_terms") or []),
        transliteration_variants=variants_for(answer_key_data),
        distractors=format_distractors(answer_key_data.get("do_not_credit")),
        marking_rules_block=MARKING_RULES_BLOCK,
        question=question,
        model_answer=answer_key_data.get("model_answer", ""),
        principle=answer_key_data.get("principle", ""),
        response=clean_answer(answer),
    )
    result = {
        "score": None,
        "reason": "",
        "gate_passed": None,
        "components": None,
        "adjudication_required": None,
        "adjudication_note": None,
    }
    try:
        for attempt in range(1, JUDGE_JSON_RETRIES + 1):
            text = call_judge_api(prompt, expect_pattern=r'"gate_passed"')
            result["reason"] = text
            obj = extract_judge_json(text)
            problem = (
                "no JSON object found in response"
                if obj is None
                else validate_judge_result(obj, answer_key_data.get("components", []))
            )
            if not problem:
                result["score"] = obj["total"]
                result["gate_passed"] = obj["gate_passed"]
                result["components"] = obj["components"]
                result["adjudication_required"] = bool(
                    obj.get("adjudication_required", False)
                )
                result["adjudication_note"] = obj.get("adjudication_note")
                return result
            print(
                f"  [judge json retry {attempt}/{JUDGE_JSON_RETRIES}] {problem}",
                file=sys.stderr,
            )
        print(
            "  [warn] judge never returned contract-valid JSON; left unscored",
            file=sys.stderr,
        )
        return result
    except Exception as e:
        exit_if_unauthorized(e)
        print(f"  [score error] {e}", file=sys.stderr)
        result["reason"] = result["reason"] or str(e)
        return result


# Main
RUBRIC_SCHEMA = "2.0"


def validate_rubric(data: dict, path) -> None:
    """Stop on a rubric this build cannot grade with. Every rubric field is read
    with .get(), so an unusable one would otherwise sail through and hand the
    judge empty criteria — which still produces plausible-looking scores."""
    version = str(data.get("schema_version", "")).strip()
    if version != RUBRIC_SCHEMA:
        sys.exit(
            f"[error] {path}: schema_version {version or 'missing'}, but this "
            f"build reads {RUBRIC_SCHEMA}. Regenerate the rubric under "
            f"{RUBRIC_SCHEMA} with the authoring skill "
            "(.claude/skills/build-source-grounded-groundtruth-benchmarking-geology)."
        )
    problems = []
    for q in data.get("questions") or []:
        qid = q.get("id", "?")
        if not (q.get("gate") or {}).get("pass_condition"):
            problems.append(f"{qid}: gate.pass_condition is empty")
        components = q.get("components") or []
        if not components:
            problems.append(f"{qid}: no components")
        for c in components:
            if not c.get("credit_if"):
                problems.append(f"{qid}/{c.get('id', '?')}: credit_if is empty")
    if problems:
        sys.exit(
            f"[error] {path}: unusable rubric — the judge would receive empty "
            "criteria:\n  " + "\n  ".join(problems)
        )


with open(ANSWER_KEY_FILE) as f:
    rubric_data = json.load(f)
validate_rubric(rubric_data, ANSWER_KEY_FILE)
if args.check_rubric:
    print(
        f"[ok] {ANSWER_KEY_FILE}: schema {RUBRIC_SCHEMA}, "
        f"{len(rubric_data['questions'])} questions"
    )
    sys.exit(0)
answer_key_map = {norm_id(item["id"]): item for item in rubric_data["questions"]}

GLOBAL_VARIANTS = rubric_data.get("global_variants", [])
MARKING_RULES_BLOCK = format_marking_rules_block(rubric_data.get("scoring_model"))
QUESTION_TEXT_BY_ID = {q["id"]: q["question"] for q in rubric_data["questions"]}


def warn_rubric_mismatch(items, label) -> None:
    mismatched = sorted(
        {
            item["id"]
            for item in items
            if item.get("id") in QUESTION_TEXT_BY_ID
            and item.get("question") is not None
            and item["question"] != QUESTION_TEXT_BY_ID[item["id"]]
        }
    )
    if mismatched:
        print(
            f"[warn] {label}: {len(mismatched)} entries have an id matching "
            f"--rubric {args.rubric} but different question text (likely from a "
            f"different rubric) — ids: {', '.join(mismatched)}",
            file=sys.stderr,
        )


file_answers_map = {}
source_a = ""
source_b = ""

if args.score:
    file_a, file_b = args.score[0], args.score[1]
    with open(file_a) as f:
        file_a_items = json.load(f)
    warn_rubric_mismatch(file_a_items, f"File A ({file_a})")
    file_answers_map = {
        item["id"]: item.get("answer_b", item.get("answer", ""))
        for item in file_a_items
    }
    with open(file_b) as f:
        questions_to_run = json.load(f)
    warn_rubric_mismatch(questions_to_run, f"File B ({file_b})")
    source_a = str(file_a)
    source_b = str(file_b)
else:
    questions_to_run = rubric_data["questions"]

if args.ids:
    wanted = {str(x) for x in args.ids}
    wanted |= {norm_id(x) for x in args.ids}
    questions_to_run = [
        q
        for q in questions_to_run
        if str(q["id"]) in wanted or norm_id(q["id"]) in wanted
    ]
    if not questions_to_run:
        print(f"[error] No questions match --ids {args.ids}", file=sys.stderr)
        sys.exit(1)
    print(
        f"[ids] Limiting to {len(questions_to_run)} question(s): "
        f"{', '.join(str(q['id']) for q in questions_to_run)}"
    )

if args.score:
    missing_a = [
        str(q["id"]) for q in questions_to_run if q["id"] not in file_answers_map
    ]
    if missing_a and len(missing_a) == len(questions_to_run):
        sys.exit(
            f"[error] No question id in File B ({file_b}) matches any id in "
            f"File A ({file_a}). Ids must match exactly — check that both "
            "files come from the same rubric and id convention."
        )
    if missing_a:
        print(
            f"[warn] File A ({file_a}) has no answer for {len(missing_a)} of "
            f"{len(questions_to_run)} question ids: {', '.join(missing_a[:8])}"
            f"{', ...' if len(missing_a) > 8 else ''}. Those questions score "
            "A as an empty answer (gate fail -> 0).",
            file=sys.stderr,
        )


total = len(questions_to_run)
answers = []
if OUTPUT_FILE.exists():
    with open(OUTPUT_FILE) as f:
        answers = json.load(f)
    fields_to_check = ["answer_a", "answer_b"] if args.score else ["answer_b"]
    done_ids = set()
    wrong_rubric_ids = set()
    for e in answers:
        if any(is_failed_answer(e.get(f, "") or "") for f in fields_to_check):
            continue
        expected_q = QUESTION_TEXT_BY_ID.get(e["id"])
        if expected_q is not None and e.get("question") != expected_q:
            wrong_rubric_ids.add(e["id"])
            continue
        done_ids.add(e["id"])
    if wrong_rubric_ids:
        print(
            f"[warn] {len(wrong_rubric_ids)} entries in {OUTPUT_FILE} have an id "
            f"matching --rubric {args.rubric} but different question text (likely "
            f"from a different rubric run sharing this output file): "
            f"{', '.join(sorted(wrong_rubric_ids))}. Re-running them for this rubric.",
            file=sys.stderr,
        )
    answers = [e for e in answers if e["id"] in done_ids]
    questions_to_run = [q for q in questions_to_run if q["id"] not in done_ids]
    if done_ids:
        print(
            f"[resume] Skipping {len(done_ids)} already completed: {', '.join(sorted(done_ids))}"
        )

if args.score:
    print(f"Scoring: A = {source_a}  vs  B = {source_b}  (judge: {SCORE_MODEL})")
else:
    print(f"Generating answers with the live model ({args.mode} mode) -> {OUTPUT_FILE}")
if args.score:
    if not SCORE_API_KEY.strip():
        print(
            "[error] OPENROUTER_API_KEY not set (check your .env). Stopping.",
            file=sys.stderr,
        )
        sys.exit(1)
    missing = [
        item["id"]
        for item in questions_to_run
        if not answer_key_map.get(norm_id(item["id"]))
    ]
    if missing:
        print(
            f"[error] Missing answer key in rubrics for ID: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)
    check_service_tier()
    print_cost_estimate(len(questions_to_run))

write_lock = threading.Lock()


def log_error_entry(entry: dict, qid, message: str, raw_output: str) -> None:
    entry["error"] = message
    entry["raw_output"] = raw_output  # full opencode JSON event stream for debugging
    with write_lock:
        existing = []
        if ERROR_FILE.exists():
            try:
                with open(ERROR_FILE) as f:
                    existing = json.load(f)
            except (ValueError, OSError):
                existing = []
        existing = [e for e in existing if e.get("id") != qid]  # dedupe by id
        existing.append(entry)
        with open(ERROR_FILE, "w") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    print(f"  -> FAILED, logged to {ERROR_FILE}", file=sys.stderr)


def clear_error_entry(qid) -> None:
    """Drop qid from ERROR_FILE after it succeeds. A stale entry would keep
    start_eval.sh's retry loop creating pods for runs with nothing left to do.
    Caller must hold write_lock. Deletes the file when it empties out — the
    shell check treats a missing file and an empty list the same."""
    if not ERROR_FILE.exists():
        return
    try:
        with open(ERROR_FILE) as f:
            errors = json.load(f)
    except (ValueError, OSError):
        return
    kept = [e for e in errors if e.get("id") != qid]
    if len(kept) == len(errors):
        return
    try:
        if kept:
            with open(ERROR_FILE, "w") as f:
                json.dump(kept, f, indent=2, ensure_ascii=False)
        else:
            ERROR_FILE.unlink()
    except OSError as e:
        print(f"  [errors] failed to update {ERROR_FILE}: {e}", file=sys.stderr)


def save_entry(entry, announce=True) -> None:
    with write_lock:
        answers.append(entry)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(answers, f, indent=2, ensure_ascii=False)
        clear_error_entry(entry["id"])
    if announce:
        print(f"  -> saved to {OUTPUT_FILE}")


def process_item_generate(item, idx):
    """No --score: live-generate one answer (answer_b) and save it."""
    qid = item["id"]
    question = item["question"]
    print(f"[{idx}/{total}] {qid}: {question[:100]}")

    if args.mode == "api":
        answer_b, raw_output, gen_error = ask_api(question), "", ""
    else:
        answer_b, raw_output, gen_error = ask_opencode(question)
    write_transcript(qid, raw_output)  # no-op when raw_output is empty

    entry = {"id": qid, "question": question}
    entry["answer_b"] = answer_b  # raw, kept intact
    entry["answer_b_clean"] = clean_answer(answer_b)  # control tokens stripped
    if is_failed_answer(answer_b):
        log_error_entry(
            entry,
            qid,
            f"{args.mode} failed: "
            + (gen_error or "empty / thinking-only / leaked control tokens"),
            raw_output,
        )
        return entry

    save_entry(entry)
    return entry


def process_item_score(item, idx):
    """--score FILE_A FILE_B: both answers already exist on disk, judge them."""
    qid = item["id"]
    question = item["question"]
    header = f"[{idx}/{total}] {qid}: {question[:100]}"
    if args.workers == 1:
        print(header, flush=True)

    answer_a = file_answers_map.get(qid, "")
    answer_b = item.get("answer_b", item.get("answer", ""))

    rubric = answer_key_map.get(norm_id(qid), {})
    result = compare_answers(question, rubric, answer_a, answer_b)
    score_a = score_answer(question, rubric, answer_a)
    score_b = score_answer(question, rubric, answer_b)

    entry = {"id": qid, "question": question}
    entry["answer_a"] = answer_a
    entry["answer_a_clean"] = clean_answer(answer_a)
    entry["source_answer_a"] = source_a
    entry["answer_b"] = answer_b
    entry["answer_b_clean"] = clean_answer(answer_b)
    entry["source_answer_b"] = source_b
    entry["verdict"] = result["verdict"]
    entry["verdict_normal"] = result.get("verdict_normal")
    entry["verdict_normal_score"] = result.get("verdict_normal_score")
    entry["verdict_swapped"] = result.get("verdict_swapped")
    entry["verdict_swapped_score"] = result.get("verdict_swapped_score")
    entry["avg_score"] = result.get("avg_score")
    entry["reason"] = result["reason"]
    entry["score_a"] = score_a["score"]
    entry["score_a_reason"] = score_a["reason"]
    entry["score_a_gate_passed"] = score_a["gate_passed"]
    entry["score_a_components"] = score_a["components"]
    entry["score_a_adjudication_required"] = score_a["adjudication_required"]
    entry["score_a_adjudication_note"] = score_a["adjudication_note"]
    entry["score_b"] = score_b["score"]
    entry["score_b_reason"] = score_b["reason"]
    entry["score_b_gate_passed"] = score_b["gate_passed"]
    entry["score_b_components"] = score_b["components"]
    entry["score_b_adjudication_required"] = score_b["adjudication_required"]
    entry["score_b_adjudication_note"] = score_b["adjudication_note"]
    save_entry(entry, announce=False)
    result_block = (
        f"  -> verdict: {result['verdict']} | score_a: {score_a['score']} | "
        f"score_b: {score_b['score']}\n"
        f"  -> saved to {OUTPUT_FILE}"
    )
    print(result_block if args.workers == 1 else f"{header}\n{result_block}")
    return entry


process_item = process_item_score if args.score else process_item_generate

if args.workers > 1:
    print(f"[parallel] processing with {args.workers} workers")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(process_item, item, idx)
            for idx, item in enumerate(questions_to_run, 1)
        ]
        for future in concurrent.futures.as_completed(futures):
            future.result()  # surface exceptions (e.g. SystemExit from a 401)
else:
    for idx, item in enumerate(questions_to_run, 1):
        process_item(item, idx)
        if not args.score and args.mode == "api":
            time.sleep(1)

if args.score and answers:
    verdicts = [e.get("verdict", "") for e in answers]
    a_wins = sum(1 for v in verdicts if v in ("A>>B", "A>B"))
    b_wins = sum(1 for v in verdicts if v in ("B>>A", "B>A"))
    ties = sum(1 for v in verdicts if v == "A=B")
    unknown = sum(1 for v in verdicts if v == "unknown")
    scores_a = [
        e["score_a"] for e in answers if isinstance(e.get("score_a"), (int, float))
    ]
    scores_b = [
        e["score_b"] for e in answers if isinstance(e.get("score_b"), (int, float))
    ]
    print("\n=== Summary ===")
    print(
        f"Preference -> A wins: {a_wins} | B wins: {b_wins} | Ties: {ties} | Unknown: {unknown} | Total: {len(verdicts)}"
    )
    if scores_a:
        print(
            f"Score A    -> avg: {sum(scores_a) / len(scores_a):.2f}/10 (n={len(scores_a)})"
        )
    if scores_b:
        print(
            f"Score B    -> avg: {sum(scores_b) / len(scores_b):.2f}/10 (n={len(scores_b)})"
        )
    flagged = [
        str(e["id"])
        for e in answers
        if e.get("score_a_adjudication_required")
        or e.get("score_b_adjudication_required")
    ]
    if flagged:
        print(
            f"Adjudication -> {len(flagged)} question(s) flagged: {', '.join(flagged)}"
        )
    if JUDGE_USAGE["calls"]:
        cost = JUDGE_USAGE["cost"]
        # flex is ~50% off standard, so the two tiers differ by roughly 2x.
        if SERVICE_TIER == "flex":
            tier_note = f"${cost:.4f} (flex) | ~${cost * 2:.4f} est. standard"
        else:
            tier_note = f"${cost:.4f} (standard) | ~${cost / 2:.4f} est. flex"
        print(
            f"Judge cost -> {tier_note} | {JUDGE_USAGE['calls']} calls, "
            f"{JUDGE_USAGE['prompt_tokens']:,} in + {JUDGE_USAGE['completion_tokens']:,} out tokens"
        )
