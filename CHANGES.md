# Changes

## tp360 v0.2 (2026-11-09)

- About 300 synthetic closed cases, beyond AIMS: case-level closure (AIMS-equivalent) plus issue-level detail (proposed vs. sustained, how found, hours), line adjustments tied to issues, and the tax computation filed vs. examined.
- Issue → MeF line translation: `tp_issue_code`, `tp_issue_line_map`, `tp_line_catalog`, and `v_issue_to_1040_trace`.
- Variance root causes on `tp_rri_finding`; signal SG10 repeat issue; 7 analytics views; Genie benchmarks Q15–Q22.
- Hero back-fill: Marisol's TY2019 field exam and TY2021 AUR; the Thornburys' TY2021 no-change. The walkthrough shows prior audit history.
- `docs/TP360_Data_Model.md` (generated).
- Re-run `tp360/setup_tp360.ipynb`; it replaces the tables in `tp360_poc`. Add the new views to the Genie agent.

## tp360 v0.1 (2026-11-08)

- New `tp360/` folder: TP360 + RVE POC with two hero cases (Vance, Thornbury), 23 synthetic tables, 9 signal rules validated against a Python answer key, 14 Genie benchmarks, setup notebook with optional GraphFrames, and a staged walkthrough viewer. Passport kit unchanged.

## v0.5.3 docs update — 2026-11-06
- README: "Setting up in a team or enterprise workspace" (repo access, admin asks, per-person schema names, troubleshooting).
- `docs/Passport_Certification_Analytics_POC_User_Guide.pdf` added (export of the live User Guide).

## v0.5.3 — 2026-11-05
- **CDP request deadline per IRM 5.19.4.6.2 (12-30-2024).** Letter 3172 must-file date = NFTL mailing date
  + 3 business days (estimated filing date) + 5 business days + 30 calendar days, federal holidays observed.
  `data/pp_lien.csv` regenerated: all 43 deadlines changed; answer key unchanged (0 mismatches, same 11 counts).
- **"Start from CDW" demo** (`cdw_demo_passport_poc.ipynb`, `sql/cdw_extract_passport.sql`): simulated CDW with
  masked TINs (per-TIN hash, consistent across IMF/ALS/ACDS/ACMS, stable across refreshes), noise the extract must
  filter, round-trip check. The extract pulls the Letter 3172 must-file date when present, else computes it.
  Passed on Databricks Free Edition 2026-11-05.
- **CDW extract template v0.2:** token crosswalk dropped (masked TIN passes through); 4.6 deadline per IRM with three
  new placeholders flagged CONFIRM EXISTS IN CDW (must-file date, NFTL mailing date, business-day calendar).
- Workbook v0.5.3: deadline definition, four new open items.

## v0.5.2 — 2026-11-04
- Rules run on Databricks serverless: `v_txn` / `v_indicator_active` materialized as `t_txn` / `t_indicator_active`;
  `v_module_eval` restructured (fixes MISSING_ATTRIBUTES.RESOLVED_ATTRIBUTE_APPEAR_IN_OPERATION; outputs identical).
- New `v_module_reversal_reason` for Genie. USE lines live in the script.
- Genie instructions and 14 benchmark questions with independent SQL answers (Q5, Q9, Q11 reworded); all Good.
- `setup_passport_poc.ipynb` one-step setup/refresh with validation; benchmark SQL as a catalog/schema template.

## v0.5 — 2026-10-30
- Indicator codes checked against IRM 5.19.25 (10-10-2024); combat zone cc 52/54/56; thresholds 2018–2025;
  `ref_noncert_mft` adds 43 and 59; `v_threshold_gaps` control view; answer-key query fixed.
