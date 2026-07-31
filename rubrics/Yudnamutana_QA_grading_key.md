# Yudnamutana Copper (sample) — Graded Answer Key & Marking Scheme

**Corpus:** `corpus/yudnamutana/` — 34 mineral deposit records from the Yudnamutana Copper district, extracted from the SA Geodata / SARIG Data Package published by the Geological Survey of South Australia. CC BY 4.0 AU; see `corpus/yudnamutana/ATTRIBUTION.md` for the required attribution and the exact extraction.
**Scope:** Grading scheme for the 3 Yudnamutana sample items. Each question gives the prompt, model answer, mandatory gate with fail examples, scored components totalling 10, required concepts, and do-not-credit guidance. Per-claim evidence locators and calibration fixtures live in the sidecar (`Yudnamutana_QA_grading_key.json`), which is the authoring source of truth.

> **Three questions only.** This is a format demonstration and an end-to-end smoke test, not a full benchmark. Author a real one with the `build-source-grounded-geology-benchmark` skill in `.claude/skills/`.

**Candidate access mode:** `OPEN_CORPUS` — the candidate may read the four CSVs while answering.

---

## §0 · How to use this marking scheme

Every question produces one whole-number score **out of 10 (hard cap)**.

**1 — Mandatory gate.** Each question names one gate, component **C1**, worth 2–4 points. **If the gate fails the score is 0** — no component or concept credit leaks through, however much correct peripheral material surrounds it. Passing the gate always earns C1's points. Every gate carries concrete **fail examples**: plausible answers that must still score zero.

**2 — Graduated components.** Above the gate, award each component's points against its stated credit condition. Components are non-overlapping, use whole points, and total exactly 10. Where a component lists two credit routes at 2 points each, cap it at the stated maximum.

**3 — Positive marking.** After the gate passes, credit what the response demonstrates. Do not deduct for omissions, style, or unrelated errors; simply do not award that component. A statement that directly contradicts a component's required claim means the component is not demonstrated.

**4 — Reasoning ≠ vocabulary.** Required concepts summarise what a component tests; exact wording is never required. Indicative terms carry no marks on their own.

**5 — Grade meaning, not form.** Accept paraphrases and the variants listed in `global_variants`.

---

## A · Host-rock control

### A1 · Recurring host unit across the district
**Q.** Eleven of the 34 Yudnamutana Copper records name the Wywyana Formation as the host, described variously as marble, limestone, calcareous beds and actinolitic rock. What does this recurrence indicate about the control on copper mineralisation in the district, what second control do the same summaries record, and what does this pattern on its own not establish?
**Type:** Cross-source synthesis + evidence evaluation · **Difficulty:** Hard · **Total: 10**

**Model answer.** The recurrence points to a **lithological (stratigraphic) control**: the Wywyana Formation is a carbonate and calc-silicate unit, and a chemically reactive carbonate host favours **replacement-style** copper mineralisation — Pinnacles is logged as exactly that. The same summaries record a second, **structural control** acting with it: mineralisation sits on faults, shears and folds rather than spreading evenly through the unit (Yudnamutana on a fracture system over an anticlinal fold; Mount McDonnell on a fault within a shear zone; Wheal Frost at a faulted contact). What the pattern does **not** establish is a genetic model or a metal source. A count of host-unit mentions in a compiled database also reflects where people looked and what has been mapped, so it is evidence of a favourable host, not proof the formation controlled ore genesis.

**Gate — C1 (3 points).** Must identify the recurrence as a lithological or stratigraphic host-rock control, tied to the carbonate or calc-silicate character of the unit.
**Gate-fail examples:** states only that Wywyana is the commonest host without saying what that implies; concludes the formation is the *source* of the copper; attributes the recurrence solely to structure.
**If C1 fails: total = 0.**

**Scored components.**
- **C1 [3] (GATE)** — Reads the recurrence as a lithological/stratigraphic control linked to the carbonate or calc-silicate host.
- **C2 [3]** — Identifies the second, structural control in the same summaries (faults, shears, breccia zones, fold-related fractures), acting *with* the host rather than instead of it.
- **C3 [4]** — States the limits, 2 points each to a cap of 4: (a) no genetic model or metal source is established, only a favourable site; (b) counts in a compiled inventory carry exploration/mapping bias.

**Required concepts.** Lithological or stratigraphic host control · reactive carbonate/calc-silicate host · structural control acting with the host · does not establish genesis or source.
**Indicative (non-scoring).** trap · chemical reactivity · rheological contrast · sampling bias.
**Do not credit.** Calling the Wywyana Formation the *source* of the copper (gate fail). Treating the eleven mentions as a clean measure of prospectivity with no nod to compilation bias (loses C3b). Asserting a specific deposit model (IOCG, sediment-hosted, MVT) as established. Claiming the other 23 records therefore have no host control.

---

## B · Mineralogy and weathering

### B2 · Supergene versus hypogene copper mineralogy
**Q.** In the district's mineralogy records, malachite, azurite and cuprite are flagged `WEATHERING_PRODUCT = Y`, while chalcopyrite and bornite are flagged `N`. Explain the geological distinction this flag records, what it implies about the samples' position relative to depth, and why the ~30% Cu reported for supergene ore at Wheal Gleeson should not be taken as the grade of the deposit at depth.
**Type:** Mechanism explanation + evidence-strength assessment · **Difficulty:** Moderate · **Total: 10**

