---
name: build-source-grounded-groundtruth-benchmarking-geology
description: Use to create or revise a set of corpus-grounded geology benchmark questions, reference answers, (machine-readable) rubrics, and validation evidence
---

## Role and task

You are constructing a source-grounded benchmark of geological reasoning over a supplied corpus. Produce questions, concise but complete reference answers, and a marking scheme rigorous enough for consistent human or LLM grading.

The benchmark should resemble a good external-examination paper and marking scheme: criterion-referenced, explicit about what earns credit, tolerant of valid alternative wording, and capable of distinguishing shallow retrieval from sound geological reasoning. It is not a trivia quiz, a keyword-matching exercise, or a data-cleaning test.

## Required Inputs

Establish these before authoring questions.

If an input is missing and materially impacts benchmark validity, escalate this to the user rather than silently guessing. Use the question asking tool call for this if available.

```yaml
benchmark_name: "[name]"
region_or_dataset: "[region, survey, deposit, or corpus]"
corpus_root: "[path]"
domain_scope: "[geology/mineral systems/exploration scope]"
candidate_access_mode: "OPEN_CORPUS | RETRIEVAL_ASSISTED | CLOSED_CORPUS"
target_question_count: "[not a quota if evidence is thin: escalate if necessary]"
operation: "CREATE | EXTEND | REVISE"
target_categories: "[optional topic groups]"
difficulty_profile: "[optional Easy/Moderate/Hard/Expert targets]"
expected_response_budget: "[optional words, tokens, or time per question]"
score_per_question: 10
drift_check_interval: 50
output_root: "[path]"
source_authority_notes: "[known primary sources, derived files, OCR limitations]"
special_constraints: "[language, commodities, benchmark audience, etc.]"
```

Record all assumptions. In particular, do not leave the candidate's corpus-access mode implicit: self-containedness for a marker does not imply that a retrieval-heavy question is answerable without the corpus.

One execution builds one benchmark over one declared corpus. Run the workflow separately for multiple corpora unless a cross-corpus benchmark is explicitly requested. There is no minimum question count: deliver fewer questions when the evidence cannot support the target count.

Candidate-access modes mean:

- `OPEN_CORPUS`: the candidate may browse the full supplied corpus while answering.
- `RETRIEVAL_ASSISTED`: the candidate may use an approved search/retrieval layer over the corpus, but is not assumed to inspect every raw file directly.
- `CLOSED_CORPUS`: all source facts needed to answer must be supplied in the question or declared study material; live corpus retrieval is unavailable.

For `EXTEND` or `REVISE`, inventory the existing benchmark artifacts first. Preserve published IDs, record retired IDs, and apply any intentional wording change to every companion artifact and calibration fixture in the same revision.

## Non-Negotiable Principles

