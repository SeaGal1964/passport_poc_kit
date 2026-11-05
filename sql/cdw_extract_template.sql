/* =====================================================================================
   IRC 7345 Passport Analytics - CDW Extract Query Template (DRAFT v0.2)
   -------------------------------------------------------------------------------------
   PURPOSE  Pull the extract defined in Passport_Certification_Extract_Spec_v0.5.xlsx.
   STATUS   Logic pattern only. Every <<...>> is a placeholder for a CDW database, table
            or column name. Confirm all of them in the CDW Database Library / data
            dictionaries. Nothing here is a real CDW object name.
   DIALECT  ANSI-style SQL. Run it as-is, or wrap it in SAS PROC SQL using explicit
            pass-through (see the bottom), so the heavy joins run in the database rather
            than pulling rows into SAS.
   v0.2     4.6 cdp_request_deadline = Letter 3172 must-file date per IRM 5.19.4.6.2 (12-30-2024).
            THREE ELEMENTS TO CONFIRM EXIST IN CDW: <<L3172_MUST_FILE_DATE>>, <<NFTL_MAILING_DATE>>,
            <<BUSINESS_DAY_CALENDAR>>.
   ORDER    1 parameters -> 2 driver population -> 3 token crosswalk -> 4 table pulls -> 5 checks
   ===================================================================================== */

/* ---------- 1. Parameters ---------------------------------------------------------- */
-- Lookback start: Jan 2018, when certification began. Shorten it if CDW retention is less.
-- Threshold: the current year's indexed amount ($66,000 for 2026).
-- Individual MFTs in scope: 30, 31, 55 (35/65 are pulled only so they can be excluded visibly).
--   :LOOKBACK_START = DATE '2018-01-01'
--   :AS_OF          = DATE '2026-10-23'
--   :THRESHOLD      = 66000

/* ---------- 2. Driver population (one row per TIN) -------------------------------- */
-- (a) Everyone who has ever been certified (TC 971 AC 641) within the lookback
CREATE TABLE drv_certified AS
SELECT DISTINCT t.<<TIN>> AS tin
FROM   <<CDW_IMF_TRANSACTION>> t
WHERE  t.<<TC>> = 971 AND t.<<ACTION_CODE>> = 641
  AND  t.<<TXN_DATE>> >= :LOOKBACK_START;

-- (b) Individuals with an assessed balance over the threshold on individual MFTs
--     (needed to find MISSED certifications). Uses the module-balance snapshot.
--     The rules are applied downstream in Databricks; this is only a wide net.
CREATE TABLE drv_high_balance AS
SELECT m.<<TIN>> AS tin
FROM   <<CDW_IMF_MODULE>> m
WHERE  m.<<MFT>> IN (30, 31, 55)
  AND  m.<<MODULE_BALANCE>> > 0           -- must be the unpaid balance of ASSESSMENT (tax + assessed
                                          -- penalty/interest), never a payoff with accruals (IRM 5.19.25.3(2))
GROUP BY m.<<TIN>>
HAVING SUM(m.<<MODULE_BALANCE>>) > :THRESHOLD;

CREATE TABLE drv AS
SELECT tin FROM drv_certified
UNION
SELECT tin FROM drv_high_balance;

/* ---------- 3. Token crosswalk (built and KEPT inside CDW) ------------------------ */
-- Only tokens leave CDW. The crosswalk stays in an access-controlled CDW workspace,
-- so findings can be traced back to a TIN by authorized users.
CREATE TABLE xwalk AS
SELECT tin,
       'T' || <<RANDOM_OR_HASH_FUNCTION>>(tin || <<SECRET_SALT>>) AS tin_token
FROM   drv;

/* ---------- 4. Table pulls (all joined to the driver, all output tokenized) ------- */

-- 4.1 pp_entity
SELECT x.tin_token, 'SSN' AS tin_type, e.<<NAME_CONTROL>> AS name_control,
       e.<<DATE_OF_DEATH>> AS date_of_death,
       CASE WHEN e.<<FOREIGN_ADDR_IND>> = <<Y_VALUE>> THEN 'Y' ELSE 'N' END AS foreign_address_ind,
       e.<<STATE>> AS address_state
