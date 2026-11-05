/* =====================================================================================
   IRC 7345 Passport Analytics - CDW Extract, filled against the SIMULATED CDW (v0.1)
   -------------------------------------------------------------------------------------
   SOURCE   cdw_extract_template.sql (DRAFT v0.1). Same order and logic; every <<...>>
            placeholder is replaced with a SIMULATED CDW-style name. The mapping is in
            cdw_placeholder_map.csv - swap in real CDW Database Library names there and
            here, inside an IRS/BAH-controlled environment only. Nothing here is a real
            CDW object name.
   DIALECT  Databricks SQL. {{cdw}} = simulated CDW schema, {{out}} = extract target schema.
            {{AS_OF}}, {{LOOKBACK_START}}, {{THRESHOLD}} are filled by the demo notebook.
   CHANGES FROM THE TEMPLATE
     * Step 3 (token crosswalk) is dropped. CDW supplies a masked TIN that is consistent
       across IMF, ALS and ACDS/ACMS and stable across refreshes, so the masked TIN is
       passed through as tin_token. Raw TINs never appear anywhere.
     * pp_entity.tin_type comes from the entity table instead of a hard-coded 'SSN'.
     * Hearing types are mapped from source codes to LIEN_CDP / LEVY_CDP / EQUIV.
     * cdp_request_deadline = the Letter 3172 "must file" date per IRM 5.19.4.6.2 (12-30-2024):
       pulled when CDW carries it, else computed from the NFTL mailing date with a business-day
       calendar. THREE ELEMENTS TO CONFIRM EXIST IN CDW: the must-file date, the NFTL mailing
       date, and a business-day/holiday calendar (see cdw_placeholder_map.csv).
   ===================================================================================== */

/* ---------- 2. Driver population (one row per masked TIN), kept inside "CDW" ------ */
-- (a) Everyone certified (TC 971 AC 641) within the lookback
CREATE OR REPLACE TABLE {{cdw}}.WRK_PP_DRV_CERTIFIED AS
SELECT DISTINCT t.MASKED_TIN AS tin
FROM   {{cdw}}.IMF_TXN t
WHERE  t.TC = 971 AND t.ACTN_CD = 641
  AND  t.TRANS_DT >= DATE '{{LOOKBACK_START}}';

-- (b) Assessed balance over the threshold on individual MFTs (wide net for MISSED certifications)
CREATE OR REPLACE TABLE {{cdw}}.WRK_PP_DRV_HIGH_BALANCE AS
SELECT m.MASKED_TIN AS tin
FROM   {{cdw}}.IMF_MODULE m
WHERE  m.MFT_CD IN (30, 31, 55)
  AND  m.MOD_BAL_AMT > 0          -- unpaid balance of ASSESSMENT only, never accruals (IRM 5.19.25.3(2))
GROUP BY m.MASKED_TIN
HAVING SUM(m.MOD_BAL_AMT) > {{THRESHOLD}};

CREATE OR REPLACE TABLE {{cdw}}.WRK_PP_DRV AS
SELECT tin FROM {{cdw}}.WRK_PP_DRV_CERTIFIED
UNION
SELECT tin FROM {{cdw}}.WRK_PP_DRV_HIGH_BALANCE;

/* ---------- 3. Token crosswalk: not needed (masked TIN passes through) ------------ */

/* ---------- 4. Table pulls (all joined to the driver) ----------------------------- */

-- 4.1 pp_entity
CREATE OR REPLACE TABLE {{out}}.pp_entity AS
SELECT d.tin AS tin_token, e.TIN_TYPE_CD AS tin_type, e.NM_CTRL AS name_control,
       e.DOD_DT AS date_of_death,
       CASE WHEN e.FRGN_ADDR_IND = 'Y' THEN 'Y' ELSE 'N' END AS foreign_address_ind,
       e.ADDR_ST_CD AS address_state
FROM   {{cdw}}.WRK_PP_DRV d
JOIN   {{cdw}}.IMF_ENTITY e ON e.MASKED_TIN = d.tin;

-- 4.2 pp_module: every individual module for driver TINs (including zero-balance and MFT 35/65)
CREATE OR REPLACE TABLE {{out}}.pp_module AS
SELECT d.tin AS tin_token, m.MFT_CD AS mft, m.TAX_PRD AS tax_period,
       m.JNT_FLR_IND AS joint_ind, sd.tin AS secondary_tin_token,   -- secondary only if also in driver
       m.MOD_BAL_AMT AS assessed_balance,                            -- assessed only; no accruals
       m.MOD_STAT_CD AS status_code,
       DATE '{{AS_OF}}' AS extract_date