1. **Explore before authoring.** Inspect the corpus broadly enough to understand its source types, themes, terminology, duplicated material, gaps, and contradictions before selecting questions.
2. **Admit only verifiable questions.** Every determinate factual requirement must have an internal evidence anchor. A database column, filename, or generated summary alone does not justify a question if the interpretation requires a geological narrative the corpus does not contain.
3. **Test geological understanding.** Prefer explanation, mechanism, comparison, evidence evaluation, uncertainty, and cross-source synthesis. Data interaction should support the reasoning task rather than become the task.
4. **Exclude irrelevant task types.** Do not add coding, file-manipulation, administrative-record, or generic data-cleaning questions unless those operations are themselves part of the benchmark's declared construct. Data-quality issues may be used only when they require geologically meaningful interpretation.
5. **Separate authoring stages to reduce bias.** Question selection and drafting must occur before reference-answer and rubric construction. Prefer separate agents or contexts for question authoring and answer/rubric authoring. A final verifier adjudicates both against the corpus.
6. **Make every grading block self-contained.** A marker receiving only one question, one candidate response, and that question's marking block must have enough information to grade without opening the corpus, another question, an appendix, or a revision history. No answer, example, premise, or rule may be supplied only by another question block.
7. **Put principles before keywords.** Explain the geological reason an answer is correct. Keywords and examples are indicative evidence, never a substitute for demonstrated logic.
8. **Use a real correctness gate.** Every question has a narrow minimum-correctness gate. Gate failure gives zero, with no peripheral credit leakage. The gate must not demand the whole answer or make graduated scoring meaningless.
9. **Award marks positively after the gate.** Credit demonstrated knowledge and reasoning. Do not deduct marks for omissions, style, or unrelated errors. A directly contradictory statement means the affected criterion has not been demonstrated; it is not a free-floating penalty.
10. **Use whole, non-overlapping marks.** Each question is scored from 0 to 10 in integer points. Components total exactly 10, and the same fact or inference is credited once.
11. **Preserve uncertainty and disagreement.** Do not silently normalize source conflicts, OCR uncertainty, different scopes, or legitimately competing geological models. Resolve them by source authority where justified, or expose and attribute them in the question and rubric.
12. **Accept meaning, not surface form.** Credit valid paraphrases, spelling/transliteration/OCR variants, and unexpected but sound approaches. Do not call materially different methods, orientations, scales, or claims "variants."
13. **Keep source fidelity distinct from outside expertise.** For corpus-specific facts, the verified benchmark evidence controls grading even when an expert might expect something else. Outside knowledge may enrich reasoning but may not replace the corpus-specific answer actually asked for.
14. **Do not require candidate citations by default.** Keep provenance for internal verification and adjudication. Require citations in candidate answers only when source use is an explicit assessed skill.
15. **Keep identifiers stable.** Once questions are referenced by grading blocks, sidecars, results, or reports, retire redundant IDs rather than casually renumbering the set.
16. **Prefer fewer defensible questions to padded coverage.** The target count and difficulty distribution are planning guides, not reasons to admit weak, redundant, or ungradeable items.

## Source Authority Contract

Before selecting questions, write a corpus-specific source authority contract. Do not assume that all file types are equally reliable.

A reasonable default hierarchy is:

1. Direct primary-source text, original structured measurements, and official records whose semantics are understood.
2. Primary maps, figures, tables, logs, and appendices inspected directly.
3. OCR or translations of primary material, with page images or independent passages used to check high-risk facts.
4. Human-authored descriptions or verified derived tables.
5. Automatically generated figure descriptions, summaries, extracted memories, and filenames.

Adapt this hierarchy to the corpus. A lower-ranked source can still be the only evidence for a fact, but that limitation must be recorded. Generated descriptions should not control fine numerals, exact names, orientations, or units when direct evidence is available.

For each conflict:

- Determine whether the sources actually disagree or instead address different scales, dates, definitions, locations, or questions.
- Prefer the more direct and authoritative evidence only when there is a defensible basis.
- If co-equal sources disagree, preserve both with attribution and define how each is graded.
- Never merge separate datasets into a fictitious compound observation.
- Never turn contradictory orientations, drilling methods, counts, or geological scopes into accepted synonyms.
- Record why a canonical answer was chosen and what supported alternatives receive credit.

## Phase 1: Corpus Exploration

Explore the corpus exhaustively enough to create an evidence and opportunity inventory. Parallelize bounded searches by source family or geological theme where possible.

Produce an internal inventory containing:

- Source families, formats, paths, dates, provenance, and likely authority.
- Major geological domains, stratigraphy, structures, mineral systems, exploration methods, regolith issues, deposits/prospects, and history.
- High-value named facts: features, IDs, locations, methods, grades, widths, depths, orientations, scales, counts, and units.
- Mechanisms and causal chains that can support reasoning questions.
- Cross-source relationships suitable for synthesis.
- Contradictions, OCR/transliteration variants, absent records, duplicate records, and artefacts that could support careful-reading questions.
- Areas with enough narrative support for non-dominant commodities or mineral systems.
- Areas that are too thin, ambiguous, or source-dependent to assess fairly.

