"""Writes tp360/dashboards/TP360_RVE_POC.lvdash.json — a Databricks AI/BI dashboard over the tp360 tables.

    python tp360/tools/make_dashboard.py [catalog] [schema]      (defaults: workspace tp360_poc)

Four pages: Taxpayer 360 (Marisol T. Vance), Return Viewer Editor, Signals across the population,
Closed cases — beyond AIMS. Every dataset is plain SQL over the views built by setup_tp360, so the
dashboard shows exactly what Genie and the notebook see.
"""
import json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CAT, SCH = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("workspace", "tp360_poc")
Q = f"{CAT}.{SCH}"
HERO = "Marisol T. Vance"
HERO_LABEL = "Marisol T. Vance (TK100001)"
PICK = "concat(t.display_name, ' (', t.tin_token, ')') = :taxpayer"

DATASETS = {
    # ---- page 1: Taxpayer 360 -------------------------------------------------------------
    "ds_hero_header": ("TP360 header — hero", f"""
SELECT t.display_name, t.total_balance, t.modules_with_balance, t.signal_count,
       coalesce(size(split(t.open_episodes, '; ')), 0) AS open_episode_count
FROM {Q}.v_tp360_header t WHERE {PICK}"""),
    "ds_hero_signals": ("Signals — hero", f"""
SELECT s.signal_id, s.severity, s.evidence
FROM {Q}.v_tp_signals s JOIN {Q}.tp_taxpayer t USING (tin_token)
WHERE {PICK}
ORDER BY CASE s.severity WHEN 'HIGH' THEN 1 ELSE 2 END, s.signal_id"""),
    "ds_hero_modules": ("Modules — hero", f"""
SELECT CAST(m.tax_period AS STRING) AS tax_period, m.assessed_balance AS balance,
       CAST(m.csed AS STRING) AS csed, CASE WHEN c.suspended_ind = 'Y' THEN 'Suspended' ELSE 'Running' END AS csed_status
FROM {Q}.tp_tax_module m JOIN {Q}.tp_taxpayer t USING (tin_token)
LEFT JOIN {Q}.tp_statutory_clock c ON c.module_id = m.module_id AND c.clock_type = 'CSED'
WHERE {PICK} AND m.assessed_balance > 0
ORDER BY tax_period"""),
    "ds_hero_episodes": ("Open episodes — hero", f"""
SELECT e.episode_type, e.episode_subtype, e.status, CAST(e.opened_date AS STRING) AS opened
FROM {Q}.tp_compliance_episode e JOIN {Q}.tp_taxpayer t USING (tin_token)
WHERE {PICK} AND e.closed_date IS NULL
ORDER BY e.opened_date"""),
    "ds_hero_history": ("Prior audit results by case — selected taxpayer", f"""
SELECT CAST(tax_period AS STRING) AS tax_period, program, selection_source, outcome, appeals_outcome,
       CAST(closed_date AS STRING) AS closed, deficiency, penalty_amount, issues
FROM {Q}.v_prior_audit_history t WHERE {PICK}
ORDER BY tax_period"""),
    "ds_audit_kpis": ("Prior audit summary — selected taxpayer", f"""
SELECT coalesce(s.prior_exams, 0) AS prior_exams, coalesce(s.total_deficiency, 0) AS total_deficiency,
       coalesce(s.issues_adjusted, 0) AS issues_adjusted, coalesce(s.repeat_issue_codes, 0) AS repeat_issue_codes
FROM {Q}.tp_taxpayer t LEFT JOIN {Q}.v_prior_audit_summary s ON s.tin_token = t.tin_token
WHERE {PICK}"""),
    "ds_audit_issues": ("Prior audit issues — selected taxpayer", f"""
SELECT i.tax_period, i.program, i.issue_code, i.issue_name, i.return_ref, i.amount_proposed, i.amount_sustained,
       i.issue_status, i.detection_source, i.hours_charged, i.repeat_issue
FROM {Q}.v_prior_audit_issues i JOIN {Q}.tp_taxpayer t ON t.tin_token = i.tin_token
WHERE {PICK}
ORDER BY i.tax_period, abs(i.amount_sustained) DESC"""),
    "ds_notice_kpis": ("Notice summary — selected taxpayer", f"""
SELECT coalesce(s.notices, 0) AS notices, coalesce(s.statutory_notices, 0) AS statutory_notices,
       coalesce(s.unanswered_notices, 0) AS unanswered_notices
FROM {Q}.tp_taxpayer t LEFT JOIN {Q}.v_notice_summary s ON s.tin_token = t.tin_token
WHERE {PICK}"""),
    "ds_notice_history": ("Notice history — selected taxpayer", f"""
SELECT CAST(n.issued_date AS STRING) AS issued, n.tax_periods, n.treatment, n.contact_type, n.item_code,
       n.statutory_flag, n.recipient, CAST(n.response_due AS STRING) AS response_due,
       CAST(n.response_received AS STRING) AS received, n.response_status, n.days_to_respond
FROM {Q}.v_notice_history n JOIN {Q}.tp_taxpayer t ON t.tin_token = n.tin_token
WHERE {PICK}
ORDER BY n.issued_date DESC"""),
    "ds_hero_related": ("Related parties with signals — hero", f"""
SELECT DISTINCT r.related_name, r.hops, r.path, r.via_name, r.related_signals
FROM {Q}.v_related_parties_named r JOIN {Q}.tp_taxpayer t ON t.tin_token = r.tin_token
WHERE {PICK} AND r.related_signals IS NOT NULL"""),
    "ds_taxpayer_list": ("Taxpayer picker values", f"""
SELECT concat(t.display_name, ' (', t.tin_token, ')') AS taxpayer
FROM {Q}.v_tp360_header t
WHERE t.entity_type = 'INDIVIDUAL'
  AND (t.signal_count > 0 OR t.total_balance > 0
       OR t.tin_token IN (SELECT tin_token FROM {Q}.tp_case_closure)
       OR t.tin_token IN (SELECT tin_token FROM {Q}.tp_compliance_episode WHERE closed_date IS NULL))
ORDER BY CASE WHEN t.case_group LIKE 'HERO%' THEN 0 ELSE 1 END, taxpayer"""),
    # ---- page 2: RVE ----------------------------------------------------------------------
    "ds_rve_compare": ("RVE three-column view — 2024 heroes", f"""
SELECT t.display_name AS taxpayer, c.form, c.line, c.line_desc, c.as_filed, c.as_adjusted, c.delta, c.data_origin
FROM {Q}.v_return_compare c JOIN {Q}.tp_taxpayer t USING (tin_token)
WHERE c.tax_period = 202412 AND c.delta <> 0 AND t.case_group IN ('HERO_A', 'HERO_B')
ORDER BY taxpayer, c.form_sort, c.line_sort, c.line, c.sub_id"""),
    "ds_rve_origin": ("Where return data came from — 2024 heroes", f"""
SELECT concat(t.display_name, ' · ', o.version_type) AS snapshot, o.data_origin, o.line_count
FROM {Q}.v_rve_data_origin o JOIN {Q}.tp_taxpayer t USING (tin_token)
WHERE o.tax_period = 202412 AND t.case_group IN ('HERO_A', 'HERO_B')
ORDER BY snapshot, o.data_origin"""),
    "ds_rve_findings": ("Reconciliation findings — 2024 heroes", f"""
SELECT t.display_name AS taxpayer, f.branch,
       CASE f.branch WHEN 'A' THEN 'Resolved from data' WHEN 'B' THEN 'Not a taxpayer issue' ELSE 'Needs the taxpayer (IDR)' END AS branch_meaning,
       f.item, f.irp_amount, f.return_ref, f.return_amount, f.root_cause, f.note
FROM {Q}.tp_rri_finding f JOIN {Q}.tp_taxpayer t USING (tin_token)
WHERE f.tax_period = 202412 AND t.case_group IN ('HERO_A', 'HERO_B')
ORDER BY taxpayer, f.branch, f.finding_id"""),
    "ds_rve_exams": ("2024 exam results — heroes", f"""
SELECT t.display_name AS taxpayer, r.deficiency, r.taxable_income_change, r.episode_status
FROM {Q}.v_exam_results r JOIN {Q}.tp_taxpayer t USING (tin_token)
WHERE r.tax_period = 202412 ORDER BY r.deficiency DESC"""),
    # ---- page 3: signals ------------------------------------------------------------------
    "ds_sig_kpis": ("Signal KPIs", f"""
SELECT count(DISTINCT tin_token) AS taxpayers_with_signals,
       count(DISTINCT CASE WHEN severity = 'HIGH' THEN tin_token END) AS taxpayers_with_high,
       count(*) AS signal_rows
FROM {Q}.v_tp_signals"""),
    "ds_sig_by_rule": ("Taxpayers per signal", f"""
SELECT signal_id, count(DISTINCT tin_token) AS taxpayers
FROM {Q}.v_tp_signals GROUP BY signal_id ORDER BY taxpayers DESC"""),
    "ds_sig_top": ("Taxpayers with the most signals", f"""
SELECT display_name, tin_token, entity_type, total_balance, signal_count, signals, open_episodes
FROM {Q}.v_tp360_header WHERE signal_count > 0
ORDER BY signal_count DESC, total_balance DESC LIMIT 25"""),
    # ---- page 4: closed cases -------------------------------------------------------------
    "ds_cc_kpis": ("Closed-case KPIs", f"""
SELECT count(*) AS closed_cases, sum(deficiency) AS total_deficiency,
       round(100.0 * count_if(outcome = 'NO_CHANGE') / count(*), 1) AS no_change_pct,
       round(sum(deficiency) / sum(total_hours), 0) AS deficiency_per_hour
FROM {Q}.v_case_results"""),
    "ds_cc_lines": ("Most adjusted source lines", f"""
SELECT concat(form, ' ', line, ' — ', line_desc) AS return_line, adjustments, cases, avg_abs_adjustment
FROM {Q}.v_line_adjustment_frequency ORDER BY adjustments DESC LIMIT 10"""),
    "ds_cc_detection": ("How adjustments were found", f"""
SELECT detection_source, issues, adjusted, adjusted_pct, total_abs_sustained
FROM {Q}.v_detection_mix ORDER BY adjusted DESC"""),
    "ds_cc_issues": ("Issue outcomes (raised at least 10 times)", f"""
SELECT issue_code, issue_name, times_raised, adjusted, conceded, no_change, no_change_pct,
       avg_pct_sustained_of_proposed, avg_hours, sustained_per_hour
FROM {Q}.v_issue_outcomes WHERE times_raised >= 10 ORDER BY times_raised DESC"""),
    "ds_cc_program": ("Results by program and outcome", f"""
SELECT program, outcome, count(*) AS cases, round(avg(deficiency), 0) AS avg_deficiency,
       round(avg(total_hours), 1) AS avg_hours, round(sum(deficiency) / sum(total_hours), 0) AS deficiency_per_hour
FROM {Q}.v_case_results GROUP BY program, outcome ORDER BY program, cases DESC"""),
    "ds_cc_rootcause": ("Variance root causes", f"""
SELECT root_cause, sum(findings) AS findings
FROM {Q}.v_variance_root_causes GROUP BY root_cause ORDER BY findings DESC"""),
    "ds_cc_trace": ("Issue code → Form 1040 trace", f"""
SELECT issue_code, issue_name, role, source_line, rollup_path
FROM {Q}.v_issue_to_1040_trace ORDER BY issue_code, role DESC"""),
}

