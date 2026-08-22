# Groundtruth Dynamic Benchmarking (Geology Edition)
Benchmark harness for evaluating fine-tuned geology LLMs (LoRA adapters on Gemma) against a baseline on a fixed question set, using another LLM as judge. Questions and grading keys are authored from real geological source material; the rubric that ships with the repo is grounded in an openly licensed corpus for the Yudnamutana Copper district, South Australia.

Evaluation is always a two-step process — there is no "compare while generating" mode:

1. **Generate** — ask a model every rubric question and save the raw answers. Repeat once per model you want to test (baseline, LoRA gen 1, ...) to get one answer file each.
2. **Score** — feed two answer files to the judge, which compares them question-by-question and also scores each answer 0–10 against the rubric.

## Quick start

```bash
cp .env.example .env   # fill in the keys you need (see below)
uv sync
./start_eval.sh        # interactive: walks through every choice
```

`start_eval.sh` asks what you want to do, validates only the keys that path needs, shows a summary, and asks for confirmation before creating anything billable. For generation it creates a RunPod GPU pod, runs the eval, and tears the pod down afterwards (also on Ctrl+C).

### Required keys per path

| Key | Needed for |
|---|---|
| `RUNPOD_API_KEY` | Generate — creating the GPU pod |
| `HF_TOKEN` | Generate — pulling the model/LoRA on the pod |
| `OPENROUTER_API_KEY` | Score — the LLM judge |
| `VLLM_API_URL`, `VLLM_API_KEY` | Only for standalone `main.py --mode api` runs against an already-running vLLM server |
| `GOOGLE_SERVICE_ACCOUNT_FILE`, `GOOGLE_SHEET_ID` | Optional — Google Sheets export |

### Running `main.py` directly

```bash
# generate (needs a running vLLM endpoint, or use start_eval.sh to get one)
uv run python main.py --mode api --workers 2 --output output/answers-gen2.json

# score two existing answer files (no GPU needed)
uv run python main.py --score output/answers-gen2.json output/answers-base.json \
  --output output/score-gen2-vs-base.json
```

## Rubrics

A rubric file is both the **question set** (generate mode reads the questions from it) and the **grading key** (score mode feeds its gate / component criteria to the judge).

Available rubrics are registered in [`configs/rubrics.json`](configs/rubrics.json), which both `--rubric` and the `start_eval.sh` menu read, so the two can never drift apart. Add an entry there to register your own; `--rubric` also accepts a path directly for a one-off run.

| Field | Required | Meaning |
|---|---|---|
| `key` | yes | What `--rubric` matches on |
| `label` | yes | Display name in the `start_eval.sh` menu |
| `file` | yes | Path to the rubric JSON |
| `project_dir` | no | Source documents opencode may explore for this rubric; omit for none |

`example` is a three-question sample rubric over the **Yudnamutana Copper** district of South Australia, and the only one whose corpus ships with the repo — so `./start_eval.sh` works on a fresh clone with nothing else to download. Use it to see the format, smoke-test a judge run, or as the starting point for your own.

Its corpus is in [`corpus/yudnamutana/`](corpus/yudnamutana/): 34 mineral deposit records extracted from the SA Geodata / SARIG Data Package published by the Geological Survey of South Australia, under CC BY 4.0 AU. Attribution and the exact extraction are recorded in [`corpus/yudnamutana/ATTRIBUTION.md`](corpus/yudnamutana/ATTRIBUTION.md). Because the corpus is real, every claim in the rubric carries an evidence locator (`MINERAL_DEPOSIT_NO` plus column) rather than resting on invented geology.

Rubrics must be **schema 2.0** — the structured gate/component format defined by the authoring skill below. The rubric is validated as soon as it is chosen — before any further prompts or a billable GPU pod — and an older or malformed one is rejected with a message rather than silently grading against empty criteria.

### How the rubrics are built