FROM   {{cdw}}.WRK_PP_DRV d
JOIN   {{cdw}}.IMF_MODULE m      ON m.MASKED_TIN = d.tin
LEFT JOIN {{cdw}}.WRK_PP_DRV sd  ON sd.tin = m.SEC_MASKED_TIN
WHERE  m.MFT_CD IN (30, 31, 35, 55, 65);

-- 4.3 pp_csed: one row per assessment
CREATE OR REPLACE TABLE {{out}}.pp_csed AS
SELECT d.tin AS tin_token, c.MFT_CD AS mft, c.TAX_PRD AS tax_period,
       c.ASSMT_TC AS assessment_tc, c.ASSMT_DT AS assessment_date, c.CSED_DT AS csed_date
FROM   {{cdw}}.WRK_PP_DRV d
JOIN   {{cdw}}.IMF_CSED c ON c.MASKED_TIN = d.tin
WHERE  c.MFT_CD IN (30, 31, 35, 55, 65);

-- 4.4 pp_transaction: FULL history for in-scope modules. Don't filter by TC.
CREATE OR REPLACE TABLE {{out}}.pp_transaction AS
SELECT ROW_NUMBER() OVER (ORDER BY d.tin, t.MFT_CD, t.TAX_PRD, t.TRANS_DT, t.DLN) AS txn_seq,
       d.tin AS tin_token, t.MFT_CD AS mft, t.TAX_PRD AS tax_period,
       t.TC AS tc, t.ACTN_CD AS action_code, t.CLSNG_CD AS closing_code,
       t.TRANS_DT AS txn_date, t.PSTNG_CYC AS posting_cycle,
       t.TRANS_AMT AS amount,                    -- credits negative
       t.DLN AS dln, t.MISC_FLD AS misc_field    -- 'FINAL' on the last TC 972 AC 641
FROM   {{cdw}}.WRK_PP_DRV d
JOIN   {{cdw}}.IMF_TXN t ON t.MASKED_TIN = d.tin
WHERE  t.MFT_CD IN (30, 31, 35, 55, 65);

-- 4.5 pp_notice
CREATE OR REPLACE TABLE {{out}}.pp_notice AS
SELECT d.tin AS tin_token, n.MFT_CD AS mft, n.TAX_PRD AS tax_period,
       n.NTC_CD AS notice_code, n.NTC_ISS_DT AS issue_date, n.UNDLV_IND AS undeliverable_ind
FROM   {{cdw}}.WRK_PP_DRV d
JOIN   {{cdw}}.IMF_NOTICE n ON n.MASKED_TIN = d.tin
WHERE  n.NTC_CD IN ('CP508C','CP508R','LT11','L1058','L3172','L6152');

-- 4.6 pp_lien: ALS lien + lien-to-module link
--     cdp_request_deadline = Letter 3172 "must file" date (IRM 5.19.4.6.2, 12-30-2024):
--       PULLED from ALS/Letter 3172 data when present (CONFIRM THIS FIELD EXISTS IN CDW), else
--       COMPUTED: NFTL mailing date + 3 business days (estimated filing date) + 5 business days
--       + 30 calendar days (CONFIRM NFTL MAILING DATE and a BUSINESS-DAY CALENDAR EXIST IN CDW).
--     Weekend/holiday handling of the final day is not stated in IRM 5.19.4.6.2 (open item);
--     WRK_PP_MUST_FILE counts such dates for review.
CREATE OR REPLACE TABLE {{cdw}}.WRK_PP_MUST_FILE AS
SELECT l.LIEN_ID, l.NFTL_MAIL_DT, e.CAL_DT AS est_filing_dt,
       date_add(f.CAL_DT, 30)                          AS computed_must_file_dt,
       l.L3172_MUST_FILE_DT                            AS pulled_must_file_dt,
       COALESCE(l.L3172_MUST_FILE_DT, date_add(f.CAL_DT, 30)) AS must_file_dt,
       CASE WHEN l.L3172_MUST_FILE_DT IS NOT NULL THEN 'PULLED' ELSE 'COMPUTED' END AS must_file_source
FROM   {{cdw}}.ALS_LIEN l
LEFT JOIN {{cdw}}.REF_BUS_CALENDAR m ON m.CAL_DT = l.NFTL_MAIL_DT
LEFT JOIN {{cdw}}.REF_BUS_CALENDAR e ON e.IS_BUS_DAY AND e.BUS_DAY_SEQ = m.BUS_DAY_SEQ + 3
LEFT JOIN {{cdw}}.REF_BUS_CALENDAR f ON f.IS_BUS_DAY AND f.BUS_DAY_SEQ = e.BUS_DAY_SEQ + 5;

CREATE OR REPLACE TABLE {{out}}.pp_lien AS
SELECT l.LIEN_ID AS lien_id, d.tin AS tin_token, lm.MFT_CD AS mft, lm.TAX_PRD AS tax_period,
       l.NFTL_FILED_DT AS nftl_filed_date, l.CDP_NTC_DT AS cdp_notice_date,
       mf.must_file_dt AS cdp_request_deadline,
       l.LIEN_RLSE_DT AS lien_release_date
