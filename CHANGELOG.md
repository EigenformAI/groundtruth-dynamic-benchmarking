# Changelog

## v1.1.0 — Public leaderboard, pointwise scoring, and answer-key isolation

Adds the public leaderboard site, splits scoring into an independent pointwise score and an optional pairwise verdict, lets the candidate run as a hosted API model with no GPU pod, moves the answer key off disk while the candidate works, and writes a cost ledger for every billable call.

### Upgrading from v1.0.0

No breaking changes.

- `--score` now also accepts a **single** answer file — pointwise only (see below). The two-file form is unchanged.
- The sample rubric moved to `rubrics/Yudnamutana/`. The `example` registry key already points at the new path; update anything that hard-codes `rubrics/Yudnamutana_QA_grading_key.json`.
- During a generation run `main.py` now moves `.claude/` and `rubrics/` to a sibling directory of the repo and moves them back on exit. A run killed with `SIGKILL` cannot restore them; the next run recovers them automatically, or you can move `../.gtb-parked-*/` back by hand.

### New

- **Public leaderboard** — served from `docs/` at [eigenform.ai/benchmark](https://eigenform.ai/benchmark). A Model × district table over the three 50-question sites (Technical, WAMEX, USGS), built from pointwise multi-rubric scores with bootstrap confidence intervals, per-section and per-difficulty breakdowns, and gate-fail counts. Two tracks: self-reported and harness-run. The question sets and the submitted runs are published as Hugging Face datasets — [`EigenformAI/groundtruth-dynamic-benchmarking`](https://huggingface.co/datasets/EigenformAI/groundtruth-dynamic-benchmarking) for the rubrics, [`…-submissions`](https://huggingface.co/datasets/EigenformAI/groundtruth-dynamic-benchmarking-submissions) for the runs.
- **Pointwise scoring, independent of any other model** — `--score FILE` judges one answer file: each answer scored 0–10 against the rubric's gate and components on its own, one judge call per question. This is what a published leaderboard column is built from — a model is graded once, so the same answer can't come back with two different scores. `--score A B` still adds the order-swapped A-vs-B preference verdict on top (four calls per question); `--score-mode {both,pointwise,pairwise}` selects what to pay for with two files.
- **Candidate as a hosted API model, no pod** — `--model openrouter/<id>` (or `$OPENCODE_MODEL`) points the candidate at any provider opencode is configured for. An OpenRouter candidate needs no RunPod pod, no `HF_TOKEN`, and no `RUNPOD_API_KEY`. `configs/models.json` entries carry a `provider` field (`vllm` default, or `openrouter`); `start_eval.sh` gains a score-only path that never starts a GPU. The judge stays a separate, fixed model (`openai/gpt-5.5`) — its id is recorded in each run's record (`<output>.runs.jsonl`) so a mixed-judge table is detectable.
- **Answer-key isolation during generation.** In opencode mode the candidate is an agent with file tools, and `--dir` is a working directory, not a boundary. Two independent measures keep it away from its own grading key: the authoring skill is switched off (`OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1`, covering a skill in `~/.claude/` or a parent directory as well as this repo's); and `.claude/` plus `rubrics/` are moved outside the repository for the duration of the run and restored on exit (clean, Ctrl-C, or SIGTERM; recovered after SIGKILL on the next start). `permission.external_directory: "deny"` was measured against opencode 1.16.2 and does not restrict paths, so the fence is the files' absence, not configuration. The candidate's other tools and subagents are not restricted — this is not a general sandbox.
- **Cost ledger** — every billable call (the judge, plus the candidate when it is an API model) is appended to `<output>.costs.jsonl` and a repo-wide `output/cost_ledger.jsonl` as it happens, so a run killed midway still leaves on disk what it spent. Per-run totals and per-question cost land in `<output>.runs.jsonl`. The pre-run judge estimate now scales with `--score-mode` instead of assuming four calls per question.
- **Weekly repo-metrics snapshot** — `.github/workflows/repo-metrics.yml` appends stars, forks, clones, and views to `.github/metrics/stats.csv`.

### Rubric authoring

- **One-prompt authoring flow** — the README now carries the fixed prompt for the `build-source-grounded-groundtruth-benchmarking-geology` skill: corpus preparation (per-source `pdftotext` handling, page markers, an evidence-free `INDEX.md`), then a single template whose bracketed slots take measurements rather than rules. It stops once, at the Phase 2 blueprint, then runs to completion on machine gates; re-running the same prompt resumes from `_work/`. Two manual passes after the build remain non-optional: independent fixture re-scoring through the production judge, and geological review of flagged items.
- **Fixed element shapes in schema 2.0** (`SKILL.md`) — `required_concepts` / `accepted_variants` / `indicative_terms` / `do_not_credit` are plain strings; `evidence` is an object with exactly `claim`, `source`, `locator`, `authority`, `confidence`, `notes` and no extra keys; `global_variants` and `source_authority` have fixed object shapes. Three benchmarks built from the old `[]` examples had produced three incompatible shapes for one grading harness.
- **Gate double-credit rule** (`SKILL.md`) — no post-gate component may pay for what the gate already requires; the minimum-pass fixture must score exactly the gate points.

### Known limitations

- The judge model is fixed at `openai/gpt-5.5` in `main.py`; there is no flag to change it.
- In opencode mode the candidate's sampling is set by your local opencode config, not by `main.py`, and reasoning models may receive no temperature at all — repeat runs will vary.
- Calibration fixtures in a rubric are still not auto-executed by the harness.
- `main.py` emits an aggregate score per run; the section and difficulty breakdowns on the leaderboard are computed downstream from the pointwise score files.

### License

Code and prompts: MIT. The `corpus/yudnamutana/` sample stays CC BY 4.0 AU (SA Geodata / SARIG) — see `corpus/yudnamutana/ATTRIBUTION.md`. On Hugging Face each site's source material is licensed on its own terms: the USGS (Supergene) material is US public domain, Yudnamutana is CC BY 4.0 AU, the WAMEX (Coe) material is public Western Australian government data, and the NI 43-101 technical set is text extracted from filings whose copyright stays with the issuers.

## v1.0.0 — Initial release

A benchmark harness for evaluating fine-tuned geology LLMs against a baseline, using an LLM judge.

### Quickstart

```bash
cp .env.example .env   # fill in the keys you need — see README
uv sync
./start_eval.sh
```

Requires API keys depending on what you run: RunPod (generation), OpenRouter (judge), Hugging Face (pulling gated models). See the README for which keys each path needs.

### What's included

- **Generate + score pipeline** (`main.py`) — run a model against a fixed question set, then score it pointwise (0–10, gated rubric) and pairwise against a baseline, with position-bias correction.
- **Structured grader output** — the judge returns JSON (gate decision, per-component awarded/maximum, total, an adjudication flag for responses it can't verify from the rubric alone), not a single number. `main.py` validates the contract itself — component awards must sum to the total, and a failed gate zeroes everything — and re-asks the judge (up to 3 times) when the JSON breaks it. A question the judge never returns valid JSON for is left unscored rather than guessed.
- **Rubric schema 2.0** — gate + graduated components, required concepts, and do-not-credit lists. Rubrics are validated on load; a malformed or wrong-schema rubric fails loudly instead of silently grading against empty criteria.
- **Sample rubric + corpus** (`rubrics/Yudnamutana_QA_grading_key.json`) — a worked, corpus-grounded example over a small, CC BY 4.0–licensed extract of the SA Geodata / SARIG Data Package (South Australian government), shipped in the repo so the harness runs end to end on a fresh clone.
- **`start_eval.sh`** — interactive wrapper: spins up a RunPod GPU pod, runs generation, tears the pod down, with cost estimates and confirmation before anything billable happens.
- **Model & rubric registries** (`configs/models.json`, `configs/rubrics.json`) — add your own model/LoRA or rubric without touching code.
- **`build-source-grounded-groundtruth-benchmarking-geology` skill** — the agent skill used to author the sample rubric from a source corpus; reusable for other domains. Each authored rubric carries calibration fixtures (expected scores for known-good/bad responses), currently for manual review — the harness does not yet run them automatically.

### Known limitations

- Only one rubric ships ready to run (`example`, Yudnamutana). Others must be authored with the skill or supplied via `--rubric <path>`.
- Calibration fixtures in a rubric are not auto-executed by the harness.
- Results aren't broken down by rubric section or difficulty — only an aggregate score.

### License

Code: MIT. The sample corpus (`corpus/yudnamutana/`) is CC BY 4.0 AU, separately from the code — see `corpus/yudnamutana/ATTRIBUTION.md` for the required attribution.
