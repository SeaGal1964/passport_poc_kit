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
    ├── Passport_Certification_Analytics_POC_User_Guide.pdf  the User Guide (export of the live doc, 2026-11-06)
    └── README_cdw_demo.md           detail on the CDW demo
```

## Also in this repo: `tp360/` — Taxpayer 360 + Return Viewer Editor POC

A second, separate POC: a TP360 view on the UCP canonical model plus individual returns through RVE (two TY2024
hero cases, Genie benchmarks, a staged HTML walkthrough). It has its own setup notebook and schema
(`tp360_poc`). See [`tp360/README.md`](tp360/README.md).

## Quick start (Databricks, Unity Catalog workspace)

**Connecting GitHub to Databricks is not required.** There are two ways to get the kit into a workspace; the
upload route is the one tested end to end (Databricks Free Edition, Nov 2026).

### Step 1 — get the files into the workspace (pick one)

**Option A — Upload (tested; no GitHub connection needed)**

1. Unzip the kit (or download the repo as a zip) on your computer.
2. In a SQL editor tab (SQL warehouse compute), create the schema and a volume for the files, using your own names:
   ```sql
   CREATE SCHEMA IF NOT EXISTS workspace.passport_poc;
   CREATE VOLUME IF NOT EXISTS workspace.passport_poc.raw;
   ```
3. Catalog → *your catalog* → *your schema* → Volumes → **raw** → **Upload to this volume**: upload all 13
   `data/*.csv` files, the three `sql/*.sql` files and `genie/genie_benchmark_answers.sql`.
4. Workspace → Home → ⋮ → **Import**: import `setup_passport_poc.ipynb` (and `cdw_demo_passport_poc.ipynb` if you
   want the CDW demo). Importing doesn't open them; find them in Home.
5. Open a notebook, attach **Serverless**, and run **only the first code cell** — the input boxes then appear at
   the top. Fill them in as below (shown for `workspace` / `passport_poc`; use your names), then **Run all**.

| Notebook | Box | Value |
|---|---|---|
| `setup_passport_poc` | catalog / schema | `workspace` / `passport_poc` |
| | data_dir | `/Volumes/workspace/passport_poc/raw` |
| | rules_sql | `/Volumes/workspace/passport_poc/raw/passport_rules.sql` |
| | benchmark_sql | `/Volumes/workspace/passport_poc/raw/genie_benchmark_answers.sql` |
| `cdw_demo_passport_poc` | catalog | `workspace` |
| | source_schema / cdw_schema / target_schema | `passport_poc` / `cdw_sim` / `passport_poc_cdw` |
| | extract_sql | `/Volumes/workspace/passport_poc/raw/cdw_extract_passport.sql` |
| | rules_sql | `/Volumes/workspace/passport_poc/raw/passport_rules.sql` |

**Option B — Git folder (convenient for ongoing team use)**

Link your GitHub account once (User settings → Linked accounts; a personal access token is needed because the repo
is private), then Workspace → Create → **Git folder** with the repo URL. The notebooks' default paths (`./data`,
`./sql`, `./genie`) then work as-is — set only catalog and schema — and `git pull` brings in updates.
Some enterprise workspaces don't allow Git folders; use Option A there.

### Steps 2–4 — run, then add Genie

2. **Run `setup_passport_poc`.** Expect `VALIDATION PASSED` and every finding count "same".
3. **Genie:** create a space on the 9 tables (`v_findings`, `v_taxpayer_eval`, `v_module_eval`,
   `v_module_reversal_reason`, `v_appeals_cdp`, `pp_entity`, `pp_module`, `ref_threshold`, `ref_indicator`) —
   never `pp_answer_key`. Paste `genie/genie_instructions.md`. Add benchmarks from the file the setup notebook
   writes to the `raw` volume (`genie_benchmark_answers_<catalog>_<schema>.sql`). All should be Good.
4. **Optional — start from CDW:** run `cdw_demo_passport_poc` with `source_schema` = the schema from step 2.
   It builds `cdw_sim`, runs the extract into `passport_poc_cdw`, checks the round trip, and validates.
   Expect `ROUND TRIP PASSED` and `VALIDATION PASSED`. See `docs/README_cdw_demo.md`.

## Setting up in a team or enterprise workspace (e.g. a BAH Databricks dev workspace)

Everything above was tested on Databricks Free Edition (serverless, single user). An enterprise workspace adds
access controls and shared schemas. **This path is untested**: whoever goes first, please note anything that differs
and update this section.

### 1. Get the files

- Either route in Quick start step 1 works. **Option A (upload) needs no GitHub connection** and is the tested path.
- For Option B, the repo must be reachable: it is private to SeaGal1964, so ask Colleen Newman for collaborator
  access until it moves to a BAH-controlled repo, and check that your workspace allows Git folders.

### 2. Ask your workspace admin for

| Need | Why |
|---|---|
| A Unity Catalog catalog where you can **create schemas** (or schemas pre-created for you) | Both notebooks create their schemas |
| **Create volume** / write access in those schemas | CSVs are staged in a `raw` volume |
| **Serverless** notebook compute, or a **Unity Catalog–enabled cluster** | Running the notebooks (clusters untested) |
| The **Databricks SQL** entitlement and **CAN USE** on a **Pro or Serverless SQL warehouse** | SQL editor checks and Genie |
| **Genie (AI/BI) enabled** for the workspace, and permission to create Genie spaces | The Genie space and benchmarks |

All data in this kit is synthetic (no FTI, no PII). Confirm with your project's data-handling lead that synthetic
test data is fine in the dev workspace.

### 3. Use your own schema names

In a shared catalog, prefix the schemas so people don't overwrite each other — the notebooks use
`CREATE OR REPLACE`, so pointing at someone else's schema replaces their tables.

| Notebook | Widgets to set | Example |
|---|---|---|
| `setup_passport_poc` | `catalog`, `schema` | `dev_catalog`, `jdoe_passport_poc` |
| `cdw_demo_passport_poc` | `catalog`, `source_schema`, `cdw_schema`, `target_schema` | `jdoe_passport_poc`, `jdoe_cdw_sim`, `jdoe_passport_poc_cdw` |

The setup notebook writes the Genie benchmark SQL with your catalog and schema already filled in.

### 4. Troubleshooting (problems we actually hit)

| Symptom | Fix |
|---|---|
| No input boxes at the top of the notebook | Run only the first code cell (Shift+Enter); the boxes then appear above the title. Cells may show collapsed as numbers. |
| Imported notebook didn't open | Import only saves it: Workspace → Home (or search its name). |
| `TABLE_OR_VIEW_NOT_FOUND` with "search path … `default`" | A new SQL editor tab starts in the `default` schema. Use full names (`catalog.schema.table`) or set the tab's catalog/schema dropdown. |
| `MISSING_ATTRIBUTES.RESOLVED_ATTRIBUTE_APPEAR_IN_OPERATION` | An older rules script. Use `sql/passport_rules.sql` from this repo (v0.5.2+). |
| "Pulled must-file dates disagree with the IRM 5.19.4.6.2 calculation" | The source schema has pre-v0.5.3 lien data. Rerun `setup_passport_poc` with this repo's `data/`. |
| New schema not visible in Catalog | Click refresh in the Catalog tree; it can take a minute. |
| Genie menu or setup screens look different | The sidebar may say "Genie" or "Genie Agents", and setup may build the space from a description. Then check the table list (9 tables, never `pp_answer_key`) and replace the instructions with `genie/genie_instructions.md`. |
| A benchmark fails with `PARSE_SYNTAX_ERROR` | One SQL statement per benchmark; leave out the "CHECK ONLY" query. |
| A benchmark is red but Genie's numbers look right | Compare Genie's SQL with the expected SQL. The User Guide's "Lessons learned" table lists the rules Genie got wrong and the fixes. |

### 5. Documentation

`docs/Passport_Certification_Analytics_POC_User_Guide.pdf` is the full User Guide: how the rules work, setup,
Genie setup and benchmarks, lessons learned, the CDW demo and open items. The live version is a Claude Doc owned
by Colleen Newman; ask her for access if you need the latest.

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
