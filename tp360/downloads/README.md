# TP360 + RVE demo: synthetic data download

`TP360_RVE_synthetic_data.zip` in this folder holds every CSV from `tp360/data/`, the data model (`tp360/docs/TP360_Data_Model.md`) and this README, for anyone who wants the data without cloning the repo. It contains no code. If the data in `tp360/data/` changes, rebuild the zip so the two stay in step.

All data in these files is synthetic: every taxpayer, TIN token, account and amount is fictional. It is the data the TP360 + Return Viewer Editor POC loads into Databricks (repo SeaGal1964/passport_poc_kit, folder tp360/data, as of the income-probes update).

- One CSV per table, with a header row. Tax periods are YYYYMM (for example 202412).
- Table and column definitions, and how the tables join: `TP360_Data_Model.md` in this folder.
- `tp_signal_answer_key.csv` is the test key for signals SG01-SG11; it is used to validate the SQL rules, not as source data.
- `tp_ref_ple.csv` (living expenses) is synthetic and only shaped like BLS data.

| File | Rows | Columns |
|---|---:|---:|
| tp_adjustment.csv | 2,544 | 15 |
| tp_asset.csv | 18 | 10 |
| tp_bank_account.csv | 32 | 8 |
| tp_bdce_line.csv | 13 | 7 |
| tp_case_closure.csv | 302 | 18 |
| tp_compliance_episode.csv | 474 | 8 |
| tp_contact_event.csv | 1,839 | 14 |
| tp_determination.csv | 7 | 10 |
| tp_financial_profile.csv | 1 | 9 |
| tp_fsa.csv | 6 | 14 |
| tp_fsa_line.csv | 52 | 8 |
| tp_idr.csv | 4 | 11 |
| tp_indirect_method_gate.csv | 2 | 12 |
| tp_information_return.csv | 22 | 9 |
| tp_issue.csv | 472 | 13 |
| tp_issue_code.csv | 23 | 7 |
| tp_issue_line_map.csv | 29 | 8 |
| tp_line_catalog.csv | 64 | 8 |
| tp_net_worth_item.csv | 35 | 8 |
| tp_procedural_overlay.csv | 15 | 8 |
| tp_ref_ple.csv | 140 | 5 |
| tp_relationship.csv | 45 | 8 |
| tp_return_line.csv | 582 | 10 |
| tp_return_snapshot.csv | 37 | 10 |
| tp_root_cause.csv | 8 | 3 |
| tp_rri_finding.csv | 446 | 16 |
| tp_run_params.csv | 1 | 2 |
| tp_signal_answer_key.csv | 81 | 2 |
| tp_statutory_clock.csv | 7 | 9 |
| tp_tax_computation.csv | 302 | 23 |
| tp_tax_module.csv | 221 | 8 |
| tp_taxpayer.csv | 415 | 9 |
| tp_transfer.csv | 8 | 8 |
| tp_treatment_assignment.csv | 8 | 5 |

34 files, 8,255 rows in all.