Create a private evidence card for every candidate question:

```yaml
candidate_id: "[temporary ID]"
construct: "[what capability this tests]"
question_opportunity: "[short description]"
primary_evidence:
  - source: "[path/document]"
    locator: "[page/line/row/figure/table]"
    supported_claim: "[claim]"
secondary_evidence: []
source_risks: "[OCR, unit, conflict, derived source, etc.]"
expected_reasoning: "[mechanism or synthesis]"
answerability: "PASS | REWRITE | REJECT"
```

Reject an opportunity if the evidence card cannot support both a defensible answer and a self-contained rubric.

## Phase 2: Benchmark Blueprint

Build a blueprint before writing polished questions.

### Categories

Group questions into coherent lettered sections. Categories should reflect the corpus, for example:

- Regional setting and stratigraphy
- Structure and tectonics
- Mineralisation and deposit models
- Geochemistry, regolith, and drilling
- Geophysics and targeting
- Exploration history and model evolution
- Integrated synthesis and target ranking
- Foundational on-ramps

Do not force equal category sizes when the evidence does not support them.

### Question Types

Use a deliberate mixture of:

- Focused factual retrieval with an interpretive consequence
- Mechanism explanation
- Comparison or discrimination between models
- Evidence-strength or uncertainty assessment
- Reconciliation of sources, scales, or historical interpretations
- Spatial, stratigraphic, temporal, or multi-scale reasoning
- Cross-source synthesis and target ranking
- Careful-reading items about a genuine contradiction, absence, provenance issue, or artefact

Careful-reading items must assess meaningful source literacy, not arbitrary trick wording. If a premise is contested, say so or explicitly ask the candidate to evaluate it rather than embedding a misleading assertion as unquestioned fact.

### Difficulty

Assign difficulty on two independent axes:

1. **Data-interaction load:** from one direct source fact to multi-source retrieval and reconciliation.
2. **Reasoning depth:** from recall, to one mechanism, to multi-step comparison, to open synthesis under uncertainty.

Then assign an advisory label:

| Label    | Typical profile                                                                      |
| -------- | ------------------------------------------------------------------------------------ |
| Easy     | Low retrieval load; one foundational concept or direct implication                   |
| Moderate | One or two sources; a clear mechanism or comparison                                  |
| Hard     | Several linked facts; multi-step reasoning, caveats, or source reconciliation        |
| Expert   | Open but bounded synthesis, ranking, model discrimination, or uncertainty management |

Difficulty never changes the 10-point scale or marking strictness. Include accessible, reasoning-based on-ramps and genuinely discriminating hard/expert items. Do not target a candidate pass rate or force a bell curve.

### Coverage And Redundancy

For every proposed item, identify:

- The capability it uniquely tests.
- The primary geological principle.
- Its main evidence sources.
- Its expected difficulty on both axes.
- Its overlap with all other questions.

Retire or merge questions that test the same facts and reasoning. Preserve stable IDs after publication.

Include non-dominant commodities when the corpus contains a coherent exploration or mineral-system narrative.

## Phase 3: Question Drafting

Draft the questions without drafting their answers or rubrics in the same pass.

Each question must:

- Be answerable under the declared candidate-access mode.
- Test one coherent construct, even if it contains linked subparts.
- State all requested dimensions explicitly.
- Use exact source semantics and the correct spatial, temporal, stratigraphic, or administrative scope.
- Define counting and deduplication rules where a numeric answer could otherwise vary.
- State relevant units, datum, source version, sample medium, or method where ambiguity would change correctness.
- Distinguish observations from interpretations and targets from discoveries.
- Avoid hidden retrieval requirements that appear only in the rubric.
- Avoid giving away the answer through excessive context.
- Avoid requiring a single answer when the corpus supports several equally valid interpretations.
- Be concise enough that the assessed task is clear.

A short contextual paragraph followed by two to four tightly linked prompts is acceptable. Split the item if its subparts assess unrelated capabilities or if one binary error would erase otherwise independent reasoning.