FROM   {{cdw}}.WRK_PP_DRV d
JOIN   {{cdw}}.ALS_LIEN l          ON l.MASKED_TIN = d.tin
JOIN   {{cdw}}.ALS_LIEN_MODULE lm  ON lm.LIEN_ID = l.LIEN_ID
JOIN   {{cdw}}.WRK_PP_MUST_FILE mf ON mf.LIEN_ID = l.LIEN_ID;

-- 4.7 pp_appeals_cdp: lien/levy CDP and equivalent hearings from ACDS and ACMS (join on masked TIN)
CREATE OR REPLACE TABLE {{out}}.pp_appeals_cdp AS
SELECT a.WUNO AS appeal_key, 'ACDS' AS source_system, d.tin AS tin_token, a.MFT_CD AS mft, a.TAX_PRD AS tax_period,
       CASE a.HRG_TYPE_CD WHEN 'L' THEN 'LIEN_CDP' WHEN 'V' THEN 'LEVY_CDP' WHEN 'E' THEN 'EQUIV' END AS hearing_type,
       a.RQST_RCVD_DT AS cdp_request_date, a.TIMELY_IND AS timely_ind, a.CLOSED_DT AS cdp_closed_date
FROM   {{cdw}}.WRK_PP_DRV d JOIN {{cdw}}.ACDS_CASE a ON a.MASKED_TIN = d.tin
WHERE  a.CASE_CAT_CD = 'CDP'
UNION ALL
SELECT a.APPEAL_NUM, 'ACMS', d.tin, a.MFT_CD, a.TAX_PRD,
       CASE a.HRG_TYPE_CD WHEN 'LIEN' THEN 'LIEN_CDP' WHEN 'LEVY' THEN 'LEVY_CDP' WHEN 'EQUIV' THEN 'EQUIV' END,
       a.RQST_RCVD_DT, a.TIMELY_IND, a.CLOSED_DT
FROM   {{cdw}}.WRK_PP_DRV d JOIN {{cdw}}.ACMS_APPEAL a ON a.MASKED_TIN = d.tin
WHERE  a.CASE_TYPE_CD = 'CDP';

/* ---------- 5. Control checks ------------------------------------------------------ */
CREATE OR REPLACE TABLE {{cdw}}.WRK_PP_CONTROL AS
SELECT 'driver_certified' AS check_name, COUNT(*) AS n FROM {{cdw}}.WRK_PP_DRV_CERTIFIED
UNION ALL SELECT 'driver_high_balance', COUNT(*) FROM {{cdw}}.WRK_PP_DRV_HIGH_BALANCE
UNION ALL SELECT 'driver_total', COUNT(*) FROM {{cdw}}.WRK_PP_DRV
UNION ALL SELECT 'certified_tin_without_module', COUNT(*) FROM {{cdw}}.WRK_PP_DRV_CERTIFIED c
          LEFT ANTI JOIN {{out}}.pp_module m ON m.tin_token = c.tin
UNION ALL SELECT 'must_file_pulled', COUNT_IF(must_file_source = 'PULLED') FROM {{cdw}}.WRK_PP_MUST_FILE
UNION ALL SELECT 'must_file_computed_fallback', COUNT_IF(must_file_source = 'COMPUTED') FROM {{cdw}}.WRK_PP_MUST_FILE
UNION ALL SELECT 'must_file_pulled_ne_computed', COUNT_IF(pulled_must_file_dt <> computed_must_file_dt) FROM {{cdw}}.WRK_PP_MUST_FILE
UNION ALL SELECT 'must_file_missing', COUNT_IF(must_file_dt IS NULL) FROM {{cdw}}.WRK_PP_MUST_FILE
UNION ALL SELECT 'must_file_on_weekend_or_holiday', COUNT(*) FROM {{cdw}}.WRK_PP_MUST_FILE w
          JOIN {{cdw}}.REF_BUS_CALENDAR c ON c.CAL_DT = w.must_file_dt WHERE NOT c.IS_BUS_DAY
UNION ALL SELECT 'txn_without_module', COUNT(*) FROM {{out}}.pp_transaction t
          LEFT ANTI JOIN {{out}}.pp_module m USING (tin_token, mft, tax_period)
UNION ALL SELECT 'module_balance_ne_txn_sum', COUNT(*) FROM (
          SELECT m.tin_token FROM {{out}}.pp_module m
          LEFT JOIN (SELECT tin_token, mft, tax_period, SUM(amount) AS s FROM {{out}}.pp_transaction
                     GROUP BY tin_token, mft, tax_period) t USING (tin_token, mft, tax_period)
          WHERE m.assessed_balance <> coalesce(t.s, 0));
