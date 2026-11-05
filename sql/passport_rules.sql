-- =====================================================================================
-- IRC 7345 Passport Certification / Decertification Rules - Databricks SQL (POC)
-- v0.5.2 - Databricks serverless fix + reversal-reason view (validated on Databricks Free Edition, 2026-11-04).
--   * v_txn and v_indicator_active are now materialized as tables (t_txn,
--     t_indicator_active). Re-run this whole script after reloading the source tables.
--   * v_module_eval reads each source once (conditional aggregation) and uses explicit
--     join keys. This avoids the MISSING_ATTRIBUTES.RESOLVED_ATTRIBUTE_APPEAR_IN_OPERATION
--     error that Databricks raised on the v0.5 version. Logic and outputs are unchanged.
--   * v0.5.2 adds v_module_reversal_reason (section 5b) so Genie reads the reason a
--     certified module needs reversal instead of deriving it.
--   * Change the catalog/schema in the two USE lines below if yours differ.
-- Rule codes live in ref_indicator / ref_indicator_reversal so the business can maintain
-- them without code changes. v0.5: every indicator code (TC/AC/closing code) is checked
-- against the IRM 5.19.25 text (transmittal 10-10-2024). Reversal pairings other than
-- TC 972 AC 641 are not stated in the IRM and stay flagged "verify vs Doc 6209" in
-- ref_indicator_reversal.verification.
-- Balances: the threshold test uses pp_module.assessed_balance and, for balance at
-- certification, the sum of posted transaction amounts. Both are the unpaid balance of
-- assessment (tax + assessed penalty and interest); accrued, unassessed interest and
-- penalty are never included (IRM 5.19.25.3(2)).
-- As-of date comes from pp_run_params (not current_date) so results are reproducible.
-- =====================================================================================

USE CATALOG workspace;
USE SCHEMA passport_poc;