# column types for tables: name -> (type, displayAs)
NUMERIC_HINTS = ("balance", "deficiency", "amount", "count", "cases", "hours", "pct", "per_hour", "adjust", "findings",
                 "issues", "taxpayers", "hops", "raised", "conceded", "no_change", "sustained", "delta", "as_filed",
                 "as_adjusted", "line_count", "change", "notices", "exams", "days_to", "codes")


def col_type(name):
    if name in ("line", "tin_token", "csed", "opened", "closed", "tax_year", "tax_period", "tax_periods", "issued",
                "response_due", "received", "issue_code", "repeat_issue", "issue_status", "issue_name"):
        return "string"
    return "float" if any(h in name for h in NUMERIC_HINTS) else "string"


def table_columns(cols, titles):
    out = []
    for i, c in enumerate(cols):
        typ = col_type(c)
        out.append({
            "fieldName": c, "booleanValues": ["false", "true"], "imageUrlTemplate": "{{ @ }}", "imageTitleTemplate": "{{ @ }}",
            "imageWidth": "", "imageHeight": "", "linkUrlTemplate": "{{ @ }}", "linkTextTemplate": "{{ @ }}",
            "linkTitleTemplate": "{{ @ }}", "linkOpenInNewTab": True, "type": typ,
            "displayAs": "number" if typ == "float" else "string", "numberFormat": "#,##0.##" if typ == "float" else None,
            "visible": True, "order": 100000 + i, "title": titles.get(c, c.replace("_", " ")), "allowSearch": False,
            "alignContent": "right" if typ == "float" else "left", "allowHTML": False, "highlightLinks": False,
            "useMonospaceFont": False, "preserveWhitespace": False, "displayName": titles.get(c, c.replace("_", " ")),
        })
        if out[-1]["numberFormat"] is None:
            del out[-1]["numberFormat"]
    return out