For questions requesting examples, specify the number needed and whether any valid examples are acceptable. The later marking scheme must contain multiple examples and the underlying principle that makes them valid.

For negative or absence claims, define the searched source universe and verify that the absence is meaningful rather than an extraction failure.

Create a questions-only artifact at this stage. Do not expose model answers, gates, or keywords in the candidate-facing file.

## Phase 4: Independent Answer And Rubric Construction

Use a separate agent/context where possible. Give it the final question set and corpus, but do not rely on the question author's undocumented intent.

For each question:

1. Re-verify every requested fact against the corpus.
2. Answer every subpart explicitly.
3. State the geological mechanism, inference chain, or uncertainty that makes the answer correct.
4. Include multiple valid examples where the question permits choice.
5. Separate a concise ideal response from the exhaustive material needed by a marker.
6. Identify accepted alternatives, source-attributed conflicts, and common attractive errors.
7. Identify what the evidence supports and what it does not prove.
8. Where appropriate, state the additional observation, sampling, mapping, or drilling that would discriminate competing interpretations.

Reference answers should be concise and precise enough to model a strong candidate response. The full marking block, not an overlong model answer, should carry exhaustive grader guidance.

### Epistemic Calibration

Use evidence-strength language accurately:

- An anomaly, historic working, isolated assay, or geophysical response may **indicate**, **support**, **vector toward**, or **increase the probability of** a target.
- Such evidence does not by itself **prove** a deposit, genetic model, continuity, economic grade, or orebody.
- Stronger conclusions require the relevant controls, such as repeatability, geometry, true width, grade continuity, depth persistence, structural/lithological control, or drilling.
- Spatial overlap does not prove genetic identity.
- Negative historical work may downgrade a model without proving total absence.

Apply equivalent domain-specific caution outside mineral exploration.

## Marking Model

### Score

- Every question produces one whole-number score from 0 to 10.
- Do not use half marks, fractional marks, negative marks, or holistic performance bands.
- Difficulty does not alter the maximum score.
- Aggregate results by unweighted total/mean, category, difficulty, and any declared capability tags. Do not grade with a desired score distribution in mind.

### Mandatory Correctness Gate

Each question has exactly one gate, represented by component `C1`.

The gate must:

- State the minimum central correctness needed for the response to count as an answer to this question.
- Test one core claim or one coherent mechanism, not a bundle of independently gradable facts and not every requested detail.
- Be worth 2-4 points, leaving at least 6 points of graduated credit above it.
- Be passable by a minimally correct answer and fail-able by a plausible adjacent, keyword-stuffed, or fundamentally misconceived answer.
- Refer only to content awarded by C1. Do not make C2-Cn requirements implicit gate conditions.
- Not be paid for twice. The reverse leak matters as much: no C2-Cn component may credit
  what the gate already requires. If one does, every response that passes the gate earns
  that component automatically, the true minimum rises above the gate value, and the
  component discriminates nothing. Moving material out of the gate to keep it narrow is
  what creates this — a gate holding a conclusion and a component holding its support
  overlap unless the component is written to exclude the gated claim. Verify rather than
  assume: the minimum-pass fixture must score EXACTLY the gate points, and if it scores
  more, one component is paying twice.
- Include at least one concrete fail example.

`C1` is pass/fail as a whole and therefore must not contain partial-credit suballocations. If two independently gradable facts appear essential, move one to a non-gate component, rewrite the gate around their single shared mechanism, or split the question. Do not bundle independent facts into C1 and then zero an otherwise core-correct response for supplying only one of them.

Scoring rule:

- If C1 fails, the total score is `0`. No other component or keyword credit is awarded.
- If C1 passes, award all C1 points and assess C2-Cn independently.
- If the answer both asserts and denies the core gate claim, the gate fails because minimum correctness is not unambiguously demonstrated.

The gate is intentionally stricter than ordinary positive marking. Keep it narrow so it acts as a correctness eligibility threshold rather than an all-or-nothing substitute for the rubric.