The rubric files are authored from a source corpus of geological reports using the agent skill in [`.claude/skills/build-source-grounded-groundtruth-benchmarking-geology/`](.claude/skills/build-source-grounded-groundtruth-benchmarking-geology/SKILL.md). It turns a supplied corpus into questions, reference answers, a machine-readable grading rubric (the gate/component scheme this benchmark scores against), and validation evidence. Open the repo in Claude Code and invoke `/build-source-grounded-groundtruth-benchmarking-geology` to author a new rubric.

## Models

The model menu in `start_eval.sh` is defined in [`configs/models.json`](configs/models.json) — add an entry there to benchmark your own base model or LoRA adapter. Field reference and vLLM details live in [`docs/runpod.md`](docs/runpod.md).

## How scoring works

Each question is judged **twice** — once as (A, B) and once order-swapped as (B, A) — and the verdicts are averaged. This corrects for position bias: LLM judges tend to favor whichever answer they see first. If both orderings agree the verdict is confident; if they disagree it nets toward a tie. See the docstring on `compare_answers()` in `main.py` for the scoring math.

Every answer additionally gets an independent 0–10 score (`score_answer()`) against the rubric's gate/component criteria, separate from the pairwise verdict. The judge reports this as structured JSON following the grader output contract in the [authoring skill](.claude/skills/build-source-grounded-groundtruth-benchmarking-geology/SKILL.md): the gate decision, per-component `awarded`/`maximum` with reasons, and an adjudication flag for answers it cannot verify from the rubric alone. `main.py` validates the contract — component awards must sum to the total, and a failed gate zeroes everything — and re-asks the judge when the JSON breaks it. The per-component breakdown is saved next to the total in the score file. A cost estimate for the judge calls is printed before the run starts, and the actual spend is reported at the end.

## Outputs

All defaults land in `output/` (git-ignored):

- `output/answers*.json` — generated answers; `output/scores.json` — verdicts + scores, including the per-component breakdown and adjudication flags.
- `<output>.errors.json` — failed generations, retried automatically on the next run and removed from the file once the question succeeds.
- `output/transcripts/<output-stem>/<id>.jsonl` — raw opencode event stream per question, for debugging a specific answer.

Re-running with the same `--output` file **resumes**: completed question ids are skipped (matched by id *and* question text, so a stale file from a different rubric is never silently reused) and failed entries are retried.

## On Hugging Face

The rubrics, corpora, and grading keys are also published as a
[Hugging Face dataset](https://huggingface.co/datasets/EigenformAI/groundtruth-dynamic-benchmarking)
with one config per rubric — `yudnamutana` (3-question sample), plus three
50-question suites: `coe`, `supergene`, `technical`. Load any of them with
`datasets.load_dataset("EigenformAI/groundtruth-dynamic-benchmarking", "<key>")`.
Baseline results across six frontier models, plus community submissions, show
up on the [leaderboard](https://benchmark.eigenform.ai) —
submission instructions are in the
[submissions dataset README](https://huggingface.co/datasets/EigenformAI/groundtruth-dynamic-benchmarking-submissions).

## Google Sheets export

`scripts/export_sheets.py` pushes answer or scoring files into a Google Spreadsheet (one-time GCP service-account setup — see the docstring at the top of that file). `start_eval.sh` offers this automatically after a scoring run.

## License

Code, prompts, and rubrics are released under the [MIT License](LICENSE). The `corpus/yudnamutana/` data is an extract from the SA Geodata / SARIG Data Package and remains licensed **CC BY 4.0 AU** — it is not covered by the MIT license; attribution details are in [`corpus/yudnamutana/ATTRIBUTION.md`](corpus/yudnamutana/ATTRIBUTION.md).

## Repository layout

```
main.py            single-file eval driver (generate + score)
prompts.py         judge prompt templates
start_eval.sh      interactive wrapper: pod lifecycle + eval + export
configs/           models.json (model/LoRA registry), rubrics.json (rubric registry)
rubrics/           question sets + grading keys (see Rubrics above)
corpus/            source documents the sample rubric is grounded in
scripts/           convert_jsonl.py, export_sheets.py
docs/              runpod.md — vLLM/RunPod setup notes
output/            (git-ignored) answers, scores, transcripts
```
