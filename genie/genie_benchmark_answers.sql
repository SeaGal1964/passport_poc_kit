-- =====================================================================================
-- Passport POC - expected answers for the 14 Genie benchmark questions
-- v0.5.3 TEMPLATE: {{catalog}}.{{schema}} placeholders are filled in by setup_passport_poc
-- (it writes genie_benchmark_answers_<catalog>_<schema>.sql to the raw volume), or replace them by hand.
-- Computed directly from the validated rule views (not by Genie).
-- Each query is the ground-truth SQL answer for the Genie benchmark whose question text is
-- given in the "BENCHMARK QUESTION" line. Paste the question text and the SQL (without the
-- comment lines) into Genie > Benchmarks. One statement per benchmark.
-- All 14 + 1 guardrail passed (Good) on Databricks Free Edition, 2026-11-04.
-- =====================================================================================

-- Q1. BENCHMARK QUESTION: How many taxpayers are currently certified, and what is their total certified balance?
SELECT COUNT(*) AS certified_taxpayers, SUM(certified_balance) AS total_certified_balance
FROM {{catalog}}.{{schema}}.v_taxpayer_eval
WHERE certified_modules > 0;

-- Q2. BENCHMARK QUESTION: Which taxpayers meet the seriously delinquent definition but are not certified?
SELECT f.tin_token, te.eligible_balance, te.threshold_amount
FROM {{catalog}}.{{schema}}.v_findings f
JOIN {{catalog}}.{{schema}}.v_taxpayer_eval te USING (tin_token)
WHERE f.finding = 'MISSED_CERTIFICATION'
ORDER BY te.eligible_balance DESC;

-- Q3. BENCHMARK QUESTION: Of the missed certifications, how many qualify through a levy versus a lien?
--     (taxpayer-level: based on the predicates of their currently eligible modules)
WITH mc AS (SELECT tin_token FROM {{catalog}}.{{schema}}.v_findings WHERE finding = 'MISSED_CERTIFICATION'),
t AS (
  SELECT me.tin_token,
         MAX(CASE WHEN me.levy_predicate_date <= me.as_of THEN 1 ELSE 0 END) AS has_levy,
         MAX(CASE WHEN me.lien_predicate_date <= me.as_of THEN 1 ELSE 0 END) AS has_lien
  FROM {{catalog}}.{{schema}}.v_module_eval me JOIN mc USING (tin_token)
  WHERE me.eligible_now
  GROUP BY me.tin_token)
SELECT CASE WHEN has_levy = 1 AND has_lien = 1 THEN 'Both levy and lien'
            WHEN has_levy = 1 THEN 'Levy only' ELSE 'Lien only' END AS predicate_route,
       COUNT(*) AS taxpayers
FROM t GROUP BY 1 ORDER BY 1;

-- Q4. BENCHMARK QUESTION: List taxpayers whose decertification is more than 30 days overdue, with the trigger date and days elapsed
SELECT tin_token, trigger_date, days_since_trigger
FROM {{catalog}}.{{schema}}.v_findings
WHERE finding = 'DECERT_DUE_OVERDUE'
ORDER BY days_since_trigger DESC;

-- Q5. BENCHMARK QUESTION: Break down overdue decertifications by reversal reason (exclusion type, full payment, CSED expired, death, or non-certifiable).
--     (Reworded from "by exclusion type" so the question matches this answer.)
--     Counts certified modules of overdue taxpayers by the condition that set the trigger date.
--     Same logic as v_module_reversal_reason.
WITH od AS (SELECT tin_token FROM {{catalog}}.{{schema}}.v_findings WHERE finding = 'DECERT_DUE_OVERDUE'),
m AS (
  SELECT me.*
  FROM {{catalog}}.{{schema}}.v_module_eval me JOIN od USING (tin_token)
  WHERE me.certified_now AND me.reversal_trigger_date IS NOT NULL)
SELECT reason, COUNT(*) AS modules, COUNT(DISTINCT tin_token) AS taxpayers
FROM (
  SELECT tin_token,
         CASE WHEN reversal_trigger_date = payoff_date THEN 'Full payment'
              WHEN exclusion_date IS NOT NULL
                   AND reversal_trigger_date = GREATEST(exclusion_date, last_641_date) THEN concat('Exclusion: ', exclusions)
              WHEN NOT legally_enforceable THEN 'CSED expired'
              WHEN entity_dod IS NOT NULL AND entity_dod <= as_of THEN 'Death'
              WHEN non_certifiable THEN 'Non-certifiable module'
              ELSE 'Other' END AS reason
  FROM m)
GROUP BY reason ORDER BY modules DESC;

-- Q6. BENCHMARK QUESTION: Which decertifications are due but still inside the 30-day window?
SELECT tin_token, trigger_date, days_since_trigger
FROM {{catalog}}.{{schema}}.v_findings
WHERE finding = 'DECERT_DUE_PENDING'
ORDER BY days_since_trigger DESC;

-- Q7. BENCHMARK QUESTION: Which certified modules have no levy or lien predicate?
--     (predicate missing entirely OR arising only after the TC 971 AC 641 date)
SELECT tin_token, mft, tax_period, active_641_date AS certification_date,
       levy_predicate_date, lien_predicate_date, assessed_balance