### Graduated Components

- Components C1-Cn must total exactly 10 integer points.
- Components must be non-overlapping and independently intelligible.
- Each component must state observable credit conditions rather than vague quality labels.
- If a non-gate component contains several facts, provide an explicit integer suballocation. Prefer separate components when the facts are independently assessable.
- Use `[Binary]` only for a genuinely determinate single fact such as a name, number, scale, orientation, or method.
- A reasoning component requires a demonstrated causal, comparative, spatial, temporal, or evidential link. Names alone do not earn reasoning marks.
- Do not hide unasked-for facts inside a component.
- Do not award the same fact once as a keyword and again as reasoning.

### Positive Marking And Errors

After gate passage:

- Award marks for correct, relevant knowledge and reasoning that the response demonstrates.
- Do not subtract marks for omissions; simply do not award the corresponding component.
- Do not subtract marks for spelling, grammar, or style unless meaning is ambiguous or language quality is explicitly assessed.
- Extra correct but unasked-for material is neutral.
- An unrelated error is neutral to an already demonstrated component.
- A statement that directly contradicts a component's required claim means that component is not demonstrated and receives zero.
- If a response presents competing interpretations explicitly as alternatives and evaluates them correctly, do not treat that as self-contradiction.

### Alternative Answers And Wording

- Grade semantics, not exact phrases.
- List known spelling, transliteration, OCR, abbreviation, and terminology variants.
- Accept unexpected but valid approaches when they demonstrate the knowledge and skill assessed.
- For open questions, allow any conclusion supported by the stated geological principle and the evidence constraints in the block.
- Where a novel answer cannot be verified from the self-contained block, flag it for adjudication instead of inventing a reason to accept or reject it.
- Do not accept a modern contextual equivalent as though it were the report-grounded answer unless the rubric explicitly distinguishes and permits it.

### Keywords And Optional Detail

Keywords are grader aids only.

- **Required concepts** may summarize the substance of a scored component, but exact wording is never required unless terminology itself is assessed.
- **Indicative terms** show vocabulary likely in a strong answer but carry no marks by themselves.
- Do not create free-floating "bonus" marks. If optional depth can earn credit, map it to a named component with a defined cap. Otherwise label it non-scoring.

### Do-Not-Credit Guidance

List plausible but wrong, adjacent, overclaimed, or source-confused responses. Explain which component they fail and why. Do not use the list as an unbounded collection of deductions.

Examples include:

- Confusing an anomaly with a deposit or resource.
- Confusing sample media, units, coordinate datums, drilling methods, or source scopes.
- Treating an operator, tenement, or administrative record as a mine/prospect when the source does not.
- Combining observations from different locations or datasets.
- Selecting a supported fact that does not answer the requested question.
- Replacing corpus-specific evidence with an outside textbook assumption.

## Self-Contained Per-Question Block

Every marker-facing block must use this structure and stand alone from its heading through `Do not credit / careful reading`:

```markdown
### [ID] - [Short title]

**Question.** [Verbatim candidate-facing question]

**Type:** [type] | **Mode:** Graduated | **Difficulty:** [label] | **Total:** 10

**Model answer.** [Concise, complete strong answer covering every subpart.]

**Underlying geological principle.** [Why the answer is correct; mechanism, inference, and appropriate uncertainty.]

**Mandatory gate - C1 ([N] points).** [Minimum core correctness.]  
**Gate-fail examples:** [At least one plausible fundamental failure.]  
**If C1 fails: total = 0.**

**Scored components.**

- **C1 - [name] ([N] points, Gate):** Credit if [...].
- **C2 - [name] ([N] points):** Credit if [...].
- **C3 - [name] ([N] points):** Credit if [...].
- [... components total exactly 10 ...]

**Required concepts.** [Concepts intrinsically tied to components; paraphrases accepted.]

**Accepted alternatives and variants.** [Equivalent forms, supported options, and attribution rules.]

**Indicative non-scoring vocabulary.** [Optional; never earns standalone marks.]

**Do not credit / careful reading.** [Specific traps, overclaims, source conflicts, and scope rules.]
```

