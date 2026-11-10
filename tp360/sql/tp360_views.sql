-- TP360 / RVE POC — gold views and signal rules (Databricks SQL)
-- Synthetic data only. Table and column names are POC names, not CDW names.
-- The setup notebook runs this file statement by statement after loading tp360/data/*.csv.
-- The same rules are implemented independently in Python (tools/build_tp360_data.py) to produce
-- tp_signal_answer_key; the notebook fails if the two disagree.

-- --------------------------------------------------------------------------------------------
-- Run parameter
-- --------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_as_of AS
SELECT CAST(value AS DATE) AS as_of_date FROM tp_run_params WHERE param = 'as_of_date';

-- --------------------------------------------------------------------------------------------
-- Signals: one row per taxpayer per rule that fires, with the evidence behind it
-- --------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_open_oic AS
SELECT tin_token, CAST(opened_date AS DATE) AS oic_opened, episode_id
FROM tp_compliance_episode
WHERE episode_type = 'OIC' AND closed_date IS NULL;

CREATE OR REPLACE VIEW v_adjusted_issue_years AS
SELECT DISTINCT tin_token, issue_code, CAST(substr(CAST(tax_period AS STRING), 1, 4) AS INT) AS yr
FROM tp_issue
WHERE status = 'ADJUSTED' AND issue_code IS NOT NULL;

CREATE OR REPLACE VIEW v_tp_signal_evidence AS
SELECT b.tin_token, 'SG01_UNDISCLOSED_BANK_ACCOUNT' AS signal_id, 'HIGH' AS severity,
       concat(b.institution, ' ', b.account_type, ' ending ', CAST(b.acct_last4 AS STRING), ' — balance ', CAST(b.balance AS STRING), ' — source ', b.source) AS evidence,
       'Form 433-A (OIC) completeness; reasonable collection potential' AS basis
FROM tp_bank_account b JOIN v_open_oic o ON o.tin_token = b.tin_token
WHERE b.disclosed_on_433 = 'N'

UNION ALL
SELECT t.from_tin_token, 'SG02_RELATED_PARTY_TRANSFER_BEFORE_OFFER', 'HIGH',
       concat('Asset ', t.asset_id, ' to ', t.to_tin_token, ' on ', CAST(t.transfer_date AS STRING), ', ',
              CAST(datediff(o.oic_opened, CAST(t.transfer_date AS DATE)) AS STRING), ' days before the offer; consideration ',
              CAST(t.consideration AS STRING), ' of FMV ', CAST(t.fmv_at_transfer AS STRING)),
       'Dissipated asset; possible transferee or nominee question'
FROM tp_transfer t
JOIN v_open_oic o ON o.tin_token = t.from_tin_token
WHERE datediff(o.oic_opened, CAST(t.transfer_date AS DATE)) BETWEEN 0 AND 730
  AND t.consideration < 0.10 * t.fmv_at_transfer
  AND EXISTS (SELECT 1 FROM tp_relationship r
              WHERE (r.from_id = t.from_tin_token AND r.to_id = t.to_tin_token)
                 OR (r.from_id = t.to_tin_token AND r.to_id = t.from_tin_token))

UNION ALL
SELECT p.tin_token, 'SG03_PASSPORT_REVERSAL_TRIGGER_ARMED', 'HIGH',
       concat('Certified (', p.episode_id, ') with offer ', o.episode_id, ' pending'),
       'IRC 7345(c): acceptance would require reversal'
FROM tp_compliance_episode p JOIN v_open_oic o ON o.tin_token = p.tin_token
WHERE p.episode_type = 'PASSPORT' AND p.status = 'CERTIFIED' AND p.closed_date IS NULL

UNION ALL
SELECT tin_token, 'SG04_LEVY_BARRED_OIC_PENDING', 'MEDIUM',
       concat('Overlay ', overlay_id, ' since ', CAST(start_date AS STRING)), authority
FROM tp_procedural_overlay
WHERE overlay_type = 'OIC_PENDING' AND end_date IS NULL

UNION ALL
SELECT e.tin_token, 'SG05_REPEAT_IA_DEFAULT', 'MEDIUM',
       concat(CAST(count(*) AS STRING), ' installment agreements defaulted in the last 24 months'),
       'Agreement history; offer and agreement terms'
FROM tp_compliance_episode e CROSS JOIN v_as_of a
WHERE e.episode_type = 'IA' AND e.status = 'DEFAULTED' AND e.closed_date IS NOT NULL
  AND datediff(a.as_of_date, CAST(e.closed_date AS DATE)) <= 730
GROUP BY e.tin_token
HAVING count(*) >= 2

UNION ALL
SELECT DISTINCT f.tin_token, 'SG06_IRP_INCOME_UNREPORTED', 'HIGH',
       concat(f.item, ' — ', CAST(f.irp_amount AS STRING), ' not on ', f.return_ref), 'IRC 61; IRP match (RRI branch A)'
FROM tp_rri_finding f
WHERE f.disposition = 'UNREPORTED_INCOME' AND f.tax_period >= 202412   -- current filing year only; closed cases are history

UNION ALL
SELECT DISTINCT s.tin_token, 'SG07_REP_CLAIM_NO_AGGREGATION_ELECTION', 'MEDIUM',
       concat('Schedule E line 43 ', CAST(l.amount AS STRING), ' with no aggregation election captured'),
       'IRC 469(c)(7); Treas. Reg. 1.469-9(g) — each rental tested separately'
FROM tp_return_line l JOIN tp_return_snapshot s ON s.snapshot_id = l.snapshot_id
WHERE s.version_type = 'AS_FILED' AND l.form = 'SCH_E' AND l.line = '43' AND l.amount <> 0
  AND NOT EXISTS (SELECT 1 FROM tp_return_line l2 JOIN tp_return_snapshot s2 ON s2.snapshot_id = l2.snapshot_id
                  WHERE s2.tin_token = s.tin_token AND l2.line = 'ELECTION_469_9G' AND l2.amount = 1)

UNION ALL
SELECT r.from_id, 'SG08_RESPONSIBLE_PERSON_MULTIPLE_ENTITIES', 'HIGH',
       concat('Responsible person for ', CAST(count(DISTINCT r.to_id) AS STRING), ' entities with trust fund balances'),
       'IRC 6672 exposure across entities'
FROM tp_relationship r
WHERE r.rel_type = 'RESPONSIBLE_PERSON'
  AND r.to_id IN (SELECT tin_token FROM tp_tax_module WHERE mft = 1 AND assessed_balance > 0)
GROUP BY r.from_id
HAVING count(DISTINCT r.to_id) >= 2

UNION ALL
SELECT DISTINCT i.tin_token, 'SG09_ENTITY_INTEREST_NOT_ON_433', 'MEDIUM',
       concat('K-1 from ', i.payer_name, ' (', i.payer_tin_token, ') — interest not listed on Form 433-A'),
       'Form 433-A (OIC) completeness'
FROM tp_information_return i
JOIN v_open_oic o ON o.tin_token = i.tin_token
JOIN tp_relationship r ON r.rel_type = 'MEMBER' AND r.from_id = i.tin_token AND r.to_id = i.payer_tin_token
WHERE i.form_type LIKE 'K-1%'
  AND NOT EXISTS (SELECT 1 FROM tp_asset a
                  WHERE a.owner_tin_token = i.tin_token AND a.asset_type = 'ENTITY_INTEREST'
                    AND a.description = concat('Interest in ', i.payer_tin_token))

UNION ALL
SELECT a.tin_token, 'SG10_REPEAT_ISSUE', 'MEDIUM',
       concat(a.issue_code, ' adjusted in ', CAST(a.yr AS STRING), ' and ', CAST(b.yr AS STRING)),
       'Prior audit history — same issue adjusted within five years'
FROM v_adjusted_issue_years a
JOIN v_adjusted_issue_years b ON b.tin_token = a.tin_token AND b.issue_code = a.issue_code AND b.yr > a.yr AND b.yr - a.yr <= 5;

-- One row per taxpayer per signal (evidence combined). Use this for counts and joins; v_tp_signal_evidence keeps
-- one row per piece of evidence (e.g. each undisclosed account).
CREATE OR REPLACE VIEW v_tp_signals AS
SELECT tin_token, signal_id, max(severity) AS severity,
       concat_ws(' | ', collect_set(evidence)) AS evidence, max(basis) AS basis, count(*) AS evidence_count
FROM v_tp_signal_evidence
GROUP BY tin_token, signal_id;

-- --------------------------------------------------------------------------------------------
-- TP360 header: one row per taxpayer
-- --------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_tp360_header AS
WITH m AS (
  SELECT tin_token, sum(assessed_balance) AS total_balance,
         count_if(assessed_balance > 0) AS modules_with_balance,
         min(CAST(csed AS DATE)) AS nearest_csed
  FROM tp_tax_module GROUP BY tin_token),
e AS (
  SELECT tin_token,
         concat_ws('; ', collect_list(concat(episode_type, ' (', status, ')'))) AS open_episodes,
         max(CASE WHEN episode_type = 'PASSPORT' THEN status END) AS passport_status,
         max(CASE WHEN episode_type = 'OIC' THEN status END) AS oic_status
  FROM tp_compliance_episode WHERE closed_date IS NULL GROUP BY tin_token),
s AS (SELECT tin_token, count(*) AS signal_count, concat_ws('; ', collect_list(signal_id)) AS signals
      FROM v_tp_signals GROUP BY tin_token)
SELECT t.tin_token, t.display_name, t.entity_type, t.filing_status, t.city, t.state, t.poa_on_file, t.case_group,
       coalesce(m.total_balance, 0) AS total_balance, coalesce(m.modules_with_balance, 0) AS modules_with_balance,
       m.nearest_csed, e.open_episodes, e.passport_status, e.oic_status,
       coalesce(s.signal_count, 0) AS signal_count, s.signals
FROM tp_taxpayer t
LEFT JOIN m ON m.tin_token = t.tin_token
LEFT JOIN e ON e.tin_token = t.tin_token
LEFT JOIN s ON s.tin_token = t.tin_token;

-- --------------------------------------------------------------------------------------------
-- RVE: three-column view, as filed vs the latest snapshot (proposed or as examined)
-- --------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_latest_snapshot AS
SELECT tin_token, tax_period, snapshot_id, version_type FROM (
  SELECT s.*, row_number() OVER (PARTITION BY tin_token, tax_period
         ORDER BY CASE version_type WHEN 'AS_EXAMINED' THEN 1 WHEN 'PROPOSED' THEN 2 WHEN 'RVE_WORKING' THEN 3 ELSE 4 END) AS rn
  FROM tp_return_snapshot s) x
WHERE rn = 1;

CREATE OR REPLACE VIEW v_return_compare AS
WITH f AS (
  -- "as filed" = the MeF lines plus anything RVE extracted from attachments the taxpayer filed
  SELECT s.tin_token, s.tax_period, l.form, l.line, coalesce(l.sub_id, '') AS sub_id, l.line_desc, l.amount
  FROM tp_return_line l JOIN tp_return_snapshot s ON s.snapshot_id = l.snapshot_id
  WHERE s.version_type = 'AS_FILED'
     OR (s.version_type = 'RVE_WORKING' AND l.data_origin = 'ATTACHMENT_EXTRACT')),
c AS (
  SELECT v.tin_token, v.tax_period, v.version_type, l.form, l.line, coalesce(l.sub_id, '') AS sub_id, l.line_desc,
         l.amount, l.data_origin
  FROM tp_return_line l JOIN v_latest_snapshot v ON v.snapshot_id = l.snapshot_id)
SELECT coalesce(c.tin_token, f.tin_token) AS tin_token, coalesce(c.tax_period, f.tax_period) AS tax_period,
       coalesce(c.form, f.form) AS form, coalesce(c.line, f.line) AS line, coalesce(c.sub_id, f.sub_id) AS sub_id,
       coalesce(f.line_desc, c.line_desc) AS line_desc, c.version_type AS compared_to,
       coalesce(f.amount, 0) AS as_filed, coalesce(c.amount, f.amount) AS as_adjusted,
       coalesce(c.amount, f.amount) - coalesce(f.amount, 0) AS delta, c.data_origin
FROM f FULL OUTER JOIN c
  ON c.tin_token = f.tin_token AND c.tax_period = f.tax_period AND c.form = f.form AND c.line = f.line AND c.sub_id = f.sub_id;

-- RVE data origin: what came from MeF vs what RVE added
CREATE OR REPLACE VIEW v_rve_data_origin AS
SELECT s.tin_token, s.tax_period, s.snapshot_id, s.version_type, l.data_origin, count(*) AS line_count
FROM tp_return_line l JOIN tp_return_snapshot s ON s.snapshot_id = l.snapshot_id
GROUP BY s.tin_token, s.tax_period, s.snapshot_id, s.version_type, l.data_origin;

-- --------------------------------------------------------------------------------------------
-- Related parties: one and two hops, undirected (SQL fallback when GraphFrames isn't available)
-- --------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_edges_undirected AS
SELECT from_id AS a, to_id AS b, rel_type FROM tp_relationship
UNION ALL
SELECT to_id AS a, from_id AS b, rel_type FROM tp_relationship;

CREATE OR REPLACE VIEW v_related_parties AS
SELECT e1.a AS tin_token, e1.b AS related_id, 1 AS hops, e1.rel_type AS path, e1.b AS via
FROM v_edges_undirected e1
UNION ALL
SELECT e1.a, e2.b, 2, concat(e1.rel_type, ' > ', e2.rel_type), e1.b
FROM v_edges_undirected e1 JOIN v_edges_undirected e2 ON e2.a = e1.b
WHERE e2.b <> e1.a;

CREATE OR REPLACE VIEW v_related_parties_named AS
SELECT r.tin_token, t1.display_name AS name, r.hops, r.path, r.via,
       coalesce(tv.display_name, av.description, r.via) AS via_name,
       r.related_id, coalesce(t2.display_name, a2.description, r.related_id) AS related_name,
       h.total_balance AS related_balance, h.signals AS related_signals
FROM v_related_parties r
LEFT JOIN tp_taxpayer t1 ON t1.tin_token = r.tin_token
LEFT JOIN tp_taxpayer tv ON tv.tin_token = r.via
LEFT JOIN tp_asset av ON av.asset_id = r.via
LEFT JOIN tp_taxpayer t2 ON t2.tin_token = r.related_id
LEFT JOIN tp_asset a2 ON a2.asset_id = r.related_id
LEFT JOIN v_tp360_header h ON h.tin_token = r.related_id;

-- --------------------------------------------------------------------------------------------
-- One timeline per taxpayer across episodes, contacts, snapshots and determinations
-- --------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_tp_timeline AS
SELECT tin_token, CAST(opened_date AS DATE) AS event_date, 'EPISODE_OPENED' AS event_type,
       concat(episode_type, ' — ', episode_subtype) AS detail, episode_id AS ref
FROM tp_compliance_episode
UNION ALL
SELECT tin_token, CAST(closed_date AS DATE), 'EPISODE_CLOSED', concat(episode_type, ' — ', status), episode_id
FROM tp_compliance_episode WHERE closed_date IS NOT NULL
UNION ALL
SELECT tin_token, CAST(issued_date AS DATE), concat('CONTACT_', contact_type), item_code, contact_id FROM tp_contact_event
UNION ALL
SELECT tin_token, CAST(created_date AS DATE), 'RVE_SNAPSHOT', concat(version_type, ' — ', tax_period), snapshot_id FROM tp_return_snapshot
UNION ALL
SELECT tin_token, CAST(decided_date AS DATE), 'DETERMINATION', concat(determination_type, ' — ', outcome), determination_id FROM tp_determination;

-- --------------------------------------------------------------------------------------------
-- Exam results summary per episode (feeds the closing view and Genie)
-- --------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_exam_results AS
SELECT a.episode_id, a.tin_token, a.tax_period,
       sum(CASE WHEN a.form = '1040' AND a.line = '24' THEN a.adjustment ELSE 0 END) AS deficiency,
       sum(CASE WHEN a.form = '1040' AND a.line = '15' THEN a.adjustment ELSE 0 END) AS taxable_income_change,
       count_if(a.adjustment_kind = 'EXAMINER') AS examiner_adjustments,
       max(e.status) AS episode_status
FROM tp_adjustment a JOIN tp_compliance_episode e ON e.episode_id = a.episode_id
GROUP BY a.episode_id, a.tin_token, a.tax_period;

-- ============================================================================================
-- v0.2  Closed-case results: AIMS-equivalent case fields plus issue-level detail
-- ============================================================================================

-- One row per closed case: closure (AIMS-equivalent) + tax computation results
CREATE OR REPLACE VIEW v_case_results AS
SELECT c.episode_id, c.tin_token, t.display_name, c.tax_period, c.program, c.selection_source, c.outcome, c.appeals_outcome,
       c.closed_date, c.closing_tc, c.deficiency, c.penalty_code, c.penalty_amount, c.agreed_ind, c.total_hours,
       c.issue_count, c.adjusted_issue_count,
       x.filing_status_filed, x.filing_status_examined, x.agi_filed, x.agi_examined, x.taxable_income_filed, x.taxable_income_examined,
       x.total_tax_filed, x.total_tax_examined,
       CASE WHEN c.total_hours > 0 THEN round(c.deficiency / c.total_hours, 0) END AS deficiency_per_hour
FROM tp_case_closure c
LEFT JOIN tp_tax_computation x ON x.episode_id = c.episode_id
LEFT JOIN tp_taxpayer t ON t.tin_token = c.tin_token;

-- Which return lines examiners adjust most often (source lines only; 1040 lines are computed)
CREATE OR REPLACE VIEW v_line_adjustment_frequency AS
SELECT a.form, a.line, coalesce(lc.line_desc, max(a.line_desc)) AS line_desc, lc.line_class,
       count(*) AS adjustments, count(DISTINCT a.episode_id) AS cases,
       sum(a.adjustment) AS net_adjustment, sum(abs(a.adjustment)) AS total_abs_adjustment,
       round(avg(abs(a.adjustment)), 0) AS avg_abs_adjustment
FROM tp_adjustment a
LEFT JOIN tp_line_catalog lc ON lc.form = a.form AND lc.line = a.line
WHERE a.adjustment_kind = 'EXAMINER'
GROUP BY a.form, a.line, lc.line_desc, lc.line_class;

-- Issue outcomes: how often each issue is raised, sustained, conceded, no-changed
CREATE OR REPLACE VIEW v_issue_outcomes AS
SELECT i.issue_code, ic.issue_name, ic.category, ic.irc_reference,
       count(*) AS times_raised,
       count_if(i.status = 'ADJUSTED') AS adjusted,
       count_if(i.status = 'CONCEDED') AS conceded,
       count_if(i.status = 'NO_CHANGE') AS no_change,
       round(100.0 * count_if(i.status = 'NO_CHANGE') / count(*), 1) AS no_change_pct,
       round(avg(CASE WHEN i.status = 'ADJUSTED' THEN abs(i.amount_sustained) END), 0) AS avg_abs_sustained,
       round(avg(CASE WHEN i.amount_proposed <> 0 AND i.status IN ('ADJUSTED', 'CONCEDED')
                      THEN 100.0 * coalesce(i.amount_sustained, 0) / i.amount_proposed END), 1) AS avg_pct_sustained_of_proposed,
       round(avg(i.hours_charged), 1) AS avg_hours,
       round(sum(abs(coalesce(i.amount_sustained, 0))) / nullif(sum(i.hours_charged), 0), 0) AS sustained_per_hour
FROM tp_issue i
LEFT JOIN tp_issue_code ic ON ic.issue_code = i.issue_code
JOIN tp_case_closure c ON c.episode_id = i.episode_id
GROUP BY i.issue_code, ic.issue_name, ic.category, ic.irc_reference;

-- How adjustments were found
CREATE OR REPLACE VIEW v_detection_mix AS
SELECT i.detection_source, count(*) AS issues, count_if(i.status = 'ADJUSTED') AS adjusted,
       round(100.0 * count_if(i.status = 'ADJUSTED') / count(*), 1) AS adjusted_pct,
       sum(abs(coalesce(i.amount_sustained, 0))) AS total_abs_sustained
FROM tp_issue i JOIN tp_case_closure c ON c.episode_id = i.episode_id
GROUP BY i.detection_source;

-- Most common variances and their root causes
CREATE OR REPLACE VIEW v_variance_root_causes AS
SELECT f.variance_type, f.root_cause, rc.description AS root_cause_description, f.branch, f.return_ref,
       count(*) AS findings, round(avg(abs(f.delta)), 0) AS avg_abs_delta
FROM tp_rri_finding f LEFT JOIN tp_root_cause rc ON rc.root_cause = f.root_cause
GROUP BY f.variance_type, f.root_cause, rc.description, f.branch, f.return_ref;

-- Prior audit history per taxpayer: every closed case with its issues
CREATE OR REPLACE VIEW v_prior_audit_history AS
SELECT c.tin_token, t.display_name, c.tax_period, c.program, c.selection_source, c.outcome, c.appeals_outcome, c.closed_date,
       c.deficiency, c.penalty_amount,
       concat_ws('; ', collect_list(concat(i.issue_code, ' (', lower(i.status), ')'))) AS issues
FROM tp_case_closure c
JOIN tp_taxpayer t ON t.tin_token = c.tin_token
LEFT JOIN tp_issue i ON i.episode_id = c.episode_id
GROUP BY c.tin_token, t.display_name, c.tax_period, c.program, c.selection_source, c.outcome, c.appeals_outcome, c.closed_date,
         c.deficiency, c.penalty_amount;

-- The translation: issue code -> source line -> rollup chain to Form 1040
CREATE OR REPLACE VIEW v_issue_to_1040_trace AS
SELECT m.issue_code, ic.issue_name, m.role, m.effect,
       concat(m.form, ' ', m.line) AS source_line, l0.line_desc AS source_desc,
       concat_ws(' > ',
         concat(m.form, ' ', m.line),
         CASE WHEN l0.rolls_to_form IS NOT NULL AND l0.rolls_to_form <> '' THEN concat(l0.rolls_to_form, ' ', l0.rolls_to_line) END,
         CASE WHEN l1.rolls_to_form IS NOT NULL AND l1.rolls_to_form <> '' THEN concat(l1.rolls_to_form, ' ', l1.rolls_to_line) END,
         CASE WHEN l2.rolls_to_form IS NOT NULL AND l2.rolls_to_form <> '' THEN concat(l2.rolls_to_form, ' ', l2.rolls_to_line) END,
         CASE WHEN l3.rolls_to_form IS NOT NULL AND l3.rolls_to_form <> '' THEN concat(l3.rolls_to_form, ' ', l3.rolls_to_line) END,
         CASE WHEN l4.rolls_to_form IS NOT NULL AND l4.rolls_to_form <> '' THEN concat(l4.rolls_to_form, ' ', l4.rolls_to_line) END,
         CASE WHEN l5.rolls_to_form IS NOT NULL AND l5.rolls_to_form <> '' THEN concat(l5.rolls_to_form, ' ', l5.rolls_to_line) END,
         CASE WHEN l6.rolls_to_form IS NOT NULL AND l6.rolls_to_form <> '' THEN concat(l6.rolls_to_form, ' ', l6.rolls_to_line) END,
         CASE WHEN l7.rolls_to_form IS NOT NULL AND l7.rolls_to_form <> '' THEN concat(l7.rolls_to_form, ' ', l7.rolls_to_line) END,
         CASE WHEN l8.rolls_to_form IS NOT NULL AND l8.rolls_to_form <> '' THEN concat(l8.rolls_to_form, ' ', l8.rolls_to_line) END,
         CASE WHEN l9.rolls_to_form IS NOT NULL AND l9.rolls_to_form <> '' THEN concat(l9.rolls_to_form, ' ', l9.rolls_to_line) END
       ) AS rollup_path
FROM tp_issue_line_map m
JOIN tp_issue_code ic ON ic.issue_code = m.issue_code
LEFT JOIN tp_line_catalog l0 ON l0.form = m.form AND l0.line = m.line
LEFT JOIN tp_line_catalog l1 ON l1.form = l0.rolls_to_form AND l1.line = l0.rolls_to_line
LEFT JOIN tp_line_catalog l2 ON l2.form = l1.rolls_to_form AND l2.line = l1.rolls_to_line
LEFT JOIN tp_line_catalog l3 ON l3.form = l2.rolls_to_form AND l3.line = l2.rolls_to_line
LEFT JOIN tp_line_catalog l4 ON l4.form = l3.rolls_to_form AND l4.line = l3.rolls_to_line
LEFT JOIN tp_line_catalog l5 ON l5.form = l4.rolls_to_form AND l5.line = l4.rolls_to_line
LEFT JOIN tp_line_catalog l6 ON l6.form = l5.rolls_to_form AND l6.line = l5.rolls_to_line
LEFT JOIN tp_line_catalog l7 ON l7.form = l6.rolls_to_form AND l7.line = l6.rolls_to_line
LEFT JOIN tp_line_catalog l8 ON l8.form = l7.rolls_to_form AND l8.line = l7.rolls_to_line
LEFT JOIN tp_line_catalog l9 ON l9.form = l8.rolls_to_form AND l9.line = l8.rolls_to_line;

-- Repeat issues: the same issue code adjusted for the same taxpayer in more than one tax year
CREATE OR REPLACE VIEW v_repeat_issues AS
SELECT y.tin_token, t.display_name, y.issue_code, ic.issue_name,
       count(*) AS years_adjusted, min(y.yr) AS first_year, max(y.yr) AS last_year,
       concat_ws('; ', collect_list(CAST(y.yr AS STRING))) AS tax_years
FROM v_adjusted_issue_years y
JOIN tp_taxpayer t ON t.tin_token = y.tin_token
LEFT JOIN tp_issue_code ic ON ic.issue_code = y.issue_code
GROUP BY y.tin_token, t.display_name, y.issue_code, ic.issue_name
HAVING count(*) >= 2;

-- --------------------------------------------------------------------------------------------
-- Notice history: every notice, letter, IDR and report sent to the taxpayer, with the response
-- --------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_notice_history AS
SELECT c.contact_id, c.tin_token, t.display_name, CAST(c.issued_date AS DATE) AS issued_date,
       CAST(c.tax_periods AS STRING) AS tax_periods,
       coalesce(e.episode_type, 'BALANCE_DUE') AS treatment, c.contact_type, c.item_code, c.source_system,
       c.statutory_flag, c.recipient, c.delivery_status,
       CAST(c.response_due AS DATE) AS response_due, CAST(c.response_received AS DATE) AS response_received,
       CASE WHEN c.delivery_status = 'UNDELIVERABLE' THEN 'UNDELIVERABLE'
            WHEN c.response_due IS NULL THEN 'NO_RESPONSE_REQUIRED'
            WHEN c.response_received IS NOT NULL AND CAST(c.response_received AS DATE) <= CAST(c.response_due AS DATE) THEN 'RESPONDED'
            WHEN c.response_received IS NOT NULL THEN 'RESPONDED_LATE'
            WHEN CAST(c.response_due AS DATE) >= a.as_of_date THEN 'RESPONSE_OPEN'
            ELSE 'NO_RESPONSE' END AS response_status,
       CASE WHEN c.response_received IS NOT NULL THEN datediff(CAST(c.response_received AS DATE), CAST(c.issued_date AS DATE)) END AS days_to_respond
FROM tp_contact_event c
JOIN tp_taxpayer t ON t.tin_token = c.tin_token
LEFT JOIN tp_compliance_episode e ON e.episode_id = c.episode_id
CROSS JOIN v_as_of a;

CREATE OR REPLACE VIEW v_notice_summary AS
SELECT n.tin_token, n.display_name,
       count(*) AS notices,
       count_if(n.statutory_flag = 'Y') AS statutory_notices,
       count_if(datediff(a.as_of_date, n.issued_date) <= 365) AS notices_last_12_months,
       count_if(n.response_status = 'NO_RESPONSE') AS unanswered_notices,
       count_if(n.response_status = 'UNDELIVERABLE') AS undeliverable_notices,
       count(DISTINCT n.treatment) AS treatments,
       min(n.issued_date) AS first_notice_date,
       max(n.issued_date) AS last_notice_date,
       max_by(n.item_code, n.issued_date) AS last_notice_code,
       datediff(a.as_of_date, max(n.issued_date)) AS days_since_last_notice
FROM v_notice_history n CROSS JOIN v_as_of a
GROUP BY n.tin_token, n.display_name, a.as_of_date;

-- --------------------------------------------------------------------------------------------
-- Prior audit results: one summary row per taxpayer, and one detail row per issue
-- --------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_prior_audit_summary AS
WITH rep AS (SELECT tin_token, count(*) AS repeat_issue_codes FROM v_repeat_issues GROUP BY tin_token)
SELECT c.tin_token, t.display_name,
       count(*) AS prior_exams,
       count(DISTINCT c.tax_period) AS tax_periods_examined,
       sum(c.deficiency) AS total_deficiency,
       sum(c.penalty_amount) AS total_penalties,
       count_if(c.outcome = 'NO_CHANGE') AS no_change_exams,
       count_if(c.agreed_ind = 'Y') AS agreed_exams,
       count_if(c.outcome = 'UNAGREED_APPEALS') AS appeals_exams,
       count_if(c.outcome = 'DEFAULTED_SNOD') AS defaulted_exams,
       sum(c.issue_count) AS issues_raised,
       sum(c.adjusted_issue_count) AS issues_adjusted,
       max(CAST(c.closed_date AS DATE)) AS last_closed_date,
       coalesce(max(rep.repeat_issue_codes), 0) AS repeat_issue_codes
FROM tp_case_closure c
JOIN tp_taxpayer t ON t.tin_token = c.tin_token
LEFT JOIN rep ON rep.tin_token = c.tin_token
GROUP BY c.tin_token, t.display_name;

CREATE OR REPLACE VIEW v_prior_audit_issues AS
WITH rep AS (SELECT DISTINCT tin_token, issue_code FROM v_repeat_issues)
SELECT i.tin_token, t.display_name, CAST(c.tax_period AS STRING) AS tax_period, c.program, c.outcome,
       CAST(c.closed_date AS DATE) AS closed_date, i.issue_id, i.issue_code, ic.issue_name, i.description, i.return_ref,
       i.amount_claimed, i.amount_proposed, i.amount_sustained, i.status AS issue_status, i.detection_source, i.hours_charged,
       CASE WHEN rep.issue_code IS NOT NULL THEN 'Y' ELSE 'N' END AS repeat_issue
FROM tp_issue i
JOIN tp_case_closure c ON c.episode_id = i.episode_id
JOIN tp_taxpayer t ON t.tin_token = i.tin_token
LEFT JOIN tp_issue_code ic ON ic.issue_code = i.issue_code
LEFT JOIN rep ON rep.tin_token = i.tin_token AND rep.issue_code = i.issue_code;