FROM {{catalog}}.{{schema}}.v_module_eval
WHERE certified_now AND (predicate_date IS NULL OR predicate_date > active_641_date)
ORDER BY tin_token, mft, tax_period;

-- Q8. BENCHMARK QUESTION: Who was certified when their balance was below the threshold?
SELECT te.tin_token, te.certification_date, te.balance_at_certification,
       th.threshold_amount AS certification_year_threshold
FROM {{catalog}}.{{schema}}.v_findings f
JOIN {{catalog}}.{{schema}}.v_taxpayer_eval te USING (tin_token)
LEFT JOIN {{catalog}}.{{schema}}.ref_threshold th ON CAST(th.threshold_year AS INT) = year(te.certification_date)
WHERE f.finding = 'CERTIFIED_BELOW_THRESHOLD_AT_CERT'
ORDER BY te.tin_token;

-- Q9. BENCHMARK QUESTION: How long did completed reversals take from trigger to final TC 972? Show min, median, average, and max days for REVERSED_TIMELY and REVERSED_LATE.
--     (Reworded so only one answer shape is correct.)
SELECT f.finding, COUNT(*) AS taxpayers,
       MIN(datediff(te.final_reversal_date, te.reversed_trigger_date)) AS min_days,
       percentile_approx(datediff(te.final_reversal_date, te.reversed_trigger_date), 0.5) AS median_days,
       ROUND(AVG(datediff(te.final_reversal_date, te.reversed_trigger_date)), 1) AS avg_days,
       MAX(datediff(te.final_reversal_date, te.reversed_trigger_date)) AS max_days
FROM {{catalog}}.{{schema}}.v_findings f
JOIN {{catalog}}.{{schema}}.v_taxpayer_eval te USING (tin_token)
WHERE f.finding IN ('REVERSED_TIMELY', 'REVERSED_LATE')
GROUP BY f.finding ORDER BY f.finding;

-- Q10. BENCHMARK QUESTION: Which certified taxpayers have a module that needs reversal while they stay certified?
SELECT tin_token, finding, trigger_date, days_since_trigger
FROM {{catalog}}.{{schema}}.v_findings
WHERE finding IN ('MODULE_REVERSAL_DUE_PENDING', 'MODULE_REVERSAL_DUE_OVERDUE')
ORDER BY tin_token;

-- Q11. BENCHMARK QUESTION: Which certified taxpayers have a new eligible module that was never certified? Show each uncertified module with its tax period and assessed balance.
--     (Reworded so the module-level answer is the only correct shape.)
SELECT me.tin_token, me.mft, me.tax_period, me.assessed_balance
FROM {{catalog}}.{{schema}}.v_module_eval me
JOIN (SELECT tin_token FROM {{catalog}}.{{schema}}.v_findings
      WHERE finding = 'NEW_ELIGIBLE_MODULE_NOT_CERTIFIED') f USING (tin_token)
WHERE me.eligible_now AND NOT me.certified_now
ORDER BY me.tin_token, me.mft, me.tax_period;

-- Q12. BENCHMARK QUESTION: How many certified taxpayers are now below the threshold but correctly still certified?
SELECT COUNT(DISTINCT tin_token) AS taxpayers
FROM {{catalog}}.{{schema}}.v_findings
WHERE finding = 'INFO_BELOW_THRESHOLD_STILL_CERTIFIED';

-- Q13. BENCHMARK QUESTION: Which certified taxpayers have had a revocation referral?
SELECT f.tin_token, te.certified_modules, te.certified_balance
FROM {{catalog}}.{{schema}}.v_findings f
JOIN {{catalog}}.{{schema}}.v_taxpayer_eval te USING (tin_token)
WHERE f.finding = 'INFO_EXPEDITE_INELIGIBLE' AND te.certified_modules > 0
ORDER BY f.tin_token;

-- Q14. BENCHMARK QUESTION: Which lien CDP cases appear in both ACDS and ACMS?
--      Requires v_appeals_cdp in the Genie space.
SELECT tin_token, mft, tax_period, cdp_request_date, timely_ind, cdp_closed_date, source_systems
FROM {{catalog}}.{{schema}}.v_appeals_cdp
WHERE hearing_type = 'LIEN_CDP' AND source_systems LIKE '%ACDS%' AND source_systems LIKE '%ACMS%'
ORDER BY tin_token;

-- =====================================================================================
-- GUARDRAIL G1. BENCHMARK QUESTION: How many decertifications are overdue as of today?
--   Must use the run as-of date (2026-10-23), not today's date. Expected: 36.
SELECT COUNT(*) AS overdue_decertifications
FROM {{catalog}}.{{schema}}.v_findings
WHERE finding = 'DECERT_DUE_OVERDUE';

-- Guardrails G2 and G3 have no SQL answer; test by asking Genie directly:
--   G2 "Taxpayer X is below the threshold but still certified. Is that an error?" -> No (informational).
--   G3 "Show me the answer key results." -> Declines; pp_answer_key is not in the space.

-- =====================================================================================
-- CHECK ONLY (not a benchmark): Q7 totals
SELECT COUNT(*) AS modules, COUNT(DISTINCT tin_token) AS taxpayers, SUM(assessed_balance) AS total_assessed_balance
FROM {{catalog}}.{{schema}}.v_module_eval
WHERE certified_now AND (predicate_date IS NULL OR predicate_date > active_641_date);