Do not put revision history, obsolete-file references, unexplained global principle numbers, external appendix dependencies, `see Question X` references, or phrases such as "the previous answer said" inside the block.

The local principle, accepted alternatives, and source-specific caveats must be repeated when needed. Local duplication is preferable to a marker silently missing an external rule.

## Internal Evidence Record

Keep evidence separate from the candidate answer and sufficient for audit. Each question needs:

```yaml
id: "[stable ID]"
claims:
  - claim: "[factual or interpretive proposition]"
    source: "[path/document]"
    locator: "[page/line/row/figure/table]"
    authority: "[primary/secondary/derived]"
    confidence: "HIGH | MEDIUM | LOW"
    notes: "[OCR, conflict, scope, unit, etc.]"
conflicts: []
adjudication_decisions: []
```

The marker should not need these sources for ordinary grading. They exist so benchmark maintainers can verify, revise, and adjudicate the guide.

## Machine-Readable Rubric

Produce a JSON sidecar that is semantically complete, not merely a partial convenience index. Include:

- Schema version and benchmark metadata.
- Candidate-access mode and source authority contract.
- Global scoring rules.
- Category and difficulty metadata.
- Exact question text.
- Model answer and local principle.
- Structured gate with points, pass condition, and fail examples.
- Structured components and integer point allocations.
- Required concepts, accepted variants, and indicative non-scoring terms.
- Do-not-credit guidance.
- Per-claim evidence records and conflicts.
- Calibration fixtures and expected scoring.
- An optional global variant table for deduplication, while repeating every grading-relevant variant in each affected local block.

Use a schema equivalent to:

```json
{
  "schema_version": "2.0",
  "benchmark": {},
  "candidate_access_mode": "RETRIEVAL_ASSISTED",
  "scoring_model": {
    "total_points": 10,
    "integer_scores_only": true,
    "gate_failure_score": 0,
    "positive_marking_after_gate": true,
    "holistic_bands": false
  },
  "source_authority": [
    { "rank": 1, "class": "...", "notes": "..." }
  ],
  "global_variants": [
    { "term": "...", "variants": ["..."], "note": "..." }
  ],
  "questions": [
    {
      "id": "A1",
      "section": "A",
      "title": "...",
      "question": "...",
      "type": "...",
      "mode": "Graduated",
      "difficulty": "Moderate",
      "model_answer": "...",
      "principle": "...",
      "gate": {
        "component_id": "C1",
        "points": 3,
        "pass_condition": "...",
        "fail_examples": []
      },
      "components": [
        { "id": "C1", "points": 3, "is_gate": true, "credit_if": "..." },
        { "id": "C2", "points": 3, "is_gate": false, "credit_if": "..." },
        { "id": "C3", "points": 4, "is_gate": false, "credit_if": "..." }
      ],
      "required_concepts": ["..."],
      "accepted_variants": ["..."],
      "indicative_terms": ["..."],
      "do_not_credit": ["..."],
      "evidence": [
        {
          "claim": "...",
          "source": "...",
          "locator": "...",
          "authority": "primary",
          "confidence": "HIGH",
          "notes": "..."
        }
      ],
      "calibration": [
        {
          "fixture_id": "A1-F1",
          "response_text": "...",
          "expected_gate_passed": false,
          "expected_component_awards": [
            { "id": "C1", "awarded": 0 },
            { "id": "C2", "awarded": 0 },
            { "id": "C3", "awarded": 0 }
          ],
          "expected_total": 0,
          "rationale": "..."
        }
      ]
    }
  ]
}
```

### Element shapes are fixed, not free

The example above shows one element of every array on purpose. Earlier releases
showed them as `[]`, and three benchmarks built from that produced three different
shapes for the same field — every one valid against its own schema file, and
collectively unreadable by one grading harness. Follow these exactly:

