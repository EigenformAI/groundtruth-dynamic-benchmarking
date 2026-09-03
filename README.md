# Groundtruth Dynamic Benchmarking

**An Earth Sciences AI benchmark.** Groundtruth evaluates how well LLMs reason over **real geoscience source material** (mineral-exploration reports, government geological archives, technical filings), not textbook recall. A candidate model answers a fixed question set; an independent LLM judge grades every answer 0–10 against a calibrated, source-anchored rubric. Questions and grading keys are authored from openly licensed primary records, so every rubric claim carries an evidence locator rather than resting on invented geology.

**Geology is the first edition.** The eval harness (`main.py`) is domain-agnostic: it runs any schema-2.0 rubric. The authoring skill that turns a source corpus into a rubric is written for the geosciences today, and structured to extend to other earth-science domains.

| | |
|---|---|
| **Leaderboard** | [eigenform.ai/benchmark](https://eigenform.ai/benchmark): model and harness tracks over three 50-question districts |
| **Rubric dataset** | [`EigenformAI/groundtruth-dynamic-benchmarking`](https://huggingface.co/datasets/EigenformAI/groundtruth-dynamic-benchmarking) on Hugging Face |
| **Submissions dataset** | [`…-submissions`](https://huggingface.co/datasets/EigenformAI/groundtruth-dynamic-benchmarking-submissions): fork, add your `scores.json`, open a PR ([how ↓](#get-on-the-leaderboard)) |
| **Rubric authoring** | [`AUTHORING.md`](AUTHORING.md) |
| **Contributing** | [`CONTRIBUTING.md`](CONTRIBUTING.md) |

---

## Why it exists

Most LLM benchmarks in the geosciences test recall of facts already in the training data. Groundtruth tests something harder: can a model read the primary record for a district it has never seen (assay tables, drill logs, resource statements, cross-cutting stratigraphy) and answer a domain expert's question about it, with the evidence to back it up?

That makes it a signal for:

- **fine-tuned earth-science models:** does the adapter add domain reasoning, or just style?
- **retrieval and agent harnesses:** the harness track fixes the model, so the only variable is your scaffolding.
- **frontier-model selection** for geoscience work: the model track ranks frontier models on the same rubrics.

## How it works

Two stages, run separately. There is no "compare while generating" mode:

1. **Generate:** ask a model every rubric question, save the raw answers. One answer file per model.
2. **Score:** hand the answers to the judge.
   - **pointwise** (`--score FILE`): each answer graded 0–10 against the rubric on its own, one judge call per question. This is what a leaderboard column is built from. A model is graded once, so the same answer cannot come back with two different scores.
   - **pairwise** (`--score FILE_A FILE_B`): pointwise for both files, plus an order-swapped A-vs-B preference verdict (four judge calls per question). Use it for "did the fine-tune beat the baseline", not "what is the score".

The judge is a separate, fixed model (`openai/gpt-5.5`), deliberately independent of the candidate: one judge grades every model on every site. Its id is recorded in every run, so a mixed-judge table is detectable rather than silent. [More on scoring ↓](#how-scoring-works)

## Quick start

```bash
cp .env.example .env   # fill in the keys you need (see below)
uv sync
./start_eval.sh        # interactive: walks through every choice
```

`start_eval.sh` asks what you want to do (generate or score), validates only the keys that path needs, shows a summary, and confirms before anything billable. For generation it creates a RunPod GPU pod, runs the eval, and tears the pod down afterwards (also on Ctrl+C). The sample `example` rubric (Yudnamutana Copper, South Australia) ships with its corpus, so a fresh clone runs end to end with nothing else to download.

### Keys by path

| Key | Needed for |
|---|---|
| `RUNPOD_API_KEY` | Generate: creating the GPU pod |
| `HF_TOKEN` | Generate: pulling the model/LoRA on the pod |
| `OPENROUTER_API_KEY` | Score: the LLM judge, and OpenRouter candidates |
| `VLLM_API_URL`, `VLLM_API_KEY` | Standalone `main.py --mode api` against a running vLLM server |
| `GOOGLE_SERVICE_ACCOUNT_FILE`, `GOOGLE_SHEET_ID` | Optional: Google Sheets export |

An OpenRouter candidate (`--model openrouter/<id>`) needs no pod, no `HF_TOKEN`, and no `RUNPOD_API_KEY`. `start_eval.sh` has a score-only path that never starts a GPU.

### Running `main.py` directly

```bash
# generate (needs a running vLLM endpoint, or use start_eval.sh to get one)
uv run python main.py --mode api --workers 4 --output output/answers.json

# score one answer file pointwise (no GPU needed)
uv run python main.py --score output/answers.json --rubric <key> --output output/scores.json

# score two answer files against each other (pointwise + pairwise)
uv run python main.py --score output/answers.json output/answers-base.json --output output/score-vs-base.json
```

## Get on the leaderboard

The [leaderboard](https://eigenform.ai/benchmark) reads two Hugging Face datasets live, so a merged PR appears within minutes. Two tracks:

- **Model track:** any model, no special harness; ranks how the model does on the rubric.
- **Harness track:** retrieval / tool use / agent scaffolding, with the model pinned to a reference id (see `harness_track.json` in the dataset) so the harness is the only variable.

To submit:

1. **Score your model** against a rubric config (`coe`, `supergene`, `technical`, or `yudnamutana`): generate answers, then grade each 0–10 with the judge, using this harness.
2. **Fork** [`…-submissions`](https://huggingface.co/datasets/EigenformAI/groundtruth-dynamic-benchmarking-submissions) and copy `submissions/_template/` to `submissions/model-benchmark/<slug>/` (or `harness-benchmark/<slug>/`).
3. **Drop in** your unedited per-question `scores.json` and fill `meta.json`. `rubric_key`, `candidate_model_id`, and `contact_or_repo` matter most.
4. **Open a PR.**

Full field reference and the harness-track rules are in the [submissions dataset README](https://huggingface.co/datasets/EigenformAI/groundtruth-dynamic-benchmarking-submissions); see also [`CONTRIBUTING.md`](CONTRIBUTING.md). Submissions are self-reported and not independently re-run. The leaderboard flags mismatched question ids rather than hiding them.

## Rubrics

A rubric file is both the **question set** (generate mode reads the questions from it) and the **grading key** (score mode feeds its gate / component criteria to the judge). Available rubrics are registered in [`configs/rubrics.json`](configs/rubrics.json), which both `--rubric` and the `start_eval.sh` menu read; `--rubric` also accepts a path directly for a one-off run.

`example` is a three-question sample over the **Yudnamutana Copper** district of South Australia: 34 mineral-deposit records extracted from the SA Geodata / SARIG Data Package (Geological Survey of South Australia, CC BY 4.0 AU; attribution and the exact extraction in [`corpus/yudnamutana/ATTRIBUTION.md`](corpus/yudnamutana/ATTRIBUTION.md)). It is the only rubric whose corpus ships in the repo. The three 50-question leaderboard rubrics (Technical / WAMEX / USGS) and their corpora live on Hugging Face.

Rubrics must be **schema 2.0**, the structured gate/component format. They are validated on load; a malformed or older one is rejected with a message rather than silently grading against empty criteria.

**Building a rubric for a new corpus or domain:** the authoring flow, the one-prompt template, the schema, and the calibration discipline are in **[`AUTHORING.md`](AUTHORING.md)**. In short: it turns a prepared text corpus into questions, reference answers, a machine-readable grading rubric, and validation evidence, via the `build-source-grounded-groundtruth-benchmarking-geology` skill in [`.claude/skills/`](.claude/skills/build-source-grounded-groundtruth-benchmarking-geology/SKILL.md).

### Running the benchmark safely

In opencode mode the candidate is an agent with file tools, and the rubric that grades it lives in this repository. Two independent measures keep a candidate away from its own answer key during a run: the authoring skill is switched off (`OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1`), and `.claude/` plus `rubrics/` are moved outside the repository for the duration of the run and restored on exit (clean, Ctrl-C, SIGTERM, and recovered after SIGKILL on the next start). `main.py` reads the chosen rubric into memory up front, so the directory can be absent while the candidate works. The measurements behind this, and why `permission.external_directory: "deny"` is not enough, are in [`AUTHORING.md`](AUTHORING.md#answer-key-isolation).

## Models

The model menu in `start_eval.sh` is defined in [`configs/models.json`](configs/models.json). Add an entry to benchmark your own base model or LoRA adapter. Each entry carries a `provider` field (`vllm` default, or `openrouter`). Field reference and vLLM details are in [`RUNPOD.md`](RUNPOD.md).

## How scoring works

Pointwise scoring is one judge call per question: the judge sees the rubric's gate and components and returns a structured verdict for that answer alone. Nothing about it depends on any other model's answer, which is what makes the scores comparable across every model and site.

The pairwise verdict adds the A-vs-B comparison: each question is judged twice, once as (A, B) and once order-swapped, then the verdicts are averaged, to correct for the position bias LLM judges show. If both orderings agree the verdict is confident; if they disagree it nets toward a tie. See the docstring on `compare_answers()` in `main.py`.

The judge returns JSON, not a number: the gate decision, per-component `awarded`/`maximum` with reasons, and an adjudication flag for answers it cannot verify from the rubric alone. `main.py` validates the contract (component awards must sum to the total, and a failed gate zeroes everything) and re-asks the judge up to 3× when the JSON breaks it. A question the judge never returns valid JSON for is left unscored, not guessed.

**Sampling differs by path**, and one setting lives outside this repository. The judge is always called with `temperature 0, top_p 1`; `--mode api` sends the same. But in **opencode mode** (which includes every OpenRouter candidate) `main.py` sets nothing: it shells out, and opencode samples per its own config. A model that does not support a parameter never receives it, so some reasoning-model answers are not temperature-controlled and repeat runs will vary. And because the setting is opencode's, a different machine can produce different answers with no trace.

## Calibration fixtures

Every rubric question ships ~4 **calibration fixtures**: a fabricated candidate answer paired with the score its author *predicted* the marking block would produce (a gate-fail near miss, a bare gate pass, a partial-credit boundary, a full answer). They pin down how the gate and each component behave at their boundaries and are the reference point when an ambiguous marking block needs revising. The harness does not execute them automatically; feeding each back through `main.py --score` is one of the two non-optional manual passes after a build (see [`AUTHORING.md`](AUTHORING.md#after-the-build)).

## Outputs

All defaults land in `output/` (git-ignored):

- `output/answers*.json`: generated answers. `output/scores*.json`: scores, with the per-component breakdown, adjudication flags, and pairwise verdicts when two files were scored.
- `<output>.runs.jsonl`: one line per run, carrying the rubric and rubric file, candidate model, judge id, cost totals, and a per-question cost breakdown. Appended, so a resumed run adds a record.
- `<output>.costs.jsonl`: one line per billed call. `output/cost_ledger.jsonl`: every billed call across every run, appended.
- `<output>.errors.json`: failed generations, retried automatically on the next run and removed once the question succeeds.
- `output/transcripts/<stem>/<id>.jsonl`: raw opencode event stream per question, for debugging a specific answer.

Re-running with the same `--output` file **resumes**: completed question ids are skipped (matched by id *and* question text, so a stale file from a different rubric is never silently reused) and failed entries are retried.

## Cost

Every billable call (the judge, plus the candidate when it is an API model) is written to `<output>.costs.jsonl` and `output/cost_ledger.jsonl` as it happens, so a run that dies halfway still leaves its spend on disk. Judge and candidate spend are tracked separately and printed at the end. A local vLLM candidate reports `$0` per token, correctly, because that run is billed as GPU time on RunPod instead.

`main.py` prints a judge-cost estimate before a scoring run, scaled to `--score-mode`. The **candidate** is the hard half to predict: it is an agent loop, every step re-sends the whole conversation, and between a model that greps precisely and one that reads whole files the same question can cost more than 10× as much. Pin it down with a three-question probe and read the real per-question cost from the `<output>.costs.jsonl` it writes:

```bash
uv run python main.py --rubric <key> --ids 1 2 3 --model "openrouter/<id>" --output output/probe.json
```

## Google Sheets export

`scripts/export_sheets.py` pushes answer or scoring files into a Google Spreadsheet (one-time GCP service-account setup, see the docstring at the top of that file). `start_eval.sh` offers this automatically after a scoring run.

## Repository layout

```
main.py            single-file eval driver (generate + score)
prompts.py         judge prompt templates
start_eval.sh      interactive wrapper: pod lifecycle + eval + export
configs/           models.json (model/LoRA registry), rubrics.json (rubric registry)
rubrics/           question sets + grading keys (see Rubrics above)
corpus/            source documents for the sample rubric (Yudnamutana only; other corpora on Hugging Face)
scripts/           convert_jsonl.py, export_sheets.py
AUTHORING.md       building a rubric for a new corpus (RUNPOD.md covers vLLM/RunPod setup)
docs/              the leaderboard site (benchmark.eigenform.ai) and its assets
output/            (git-ignored) answers, scores, transcripts, cost ledger
```

## Related

Groundtruth is a project of [**Eigenform**](https://github.com/EigenformAI).

- [eigenform.ai/benchmark](https://eigenform.ai/benchmark): the live leaderboard this repo feeds
- [Rubric dataset](https://huggingface.co/datasets/EigenformAI/groundtruth-dynamic-benchmarking) · [Submissions dataset](https://huggingface.co/datasets/EigenformAI/groundtruth-dynamic-benchmarking-submissions) on Hugging Face

## License

Code and prompts: [MIT](LICENSE). The `corpus/yudnamutana/` sample is **CC BY 4.0 AU** (SA Geodata / SARIG), separate from the MIT license; attribution in [`corpus/yudnamutana/ATTRIBUTION.md`](corpus/yudnamutana/ATTRIBUTION.md). On Hugging Face each site's source material carries its own terms: the USGS (Supergene) material is US public domain, Yudnamutana is CC BY 4.0 AU, the WAMEX (Coe) material is public Western Australian government data, and the NI 43-101 technical set is text extracted from filings whose copyright stays with the issuers.

The Eigenform name and logo, and the brand assets under `docs/` (`favicon.png`, `favicon-32x32.png`, `apple-touch-icon.png`, `og.png`), are trademarks of Eigenform and are not covered by the MIT license.

## Citing

If you use Groundtruth or its rubrics, please cite it. See [`CITATION.cff`](CITATION.cff); GitHub's "Cite this repository" produces BibTeX and APA.

---

Part of [Eigenform](https://github.com/EigenformAI). Changelog in [`CHANGELOG.md`](CHANGELOG.md).
