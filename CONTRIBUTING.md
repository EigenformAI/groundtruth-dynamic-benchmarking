# Contributing

The main way to contribute is to **put a model or harness on the [leaderboard](https://eigenform.ai/benchmark)**. This needs no change to this repo. It is a pull request against the **submissions dataset**.

1. **Score your model** against a rubric config (`coe`, `supergene`, `technical`, or `yudnamutana`): generate an answer for every question, then grade each 0–10 against that rubric's gate/component criteria with the LLM judge. This harness does both (see [`README.md`](README.md#running-mainpy-directly)).
2. **Fork** [`EigenformAI/groundtruth-dynamic-benchmarking-submissions`](https://huggingface.co/datasets/EigenformAI/groundtruth-dynamic-benchmarking-submissions) and copy `submissions/_template/` to `submissions/model-benchmark/<slug>/` (or `harness-benchmark/<slug>/`).
3. **Drop in** your **unedited** per-question `scores.json`: one entry per question, `id` / `question` / `score_b` at minimum, plus `score_b_gate_passed`, `score_b_components`, `score_b_adjudication_required` for full leaderboard detail.
4. **Fill `meta.json`** for real: `rubric_key` and `candidate_model_id` so the leaderboard reads it correctly, and `contact_or_repo` so the result is traceable and reproducible.
5. **Open the PR.** Once merged it appears on the leaderboard within minutes.

Results are self-reported and not independently re-run. Submissions whose question ids or text don't match the rubric named in `rubric_key` are **flagged on the leaderboard, not hidden**, so check `meta.json` before opening the PR. The full field reference and the harness-track rules (pinned reference model, `harness_name`, `harness_repo`) are in the [submissions dataset README](https://huggingface.co/datasets/EigenformAI/groundtruth-dynamic-benchmarking-submissions).

## License

By contributing you agree that your contribution is licensed under the repository's [MIT License](LICENSE).