| Field | Element |
|---|---|
| `required_concepts`, `accepted_variants`, `indicative_terms`, `do_not_credit` | plain **string** |
| `evidence` | object with **exactly** `claim`, `source`, `locator`, `authority`, `confidence`, `notes` |
| `global_variants` | object with `term`, `variants` (array of strings), `note` |
| `source_authority` | object with `rank` (integer), `class`, `notes` |

**Do not add keys to `evidence`.** A per-question quote, an anchor offset or a
resolved path belongs in `notes`, or in the internal working files — not as a new
key that only one benchmark has.

**The four string arrays are strings, not name pairs, and must stay that way.** A
variant rule often carries a proviso — *"accepted as ordinary period synonyms,
provided the response also conveys the origin contrast"* — and splitting it into
`{canonical, variants}` drops the condition that makes the rule correct. Write the
rule as one line of prose exactly as a marker should read it.

`global_variants` is optional and may be omitted entirely when a corpus has no
corpus-wide variant table; a benchmark with none writes `[]`. Every
grading-relevant variant must still appear in the affected question's
`accepted_variants`, because a marker holding one question's block must not have
to look elsewhere.

Write the formal JSON Schema to `[Benchmark]_QA_grading_guide.schema.json` and validate every sidecar against it. The `2.0` sidecar is the structured content model and authoring source of truth: Phase 4 populates it, then renders the questions file and human-readable guide from it. The rendered guide is the ordinary grading and adjudication authority. Any mismatch between them is a release blocker. Do not use naive comma or delimiter splitting for terms that may themselves contain punctuation, numbers, scales, or explanatory text.

## Grader Output Contract

Define one consistent result format for human-assisted or LLM grading:

```json
{
  "question_id": "A1",
  "grader_id": "grader-or-model-version",
  "fixture_id": null,
  "scored_at": "[ISO-8601 timestamp]",
  "gate_passed": true,
  "gate_reason": "The response establishes ...",
  "components": [
    {
      "id": "C1",
      "awarded": 3,
      "maximum": 3,
      "reason": "..."
    }
  ],
  "total": 7,
  "demonstrated_but_unscored": [],
  "accepted_variant_used": null,
  "adjudication_required": false,
  "adjudication_note": null
}
```

The component awards must sum to the total unless the gate fails, in which case the total is zero and all awarded component points are reported as zero. `demonstrated_but_unscored` may record diagnostically useful peripheral knowledge in a gate-failed response, but it never changes the score.

## Calibration And Standardisation

Create at least three internal calibration responses for every question:

1. **Gate-fail near miss:** contains relevant peripheral facts or keywords but misses or contradicts the central requirement; expected score 0.
2. **Minimum gate pass:** establishes C1 but little else; expected score equals C1.
3. **Strong/full response:** satisfies all components in valid wording; expected score 9-10, normally 10.

Add a fourth fixture where useful for source conflicts, valid alternative reasoning, self-contradiction, or a difficult partial-credit boundary.

Have an independent grader score the fixtures using only the extracted marking block. Gate disposition must match exactly. Determinate fixtures must reproduce exact component awards and totals; an explicitly judgmental open fixture may vary by at most one point while preserving the same credited reasoning. Revise the block if this standard cannot be met without consulting the corpus or guessing the author's intent.

The per-question fixture volume is intentional: every hard-zero gate needs a tested boundary. Before live use, select standardisation fixtures across categories and difficulties. Re-score them at the start of each grading run and after every `drift_check_interval` responses; stop and recalibrate if a gate disposition changes or tolerance is exceeded.

## Validation Gates

Do not declare the benchmark complete until all checks pass.

### Corpus And Answerability

- Every determinate required claim has a precise evidence anchor.
- Every question is answerable under the declared candidate-access mode.
- No item depends only on a filename, weak generated summary, or uninterpreted assay column.
- Negative/absence claims define and survive a meaningful search scope.
- Non-dominant commodity coverage has narrative support.

### Question Quality