FROM   xwalk x
JOIN   <<CDW_IMF_ENTITY>> e ON e.<<TIN>> = x.tin;

-- 4.2 pp_module: every individual module for driver TINs (including zero-balance and
--     MFT 35/65), so reversals and non-certifiable debt stay visible
SELECT x.tin_token, m.<<MFT>> AS mft, m.<<TAX_PERIOD>> AS tax_period,
       m.<<JOINT_IND>> AS joint_ind, sx.tin_token AS secondary_tin_token,
       m.<<MODULE_BALANCE>> AS assessed_balance,   -- assessed only; no accruals (IRM 5.19.25.3(2))
       m.<<STATUS_CODE>> AS status_code,
       :AS_OF AS extract_date
FROM   xwalk x
JOIN   <<CDW_IMF_MODULE>> m  ON m.<<TIN>> = x.tin
LEFT JOIN xwalk sx           ON sx.tin = m.<<SECONDARY_TIN>>   -- secondary spouse token, if also in driver
WHERE  m.<<MFT>> IN (30, 31, 35, 55, 65);

-- 4.3 pp_csed: one row per assessment
SELECT x.tin_token, c.<<MFT>> AS mft, c.<<TAX_PERIOD>> AS tax_period,
       c.<<ASSESSMENT_TC>> AS assessment_tc, c.<<ASSESSMENT_DATE>> AS assessment_date,
       c.<<CSED_DATE>> AS csed_date
FROM   xwalk x
JOIN   <<CDW_IMF_CSED>> c ON c.<<TIN>> = x.tin
WHERE  c.<<MFT>> IN (30, 31, 35, 55, 65);

-- 4.4 pp_transaction: FULL history for in-scope modules. Don't filter by TC.
--     Balance at the certification date and payoff dates are rebuilt from these rows.
SELECT ROW_NUMBER() OVER (ORDER BY x.tin_token, t.<<MFT>>, t.<<TAX_PERIOD>>, t.<<TXN_DATE>>, t.<<DLN>>) AS txn_seq,
       x.tin_token, t.<<MFT>> AS mft, t.<<TAX_PERIOD>> AS tax_period,
       t.<<TC>> AS tc, t.<<ACTION_CODE>> AS action_code, t.<<CLOSING_CODE>> AS closing_code,
       t.<<TXN_DATE>> AS txn_date, t.<<POSTING_CYCLE>> AS posting_cycle,
       t.<<AMOUNT>> AS amount,                 -- confirm sign convention (credits negative)
       t.<<DLN>> AS dln, t.<<MISC_FIELD>> AS misc_field   -- 'FINAL' on the last TC 972 AC 641
FROM   xwalk x
JOIN   <<CDW_IMF_TRANSACTION>> t ON t.<<TIN>> = x.tin
WHERE  t.<<MFT>> IN (30, 31, 35, 55, 65);
-- Volume tip: if this is too big, keep the full history only for modules carrying a
-- 971/641, 971/640, 582, or a balance > 0, and keep 7-10 years for the rest.

-- 4.5 pp_notice
SELECT x.tin_token, n.<<MFT>> AS mft, n.<<TAX_PERIOD>> AS tax_period,
       n.<<NOTICE_CODE>> AS notice_code, n.<<NOTICE_DATE>> AS issue_date,
       n.<<UNDELIVERABLE_IND>> AS undeliverable_ind
FROM   xwalk x
JOIN   <<CDW_IMF_NOTICE>> n ON n.<<TIN>> = x.tin
WHERE  n.<<NOTICE_CODE>> IN ('CP508C','CP508R','LT11','L1058','L3172','L6152');  -- confirm code formats

