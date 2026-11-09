# Taxpayer 360 + Return Viewer Editor (RVE) POC — v0.2

Fictional taxpayers, synthetic data, no FTI. Table and column names are POC names (`tp_*`), not CDW names.
Real CDW names never go in this repo.

This shows what the UCP canonical model on EDP lets the business do:

- **One contextual view of a taxpayer (TP360):** every episode, module, contact, asset, account and
  relationship, plus rule-based signals over all of them.
- **Individual returns through RVE:** versioned snapshots of the return (as filed, working, proposed,
  as examined). Every line records where it came from: MeF, an attachment extract, an RVE supplement, an
  examiner adjustment, or a computed value.
- **Reconciliation (RRI):** information returns are matched against the return, and each finding gets a
  branch. A is resolved from data. B is not a taxpayer issue and never becomes an IDR. C needs the
  taxpayer and goes into an IDR.
- **Effects:** exam results flow back into the same tables, so the 360 view and the other episodes see
  them straight away.

## v0.2 — closed cases, beyond AIMS

About 300 synthetic closed AUR, correspondence and field cases (TY2019–2023) across ~260 more taxpayers.
Each case has the AIMS-equivalent record (`tp_case_closure`) **plus** what AIMS doesn't hold:

- **Issue level:** the issue code, amount proposed vs. sustained, status, how the adjustment was found, and hours.
- **Line level:** every source-line adjustment tied to its issue.
- **Tax computation:** filed vs. examined.

The **issue → MeF line translation** sits in three reference tables:

- `tp_issue_code` names the issue.
- `tp_issue_line_map` says which source lines it adjusts.
- `tp_line_catalog` says how each line rolls up to Form 1040.

`v_issue_to_1040_trace` shows the whole path. New views answer "which lines are adjusted most often", "no-change rate by issue",
"how adjustments were found", "most common variances and root causes" and "prior audit history". There is also a new signal,
SG10 repeat issue. Marisol's 2019 field exam and 2021 AUR are now real closed cases, and the 2019 Schedule C other-expense
adjustment repeats in 2024. The Thornburys have a prior no-change exam.

See [`docs/TP360_Data_Model.md`](docs/TP360_Data_Model.md) for the ER diagram, every table's columns, and the AIMS-equivalent
field list (SME to confirm). Closed-case figures are illustrative and computed with TY2024 parameters.

## The two hero cases (TY2024)

| | Case A — Marisol T. Vance (`TK100001`) | Case B — Marcus & Elena Thornbury (`TK200001`) |
|---|---|---|
| Setting | Exam inside a live collection case: ACS suspended, OIC pending, Passport certified | Exam only |
| Return | HOH; Sch C (Vance Builders), Sch B, 8949, Sch E rental + Latimer Grove K-1 | MFJ; W-2, Sch C (commissions), three rentals, Sch A |
| RVE angle | Sch C line 27a detail came as a PDF; RVE captures the Part V lines (attachment extract) | MeF can't carry an aggregation election or hours; RVE holds them as supplements |
| RRI | Harbor Trust 1099-INT unreported (A); 1099-B noncovered (B); receipts exceed IRP (B); Part V (C) | REP claim, no election (C); 1099-MISC, 1099-NEC, W-2 match (A) |
| Result | Agreed; deficiency **$2,417**; flows to the TY2024 module, OIC/RCP, Passport | Unagreed, protest; deficiency **$11,000**; $50,000 suspended passive loss carries to 2025 |

Points that need SME judgment are marked "SME to confirm" in the walkthrough. They are listed in
`tools/hero_cases.py` (`SME_FLAGS`).

## What's here

```
tp360/
├── setup_tp360.ipynb            run in Databricks: load, build views, validate, show heroes, GraphFrames (optional)
├── data/                        29 CSVs (tp_*) — ~410 taxpayers, ~300 closed cases, reference tables, answer key, run params
├── docs/TP360_Data_Model.md     ER diagram, tables, the issue → line translation, AIMS-equivalent fields
├── sql/tp360_views.sql          signals (10 rules), TP360 header, RVE compare, closed-case results and analytics views
├── genie/                       genie_instructions.md + 22 benchmark questions with SQL answers
├── viewer/TP360_RVE_Walkthrough.html   the staged walkthrough (7 stages, both cases), open in any browser
└── tools/                       generators — the single source for data, notebook and viewer
    ├── reference_tables.py      issue codes, issue → line map, line catalog, root causes
    ├── closed_cases.py          the closed-case population (runs every case through the tax engine)
    ├── make_data_model_doc.py   writes docs/TP360_Data_Model.md from the CSV headers
    ├── hero_cases.py            both cases: return inputs, findings, IDRs, determinations, effects, SME flags
    ├── tax_engine_ty2024.py     simplified TY2024 1040 engine (illustrative; not the production calculator)
    ├── build_tp360_data.py      writes data/*.csv, the answer key and viewer/scenarios.json
    ├── check_sql_local.py       runs the SQL in DuckDB against the answer key (no Databricks needed)
    ├── build_viewer.py          injects scenarios.json into walkthrough_template.html
    └── make_notebook.py         writes setup_tp360.ipynb
```

## Databricks quick start

1. Use the Git folder you already have for `passport_poc_kit` (pull), or create one.
2. Open `tp360/setup_tp360.ipynb`. Set `catalog` / `schema` (default `workspace` / `tp360_poc`), attach
   Serverless, and **Run all**. You should see `VALIDATION PASSED`: 0 signal mismatches, deficiencies of 2417 and
   11000, and every closed case's deficiency matching its tax computation.
3. **Genie:** create a space on the tables the last cell lists (never `tp_signal_answer_key`). Paste
   `genie/genie_instructions.md`, then add the benchmarks from the file the notebook writes to the `raw`
   volume.
4. **Graph:** section 6 tries GraphFrames, which comes with Databricks Runtime ML. On Serverless or Free
   Edition it probably isn't available, so the cell falls back to `v_related_parties_named` (SQL, two hops).

## Rebuild after changing a case

```
python tp360/tools/build_tp360_data.py    # data + answer key + scenarios.json
python tp360/tools/check_sql_local.py     # needs: pip install duckdb  -> LOCAL CHECK PASSED
python tp360/tools/build_viewer.py         # walkthrough HTML
python tp360/tools/make_notebook.py        # only if the notebook source changed
python tp360/tools/make_data_model_doc.py  # if tables or columns changed
```

## Limits (v0.1)

- Tax figures come from a simplified engine. It uses rate schedules, not the Tax Table, and has no
  W-2/UBIA limitation or capital-gain rate worksheet. RVE's production recompute is the Thomson Reuters
  calculator (FYT in future).
- MeF element names in `tp_return_line.mef_element` are illustrative. Verify them against the IRS1040
  schema before reuse.
- Attachment extraction, shown in Case A, is not an RVE capability today. The case is the argument for
  adding it.
- The Databricks notebook has been checked locally with DuckDB only. The first Databricks run is the
  real test.
