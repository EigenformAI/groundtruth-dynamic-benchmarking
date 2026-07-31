# Source and attribution

The CSV files in this folder are a filtered extract of the **SA Geodata / SARIG
Data Package**, published by the Geological Survey of South Australia.

## Required attribution

> Department for Energy and Mining, the Government of South Australia, SA
> Geodata / SARIG Data Package, Sourced on 28 July 2026,
> https://dem-sdp.s3-ap-southeast-2.amazonaws.com/index.html

## Licence

Creative Commons Attribution 4.0 Australia (CC BY 4.0 AU), per
`Disclaimer and CCBY.txt` in the source bucket. Reuse is permitted with the
attribution above; the attribution must not imply endorsement by the
Government of South Australia. The State makes no representation as to the
accuracy or completeness of the data and disclaims liability for its use.

## What was extracted

Every record whose `MINERAL_DISTRICT` is **Yudnamutana Copper** (34 mineral
deposits), taken from four tables in the package:

| File here | Source file | Rows |
|---|---|---|
| `deposits.csv` | `sarig_md_details_exp.csv` | 34 |
| `mineralogy.csv` | `sarig_md_mineralogy_exp.csv` | 206 |
| `commodity.csv` | `sarig_md_commodity_exp.csv` | 48 |
| `host_lithology.csv` | `sarig_md_zone_lith_exp.csv` | 34 |

Two changes were made to the source records:

1. **Row filter** — only the Yudnamutana Copper district was kept, to give the
   benchmark a small, coherent corpus. No rows within the district were dropped.
2. **Column filter** — survey and coordinate columns were removed (eastings,
   northings, latitude, longitude, zone, accuracy, survey method, site number,
   GIS code, map symbol). They carry no geological reasoning content and would
   only add noise to the questions.

No values were edited, corrected, or reworded. Field names are unchanged, so
every claim in the rubric can be traced back to the published package by
`MINERAL_DEPOSIT_NO` and column name.

## Why this corpus

It is public, clearly licensed, and small enough to ship with the harness, so
the example rubric can be genuinely corpus-grounded — each rubric claim carries
a real evidence locator — rather than synthetic. See the rubric at
`rubrics/Yudnamutana_QA_grading_key.json`.