-- 4.6 pp_lien: from the ALS feed into CDW (per the ALS-Entity PCLIA). If ALS isn't
--     in CDW, request this from ALS directly. CDP fields come from 4.7, not ALS.
SELECT l.<<LIEN_ID>> AS lien_id, x.tin_token, lm.<<MFT>> AS mft, lm.<<TAX_PERIOD>> AS tax_period,
       l.<<NFTL_FILED_DATE>> AS nftl_filed_date, l.<<CDP_NOTICE_DATE>> AS cdp_notice_date,
       -- Letter 3172 "must file" date (IRM 5.19.4.6.2, 12-30-2024). Prefer the date on the letter:
       --   *** CONFIRM <<L3172_MUST_FILE_DATE>> EXISTS IN CDW ***
       -- Fallback: NFTL mailing date + 3 business days (estimated filing date) + 5 business days
       --   + 30 calendar days. *** CONFIRM <<NFTL_MAILING_DATE>> AND <<BUSINESS_DAY_CALENDAR>> EXIST IN CDW ***
       -- Weekend/holiday handling of the final day: not stated in IRM 5.19.4.6.2 (open item).
       COALESCE(l.<<L3172_MUST_FILE_DATE>>,
                <<ADD_CALENDAR_DAYS>>(<<ADD_BUSINESS_DAYS>>(<<ADD_BUSINESS_DAYS>>(l.<<NFTL_MAILING_DATE>>, 3), 5), 30)
       ) AS cdp_request_deadline,
       l.<<RELEASE_DATE>> AS lien_release_date
FROM   xwalk x
JOIN   <<CDW_ALS_LIEN>> l          ON l.<<TIN>> = x.tin
JOIN   <<CDW_ALS_LIEN_MODULE>> lm  ON lm.<<LIEN_ID>> = l.<<LIEN_ID>>;   -- lien-to-module link

-- 4.7 pp_appeals_cdp (new table): lien and levy CDP hearings from ACDS and ACMS.
--     Join on TIN, not on WUNO / Appeal Number (the identifiers differ between the systems).
SELECT a.<<WUNO>> AS appeal_key, 'ACDS' AS source_system, x.tin_token, a.<<MFT>> AS mft, a.<<TAX_PERIOD>> AS tax_period,
       a.<<HEARING_TYPE>> AS hearing_type,          -- map to LIEN_CDP / LEVY_CDP / EQUIV
       a.<<REQUEST_RECEIVED_DATE>> AS cdp_request_date, a.<<TIMELY_IND>> AS timely_ind,
       a.<<CLOSED_DATE>> AS cdp_closed_date
FROM   xwalk x JOIN <<CDW_ACDS_CASE>> a ON a.<<TIN>> = x.tin
WHERE  a.<<CASE_CATEGORY>> IN (<<CDP_CODES>>)
UNION ALL
SELECT a.<<APPEAL_NUMBER>>, 'ACMS', x.tin_token, a.<<MFT>>, a.<<TAX_PERIOD>>, a.<<HEARING_TYPE>>,
       a.<<REQUEST_RECEIVED_DATE>>, a.<<TIMELY_IND>>, a.<<CLOSED_DATE>>
FROM   xwalk x JOIN <<CDW_ACMS_APPEAL>> a ON a.<<TIN>> = x.tin
WHERE  a.<<CASE_TYPE>> IN (<<CDP_CODES>>);
-- Duplicates across ACDS/ACMS are collapsed downstream in v_appeals_cdp (token/MFT/period/hearing type/request date).

/* ---------- 5. Control checks (run before export) --------------------------------- */
-- Driver counts by source; certified TINs with no module rows; transactions with no
-- matching module; module balance vs. the sum of transaction amounts (they should tie);
-- and the date range covered by each source table.
SELECT 'certified' src, COUNT(*) FROM drv_certified
UNION ALL SELECT 'high_balance', COUNT(*) FROM drv_high_balance
UNION ALL SELECT 'driver_total', COUNT(*) FROM drv;

/* ---------- SAS wrapper (explicit pass-through) ----------------------------------- */
/*
proc sql;
  connect to <<ENGINE>> as cdw (<<CONNECTION OPTIONS>>);
  create table work.pp_transaction as
  select * from connection to cdw (
      -- paste query 4.4 here (database-native SQL)
  );
  disconnect from cdw;
quit;
proc export data=work.pp_transaction outfile="<<secure path>>/pp_transaction.csv"
            dbms=csv replace; run;
*/
