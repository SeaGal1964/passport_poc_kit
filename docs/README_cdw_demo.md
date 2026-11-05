# Passport POC — "Start from CDW" demo (v0.2, 2026-11-05)

**Synthetic data only. Every CDW table and column name is SIMULATED** (illustrative, CDW-style).

> **CONFIRM IN CDW before real use — three data elements this version depends on:**
> 1. **Letter 3172 must-file date** (the date printed on the letter) — the extract pulls it when present.
> 2. **NFTL mailing date** (ALS) — needed to compute the must-file date when the letter date isn't available.
> 3. **Business-day / federal holiday calendar** — needed for that calculation (simulated here as `REF_BUS_CALENDAR`).
>
> All three are simulated in `cdw_sim` and flagged `*** CONFIRM EXISTS IN CDW ***` in `sql/cdw_placeholder_map.csv`
> and in `sql/cdw_extract_template.sql` (v0.2).
Real CDW Database Library names belong only in an IRS/BAH-controlled environment — never in a personal repo.

## What it shows

```
simulated CDW (cdw_sim)  ->  extract SQL  ->  pp_* tables  ->  rule views  ->  Genie
 IMF / ALS / ACDS / ACMS      driver pop.      (passport_poc_cdw)
 masked TINs + noise          + table pulls
```

- **Masked TINs end to end.** CDW supplies a masked TIN that is the same in IMF, ALS and ACDS/ACMS and stable across
  refreshes, so the extract passes it through as `tin_token`. The template's token-crosswalk step is dropped; raw TINs
  never exist anywhere in the demo.
- **The extract does real filtering.** The simulated CDW holds more than the extract needs: 40 taxpayers outside the
  population (low balance or paid, never certified, some with liens), notice codes the extract doesn't pull
  (CP14/CP501/CP503/CP504), and non-CDP Appeals cases (CAP in ACMS, OIC in ACDS).
- **Round trip proves it.** The extract must rebuild the validated synthetic tables exactly for every taxpayer in the
  driver population, and the rules must reproduce the reference findings.

## Files

| File | Purpose |
|---|---|
| `cdw_demo_passport_poc.ipynb` | Builds the simulated CDW, runs the extract, round-trip check, rules and validation |
| `sql/cdw_extract_passport.sql` | `cdw_extract_template.sql` filled against the simulated CDW (Databricks SQL) |
| `sql/cdw_placeholder_map.csv` | Every template `<<placeholder>>` -> simulated name, with a blank column for the real CDW name |
| `sql/cdw_extract_template.sql` | Template **v0.2**: 4.6 now uses the IRM 5.19.4.6.2 must-file date (pull, else compute), with the three CONFIRM IN CDW placeholders |
| `data/pp_lien.csv` | **Data v0.5.3**: lien deadlines regenerated under IRM 5.19.4.6.2 — replace the v0.5 file and reload the source schema first |
| `sql/passport_rules.sql` | Rules (v0.5.2), unchanged |

## Run it (Databricks Free Edition or any UC workspace)

1. Replace `data/pp_lien.csv` with the v0.5.3 file and reload the source schema (run `setup_passport_poc`; default `passport_poc`).
   With the old v0.5 lien data the notebook stops with "Pulled must-file dates disagree with the IRM 5.19.4.6.2 calculation".
2. Import `cdw_demo_passport_poc.ipynb`, run the first cell, set the widgets
   (`source_schema`, `cdw_schema` = `cdw_sim`, `target_schema` = `passport_poc_cdw`, and the two SQL paths —
   upload the SQL files to a volume and use `/Volumes/...` paths if the notebook isn't in the kit folder), then **Run all**.
3. Expect: control checks (driver 304 = 185 certified ∪ 268 high balance; must-file dates 42 pulled / 7 computed,
   0 pulled-vs-computed disagreements, 0 missing), round-trip table all zeros,
   61 left-out taxpayers (all S03, expected findings NONE), `VALIDATION PASSED`, and every finding count "same".
4. Point a Genie space at `passport_poc_cdw` (same 9 tables and `genie_instructions.md`) to demo questions on data that
   started in CDW. Token values are masked TINs (`M########`), not `T######`.

## Tested (2026-11-05, local Spark with Databricks shims, on the v0.5 kit CSVs)

- Simulated CDW: 405 entities, 500 modules, 2,241 transactions, 423 notices, 49 liens, 14 ACDS + 64 ACMS cases.
- Extract: 304 taxpayers; all 7 `pp_*` tables rebuilt with 0 missing / 0 extra rows; control checks 0.
- 0 answer-key mismatches, 0 threshold gaps, all 11 finding counts match the reference.
- Negative tests: changing the CDP deadline rule fails the round trip on all 43 lien rows; running against the old
  v0.5 lien data stops on the pulled-vs-computed check.
- Data v0.5.3: all 43 synthetic lien deadlines changed under the IRM rule; answer key unchanged (0 mismatches, same 11 counts).

## Demo talking points

- The driver population leaves out **61 below-threshold, never-certified taxpayers (S03)** — correct, since they cannot
  produce a finding. The round trip proves no taxpayer with a finding is lost.
- `module_balance_ne_txn_sum = 0`: module balances tie to the transaction history.
- ACDS/ACMS duplicates (S24) are carried through and collapsed downstream in `v_appeals_cdp`, as designed.

## Open items

1. **CDP request deadline — implemented per IRM 5.19.4.6.2 (12-30-2024); confirm the CDW data.** The extract pulls the
   Letter 3172 must-file date, else computes NFTL mailing date + 3 business days + 5 business days + 30 calendar days
   (`WRK_PP_MUST_FILE` shows which). Still open: (a) confirm the three CDW elements above; (b) weekend/holiday handling
   of the final day is not stated in the IRM — 30 of 49 simulated must-file dates land on a weekend or holiday, so the
   answer moves the lapse date by up to 3 days. Letter 3172 goes to every taxpayer on the NFTL (including a secondary
   spouse on a joint liability), so each liable spouse has their own must-file date.
2. ~~Masked TIN on joint modules.~~ **Resolved (SME, 2026-11-05):** CDW applies its masking algorithm (hash-like) to each TIN, so every TIN, including a secondary spouse's, has its own consistent masked value throughout CDW. The simulation does the same (per-TIN deterministic hash).
3. **Real names.** Fill the last column of `cdw_placeholder_map.csv` from the CDW Database Library (controlled environment).
4. **Source codes.** ACDS/ACMS hearing-type and case-category codes are simulated; confirm the real code values.
5. **Out-of-scope MFTs.** The simulated CDW adds no noise MFTs outside (30, 31, 35, 55, 65); add them once the scope list is confirmed.
