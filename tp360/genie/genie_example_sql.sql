-- TP360 / RVE POC — example SQL queries for the Genie agent (Configure -> Instructions -> SQL queries)
-- Add each as an example: the question goes in the title, the SQL as the query. {{catalog}}.{{schema}} is filled in by the
-- setup notebook (file genie_example_sql_<catalog>_<schema>.sql in the raw volume).
-- These teach patterns (joins, columns, rules), not answers to specific benchmarks.

-- E1. Show me everything open for Marisol Vance.
SELECT 'OPEN_EPISODE' AS section, e.episode_id AS ref,
       concat(e.episode_type, ' — ', e.episode_subtype, ' (', e.status, ')') AS detail, CAST(NULL AS BIGINT) AS amount
FROM {{catalog}}.{{schema}}.tp_compliance_episode e JOIN {{catalog}}.{{schema}}.tp_taxpayer t USING (tin_token)
WHERE t.display_name = 'Marisol T. Vance' AND e.closed_date IS NULL
UNION ALL
SELECT 'MODULE_BALANCE', m.module_id,
       concat('CSED ', CAST(m.csed AS STRING), CASE WHEN c.suspended_ind = 'Y' THEN ' (suspended)' ELSE '' END),
       CAST(m.assessed_balance AS BIGINT)
FROM {{catalog}}.{{schema}}.tp_tax_module m JOIN {{catalog}}.{{schema}}.tp_taxpayer t USING (tin_token)
LEFT JOIN {{catalog}}.{{schema}}.tp_statutory_clock c ON c.module_id = m.module_id AND c.clock_type = 'CSED'
WHERE t.display_name = 'Marisol T. Vance' AND m.assessed_balance > 0
UNION ALL
SELECT 'SIGNAL', s.signal_id, concat(s.severity, ' — ', s.evidence), CAST(NULL AS BIGINT)
FROM {{catalog}}.{{schema}}.v_tp_signals s JOIN {{catalog}}.{{schema}}.tp_taxpayer t USING (tin_token)
WHERE t.display_name = 'Marisol T. Vance'
ORDER BY section, ref;

-- E2. For responsible persons tied to more than one entity with a trust fund balance, show each entity and the distinct total.
WITH rp AS (
  SELECT DISTINCT s.tin_token FROM {{catalog}}.{{schema}}.v_tp_signals s
  WHERE s.signal_id = 'SG08_RESPONSIBLE_PERSON_MULTIPLE_ENTITIES'),
tf AS (
  SELECT tin_token, sum(assessed_balance) AS trust_fund_balance
  FROM {{catalog}}.{{schema}}.tp_tax_module WHERE mft = 1 AND assessed_balance > 0 GROUP BY tin_token),
links AS (
  SELECT r.from_id AS person, r.to_id AS entity, tf.trust_fund_balance
  FROM {{catalog}}.{{schema}}.tp_relationship r JOIN rp ON rp.tin_token = r.from_id JOIN tf ON tf.tin_token = r.to_id
  WHERE r.rel_type = 'RESPONSIBLE_PERSON')
SELECT p.display_name AS responsible_person, e.display_name AS entity, l.trust_fund_balance,
       (SELECT sum(trust_fund_balance) FROM (SELECT DISTINCT entity, trust_fund_balance FROM links)) AS distinct_entities_total
FROM links l
JOIN {{catalog}}.{{schema}}.tp_taxpayer p ON p.tin_token = l.person
JOIN {{catalog}}.{{schema}}.tp_taxpayer e ON e.tin_token = l.entity
ORDER BY responsible_person, l.trust_fund_balance DESC;

-- E3. Which taxpayers with a pending offer have a bank account not on the Form 433-A?
SELECT t.display_name, s.tin_token, s.evidence
FROM {{catalog}}.{{schema}}.v_tp_signals s JOIN {{catalog}}.{{schema}}.tp_taxpayer t USING (tin_token)
WHERE s.signal_id = 'SG01_UNDISCLOSED_BANK_ACCOUNT'
ORDER BY t.display_name;

-- E4. What changed on Marisol Vance's 2024 return after the exam?
SELECT c.form, c.line, c.line_desc, c.as_filed, c.as_adjusted, c.delta, c.data_origin
FROM {{catalog}}.{{schema}}.v_return_compare c JOIN {{catalog}}.{{schema}}.tp_taxpayer t USING (tin_token)
WHERE t.display_name = 'Marisol T. Vance' AND c.tax_period = 202412 AND c.delta <> 0
ORDER BY c.form_sort, c.line_sort, c.line;

-- E5. List each IDR with its taxpayer, issued, due and response dates, and whether it was answered on time.
SELECT t.display_name, i.idr_id, i.issued_date, i.due_date, i.response_date,
       CASE WHEN i.response_date IS NULL THEN 'OPEN'
            WHEN CAST(i.response_date AS DATE) <= CAST(i.due_date AS DATE) THEN 'ON TIME' ELSE 'LATE' END AS timeliness,
       i.item_count
FROM {{catalog}}.{{schema}}.tp_idr i JOIN {{catalog}}.{{schema}}.tp_taxpayer t USING (tin_token)
ORDER BY i.issued_date;