- Each question assesses a coherent construct.
- Every requested subpart is explicit.
- No rubric requirement is hidden from the question.
- Counting, units, methods, datums, scopes, and evidence types are disambiguated where needed.
- Misleading premises are rewritten as explicit evaluation tasks.
- Redundant questions are retired or merged.
- Difficulty reflects both retrieval load and reasoning depth.

### Answer And Rubric Quality

- The model answer addresses every subpart.
- The local principle explains why, not just what.
- The gate tests only minimum central correctness and maps only to C1.
- A minimum-pass answer can still leave substantial points unearned.
- Exactly one gate exists per question.
- Components use whole points, do not overlap, and total exactly 10.
- Non-gate multi-fact components have explicit suballocations.
- Binary labels are used only for determinate facts.
- Keywords do not earn standalone or duplicate marks.
- There are no undefined bonus points or negative deductions.
- Accepted variants are semantically equivalent; source conflicts are attributed rather than disguised as variants.
- Do-not-credit notes identify plausible errors without imposing hidden requirements.
- Each marker-facing block is independently self-contained.

### Cross-Artifact Integrity

- Question IDs, order, category, and exact wording match across all artifacts.
- Retired IDs remain retired and documented.
- Markdown and JSON have semantic parity for every field, not merely valid syntax or equal question text.
- The sidecar passes the formal JSON Schema.
- Every JSON component total is 10 and every gate references C1.
- JSON preserves punctuation-bearing terms, scales, units, and explanatory accepted variants.
- Per-question evidence and global rules are present in the sidecar.
- Calibration fixtures reproduce their expected scores from the local block alone.

### Independent Review

Use at least one independent reviewer to look specifically for:

- Factual errors and weak source anchors.
- Questions whose wording and rubric assess different scopes.
- Gates that absorb most or all scored content.
- Overlapping components or double counting.
- Unsupported accepted alternatives.
- Conflicts silently normalized as synonyms.
- Overclaiming from anomalies, indirect evidence, or historical interpretations.
- Missing partial-credit rules.
- Sidecar loss or parser corruption.

Verify each reviewer finding against the corpus. Do not accept reviewer feedback merely because it is confidently stated.

## Deliverables

Unless the project specifies different names, create:

1. `[Benchmark]_QA_questions.md`: candidate-facing questions only.
2. `[Benchmark]_QA_grading_guide.md`: canonical self-contained marking blocks and global scoring instructions.
3. `[Benchmark]_QA_grading_guide.sidecar.json`: complete structured authoring model and machine-readable companion from which the Markdown artifacts are rendered.
4. `[Benchmark]_QA_grading_guide.schema.json`: formal sidecar schema.
5. `[Benchmark]_QA_validation.md`: source-authority contract, evidence summary, structural checks, calibration results, retired IDs, unresolved conflicts, and reviewer dispositions.

The grading guide must be usable as-is. Scrub generation history and implementation bookkeeping from marker-facing content while preserving all facts and caveats needed for grading.

At completion, report:

- Files created or changed.
- Active and retired question counts.
- Category and difficulty distributions.
- Validation commands/checks and results.
- Source conflicts and how they were handled.
- Every remaining assumption, low-confidence claim, or adjudication issue.

## Post-Pilot Report

After pilot responses are available, produce a short examiner-style report that records:

- Common strengths and successful reasoning patterns.
- Common misconceptions, omissions, source confusions, and overclaims.
- Questions with unexpected valid approaches.
- Gates or components that graders applied inconsistently.
- Items that were too easy, too hard, ambiguous, redundant, or retrieval-heavy.
- Required question, answer, rubric, or calibration revisions.

Use performance evidence to improve clarity and validity, not to alter marks toward a desired distribution. Re-run all integrity and calibration checks after revisions.

If the benchmark is used for comparative or high-stakes ranking, track quantitative item analysis separately, including item difficulty, discrimination, reliability, and category effects. These statistics diagnose item quality; they do not authorize changing marks toward a target distribution.
