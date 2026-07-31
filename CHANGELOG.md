# Changelog

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