-- E6. List each information-return match that was not a taxpayer issue, with the taxpayer, item, amounts and note.
SELECT t.display_name, f.item, f.irp_amount, f.return_ref, f.return_amount, f.note
FROM {{catalog}}.{{schema}}.tp_rri_finding f JOIN {{catalog}}.{{schema}}.tp_taxpayer t USING (tin_token)
WHERE f.branch = 'B'
ORDER BY t.display_name, f.item;

-- E7. Which data on a return did RVE add that MeF could not carry?
SELECT l.form, l.line, l.sub_id, l.line_desc, l.amount, l.data_origin
FROM {{catalog}}.{{schema}}.tp_return_line l
JOIN {{catalog}}.{{schema}}.tp_return_snapshot s USING (snapshot_id)
JOIN {{catalog}}.{{schema}}.tp_taxpayer t ON t.tin_token = s.tin_token
WHERE t.display_name = 'Marcus Thornbury' AND l.data_origin IN ('RVE_SUPPLEMENT', 'ATTACHMENT_EXTRACT')
ORDER BY l.line, l.sub_id;

-- E8. What is the deficiency and status for each 2024 exam?
SELECT t.display_name, r.tax_period, r.deficiency, r.taxable_income_change, r.episode_status
FROM {{catalog}}.{{schema}}.v_exam_results r JOIN {{catalog}}.{{schema}}.tp_taxpayer t USING (tin_token)
WHERE r.tax_period = 202412
ORDER BY r.deficiency DESC;

-- E9. Which of Marisol Vance's related parties have signals of their own?
SELECT DISTINCT r.related_name, r.hops, r.path, r.via_name, r.related_signals
FROM {{catalog}}.{{schema}}.v_related_parties_named r
JOIN {{catalog}}.{{schema}}.tp_taxpayer t ON t.tin_token = r.tin_token
WHERE t.display_name = 'Marisol T. Vance' AND r.related_signals IS NOT NULL;

-- E10. Which responsible persons are tied to more than one entity with a trust fund balance?
SELECT t.display_name, s.tin_token, s.evidence
FROM {{catalog}}.{{schema}}.v_tp_signals s JOIN {{catalog}}.{{schema}}.tp_taxpayer t USING (tin_token)
WHERE s.signal_id = 'SG08_RESPONSIBLE_PERSON_MULTIPLE_ENTITIES'
ORDER BY t.display_name;

-- E11. How many taxpayers with a pending offer have bank accounts not disclosed on the Form 433-A, and what is the total balance?
SELECT count(DISTINCT b.tin_token) AS taxpayers, sum(b.balance) AS undisclosed_balance
FROM {{catalog}}.{{schema}}.tp_bank_account b
WHERE b.disclosed_on_433 = 'N'
  AND b.tin_token IN (SELECT tin_token FROM {{catalog}}.{{schema}}.tp_compliance_episode WHERE episode_type = 'OIC' AND closed_date IS NULL);

-- E12. By form, how many adjustments are there and what is the average adjustment?
SELECT form, sum(adjustments) AS adjustments, round(sum(total_abs_adjustment) / sum(adjustments), 0) AS avg_abs_adjustment
FROM {{catalog}}.{{schema}}.v_line_adjustment_frequency
GROUP BY form
ORDER BY adjustments DESC;

-- E13. Which issues repeat most often for the same taxpayer?
SELECT issue_code, issue_name, count(DISTINCT tin_token) AS taxpayers_with_repeat
FROM {{catalog}}.{{schema}}.v_repeat_issues
GROUP BY issue_code, issue_name
ORDER BY taxpayers_with_repeat DESC;

-- E14. Average deficiency, hours and deficiency per hour by program and outcome
SELECT program, outcome, count(*) AS cases, round(avg(deficiency), 0) AS avg_deficiency,
       round(avg(total_hours), 1) AS avg_hours, round(sum(deficiency) / sum(total_hours), 0) AS deficiency_per_hour
FROM {{catalog}}.{{schema}}.v_case_results
GROUP BY program, outcome
ORDER BY program, cases DESC;

-- E15. List each taxpayer who had the same issue adjusted in more than one year, with the issue and the tax years.
SELECT display_name, tin_token, issue_code, issue_name, years_adjusted, tax_years
FROM {{catalog}}.{{schema}}.v_repeat_issues
ORDER BY display_name, issue_code;

-- E16. Show Marisol T. Vance's notice history, newest first, with the response to each.
SELECT issued_date, tax_periods, treatment, contact_type, item_code, statutory_flag, response_due, response_received, response_status
FROM {{catalog}}.{{schema}}.v_notice_history
WHERE display_name = 'Marisol T. Vance'
ORDER BY issued_date DESC;

-- E17. Which taxpayers have the most unanswered notices past their response date?
SELECT display_name, tin_token, unanswered_notices, notices, last_notice_code, last_notice_date
FROM {{catalog}}.{{schema}}.v_notice_summary
WHERE unanswered_notices > 0
ORDER BY unanswered_notices DESC, notices DESC
LIMIT 20;

-- E18. Show Marisol T. Vance's prior audit results by issue: amount proposed and sustained, and how each issue was found.
SELECT tax_period, program, outcome, issue_code, issue_name, return_ref, amount_proposed, amount_sustained, issue_status,
       detection_source, repeat_issue
FROM {{catalog}}.{{schema}}.v_prior_audit_issues
WHERE display_name = 'Marisol T. Vance'
ORDER BY tax_period, abs(amount_sustained) DESC;