def cols_of(ds):
    sql = DATASETS[ds][1]
    sel = sql.split("SELECT", 1)[1].split("\nFROM", 1)[0]
    parts, depth, cur = [], 0, ""
    for ch in sel:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur); cur = ""
        else:
            cur += ch
    parts.append(cur)
    names = []
    for p in parts:
        p = p.strip().replace("DISTINCT ", "")
        if " AS " in p:
            names.append(p.rsplit(" AS ", 1)[1].strip())
        else:
            names.append(p.split(".")[-1].strip())
    return names


def query(ds, fields):
    return [{"name": "main_query", "query": {"datasetName": ds,
             "fields": [{"name": f, "expression": f"`{f}`"} for f in fields], "disaggregated": True}}]


n = {"w": 0}


def wid(prefix):
    n["w"] += 1
    return f"{prefix}{n['w']:03d}"


def text(lines, x, y, w, h):
    return {"widget": {"name": wid("t"), "multilineTextboxSpec": {"lines": lines}}, "position": {"x": x, "y": y, "width": w, "height": h}}


def counter(ds, field, title, x, y, w=2, h=2):
    return {"widget": {"name": wid("c"), "queries": query(ds, [field]),
                       "spec": {"version": 2, "widgetType": "counter",
                                "encodings": {"value": {"fieldName": field, "displayName": title}},
                                "frame": {"showTitle": True, "title": title}}},
            "position": {"x": x, "y": y, "width": w, "height": h}}


