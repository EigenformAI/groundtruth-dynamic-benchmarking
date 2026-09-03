# Authoring a rubric

A rubric turns a source corpus of geological reports into a **question set**, **reference answers**, a **machine-readable grading rubric** (the gate/component scheme this benchmark scores against), and **validation evidence**. Rubrics are authored with the agent skill in [`.claude/skills/build-source-grounded-groundtruth-benchmarking-geology/`](.claude/skills/build-source-grounded-groundtruth-benchmarking-geology/SKILL.md).

Open the repo in Claude Code and invoke `/build-source-grounded-groundtruth-benchmarking-geology` to author a new rubric.

Rubrics must be **schema 2.0**, the structured gate/component format defined by the skill. The rubric is validated as soon as it is chosen, before any further prompts or a billable GPU pod, and an older or malformed one is rejected with a message rather than silently grading against empty criteria.

---

## Prepare the corpus first

The candidate reads text, not PDFs, and the extraction is not one command for every source:

- **Single-column PDFs:** `pdftotext -layout`. The layout flag is required: assay and resource tables are unreadable without it.
- **Two-column PDFs:** `pdftotext -raw`. `-layout` preserves *visual* position, so on a two-column page every output line splices both columns together. Detect this by line-length distribution, not by looking for a gutter: a merged line may join with a single space.
- Always rewrite the form-feed page breaks as a visible `=== page N ===` marker. `grep` cannot see a form feed, and every evidence locator depends on citing a page.
- Always check the extracted page count against `pdfinfo`.
- Measure legibility yourself rather than trusting a metadata field, and count the four traps before authoring: words hyphenated across line breaks, soft hyphens (U+00AD), OCR-damaged numerals (digit strings containing `l`, `O`, `I`; these live in the PDF's own text layer, so verifying means rendering the page, not re-reading the text), and claims whose sentence spans a page boundary.
- Write an `INDEX.md` navigation aid beside the text: structure, metadata, known traps, attribution hazards, and **no geological claims**, so it can never become a low-authority source that contaminates authoring.

## The one-prompt authoring flow

Filling in the bracketed values is the whole of it; everything else is fixed, because leaving it to judgement is what produced three benchmarks with three different shapes. The bracketed slots take **measurements, not rules**. The rules are in the fixed text and apply to every corpus. If a corpus seems to need a fixed field changed, that is a signal the fixed field is wrong for every corpus: change it here, in the template, and re-check the benchmarks already built against the new rule. Only the items that fail it get revised; a template edit is not a reason to regenerate a site.

The flow stops **once**, at the Phase 2 blueprint, the only point where a script cannot judge what matters, and after approval it runs to the end on machine gates alone. If the session ends partway, run the same prompt again; the resume rule makes it continue from `_work/` instead of starting over. "One prompt" means one command that converges on a finished benchmark, not one heroic sitting.

```
Use the build-source-grounded-groundtruth-benchmarking-geology skill to create a new benchmark.

Run with exactly ONE approval stop. Present the Phase 2 blueprint and WAIT — that is
the only point where a human judges what a script cannot: whether the section scheme
carves the corpus well and every item is in scope. After approval, run END TO END
autonomously: make routine judgement calls yourself and record every one in the
validation document. Stop early for exactly two reasons:
- the corpus cannot support 50 defensible items (principle 16): report how many it can
  support and why, rather than padding;
- session capacity is nearly exhausted: write resume state and stop cleanly. NEVER
  compress quality to finish — a template fixture or an unverified anchor is worse
  than an honest partial, and the same prompt resumes the work.

RESUME RULE: if [output_root]/_work/BLUEPRINT.md already exists, this run is a resume,
not a fresh start. If it lacks the line "APPROVED", present the blueprint and wait for
approval again; if it carries it, do not stop — re-run the machine gates over
everything already on disk, read _work/PENDING.json, and continue from the first
unfinished item. Never regenerate
finished items and never renumber existing ids.

operation: "CREATE"
benchmark_name: "[NAME]"
region_or_dataset: "[what the corpus covers — properties, districts, era, reporting code]"
corpus_root: "[absolute path to the prepared text/ directory]"
domain_scope: "[what is in scope. Name the reporting code explicitly and say which
  codes are NOT in play, so questions are never framed around a standard the corpus
  does not follow.]"
candidate_access_mode: "RETRIEVAL_ASSISTED"

target_question_count: 50
  # Target, not a licence to pad. Per principle 16, if the corpus cannot support 50
  # defensible items, STOP and report how many it can and why.

target_categories: "Propose the section scheme from the corpus. The 50 questions must
  divide as evenly as the evidence allows — 10 sections x 5, or 8 sections x 6-7, is
  preferred over a lopsided split, because aggregation is unweighted and a large
  section would otherwise dominate the score. Balance the documents as well as the
  sections: derive a per-document item cap from content richness rather than page count,
  declare it in the blueprint with the resulting per-document counts, and treat it as a
  gate condition. A corpus where one source holds most of the words will otherwise
  become a benchmark on that source with the others as appendices — and where several
  documents address the same question in different settings, cross-document comparison
  items are the highest-value items available. MACHINE GATE 1 must pass BEFORE the
  blueprint is presented, so approval is spent on substance rather than arithmetic.
  On approval, write the line APPROVED into _work/BLUEPRINT.md and proceed — nothing
  after this point waits for a human."

difficulty_profile: "10 Easy, 17 Moderate, 17 Hard, 6 Expert. Every section carries at
  least one Easy item as an on-ramp. Easy means a genuine reasoning on-ramp per the
  skill's difficulty table, never trivia lookup."

expected_response_budget: "250-400 words per question"
score_per_question: 10
drift_check_interval: 25
output_root: "[repo]/rubrics/[site]"

source_authority_notes: "The candidate reads the prepared corpus and nothing else.
  Every evidence locator must be written in that corpus's own addressing scheme, and
  that scheme must identify one passage unambiguously and survive being pasted into a
  search — a page marker for extracted text, a file plus record key for chunked text, a
  table plus row key for structured data. State the scheme below and use it in every
  locator. Where the addressing differs from what a reader sees printed on the page,
  say so and cite the machine-visible one. Navigation aids, indexes, agent guides and
  generated summaries are never evidence. [Supply the MEASUREMENTS the fixed rules below need — facts, not
  rules, because the rules are already stated and must not be restated differently here:
  (1) which document dominates and by what share of words and pages, with the per-document
  item caps you derived; (2) the extraction mode used per document and what it preserved
  or destroyed; (3) the normalisations the anchor verifier must apply, with counts and
  which documents carry them; (4) how many character-damaged strings there are and where;
  (5) the corpus's era or reporting code, and which codes are NOT in play; (6) attribution
  hazards where one source covers several parties, properties or districts; (7) anything
  that looks like evidence but is not — boilerplate headings, generated descriptions,
  stale files, third-party claims the source itself disclaims.]"

working_files: "Write these under [output_root]/_work/ and keep them current — they
  are what makes one prompt sufficient:
  - BLUEPRINT.md: the section scheme plus a table allocating ALL 50 items before any
    drafting — id, section, difficulty, source document, construct, intended evidence
    anchor. Allocating everything up front is not bureaucracy: on one build, 9 of the
    last 22 items collided with already-shipped ones because an early cross-cutting
    section had already consumed the best evidence.
  - PENDING.json: every item not yet fully built (question + rubric + 4 fixtures +
    verified anchors), removed only when it passes MACHINE GATE 3.
  - check.py and verify_anchors.py: the machine gates as runnable scripts, so a
    resume can re-verify everything on disk before continuing."

machine_gates: "Each gate must PASS before the run moves on. On failure, fix and
  re-check — never proceed past a failing gate.
  1. Blueprint: exactly 50 items; per-section counts and the difficulty bands sum to
     the declared profile exactly; every section has at least one Easy; every item
     names its source document and intended anchor; the per-document counts respect
     the caps declared in the blueprint.
  2. Questions frozen: all 50 questions written to [Benchmark]_QA_questions.md BEFORE
     any model answer, gate or component text exists anywhere; then scan the file for
     leakage — it must contain no marking language and nothing that reveals an answer.
  3. Per section, immediately after authoring it: components sum to exactly 10 with
     one gate at C1 worth 2-4 points and >=6 above it; fixtures reconcile (awards sum
     to the total, a failed gate zeroes every component, and the four-fixture pattern
     0 / exact-gate-points / partial / 9-10 is present); every evidence locator passes
     a programmatic verbatim-substring check against the .txt; the span audit is
     clean or the span is recorded.
  4. Final: the skill's own validation gates, schema validation of the sidecar, the
     element-shape table, and [Benchmark]_QA_validation.md recording every judgement
     call, every low-confidence claim, and every conflict found but not used."

phase_separation: "The skill prefers separate contexts for question drafting and
  rubric construction. In a single run, approximate it: freeze the questions file
  first (MACHINE GATE 2), then author every rubric from the frozen question text and
  the corpus only. If a rubric needs intent that is not in the question text, the
  question is defective — rewrite the question rather than smuggling the intent into
  the rubric. The independent fixture re-scoring pass after the build is the real
  backstop for this compromise and is not optional."

special_constraints: "
  IDS: number questions continuously across sections so no question id can ever equal
  a component id — A1-A5, B6-B10, C11-C15, and so on. Components are always C1..Cn
  with C1 the gate, so a section-C question numbered C1 would collide with its own
  gate in the same grading call.

  GATE DISCIPLINE: exactly one gate per question, component C1, worth 2-4 points with
  at least 6 above it. The gate tests ONE core claim or one coherent mechanism — never
  a conjunction, and never the words 'AND/OR' in a pass_condition. A gate failure
  zeroes the whole question, so an ambiguous gate turns a 10 into a 0 on a coin flip.
  If two facts both feel essential, move one to C2..Cn or split the item. A gate
  requiring the candidate to name N separate things is a conjunction however it is
  worded: 'gives all four hosts' is a four-part gate, and a response correct on three
  of four scores 0 alongside a response about the wrong subject entirely. Gate on the
  single distinction the item exists to test; put the enumeration in C2..Cn. Two-way
  contrasts are exempt — 'distinguishes A from B' is one claim, not two.

  GATE MUST NOT DOUBLE-CREDIT: the gate and the components partition the answer; they
  do not overlap. If a component credits what the gate already requires, every response
  that passes the gate earns that component automatically — the true minimum rises above
  the gate value and the component discriminates nothing. This is the commonest defect
  calibration finds: across three benchmarks, 24 minimum-pass fixtures scored above their
  gate value, and it was the dominant finding at every one. It is also the failure mode
  the rule above creates if applied carelessly — moving enumeration out of the gate
  leaves a gate holding the conclusion and components holding its support, which is
  exactly where the overlap forms. Gate on the conclusion and credit the supporting
  detail below it, or gate on the distinction and credit the elaboration below it, but
  never gate on material a component also pays for. The check is mechanical, so run it
  on every item: the minimum-pass fixture must score EXACTLY the gate points. If it
  scores more, find the component that paid twice and narrow it.

  FIGURE BAN: you can open the source PDFs and see their figures; the candidate cannot.
  No question may require reading a map, cross-section, stratigraphic column, drill
  plan or photograph. Ground every item in body text, tables or captions, and verify
  it against the .txt files rather than the PDF.

  ATTRIBUTION: where a corpus covers more than one property, operator or client, never
  attribute one party's resource, grade or history to another. Where a figure could
  belong to either, the question must name the property explicitly.

  CALIBRATION: 4 fixtures per item, written as real candidate answers and never as
  descriptions of answers. A fixture reading 'Near-miss response: the central
  requirement is not established' announces its own verdict and tests nothing. Required
  pattern: a gate-fail near miss that is strong everywhere EXCEPT the gated claim and
  scores 0; a true minimum pass at exactly the gate points and no more; a partial-credit
  boundary; a full response at 9-10.

  CORPUS INTEGRITY: extraction damages text, and damaged text is not evidence. Three
  rules follow. (a) Where extraction destroyed a structure, that whole class of evidence
  is unusable — if reflowing a two-column page separated table rows from their values,
  no item may take a number from that document's tables, however clearly the prose
  reads. (b) Never build a load-bearing claim on a character-damaged string. Damage
  lives in the source text layer, so re-reading the extraction is not verification:
  render the page and read the image, or drop the item. An item resting on damage tests
  extraction, not geology. (c) The anchor verifier must normalise whatever the extraction
  introduced — soft hyphens, line-break hyphenation, ligatures, substituted characters —
  before matching, or it reports false failures and invites 'corrections' to anchors that
  were already right.

  CORPUS AUTHORITY AND ERA: the corpus as written is the authority for what it claims.
  No item may require the candidate to correct a source against present-day
  understanding, and no superseded interpretation may be presented as current fact:
  where a source reasons to a conclusion later revised, the item tests the reasoning as
  given. Terms whose meaning has shifted, and names current only in the corpus's period
  or jurisdiction, belong in global_variants with the proviso that makes each safe.

  ANCHOR AND SPAN DISCIPLINE: verify every evidence locator with a programmatic
  verbatim-substring check, not by spot-checking — one build needed 41 anchor
  corrections found this way, three of them wrong-page locators that no amount of
  re-reading would have surfaced. Run a span audit: a claim whose sentence crosses a
  page boundary is the commonest anchor error, and running heads inject text
  mid-sentence. Check retrievability: if a key fact is only stated in a split or
  garbled passage, a retrieval agent cannot find it and the item is harder than its
  label says — re-anchor to a passage stating it whole, or record the discrepancy.

  ELEMENT SHAPES: follow the skill's table exactly. required_concepts,
  accepted_variants, indicative_terms and do_not_credit are arrays of plain strings.
  evidence objects carry exactly claim, source, locator, authority, confidence, notes —
  no extra keys. Do not invent per-question fields beyond the schema; anything else
  belongs in the working files."
```

## One stop, and why that one

The old workflow also stopped after every authoring batch; those reviews mostly confirmed what scripts can confirm, and their real catches (anchor errors, ID collisions, template fixtures) are now encoded as machine gates and skill rules. The blueprint stop stays because its catches were of a different kind: a section outside the declared scope, a lopsided allocation, evidence already spent by another section. A script sees a well-formed blueprint; only a reader sees a wrong one, and at the blueprint it costs ten minutes to fix what would otherwise cost a rebuild.

## After the build

Two passes remain **not optional**, because neither the stop nor the gates can see how the rubric actually grades. Both are manual; the harness ships no runner for either:

1. **Independent fixture re-scoring.** Every fixture carries the score its author predicted. Feed each fixture's answer text back through the production judge (the `main.py --score` path, one fixture per question at a time) and treat any disagreement with the predicted score as a rubric defect. The fix goes in the marking block, not the fixture. About 200 fixtures for a 50-question benchmark.
2. **Independent geological review** of every item the validation document flags.

**Re-run anchor verification whenever the corpus is re-extracted.** Anchors are placed inside a single line so a candidate's grep returns them, and changing the extraction moves every line boundary.

---

## Answer-key isolation

In opencode mode the candidate is an agent with file tools, and the rubric that grades it lives in this repository a couple of levels above the corpus. `opencode run --dir` sets a working directory; it is **not** a boundary, and an absolute path resolves straight past it. Left open, a candidate can read the marking scheme for the question it is answering, and the resulting answers look excellent, score well, and mean nothing.

Two things close that, and they are independent on purpose:

1. **The authoring skill is switched off for the candidate.** `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1`, so a `.claude/skills/` directory anywhere in opencode's search path is never auto-loaded. A benchmark-authoring skill tells an agent to inventory the existing artifacts first, which walks it straight to the grading key. This is not the same as mechanism 2: parking `.claude/` removes *this repository's* skill; the env var also covers one loaded from `~/.claude/` or a parent directory.
2. **The answer key is taken off disk for the run.** `.claude/` and `rubrics/` are moved to a directory outside the repository before the first candidate call and moved back when the run exits: on a clean finish, on Ctrl-C, on `kill` (SIGTERM), and, after an outright SIGKILL, recovered on the next start. The harness reads the chosen rubric into memory up front and never re-opens the file, so the directory can be absent while the candidate works; scoring and `--check-rubric` never move anything.

The candidate's tools are **not** otherwise restricted: the run is `--dangerously-skip-permissions`, and subagents, `bash` and `webfetch` are all available. A candidate spawning an `explore` agent over its corpus is the behaviour being measured (roughly 7.5 tool calls per question), and forbidding it would change what the benchmark reports. The fence is specifically around the answer key; it is not a general sandbox.

**Tested rather than assumed.** opencode's `permission.external_directory: "deny"` does **not** restrict paths in 1.16.2: a candidate reads an absolute path outside `--dir` regardless: with the bare string form, with `{"**": "deny"}`, and with `--dangerously-skip-permissions` both present and absent. There is no working path fence, so the directories are made absent instead. With only `.claude` parked, a 50-question run still reached `rubrics/` on 13 questions (having spawned an explore subagent over the whole workspace first) and had gate and reference-answer text in context on 8 of them; parking `rubrics/` as well is what closed it. The park directory sits one level above the repo, so a filesystem-wide search could in principle still reach it. Only an OS sandbox is a true boundary.