**Model answer.** The flag separates **secondary (supergene)** minerals formed by weathering from **primary (hypogene)** minerals of the original mineralising event. Malachite, azurite and cuprite formed where descending oxidising groundwater attacked primary copper sulphide near surface; chalcopyrite and bornite are the primary sulphides. The distinction is therefore **vertical**: the secondary assemblage marks the oxidised zone above the water table, and the primary sulphides lie beneath the oxidation front. This is why the ~30% Cu supergene figure at Wheal Gleeson cannot be read as grade at depth — supergene processes dissolve copper from a large rock volume and reprecipitate it in a narrow enriched zone, so enriched ore is typically far richer than the primary sulphide that sourced it. The primary grade must be established by **drilling beneath the oxidation front**.

**Gate — C1 (3 points).** Must identify the flag as separating supergene/secondary weathering products from primary/hypogene minerals, with the two sets the right way round.
**Gate-fail examples:** says only that malachite and azurite are carbonates and chalcopyrite a sulphide, without identifying one set as weathering products; reverses the sets; reads the flag as data quality rather than geological origin.
**If C1 fails: total = 0.**

**Scored components.**
- **C1 [3] (GATE)** — Supergene/secondary vs hypogene/primary, correctly assigned.
- **C2 [3]** — Links the distinction to depth: secondary assemblage = oxidised zone near surface (above water table / oxidation front); primary sulphides beneath.
- **C3 [4]** — Explains why 30% overstates depth grade, 2 points each to a cap of 4: (a) supergene enrichment concentrates copper leached from a larger volume into a narrow zone; (b) primary grade is therefore unknown and needs drilling below oxidation.

**Required concepts.** Supergene/secondary vs hypogene/primary · oxidised zone near surface · supergene enrichment concentrates copper · primary grade requires drilling.
**Indicative (non-scoring).** leached cap · gossan · enrichment blanket · descending meteoric water.
**Do not credit.** Reversing the sets (gate fail). Treating **chalcocite** as unambiguously supergene — the corpus flags it *both* ways in this district, which is geologically correct since it forms in both settings. Concluding the deposit is economic because supergene grades are high. Claiming primary grade can be back-calculated from supergene grade by a fixed ratio.

---

## C · Reading the database

### C3 · What DEPOSIT_CLASS does and does not record
**Q.** Of the 34 district records, 3 are classed Deposit, 30 Occurrence and 1 Prospect. Wheal Gleeson is classed Occurrence and records production of over 100 t at 30% supergene ore, while Shamrock is classed Deposit and records no production at all. What does this pair show about the relationship between `DEPOSIT_CLASS` and recorded production, and what can you conclude from this corpus about the criteria behind the classification?
**Type:** Careful reading + uncertainty assessment · **Difficulty:** Hard · **Total: 10**

**Model answer.** The pair shows `DEPOSIT_CLASS` is **not driven by recorded production** — the two records invert the naive expectation, with the higher class on a record with no production and substantial historic production under the lower class. As for the criteria, **this corpus does not state them**: the tables record the assigned class but define none of the terms and give no reason for any assignment. The honest conclusion is that the rule rests on something outside these tables, and determining it requires the SA Geodata documentation rather than inference from 34 rows.

**Gate — C1 (4 points).** Must state that class is not determined by recorded production, resting on the inversion in the named pair.
**Gate-fail examples:** concludes Deposit means more production and Occurrence less; explains the difference by asserting Shamrock had unrecorded production; dismisses the pair as a data-entry error.
**If C1 fails: total = 0.**

**Scored components.**
- **C1 [4] (GATE)** — Class and recorded production are not tied, argued from the inversion.
- **C2 [3]** — States the corpus does not define the classification criteria: no definitions, no reason-for-assignment column, so the rule cannot be recovered here.
- **C3 [3]** — Draws the practical consequence, either route earning full marks: 'Occurrence' must not be read as no mineralisation or no historic mining; **or** resolving the criteria needs external documentation (the SA Geodata vocabulary).

**Required concepts.** Class independent of recorded production · corpus does not define the criteria · rule cannot be inferred from these records.
**Indicative (non-scoring).** controlled vocabulary · metadata schema · compiler judgement.
**Do not credit.** Explaining class by production volume in either direction (gate fail). Inventing a criterion — tonnage threshold, resource estimate, drilling density — and presenting it as what the corpus shows (loses C2). Concluding the database is wrong or inconsistent; nothing is contradictory once class and production are seen as independent. Answering only "more information is needed" without stating what the pair *does* establish (loses C1).

---

## Appendix B · Accepted variants

| Canonical | Accepted variants |
|---|---|
| Wywyana Formation | Wywyana Fm, the Wywyana |
| supergene | secondary, oxidised, oxide zone, weathering product |
| hypogene | primary, primary sulphide, unweathered |
| oxidation front | base of oxidation, water table, weathering front, redox boundary |
| DEPOSIT_CLASS | deposit class, the class field, classification field |

Graders must treat the variants as equivalent.