def table(ds, title, x, y, w, h, titles=None, cols=None):
    cols = cols or cols_of(ds)
    return {"widget": {"name": wid("tb"), "queries": query(ds, cols),
                       "spec": {"version": 1, "widgetType": "table",
                                "encodings": {"columns": table_columns(cols, titles or {})},
                                "invisibleColumns": [], "allowHTMLByDefault": False, "itemsPerPage": 25,
                                "paginationSize": "default", "condensed": True, "withRowNumber": False,
                                "frame": {"showTitle": True, "title": title}}},
            "position": {"x": x, "y": y, "width": w, "height": h}}


def hbar(ds, cat, val, title, cat_title, val_title, x, y, w, h):
    return {"widget": {"name": wid("b"), "queries": query(ds, [cat, val]),
                       "spec": {"version": 3, "widgetType": "bar",
                                "encodings": {
                                    "x": {"fieldName": val, "scale": {"type": "quantitative"}, "displayName": val_title},
                                    "y": {"fieldName": cat, "scale": {"type": "categorical", "sort": {"by": "x-reversed"}}, "displayName": cat_title},
                                    "label": {"show": True}},
                                "frame": {"showTitle": True, "title": title}}},
            "position": {"x": x, "y": y, "width": w, "height": h}}


PARAM_DS = ["ds_hero_header", "ds_hero_signals", "ds_hero_modules", "ds_hero_episodes", "ds_hero_history", "ds_hero_related",
            "ds_audit_kpis", "ds_audit_issues", "ds_notice_kpis", "ds_notice_history"]


def dataset(k, v):
    d = {"name": k, "displayName": v[0], "queryLines": [l + "\n" for l in v[1].strip().splitlines()]}
    if k in PARAM_DS:
        d["parameters"] = [{"displayName": "taxpayer", "keyword": "taxpayer", "dataType": "STRING",
                            "defaultSelection": {"values": {"dataType": "STRING", "values": [{"value": HERO_LABEL}]}}}]
    return d