-- Remove the v0.5 views these steps replace (safe if they don't exist)
DROP VIEW IF EXISTS v_module_eval;
DROP VIEW IF EXISTS v_indicator_active;
DROP VIEW IF EXISTS v_txn;

-- 1. Typed transactions (table) -----------------------------------------------------------
CREATE OR REPLACE TABLE t_txn AS
SELECT t.txn_seq, t.tin_token, CAST(t.mft AS INT) AS mft, t.tax_period,
       CAST(t.tc AS INT) AS tc,
       CAST(NULLIF(CAST(t.action_code AS STRING), '') AS INT)  AS action_code,
       CAST(NULLIF(CAST(t.closing_code AS STRING), '') AS INT) AS closing_code,
       CAST(t.txn_date AS DATE) AS txn_date, CAST(t.amount AS DECIMAL(15,2)) AS amount,
       t.misc_field
FROM pp_transaction t
CROSS JOIN pp_run_params p
WHERE CAST(t.txn_date AS DATE) <= CAST(p.as_of_date AS DATE);

-- 2. Indicator hits and whether each is still unreversed --------------------------------
CREATE OR REPLACE VIEW v_indicator_hit AS
SELECT t.tin_token, t.mft, t.tax_period, t.txn_seq, t.txn_date AS indicator_date,
       r.indicator_code, r.category
FROM t_txn t
JOIN ref_indicator r
  ON t.tc = CAST(r.tc AS INT)
 AND (NULLIF(CAST(r.action_code AS STRING), '') IS NULL OR t.action_code = CAST(r.action_code AS INT))
 AND (NULLIF(CAST(r.cc_min AS STRING), '') IS NULL
      OR t.closing_code BETWEEN CAST(r.cc_min AS INT) AND CAST(r.cc_max AS INT));

CREATE OR REPLACE TABLE t_indicator_active AS
SELECT h.*
FROM v_indicator_hit h
WHERE NOT EXISTS (
  SELECT 1
  FROM ref_indicator_reversal rv
  JOIN t_txn x ON x.tc = CAST(rv.reversal_tc AS INT)
   AND (NULLIF(CAST(rv.reversal_action_code AS STRING), '') IS NULL
        OR x.action_code = CAST(rv.reversal_action_code AS INT))
  WHERE rv.indicator_code = h.indicator_code
    AND x.tin_token = h.tin_token AND x.mft = h.mft AND x.tax_period = h.tax_period
    AND x.txn_date >= h.indicator_date);

-- 3. Lien predicate: NFTL filed and IRC 6320 rights lapsed (no timely request) or exhausted (hearing closed)
--    Appeals CDP cases come from ACDS and ACMS; a case in both systems is collapsed to one.
CREATE OR REPLACE VIEW v_appeals_cdp AS
SELECT tin_token, CAST(mft AS INT) AS mft, tax_period, hearing_type,
       CAST(cdp_request_date AS DATE) AS cdp_request_date,
       MAX(timely_ind) AS timely_ind,
       MAX(CAST(NULLIF(CAST(cdp_closed_date AS STRING), '') AS DATE)) AS cdp_closed_date,
       concat_ws(',', sort_array(collect_set(source_system))) AS source_systems
FROM pp_appeals_cdp
GROUP BY tin_token, CAST(mft AS INT), tax_period, hearing_type, CAST(cdp_request_date AS DATE);

CREATE OR REPLACE VIEW v_lien_predicate AS
WITH l AS (
  SELECT tin_token, CAST(mft AS INT) AS mft, tax_period, lien_id,
         CAST(nftl_filed_date AS DATE) AS filed, CAST(cdp_request_deadline AS DATE) AS deadline
  FROM pp_lien),
a AS (
  SELECT l.lien_id, l.mft, l.tax_period, l.tin_token,
         MAX(1) AS has_timely_request,
         -- NULL while any timely hearing is still open
         CASE WHEN COUNT_IF(c.cdp_closed_date IS NULL) > 0 THEN NULL ELSE MAX(c.cdp_closed_date) END AS closed
  FROM l JOIN v_appeals_cdp c
    ON c.tin_token = l.tin_token AND c.mft = l.mft AND c.tax_period = l.tax_period
   AND c.hearing_type = 'LIEN_CDP' AND c.timely_ind = 'Y'
   AND c.cdp_request_date BETWEEN l.filed AND l.deadline
  GROUP BY l.lien_id, l.mft, l.tax_period, l.tin_token)
SELECT l.tin_token, l.mft, l.tax_period,
       MIN(CASE WHEN a.has_timely_request IS NULL THEN GREATEST(l.filed, date_add(l.deadline, 1))
                WHEN a.closed IS NOT NULL THEN GREATEST(l.filed, a.closed) END) AS lien_predicate_date
FROM l LEFT JOIN a ON a.lien_id = l.lien_id AND a.mft = l.mft AND a.tax_period = l.tax_period
GROUP BY l.tin_token, l.mft, l.tax_period;

-- 4. Running balance (for balance-at-certification and payoff date) -------------------
CREATE OR REPLACE VIEW v_running_balance AS
SELECT tin_token, mft, tax_period, txn_date,
       SUM(day_amt) OVER (PARTITION BY tin_token, mft, tax_period ORDER BY txn_date
                          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_balance
FROM (SELECT tin_token, mft, tax_period, txn_date, SUM(amount) AS day_amt
      FROM t_txn GROUP BY tin_token, mft, tax_period, txn_date);

-- 5. Module evaluation -------------------------------------------------------------------
CREATE OR REPLACE VIEW v_module_eval AS
WITH p AS (SELECT CAST(as_of_date AS DATE) AS as_of FROM pp_run_params),
m AS (
  SELECT tin_token, CAST(mft AS INT) AS mft, tax_period,
         CAST(assessed_balance AS DECIMAL(15,2)) AS assessed_balance, status_code, joint_ind
  FROM pp_module),
cs AS (SELECT tin_token AS k_tin, CAST(mft AS INT) AS k_mft, tax_period AS k_tp,
              MAX(CAST(csed_date AS DATE)) AS csed_max
       FROM pp_csed GROUP BY tin_token, CAST(mft AS INT), tax_period),
-- all indicator-based facts in one pass
ia AS (SELECT tin_token AS k_tin, mft AS k_mft, tax_period AS k_tp,
              MIN(CASE WHEN indicator_code = 'LEVY_PRED' THEN indicator_date END) AS levy_predicate_date,
              MIN(CASE WHEN category IN ('STAT_EXCL','DISC_EXCL') THEN indicator_date END) AS exclusion_date,
              NULLIF(concat_ws(',', sort_array(collect_set(
                CASE WHEN category IN ('STAT_EXCL','DISC_EXCL') THEN indicator_code END))), '') AS exclusions,
              MAX(CASE WHEN category = 'NONCERT' THEN 1 ELSE 0 END) AS has_noncert,
              MAX(CASE WHEN indicator_code = 'CERTIFIED' THEN indicator_date END) AS active_641_date
       FROM t_indicator_active GROUP BY tin_token, mft, tax_period),
-- all TC 971/972 AC 641 facts in one pass
tx AS (SELECT tin_token AS k_tin, mft AS k_mft, tax_period AS k_tp,
              MAX(CASE WHEN tc = 971 THEN txn_date END) AS last_641_date,
              MAX(CASE WHEN tc = 972 THEN txn_date END) AS last_972_date,
              MAX(CASE WHEN tc = 972 THEN (CASE WHEN misc_field = 'FINAL' THEN 1 ELSE 0 END) END) AS has_final
       FROM t_txn WHERE tc IN (971, 972) AND action_code = 641
       GROUP BY tin_token, mft, tax_period),
lp AS (SELECT tin_token AS k_tin, mft AS k_mft, tax_period AS k_tp, lien_predicate_date
       FROM v_lien_predicate),
nm AS (SELECT DISTINCT CAST(mft AS INT) AS nc_mft FROM ref_noncert_mft),
en AS (SELECT tin_token AS k_tin, CAST(NULLIF(CAST(date_of_death AS STRING), '') AS DATE) AS entity_dod
       FROM pp_entity),
base AS (
  SELECT m.*, p.as_of, cs.csed_max, (cs.csed_max >= p.as_of) AS legally_enforceable,
         ia.levy_predicate_date, lp.lien_predicate_date,
         least(ia.levy_predicate_date, lp.lien_predicate_date) AS predicate_date,
         ia.exclusions, ia.exclusion_date,
         en.entity_dod,
         (nm.nc_mft IS NOT NULL OR coalesce(ia.has_noncert, 0) = 1) AS non_certifiable,
         tx.last_641_date, ia.active_641_date, tx.last_972_date, tx.has_final
  FROM m CROSS JOIN p
  LEFT JOIN cs ON cs.k_tin = m.tin_token AND cs.k_mft = m.mft AND cs.k_tp = m.tax_period
  LEFT JOIN ia ON ia.k_tin = m.tin_token AND ia.k_mft = m.mft AND ia.k_tp = m.tax_period
  LEFT JOIN tx ON tx.k_tin = m.tin_token AND tx.k_mft = m.mft AND tx.k_tp = m.tax_period
  LEFT JOIN lp ON lp.k_tin = m.tin_token AND lp.k_mft = m.mft AND lp.k_tp = m.tax_period
  LEFT JOIN nm ON nm.nc_mft = m.mft
  LEFT JOIN en ON en.k_tin = m.tin_token),
-- payoff and balance-at-certification keyed off tx (not base) to keep the plan simple
payoff AS (
  SELECT tx.k_tin, tx.k_mft, tx.k_tp, MIN(rb.txn_date) AS payoff_date
  FROM tx JOIN v_running_balance rb
    ON rb.tin_token = tx.k_tin AND rb.mft = tx.k_mft AND rb.tax_period = tx.k_tp
  WHERE tx.last_641_date IS NOT NULL AND rb.txn_date >= tx.last_641_date AND rb.cum_balance <= 0
  GROUP BY tx.k_tin, tx.k_mft, tx.k_tp),
bal_at_cert AS (
  SELECT tx.k_tin, tx.k_mft, tx.k_tp, SUM(t.amount) AS balance_at_cert
  FROM tx JOIN t_txn t
    ON t.tin_token = tx.k_tin AND t.mft = tx.k_mft AND t.tax_period = tx.k_tp
  WHERE tx.last_641_date IS NOT NULL AND t.txn_date <= tx.last_641_date
  GROUP BY tx.k_tin, tx.k_mft, tx.k_tp)
SELECT b.*,
       coalesce(b.exclusion_date IS NOT NULL OR (b.entity_dod IS NOT NULL AND b.entity_dod <= b.as_of), false) AS excluded,
       (b.assessed_balance > 0 AND b.legally_enforceable AND b.predicate_date <= b.as_of
        AND NOT b.non_certifiable AND b.exclusion_date IS NULL
        AND (b.entity_dod IS NULL OR b.entity_dod > b.as_of)) AS eligible_now,
       (b.active_641_date IS NOT NULL) AS certified_now,
       po.payoff_date, bc.balance_at_cert,
       -- earliest date (on/after certification) a reversal condition became true
       CASE WHEN b.last_641_date IS NOT NULL THEN
         least(po.payoff_date,
               CASE WHEN NOT b.legally_enforceable THEN GREATEST(b.csed_max, b.last_641_date) END,
               CASE WHEN b.exclusion_date IS NOT NULL THEN GREATEST(b.exclusion_date, b.last_641_date) END,
               CASE WHEN b.entity_dod <= b.as_of THEN GREATEST(b.entity_dod, b.last_641_date) END,
               CASE WHEN b.non_certifiable THEN b.last_641_date END)
       END AS reversal_trigger_date
FROM base b
LEFT JOIN payoff po ON po.k_tin = b.tin_token AND po.k_mft = b.mft AND po.k_tp = b.tax_period
LEFT JOIN bal_at_cert bc ON bc.k_tin = b.tin_token AND bc.k_mft = b.mft AND bc.k_tp = b.tax_period;

-- 5b. Reversal reason per certified module with a trigger (for Genie) ----------------------
CREATE OR REPLACE VIEW v_module_reversal_reason AS
SELECT tin_token, mft, tax_period, reversal_trigger_date, assessed_balance,
       CASE WHEN reversal_trigger_date = payoff_date THEN 'Full payment'
            WHEN exclusion_date IS NOT NULL
                 AND reversal_trigger_date = GREATEST(exclusion_date, last_641_date) THEN concat('Exclusion: ', exclusions)
            WHEN NOT legally_enforceable THEN 'CSED expired'
            WHEN entity_dod IS NOT NULL AND entity_dod <= as_of THEN 'Death'
            WHEN non_certifiable THEN 'Non-certifiable module'
            ELSE 'Other' END AS reversal_reason
FROM v_module_eval
WHERE certified_now AND reversal_trigger_date IS NOT NULL;

-- 6. Taxpayer evaluation --------------------------------------------------------------------
CREATE OR REPLACE VIEW v_taxpayer_eval AS
WITH p AS (SELECT CAST(as_of_date AS DATE) AS as_of, CAST(threshold_year AS INT) AS ty FROM pp_run_params)
SELECT me.tin_token,
       MAX(p.as_of) AS as_of_date,
       MAX(th.threshold_amount) AS threshold_amount,
       -- unpaid balance of assessment only; no accruals (IRM 5.19.25.3(2))
       SUM(CASE WHEN me.eligible_now THEN me.assessed_balance ELSE 0 END) AS eligible_balance,
       SUM(CASE WHEN me.certified_now THEN me.assessed_balance ELSE 0 END) AS certified_balance,
       COUNT_IF(me.certified_now) AS certified_modules,
       COUNT_IF(me.certified_now AND me.reversal_trigger_date IS NOT NULL) AS certified_modules_with_trigger,
       COUNT_IF(me.certified_now AND (me.predicate_date IS NULL OR me.predicate_date > me.active_641_date)) AS certified_modules_no_predicate,
       COUNT_IF(me.eligible_now AND NOT me.certified_now) AS eligible_uncertified_modules,
       COUNT_IF(me.last_641_date IS NOT NULL) AS ever_certified_modules,
       MIN(CASE WHEN me.certified_now THEN me.active_641_date END) AS certification_date,
       SUM(CASE WHEN me.certified_now THEN me.balance_at_cert END) AS balance_at_certification,
       MAX(CASE WHEN me.certified_now THEN me.reversal_trigger_date END) AS decert_trigger_date,
       MIN(CASE WHEN me.certified_now THEN me.reversal_trigger_date END) AS first_module_trigger_date,
       MAX(me.last_972_date) AS final_reversal_date,
       MAX(CASE WHEN me.last_641_date IS NOT NULL THEN me.reversal_trigger_date END) AS reversed_trigger_date
FROM v_module_eval me
CROSS JOIN p
LEFT JOIN ref_threshold th ON CAST(th.threshold_year AS INT) = p.ty
GROUP BY me.tin_token;

-- 7. Findings (one row per taxpayer per finding) ---------------------------------------------
CREATE OR REPLACE VIEW v_findings AS
WITH rr AS (SELECT DISTINCT tin_token AS rr_tin FROM t_indicator_active
            WHERE indicator_code = 'REVOCATION_REF'),
te AS (
  SELECT te.*, ct.threshold_amount AS cert_year_threshold,
         (te.certified_modules > 0) AS is_certified,
         (te.certified_modules > 0 AND te.certified_modules_with_trigger = te.certified_modules) AS decert_due,
         (rr.rr_tin IS NOT NULL) AS revocation_referred
  FROM v_taxpayer_eval te
  LEFT JOIN ref_threshold ct ON CAST(ct.threshold_year AS INT) = year(te.certification_date)
  LEFT JOIN rr ON rr.rr_tin = te.tin_token),
f AS (
  SELECT tin_token, 'MISSED_CERTIFICATION' AS finding, 'Meets SDTD definition but not certified' AS detail,
         CAST(NULL AS DATE) AS trigger_date
  FROM te WHERE NOT is_certified AND eligible_balance > threshold_amount
  UNION ALL
  SELECT tin_token, 'NEW_ELIGIBLE_MODULE_NOT_CERTIFIED', 'Certified taxpayer has eligible module(s) without TC 971 AC 641', NULL
  FROM te WHERE is_certified AND NOT decert_due AND eligible_uncertified_modules > 0
  UNION ALL
  SELECT tin_token, 'CERTIFIED_MODULE_NO_PREDICATE', 'Certified module lacks levy (AC 640) or lapsed/exhausted lien predicate at certification', NULL
  FROM te WHERE certified_modules_no_predicate > 0
  UNION ALL
  SELECT tin_token, 'CERTIFIED_BELOW_THRESHOLD_AT_CERT', 'Assessed balance of certified modules at certification did not exceed threshold', certification_date
  FROM te WHERE is_certified AND balance_at_certification <= cert_year_threshold
  UNION ALL
  SELECT tin_token,
         CASE WHEN datediff(as_of_date, decert_trigger_date) > 30
              THEN 'DECERT_DUE_OVERDUE' ELSE 'DECERT_DUE_PENDING' END,
         'All certified modules meet a reversal condition; TC 972 AC 641 not posted', decert_trigger_date
  FROM te WHERE decert_due
  UNION ALL
  SELECT tin_token,
         CASE WHEN datediff(as_of_date, first_module_trigger_date) > 30
              THEN 'MODULE_REVERSAL_DUE_OVERDUE' ELSE 'MODULE_REVERSAL_DUE_PENDING' END,
         'Some certified modules meet a reversal condition; taxpayer remains certified', first_module_trigger_date
  FROM te WHERE is_certified AND NOT decert_due AND certified_modules_with_trigger > 0
  UNION ALL
  SELECT tin_token,
         CASE WHEN reversed_trigger_date IS NULL THEN 'REVERSED_NO_TRIGGER_FOUND'
              WHEN datediff(final_reversal_date, reversed_trigger_date) <= 30 THEN 'REVERSED_TIMELY'
              ELSE 'REVERSED_LATE' END,
         concat('Days from trigger to final reversal: ', CAST(datediff(final_reversal_date, reversed_trigger_date) AS STRING)),
         reversed_trigger_date
  FROM te WHERE NOT is_certified AND ever_certified_modules > 0
  UNION ALL
  SELECT tin_token, 'INFO_BELOW_THRESHOLD_STILL_CERTIFIED', 'Balance now below threshold; correctly remains certified (no full resolution)', NULL
  FROM te WHERE is_certified AND NOT decert_due AND certified_balance <= threshold_amount
        AND NOT (balance_at_certification <= cert_year_threshold)
  UNION ALL
  SELECT tin_token, 'INFO_EXPEDITE_INELIGIBLE', 'Revocation referred to State (TC 971 AC 644)', NULL
  FROM te WHERE revocation_referred)
SELECT f.*, datediff(p.as_of, f.trigger_date) AS days_since_trigger
FROM f CROSS JOIN (SELECT CAST(as_of_date AS DATE) AS as_of FROM pp_run_params) p;

-- 8. Control check: certification years with no threshold row ----------------------------
-- CERTIFIED_BELOW_THRESHOLD_AT_CERT and INFO_BELOW_THRESHOLD_STILL_CERTIFIED compare against
-- the threshold for the certification year. A missing year silently suppresses both, so
-- this view must return 0 rows before findings are used.
CREATE OR REPLACE VIEW v_threshold_gaps AS
SELECT DISTINCT year(te.certification_date) AS certification_year
FROM v_taxpayer_eval te
LEFT JOIN ref_threshold th ON CAST(th.threshold_year AS INT) = year(te.certification_date)
WHERE te.certification_date IS NOT NULL AND th.threshold_year IS NULL;
