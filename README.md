# Passport (IRC 7345) Certification Analytics POC — kit v0.5.3

Synthetic data only — no FTI. Every CDW table and column name in this kit is **simulated**.
Validated on Databricks Free Edition (2026-11-04/05): 0 answer-key mismatches, 0 threshold gaps,
all Genie benchmarks Good, and the "start from CDW" round trip passed.

> **Repo rule:** real CDW Database Library names go only in an IRS/BAH-controlled copy of
> `sql/cdw_placeholder_map.csv` — never in a personal repo.

## What's here

```
passport_poc_kit/
├── README.md                        this file
├── CHANGES.md                       version history (v0.5 -> v0.5.3)
├── setup_passport_poc.ipynb         1. load the synthetic extract, build the rules, validate
├── cdw_demo_passport_poc.ipynb      2. optional: start from a simulated CDW and run the extract
├── data/                            13 synthetic CSVs (pp_*, ref_*, pp_answer_key) — v0.5.3
├── sql/
│   ├── passport_rules.sql           rule tables and views (v0.5.2 logic)
│   ├── cdw_extract_template.sql     CDW extract template v0.2 (placeholders)
│   ├── cdw_extract_passport.sql     the template filled against the simulated CDW
│   └── cdw_placeholder_map.csv      every <<placeholder>> -> simulated name; blank column for real names
├── genie/
│   ├── genie_instructions.md        paste into the Genie space Instructions
│   └── genie_benchmark_answers.sql  14 questions + guardrail, SQL answers ({{catalog}}.{{schema}} template)
└── docs/
    ├── Passport_Certification_Extract_Spec_v0.5.3.xlsx   extract spec, dictionary, rules, answer key, Genie Qs, open items
    └── README_cdw_demo.md           detail on the CDW demo
```

## Quick start (Databricks, Unity Catalog workspace)

1. **Get the kit into the workspace:** Workspace → Create → **Git folder** → this repo. (Or import the folder.)
2. **Run `setup_passport_poc`:** set the `catalog` and `schema` widgets (e.g. `workspace` / `passport_poc`), attach
   Serverless, **Run all**. Expect `VALIDATION PASSED` and every finding count "same".
3. **Genie:** create a space on the 9 tables (`v_findings`, `v_taxpayer_eval`, `v_module_eval`,
   `v_module_reversal_reason`, `v_appeals_cdp`, `pp_entity`, `pp_module`, `ref_threshold`, `ref_indicator`) —
   never `pp_answer_key`. Paste `genie/genie_instructions.md`. Add benchmarks from the file the setup notebook
   writes to the `raw` volume. All should be Good.
4. **Optional — start from CDW:** run `cdw_demo_passport_poc` with `source_schema` = the schema from step 2.
   It builds `cdw_sim`, runs the extract into `passport_poc_cdw`, checks the round trip, and validates.
   Expect `ROUND TRIP PASSED` and `VALIDATION PASSED`. See `docs/README_cdw_demo.md`.

Widgets default to this folder layout, so in a Git folder no paths need changing. If the notebook can't read the
kit folder, upload the files to the schema's `raw` volume and point the path widgets at `/Volumes/...`.

## Expected results (reference run)

| Finding | Taxpayers |
|---|---|
| MISSED_CERTIFICATION | 52 |
| DECERT_DUE_OVERDUE | 36 |
| DECERT_DUE_PENDING | 18 |
| CERTIFIED_BELOW_THRESHOLD_AT_CERT, CERTIFIED_MODULE_NO_PREDICATE, INFO_BELOW_THRESHOLD_STILL_CERTIFIED, INFO_EXPEDITE_INELIGIBLE, MODULE_REVERSAL_DUE_OVERDUE, NEW_ELIGIBLE_MODULE_NOT_CERTIFIED, REVERSED_LATE, REVERSED_TIMELY | 9 each |

## Confirm before real data

- **In CDW:** the Letter 3172 must-file date, the NFTL mailing date, and a business-day/holiday calendar
  (the CDP deadline per IRM 5.19.4.6.2 depends on them).
- **SME:** whether a must-file date falling on a weekend/holiday rolls forward (30 of 49 simulated dates do);
  reversal pairings other than TC 972 AC 641 vs. Document 6209; ACDS/ACMS code values.
- Full list: the workbook's **Open Items** tab.

## Moving to real data

Run the extract in CDW (template v0.2, real names), load the output into an **FTI-approved** EDP workspace with the
same table names, set `pp_run_params`, leave out `pp_answer_key` (the setup notebook skips that check when it's
absent), and rerun. Finding counts will differ from the reference — expected on new data.