def picker(x, y, w, h):
    queries = [{"name": "q_taxpayer_values", "query": {"datasetName": "ds_taxpayer_list",
                "fields": [{"name": "taxpayer", "expression": "`taxpayer`"}], "disaggregated": False}}]
    fields = [{"fieldName": "taxpayer", "displayName": "taxpayer", "queryName": "q_taxpayer_values"}]
    for ds in PARAM_DS:
        qn = f"p_{ds}_taxpayer"
        queries.append({"name": qn, "query": {"datasetName": ds, "parameters": [{"name": "taxpayer", "keyword": "taxpayer"}],
                                              "disaggregated": False}})
        fields.append({"parameterName": "taxpayer", "queryName": qn})
    return {"widget": {"name": "f_taxpayer", "queries": queries,
                       "spec": {"version": 2, "widgetType": "filter-single-select", "encodings": {"fields": fields},
                                "frame": {"showTitle": True, "title": "Taxpayer"}}},
            "position": {"x": x, "y": y, "width": w, "height": h}}


NOTE = "Fictional taxpayers · synthetic data · not IRS data. Closed-case figures are illustrative (TY2024 parameters)."

p1 = [
    text(["## Taxpayer 360", "Pick a taxpayer: every open episode, balance, signal, prior audit result, notice and related party, read from the UCP canonical tables on EDP. Starts on Marisol T. Vance; try Marcus Thornbury (TK200001) or R. Latimer (TK100050).", NOTE], 0, 0, 4, 2),
    picker(4, 0, 2, 2),
    counter("ds_hero_header", "total_balance", "Total balance", 0, 2),
    counter("ds_hero_header", "open_episode_count", "Open episodes", 2, 2),
    counter("ds_hero_header", "signal_count", "Signals", 4, 2),
    table("ds_hero_signals", "Signals and their evidence", 0, 4, 6, 5),
    table("ds_hero_episodes", "Open episodes", 0, 9, 3, 4),
    table("ds_hero_modules", "Modules with a balance", 3, 9, 3, 4, {"csed_status": "CSED status", "tax_period": "tax period"}),
    text(["### Prior audit results", "Every closed exam and AUR case for this taxpayer: the case-level result AIMS would hold, then each issue with amount proposed vs sustained and how it was found. Repeat issue = the same issue code adjusted in two or more tax years."], 0, 13, 6, 1),
    counter("ds_audit_kpis", "prior_exams", "Prior exams and AUR cases", 0, 14),
    counter("ds_audit_kpis", "total_deficiency", "Total deficiency", 2, 14),
    counter("ds_audit_kpis", "repeat_issue_codes", "Repeat issues", 4, 14),
    table("ds_hero_history", "Summary — one row per closed case", 0, 16, 6, 4,
          {"tax_period": "tax period", "selection_source": "selected by", "appeals_outcome": "appeals", "penalty_amount": "penalty"}),
    table("ds_audit_issues", "Detail — one row per issue", 0, 20, 6, 5,
          {"tax_period": "tax period", "issue_code": "issue", "issue_name": "description", "return_ref": "return line",
           "amount_proposed": "proposed", "amount_sustained": "sustained", "issue_status": "status",
           "detection_source": "how found", "hours_charged": "hours", "repeat_issue": "repeat"}),
    text(["### Notice history", "Every notice, letter, IDR and report sent, newest first, with the response. Statutory = a notice with legal effect (notice and demand, CP504, LT11/Letter 1058, Letter 3219). Notice sequences are illustrative; item codes and timing are SME to confirm."], 0, 25, 6, 1),
    counter("ds_notice_kpis", "notices", "Notices and letters sent", 0, 26),
    counter("ds_notice_kpis", "statutory_notices", "Statutory notices", 2, 26),
    counter("ds_notice_kpis", "unanswered_notices", "Unanswered past due", 4, 26),
    table("ds_notice_history", "Notice history (newest first)", 0, 28, 6, 7,
          {"tax_periods": "tax periods", "contact_type": "type", "item_code": "notice", "statutory_flag": "statutory",
           "response_due": "response due", "response_status": "response", "days_to_respond": "days to respond"}),
    table("ds_hero_related", "Related parties with signals of their own", 0, 35, 6, 3),
]
p2 = [
    text(["## Return Viewer Editor — TY2024 heroes", "The as-filed baseline is never overwritten. Each change is versioned and every line says where its data came from: MeF, an attachment extract, an RVE supplement, an examiner adjustment, or the recompute.", NOTE], 0, 0, 6, 2),
    table("ds_rve_exams", "2024 exam results", 0, 2, 6, 3),
    table("ds_rve_compare", "Three-column view — what changed (as filed · as adjusted · delta)", 0, 5, 6, 7),
    table("ds_rve_findings", "Reconciliation findings by branch", 0, 12, 6, 6),
    table("ds_rve_origin", "Where the return data came from, by snapshot", 0, 18, 6, 5),
]
p3 = [
    text(["## Signals across the population", "Rules SG01–SG10 run as SQL over the canonical model. The same rules feed Genie, this dashboard and any case tool — nothing is copied into a workflow vendor.", NOTE], 0, 0, 6, 2),
    counter("ds_sig_kpis", "taxpayers_with_signals", "Taxpayers with any signal", 0, 2),
    counter("ds_sig_kpis", "taxpayers_with_high", "Taxpayers with a HIGH signal", 2, 2),
    counter("ds_sig_kpis", "signal_rows", "Signals firing", 4, 2),
    hbar("ds_sig_by_rule", "signal_id", "taxpayers", "Taxpayers per signal", "Signal", "Taxpayers", 0, 4, 6, 6),
    table("ds_sig_top", "Taxpayers with the most signals", 0, 10, 6, 7),
]
p4 = [
    text(["## Closed cases — beyond AIMS", "AIMS holds the case level. This adds what AIMS does not: issue codes, amount proposed vs sustained, how each adjustment was found, hours per issue, every line adjustment and the tax computation filed vs examined.", NOTE], 0, 0, 6, 2),
    counter("ds_cc_kpis", "closed_cases", "Closed cases", 0, 2, 2, 2),
    counter("ds_cc_kpis", "total_deficiency", "Total deficiency", 2, 2, 2, 2),
    counter("ds_cc_kpis", "deficiency_per_hour", "Deficiency per hour (weighted)", 4, 2, 2, 2),
    hbar("ds_cc_lines", "return_line", "adjustments", "Most adjusted source lines", "Return line", "Adjustments", 0, 4, 3, 6),
    hbar("ds_cc_detection", "detection_source", "adjusted", "How adjustments were found", "Detection source", "Issues adjusted", 3, 4, 3, 6),
    table("ds_cc_issues", "Issue outcomes (raised at least 10 times)", 0, 10, 6, 6,
          {"avg_pct_sustained_of_proposed": "% of proposed sustained", "sustained_per_hour": "sustained $ per hour"}),
    table("ds_cc_program", "Results by program and outcome", 0, 16, 4, 6),
    hbar("ds_cc_rootcause", "root_cause", "findings", "Variance root causes", "Root cause", "Findings", 4, 16, 2, 6),
    table("ds_cc_trace", "Issue code → source line → Form 1040", 0, 22, 6, 6),
]

dash = {
    "datasets": [dataset(k, v) for k, v in DATASETS.items()],
    "pages": [
        {"name": "p_tp360", "displayName": "Taxpayer 360", "layout": p1, "pageType": "PAGE_TYPE_CANVAS"},
        {"name": "p_rve", "displayName": "Return Viewer Editor", "layout": p2, "pageType": "PAGE_TYPE_CANVAS"},
        {"name": "p_signals", "displayName": "Signals", "layout": p3, "pageType": "PAGE_TYPE_CANVAS"},
        {"name": "p_closed", "displayName": "Closed cases", "layout": p4, "pageType": "PAGE_TYPE_CANVAS"},
    ],
}
os.makedirs(os.path.join(ROOT, "dashboards"), exist_ok=True)
out = os.path.join(ROOT, "dashboards", "TP360_RVE_POC.lvdash.json")
with open(out, "w") as fh:
    json.dump(dash, fh, indent=2)
print("wrote", out, "-", len(DATASETS), "datasets,", sum(len(p["layout"]) for p in dash["pages"]), "widgets")
