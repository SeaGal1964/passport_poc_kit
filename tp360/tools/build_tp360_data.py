"""Build the TP360 / RVE POC synthetic data.

Writes tp360/data/tp_*.csv (one Delta table each), tp360/data/tp_signal_answer_key.csv
(signals computed here in Python, independently of the SQL rules) and
tp360/viewer/scenarios.json (what the staged walkthroughs render).

    python tp360/tools/build_tp360_data.py

Deterministic (fixed seed). Fictional taxpayers, synthetic data, no FTI. Table and column
names are POC names, not CDW names.
"""
import csv, json, os, random, sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
import hero_cases as H
import closed_cases
from reference_tables import ISSUE_CODES, ISSUE_LINE_MAP, LINE_CATALOG, ROOT_CAUSES
from tax_engine_ty2024 import compute

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
VIEWER = os.path.join(ROOT, "viewer")
AS_OF = date.fromisoformat(H.AS_OF)
rng = random.Random(20241231)

T = {k: [] for k in [
    "tp_taxpayer", "tp_tax_module", "tp_compliance_episode", "tp_treatment_assignment",
    "tp_procedural_overlay", "tp_contact_event", "tp_issue", "tp_determination", "tp_statutory_clock",
    "tp_financial_profile", "tp_asset", "tp_bank_account", "tp_information_return", "tp_relationship",
    "tp_transfer", "tp_return_snapshot", "tp_return_line", "tp_rri_finding", "tp_idr", "tp_adjustment",
    "tp_case_closure", "tp_tax_computation", "tp_issue_code", "tp_issue_line_map", "tp_line_catalog", "tp_root_cause"]}

COLS = {
    "tp_taxpayer": "tin_token,tin_type,display_name,entity_type,filing_status,city,state,poa_on_file,case_group",
    "tp_tax_module": "module_id,tin_token,mft,tax_period,assessed_balance,last_assessment_date,csed,module_status",
    "tp_compliance_episode": "episode_id,tin_token,episode_type,episode_subtype,opened_date,closed_date,status,module_ids",
    "tp_treatment_assignment": "episode_id,function,assignee,start_date,end_date",
    "tp_procedural_overlay": "overlay_id,tin_token,episode_id,overlay_type,effect,authority,start_date,end_date",
    "tp_contact_event": "contact_id,tin_token,module_ids,episode_id,contact_type,item_code,source_system,statutory_flag,issued_date,delivery_status,response_due,response_received,recipient",
    "tp_issue": "issue_id,episode_id,tin_token,tax_period,issue_code,description,return_ref,amount_claimed,amount_proposed,amount_sustained,status,detection_source,hours_charged",
    "tp_determination": "determination_id,episode_id,issue_id,tin_token,determination_type,outcome,amount,authority,decided_date,detail",
    "tp_statutory_clock": "clock_id,tin_token,module_id,episode_id,clock_type,start_date,expiry_date,suspended_ind,authority",
    "tp_financial_profile": "tin_token,as_of_date,gross_monthly_income,allowable_monthly_expenses,net_monthly_ability,net_realizable_equity,minimum_offer,offer_amount,source",
    "tp_asset": "asset_id,owner_tin_token,asset_type,description,fmv,encumbrance,equity,disclosed_on_433,source,verified",
    "tp_bank_account": "account_id,tin_token,institution,account_type,acct_last4,balance,source,disclosed_on_433",
    "tp_information_return": "ir_id,tin_token,tax_year,form_type,box,payer_tin_token,payer_name,amount,note",
    "tp_relationship": "rel_id,from_id,to_id,rel_type,pct,start_date,end_date,source",
    "tp_transfer": "transfer_id,asset_id,from_tin_token,to_tin_token,transfer_date,fmv_at_transfer,consideration,source",
    "tp_return_snapshot": "snapshot_id,tin_token,mft,tax_period,version_type,basis_snapshot_id,source_tc,created_date,created_by,status",
    "tp_return_line": "snapshot_id,form,line,sub_id,line_desc,mef_element,amount,data_origin,modifiable,review_state",
    "tp_rri_finding": "finding_id,snapshot_id,tin_token,tax_period,source,item,irp_amount,return_ref,return_amount,delta,branch,disposition,variance_type,root_cause,issue_code,note",
    "tp_idr": "idr_id,episode_id,tin_token,form,issued_date,due_date,response_date,recipient,status,item_count,items",
    "tp_adjustment": "adjustment_id,episode_id,snapshot_id,tin_token,tax_period,form,line,line_desc,as_filed,adjustment,as_adjusted,adjustment_kind,issue_id,issue_code,detection_source",
    "tp_case_closure": "episode_id,tin_token,tax_period,program,selection_source,outcome,closed_date,closing_tc,deficiency,penalty_code,penalty_amount,appeals_outcome,agreed_ind,total_hours,issue_count,adjusted_issue_count,aims_disposal_code,computation_note",
    "tp_tax_computation": "episode_id,tin_token,tax_period,filing_status_filed,filing_status_examined,agi_filed,agi_examined,taxable_income_filed,taxable_income_examined,tax_filed,tax_examined,credits_filed,credits_examined,other_taxes_filed,other_taxes_examined,total_tax_filed,total_tax_examined,payments_filed,payments_examined,deficiency,penalty_amount,computation_engine,interest_note",
    "tp_issue_code": "issue_code,issue_name,category,program,source_form,irc_reference,reference_note",
    "tp_issue_line_map": "issue_code,seq,form,line,mef_element,effect,role,note",
    "tp_line_catalog": "form,line,line_desc,mef_element,line_class,modifiable,rolls_to_form,rolls_to_line",
    "tp_root_cause": "root_cause,branch,description",
}


def add(table, **row):
    T[table].append(row)


def d(s):
    return date.fromisoformat(s)


def iso(x):
    if isinstance(x, date):
        return x.isoformat()
    return "" if x is None else x


# ==============================================================================================
# HERO A  Marisol Vance (collection context from the TP360 page + TY2024 return through RVE)
# ==============================================================================================
A = H.A["tin"]
add("tp_taxpayer", tin_token=A, tin_type="SSN", display_name="Marisol T. Vance", entity_type="INDIVIDUAL",
    filing_status="HOH", city="Olympia", state="WA", poa_on_file="Y", case_group="HERO_A")
add("tp_taxpayer", tin_token="TK100002", tin_type="SSN", display_name="D. Vance", entity_type="INDIVIDUAL",
    filing_status="S", city="Tacoma", state="WA", poa_on_file="N", case_group="HERO_A")
add("tp_taxpayer", tin_token="TK100050", tin_type="SSN", display_name="R. Latimer", entity_type="INDIVIDUAL",
    filing_status="MFJ", city="Lacey", state="WA", poa_on_file="N", case_group="HERO_A")
add("tp_taxpayer", tin_token="TK900001", tin_type="EIN", display_name="Latimer Grove Holdings LLC", entity_type="PARTNERSHIP",
    filing_status="", city="Olympia", state="WA", poa_on_file="N", case_group="HERO_A")
add("tp_taxpayer", tin_token="TK900002", tin_type="EIN", display_name="Harborline Fabrication Inc", entity_type="CORPORATION",
    filing_status="", city="Tacoma", state="WA", poa_on_file="N", case_group="HERO_A")

mods_a = [("2019", 61240, "2029-06-14", "TC 300 exam"), ("2020", 48905, "2030-11-09", "TC 150 balance due"),
          ("2021", 44180, "2032-02-27", "TC 290 AUR"), ("2022", 29985, "2033-05-18", "TC 150 balance due")]
for y, bal, csed, src in mods_a:
    add("tp_tax_module", module_id=f"{A}-30-{y}12", tin_token=A, mft=30, tax_period=f"{y}12", assessed_balance=bal,
        last_assessment_date="", csed=csed, module_status="22")
add("tp_tax_module", module_id=f"{A}-30-202412", tin_token=A, mft=30, tax_period="202412",
    assessed_balance=H.A_DEFICIENCY, last_assessment_date="2026-10-26", csed="2036-10-26", module_status="21")
mod_ids_a = ";".join(f"{A}-30-{y}12" for y, *_ in mods_a)

for ep in [
    ("EP-A-IA1", "IA", "Online Account", "2024-03-03", "2024-11-20", "DEFAULTED", mod_ids_a),
    ("EP-A-IA2", "IA", "Reinstated", "2025-02-10", "2025-10-17", "DEFAULTED", mod_ids_a),
    ("EP-A-ACS", "ACS", "Status 22", "2025-11-03", "", "SUSPENDED_OIC", mod_ids_a),
    ("EP-A-PP", "PASSPORT", "IRC 7345", "2026-03-12", "", "CERTIFIED", mod_ids_a),
    ("EP-A-OIC", "OIC", "Doubt as to collectibility", "2026-05-24", "", "INVESTIGATION", mod_ids_a),
    ("EP-A-EX24", "EXAM", "Correspondence", "2026-08-10", "2026-10-26", "CLOSED_AGREED", f"{A}-30-202412"),
]:
    add("tp_compliance_episode", episode_id=ep[0], tin_token=A, episode_type=ep[1], episode_subtype=ep[2],
        opened_date=ep[3], closed_date=ep[4], status=ep[5], module_ids=ep[6])
for ep, fn, who, s, e in [("EP-A-ACS", "ACS", "ACS call site queue", "2025-11-03", ""),
                          ("EP-A-OIC", "COIC offer examiner", "K. Brandt", "2026-05-24", ""),
                          ("EP-A-PP", "Passport program", "Automated", "2026-03-12", ""),
                          ("EP-A-EX24", "Examination", "A. Whitfield", "2026-08-10", "2026-10-26")]:
    add("tp_treatment_assignment", episode_id=ep, function=fn, assignee=who, start_date=s, end_date=e)
add("tp_procedural_overlay", overlay_id="OV-A1", tin_token=A, episode_id="EP-A-OIC", overlay_type="OIC_PENDING",
    effect="Levy barred; CSED suspended while pending plus 30 days", authority="IRC 6331(k); IRC 6331(i)(5)",
    start_date="2026-05-24", end_date="")
add("tp_procedural_overlay", overlay_id="OV-A2", tin_token=A, episode_id="EP-A-PP", overlay_type="PASSPORT_CERTIFIED",
    effect="Certified seriously delinquent tax debt; reverse within 30 days of a trigger", authority="IRC 7345",
    start_date="2026-03-12", end_date="")

ce = 0
def contact(tin, mods, ep, ctype, code, src, stat, issued, status="DELIVERED", due="", recv="", to="TAXPAYER"):
    global ce
    ce += 1
    add("tp_contact_event", contact_id=f"CE{ce:05d}", tin_token=tin, module_ids=mods, episode_id=ep, contact_type=ctype,
        item_code=code, source_system=src, statutory_flag=stat, issued_date=issued, delivery_status=status,
        response_due=due, response_received=recv, recipient=to)

contact(A, mod_ids_a, "EP-A-ACS", "NOTICE", "LT11", "ACS", "Y", "2026-01-08", due="2026-02-07")
contact(A, mod_ids_a, "EP-A-PP", "NOTICE", "CP508C", "PASSPORT", "Y", "2026-03-12")
contact(A, mod_ids_a, "EP-A-OIC", "LETTER", "Letter 3016 (offer processable)", "COIC", "N", "2026-06-02", to="POA")
contact(A, f"{A}-30-202412", "EP-A-EX24", "IDR", "Form 4564", "EXAM", "N", "2026-08-17", due="2026-09-16", recv="2026-09-12", to="POA")
contact(A, f"{A}-30-202412", "EP-A-EX24", "REPORT", "Form 4549", "EXAM", "N", "2026-09-30", due="2026-10-30", recv="2026-10-09", to="POA")
contact(A, f"{A}-30-202412", "EP-A-EX24", "NOTICE", "CP22E", "MASTER_FILE", "Y", "2026-10-26", to="TAXPAYER")

add("tp_issue", issue_id="I-A1", episode_id="EP-A-EX24", tin_token=A, tax_period="202412", issue_code="IR03",
    description="Interest reported by Harbor Trust Savings not on Schedule B", return_ref="SCH_B 1", amount_claimed=0,
    amount_proposed=1840, amount_sustained=1840, status="ADJUSTED", detection_source="IRP_MATCH", hours_charged=1.5)
add("tp_issue", issue_id="I-A2", episode_id="EP-A-EX24", tin_token=A, tax_period="202412", issue_code="EX_SCHC_OTHER_EXP",
    description="Schedule C Part V other expenses supported only by a PDF statement", return_ref="SCH_C 27a", amount_claimed=18400,
    amount_proposed=-12300, amount_sustained=-6600, status="ADJUSTED", detection_source="RVE_ATTACHMENT_EXTRACT", hours_charged=6.5)
for x in H.A_DETERMINATIONS:
    add("tp_determination", determination_id=x["det_id"], episode_id="EP-A-EX24", issue_id=x["issue_id"], tin_token=A,
        determination_type="EXAM_ISSUE", outcome=x["outcome"], amount=x["amount"], authority=x["authority"],
        decided_date="2026-10-09", detail=x["detail"])
add("tp_determination", determination_id="D-A0", episode_id="EP-A-PP", issue_id="", tin_token=A,
    determination_type="PASSPORT_CERTIFICATION", outcome="CERTIFIED", amount=184310, authority="IRC 7345",
    decided_date="2026-03-12", detail="Certified to the Department of State (TC 971 AC 641)")

for y, bal, csed, src in mods_a:
    add("tp_statutory_clock", clock_id=f"CL-A-CSED-{y}", tin_token=A, module_id=f"{A}-30-{y}12", episode_id="",
        clock_type="CSED", start_date="", expiry_date=csed, suspended_ind="Y", authority="IRC 6502; suspended IRC 6331(i)(5), (k)")
add("tp_statutory_clock", clock_id="CL-A-ASED-2024", tin_token=A, module_id=f"{A}-30-202412", episode_id="EP-A-EX24",
    clock_type="ASED", start_date="2025-04-15", expiry_date="2028-04-15", suspended_ind="N", authority="IRC 6501(a)")
add("tp_statutory_clock", clock_id="CL-A-OIC24", tin_token=A, module_id="", episode_id="EP-A-OIC",
    clock_type="OIC_DEEMED_ACCEPTANCE", start_date="2026-05-24", expiry_date="2028-05-24", suspended_ind="N", authority="IRC 7122(f)")

add("tp_financial_profile", tin_token=A, as_of_date="2026-02-11", gross_monthly_income=9480, allowable_monthly_expenses=6215,
    net_monthly_ability=3265, net_realizable_equity=95260, minimum_offer=134440, offer_amount=52000, source="Form 433-A (OIC); FAS")

for a in [("AS-A1", A, "REAL_PROPERTY", "Residence · 1412 Larkspur Way", 412000, 338000, "Y", "County assessor; 1098; Accurint", "Verified"),
          ("AS-A2", A, "REAL_PROPERTY", "Rental · 88 Ferncroft Rd (transferred 2025-09-22)", 268000, 241000, "N", "County assessor; Accurint", "Verified"),
          ("AS-A3", A, "VEHICLE", "2022 pickup truck", 31400, 18900, "Y", "NADA; DMV", "Verified"),
          ("AS-A4", A, "BUSINESS_ASSET", "Business equipment", 22000, 0, "Y", "Depreciation schedule", "Unverified"),
          ("AS-A5", A, "RETIREMENT", "Retirement account", 26900, 0, "Y", "Taxpayer statement", "Unverified"),
          ("AS-A6", A, "BROKERAGE", "Pinnacle Brokerage", 18700, 0, "Y", "1099-B; statement", "Partial")]:
    add("tp_asset", asset_id=a[0], owner_tin_token=a[1], asset_type=a[2], description=a[3], fmv=a[4], encumbrance=a[5],
        equity=a[4] - a[5], disclosed_on_433=a[6], source=a[7], verified=a[8])
for b in [("BA-A1", "Cascade Mutual Bank", "CHECKING", "4417", 3210, "1099-INT; Form 433-A", "Y"),
          ("BA-A2", "Harbor Trust Savings", "SAVINGS", "9902", 28400, "1099-INT only", "N"),
          ("BA-A3", "Meridian Credit Union", "BUSINESS_CHECKING", "1180", 6750, "Accurint; processor records", "N"),
          ("BA-A4", "Pinnacle Brokerage", "INVESTMENT", "3345", 18700, "1099-B", "Y")]:
    add("tp_bank_account", account_id=b[0], tin_token=A, institution=b[1], account_type=b[2], acct_last4=b[3],
        balance=b[4], source=b[5], disclosed_on_433=b[6])

irn = 0
def ir(tin, yr, form, box, payer_tok, payer, amt, note=""):
    global irn
    irn += 1
    add("tp_information_return", ir_id=f"IR{irn:06d}", tin_token=tin, tax_year=yr, form_type=form, box=box,
        payer_tin_token=payer_tok, payer_name=payer, amount=amt, note=note)

for i, amt in enumerate([71200, 58900, 41600, 26700], 1):
    ir(A, 2024, "1099-NEC", "1", f"PY10{i:03d}", f"Payer {i} (general contractor)", amt)
ir(A, 2024, "1099-K", "1a", "PY10010", "Payment processor", 43100)
ir(A, 2024, "1099-INT", "1", "PY10020", "Cascade Mutual Bank", 412)
ir(A, 2024, "1099-INT", "1", "PY10021", "Harbor Trust Savings", 1840)
ir(A, 2024, "1098", "1", "PY10030", "Pinnacle Home Loans", 11260, "Residence")
ir(A, 2024, "1099-B", "1d", "PY10040", "Pinnacle Brokerage", 26400, "Box B: noncovered, basis not reported")
ir(A, 2024, "K-1 (1065)", "2", "TK900001", "Latimer Grove Holdings LLC", 31800, "Net rental real estate income")

rel = 0
def relate(a, b, typ, pct="", s="", e="", src=""):
    global rel
    rel += 1
    add("tp_relationship", rel_id=f"RL{rel:05d}", from_id=a, to_id=b, rel_type=typ, pct=pct, start_date=s, end_date=e, source=src)

relate(A, "TK900001", "MEMBER", 40, "2023-01-01", src="K-1; Accurint")
relate("TK100050", "TK900001", "MEMBER", 60, "2023-01-01", src="K-1")
relate("TK100002", A, "FORMER_SPOUSE", "", "2010-06-12", "2023-02-01", "Filed returns; Accurint")
relate("TK100050", "TK900002", "RESPONSIBLE_PERSON", "", "2019-01-01", src="Form 4180 interview")
relate(A, "AS-A2", "OWNED", "", "2017-05-01", "2025-09-22", "County records")
relate("TK900001", "AS-A2", "OWNS", "", "2025-09-22", src="County records")
add("tp_transfer", transfer_id="TR-A1", asset_id="AS-A2", from_tin_token=A, to_tin_token="TK900001", transfer_date="2025-09-22",
    fmv_at_transfer=268000, consideration=0, source="County records; Accurint")

# Harborline: trust fund case to give the graph a second hop
add("tp_tax_module", module_id="TK900002-01-202503", tin_token="TK900002", mft=1, tax_period="202503", assessed_balance=88400,
    last_assessment_date="2025-07-14", csed="2035-07-14", module_status="26")
add("tp_compliance_episode", episode_id="EP-HF-FIELD", tin_token="TK900002", episode_type="FIELD_COLLECTION",
    episode_subtype="Trust fund", opened_date="2025-09-02", closed_date="", status="OPEN", module_ids="TK900002-01-202503")

# ----------------------------------------------------------------------------------------------
# RVE: Case A snapshots and lines
# ----------------------------------------------------------------------------------------------
def snapshot(sid, tin, version, basis, tc, created, by, status):
    add("tp_return_snapshot", snapshot_id=sid, tin_token=tin, mft=30, tax_period="202412", version_type=version,
        basis_snapshot_id=basis, source_tc=tc, created_date=created, created_by=by, status=status)

def line(sid, form, ln, sub, desc, el, amt, origin, mod, review=""):
    add("tp_return_line", snapshot_id=sid, form=form, line=ln, sub_id=sub, line_desc=desc, mef_element=el, amount=amt,
        data_origin=origin, modifiable=mod, review_state=review)

def lines_from_tax(sid, tax, origin):
    for key, form, ln, el, mod in H.L1040:
        line(sid, form, ln, "", key.split(" ", 1)[1], el, tax[key], origin, mod)

snapshot("SN-A1", A, "AS_FILED", "", "150", "2025-04-14", "MeF", "POSTED")
snapshot("SN-A2", A, "RVE_WORKING", "SN-A1", "", "2026-08-12", "A. Whitfield", "WORKING")
snapshot("SN-A3", A, "PROPOSED", "SN-A2", "", "2026-09-30", "A. Whitfield", "ISSUED")
snapshot("SN-A4", A, "AS_EXAMINED", "SN-A3", "300", "2026-10-26", "Master File", "POSTED")
for sid in ["SN-A1", "SN-A2"]:
    lines_from_tax(sid, H.A_TAX_FILED, "MEF")
    for f, ln, desc, el, amt, mod, sub in H.A_SCH["filed"]:
        line(sid, f, ln, sub, desc, el, amt, "MEF", mod)
for f, ln, desc, amt, sub in H.A_SCH["part_v"]:
    line("SN-A2", f, ln, sub, desc, "", amt, "ATTACHMENT_EXTRACT", "Y", "CONFIRMED")
adj_map_a = {(f, ln): new for f, ln, _, _, new in H.A_ADJUSTMENTS}
for sid in ["SN-A3", "SN-A4"]:
    lines_from_tax(sid, H.A_TAX_ADJ, "COMPUTED")
    for f, ln, desc, el, amt, mod, sub in H.A_SCH["filed"]:
        new = adj_map_a.get((f, ln))
        if (f, ln) == ("SCH_B", "1"):
            line(sid, f, ln, sub, desc, el, amt, "MEF", mod)
            line(sid, "SCH_B", "1", "HARBOR_TRUST", "Interest — Harbor Trust Savings", "InterestAmt", 1840, "EXAMINER_ADJUSTMENT", "Y")
            continue
        if (f, ln) == ("SCH_C", "28"):
            new = 151800
        if (f, ln) == ("SCH_SE", "12"):
            new = H.A_TAX_ADJ["_se_tax"]
        line(sid, f, ln, sub, desc, el, amt if new is None else new,
             "MEF" if new is None else ("EXAMINER_ADJUSTMENT" if mod == "Y" else "COMPUTED"), mod)
    for f, ln, desc, amt, sub in H.A_SCH["part_v"]:
        allowed = {"48a": 0, "48b": 1400, "48c": 4300, "48d": 0}[ln]
        line(sid, f, ln, sub, desc + (" (moved to line 11)" if ln == "48a" else ""), "", allowed, "EXAMINER_ADJUSTMENT", "Y", "CONFIRMED")

HERO_RC = {"F-A1": ("IRP_MISMATCH", "TAXPAYER_ISSUE", "IR03"), "F-A2": ("IRP_MISMATCH", "IRP_LIMITATION", "IR18"),
           "F-A3": ("IRP_MISMATCH", "MATCHED", "IR12"), "F-A4": ("DATA_GAP", "MEF_DATA_GAP", "EX_SCHC_OTHER_EXP"),
           "F-A5": ("IRP_MISMATCH", "MATCHED", "IR23"), "F-A6": ("IRP_MISMATCH", "MATCHED", ""),
           "F-B1": ("DATA_GAP", "MEF_DATA_GAP", "EX_REP_469C7"), "F-B2": ("IRP_MISMATCH", "MATCHED", "IR21"),
           "F-B3": ("IRP_MISMATCH", "MATCHED", "IR12"), "F-B4": ("IRP_MISMATCH", "MATCHED", "IR01"), "F-B5": ("IRP_MISMATCH", "MATCHED", "")}
for fid, src, item, irp, ref, ret_amt, br, disp, note in H.A_FINDINGS:
    vt, rc, ic = HERO_RC[fid]
    add("tp_rri_finding", finding_id=fid, snapshot_id="SN-A2", tin_token=A, tax_period="202412", source=src, item=item,
        irp_amount=irp if irp is not None else "", return_ref=ref, return_amount=ret_amt if ret_amt is not None else "",
        delta=(ret_amt - irp) if (irp is not None and ret_amt is not None) else "", branch=br, disposition=disp, note=note,
        variance_type=vt, root_cause=rc, issue_code=ic)
for x in H.A_IDR:
    add("tp_idr", idr_id=x["idr_id"], episode_id="EP-A-EX24", tin_token=A, form=x["form"], issued_date=x["issued"],
        due_date=x["due"], response_date=x["response"], recipient=x["to"], status=x["status"], item_count=len(x["items"]),
        items=" | ".join(x["items"]))

adj_n = 0
HERO_ADJ_ISSUE = {("SCH_B", "2"): ("I-A1", "IR03", "IRP_MATCH"), ("SCH_C", "11"): ("I-A2", "EX_SCHC_OTHER_EXP", "RVE_ATTACHMENT_EXTRACT"),
                  ("SCH_C", "27a"): ("I-A2", "EX_SCHC_OTHER_EXP", "RVE_ATTACHMENT_EXTRACT"), ("SCH_C", "31"): ("I-A2", "EX_SCHC_OTHER_EXP", "RVE_ATTACHMENT_EXTRACT")}
def adjustments(prefix, ep, sid, tin, schedule_adj, tax_f, tax_a):
    global adj_n
    for f, ln, desc, old, new in schedule_adj:
        adj_n += 1
        iid, ic, how = HERO_ADJ_ISSUE.get((f, ln), ("I-B1", "EX_REP_469C7", "RRI_RECOMPUTE_VARIANCE") if tin == H.B["tin"] else ("", "", ""))
        add("tp_adjustment", adjustment_id=f"{prefix}{adj_n:03d}", episode_id=ep, snapshot_id=sid, tin_token=tin,
            tax_period="202412", form=f, line=ln, line_desc=desc, as_filed=old, adjustment=new - old, as_adjusted=new,
            adjustment_kind="EXAMINER", issue_id=iid, issue_code=ic, detection_source=how)
    for key, form, ln, el, mod in H.L1040:
        if tax_f[key] != tax_a[key]:
            adj_n += 1
            add("tp_adjustment", adjustment_id=f"{prefix}{adj_n:03d}", episode_id=ep, snapshot_id=sid, tin_token=tin,
                tax_period="202412", form=form, line=ln, line_desc=key.split(" ", 1)[1], as_filed=tax_f[key],
                adjustment=tax_a[key] - tax_f[key], as_adjusted=tax_a[key], adjustment_kind="COMPUTED")

adjustments("ADJ-A", "EP-A-EX24", "SN-A3", A, H.A_ADJUSTMENTS, H.A_TAX_FILED, H.A_TAX_ADJ)

# ==============================================================================================
# HERO B  Thornbury
# ==============================================================================================
B, B2 = H.B["tin"], "TK200002"
add("tp_taxpayer", tin_token=B, tin_type="SSN", display_name="Marcus Thornbury", entity_type="INDIVIDUAL", filing_status="MFJ",
    city="Seattle", state="WA", poa_on_file="N", case_group="HERO_B")
add("tp_taxpayer", tin_token=B2, tin_type="SSN", display_name="Elena Thornbury", entity_type="INDIVIDUAL", filing_status="MFJ",
    city="Seattle", state="WA", poa_on_file="N", case_group="HERO_B")
for tok, nm in [("TK900010", "Pugetview Property Management LLC"), ("TK900011", "Northbeam Realty Inc"), ("TK900012", "Lumenfield Software Inc")]:
    add("tp_taxpayer", tin_token=tok, tin_type="EIN", display_name=nm, entity_type="CORPORATION" if "Inc" in nm else "PARTNERSHIP",
        filing_status="", city="Seattle", state="WA", poa_on_file="N", case_group="HERO_B")
add("tp_tax_module", module_id=f"{B}-30-202412", tin_token=B, mft=30, tax_period="202412", assessed_balance=0,
    last_assessment_date="2025-04-28", csed="", module_status="10")
add("tp_compliance_episode", episode_id="EP-B-EX24", tin_token=B, episode_type="EXAM", episode_subtype="Field",
    opened_date="2026-05-04", closed_date="", status="UNAGREED_PROTEST", module_ids=f"{B}-30-202412")
add("tp_treatment_assignment", episode_id="EP-B-EX24", function="Examination", assignee="D. Castellanos", start_date="2026-05-04", end_date="")
add("tp_statutory_clock", clock_id="CL-B-ASED-2024", tin_token=B, module_id=f"{B}-30-202412", episode_id="EP-B-EX24",
    clock_type="ASED", start_date="2025-04-15", expiry_date="2028-04-15", suspended_ind="N", authority="IRC 6501(a)")
mb = f"{B}-30-202412"
contact(B, mb, "EP-B-EX24", "LETTER", "Letter 2205", "EXAM", "N", "2026-05-04")
contact(B, mb, "EP-B-EX24", "IDR", "Form 4564", "EXAM", "N", "2026-05-11", due="2026-06-10", recv="2026-06-08")
contact(B, mb, "EP-B-EX24", "IDR", "Form 4564", "EXAM", "N", "2026-06-22", due="2026-07-13", recv="2026-07-10")
contact(B, mb, "EP-B-EX24", "LETTER", "Letter 950", "EXAM", "N", "2026-09-28", due="2026-10-28", recv="2026-10-26")
add("tp_issue", issue_id="I-B1", episode_id="EP-B-EX24", tin_token=B, tax_period="202412", issue_code="EX_REP_469C7",
    description="Rental losses claimed as nonpassive under the real estate professional rule", return_ref="SCH_E 43",
    amount_claimed=-64000, amount_proposed=50000, amount_sustained="", status="UNAGREED", detection_source="RRI_RECOMPUTE_VARIANCE", hours_charged=34.0)
for x in H.B_DETERMINATIONS:
    add("tp_determination", determination_id=x["det_id"], episode_id="EP-B-EX24", issue_id=x["issue_id"], tin_token=B,
        determination_type="EXAM_ISSUE", outcome=x["outcome"], amount=x["amount"], authority=x["authority"],
        decided_date="2026-09-28", detail=x["detail"])
for i, (sub, addr, rents, exp, net, hrs, mgr) in enumerate(H.B_PROPS, 1):
    add("tp_asset", asset_id=f"AS-B{i}", owner_tin_token=B, asset_type="RENTAL_PROPERTY", description=addr, fmv=[612000, 455000, 780000][i - 1],
        encumbrance=[401000, 322000, 590000][i - 1], equity=[211000, 133000, 190000][i - 1], disclosed_on_433="", source="County assessor", verified="Verified")
    if mgr != "Self-managed":
        relate("TK900010", f"AS-B{i}", "MANAGES", "", "2021-01-01", src="Management agreement (IDR-B1)")
relate(B, B2, "SPOUSE", "", "2012-08-18", src="Filed returns")
relate(B2, "TK900011", "AGENT_AT", "", "2018-03-01", src="1099-NEC; licensing")
relate(B, "TK900012", "EMPLOYEE_OF", "", "2016-01-01", src="W-2")
ir(B, 2024, "W-2", "1", "TK900012", "Lumenfield Software Inc", 182000, "Box 2 withholding 29,800")
ir(B2, 2024, "1099-NEC", "1", "TK900011", "Northbeam Realty Inc", 96000)
ir(B, 2024, "1099-MISC", "1", "TK900010", "Pugetview Property Management LLC", 69000, "Rents — Delridge and Burien")
ir(B, 2024, "1099-INT", "1", "PY20020", "Sound Credit Union", 1150)
ir(B, 2024, "1098", "1", "PY20030", "Evergreen Mortgage", 18600, "Residence")

snapshot("SN-B1", B, "AS_FILED", "", "150", "2025-04-15", "MeF", "POSTED")
snapshot("SN-B2", B, "RVE_WORKING", "SN-B1", "", "2026-05-06", "D. Castellanos", "WORKING")
snapshot("SN-B3", B, "PROPOSED", "SN-B2", "", "2026-09-28", "D. Castellanos", "ISSUED")
for sid in ["SN-B1", "SN-B2"]:
    lines_from_tax(sid, H.B_TAX_FILED, "MEF")
    for f, ln, desc, el, amt, mod, sub in H.B_SCH["filed"]:
        line(sid, f, ln, sub, desc, el, amt, "MEF", mod)
# RVE supplements: data MeF cannot carry
line("SN-B2", "RVE_SUPP", "ELECTION_469_9G", "", "Aggregation election statement on file (1 = yes, 0 = none found)", "", 0, "RVE_SUPPLEMENT", "Y", "CONFIRMED")
for sub, addr, rents, exp, net, hrs, mgr in H.B_PROPS:
    line("SN-B2", "RVE_SUPP", "PARTICIPATION_HOURS", sub, f"Elena's 2024 hours — {addr} ({mgr})", "", hrs, "RVE_SUPPLEMENT", "Y", "CONFIRMED")
line("SN-B2", "RVE_SUPP", "REP_SERVICES_HOURS", "NORTHBEAM", "Elena's 2024 hours in real estate brokerage", "", 1450, "RVE_SUPPLEMENT", "Y", "CONFIRMED")
lines_from_tax("SN-B3", H.B_TAX_ADJ, "COMPUTED")
adj_b = {("SCH_E", "21", "R2_DELRIDGE"): 0, ("SCH_E", "21", "R3_BURIEN"): 0, ("SCH_E", "26", ""): -14000, ("SCH_E", "43", ""): -14000}
for f, ln, desc, el, amt, mod, sub in H.B_SCH["filed"]:
    new = adj_b.get((f, ln, sub))
    line("SN-B3", f, ln, sub, desc + (" (passive — suspended)" if new == 0 else ""), el, amt if new is None else new,
         "MEF" if new is None else ("EXAMINER_ADJUSTMENT" if mod == "Y" or ln == "21" else "COMPUTED"), mod)
line("SN-B3", "F8582", "CARRYOVER", "R2_DELRIDGE", "Suspended passive loss to 2025 — Delridge", "", 17000, "EXAMINER_ADJUSTMENT", "Y")
line("SN-B3", "F8582", "CARRYOVER", "R3_BURIEN", "Suspended passive loss to 2025 — Burien", "", 33000, "EXAMINER_ADJUSTMENT", "Y")
for fid, src, item, irp, ref, ret_amt, br, disp, note in H.B_FINDINGS:
    vt, rc, ic = HERO_RC[fid]
    add("tp_rri_finding", finding_id=fid, snapshot_id="SN-B2", tin_token=B, tax_period="202412", source=src, item=item,
        irp_amount=irp if irp is not None else "", return_ref=ref, return_amount=ret_amt if ret_amt is not None else "",
        delta=(ret_amt - irp) if (irp is not None and ret_amt is not None) else "", branch=br, disposition=disp, note=note,
        variance_type=vt, root_cause=rc, issue_code=ic)
for x in H.B_IDR:
    add("tp_idr", idr_id=x["idr_id"], episode_id="EP-B-EX24", tin_token=B, form=x["form"], issued_date=x["issued"],
        due_date=x["due"], response_date=x["response"], recipient=x["to"], status=x["status"], item_count=len(x["items"]),
        items=" | ".join(x["items"]))
adjustments("ADJ-B", "EP-B-EX24", "SN-B3", B, H.B_ADJUSTMENTS, H.B_TAX_FILED, H.B_TAX_ADJ)

# ==============================================================================================
# FILLERS: ~120 individuals and 24 entities so Genie and the signals have a population
# ==============================================================================================
FIRST = "Avery Blake Carmen Dario Elise Felix Gwen Hector Iris Jonah Kira Luis Mona Nolan Opal Pavel Quinn Rosa Silas Tess Umar Vera Wes Xena Yusuf Zara".split()
LAST = "Ashby Brennan Calloway Dunmore Ellery Faraday Galloway Hartwell Ingram Jessup Kendrick Lockhart Merriweather Northcott Oakes Prescott Quill Radcliffe Sterling Thackeray Underhill Vance-Ortiz Whitlock Yardley".split()
CITIES = [("Spokane", "WA"), ("Tacoma", "WA"), ("Bellingham", "WA"), ("Yakima", "WA"), ("Portland", "OR"), ("Boise", "ID"), ("Eugene", "OR")]
ENT = "Cedar Bluff Builders|Ironwood Logistics|Salish Coast Seafood|Tumwater Tile|Ridgeline Dental Group|Pacific Crest Holdings|Copperline Electric|Olympic Range Partners|Kitsap Marine Supply|Bluewater Staffing|Evergreen Paving|Northgate Clinics|Skagit Valley Farms|Quarry Hill LLC|Larkspur Ventures|Fernhill Rentals|Sound Freight|Highline Roofing|Cascadia Coatings|Rainier Fitness|Mason Creek Lumber|Driftwood Hospitality|Summit Ridge Partners|Puget Precision".split("|")

ents = []
for i, nm in enumerate(ENT, 1):
    tok = f"TK8{i:05d}"
    kind = "PARTNERSHIP" if any(w in nm for w in ["Holdings", "Partners", "LLC", "Ventures", "Rentals"]) else "CORPORATION"
    c = rng.choice(CITIES)
    add("tp_taxpayer", tin_token=tok, tin_type="EIN", display_name=nm + (" LLC" if kind == "PARTNERSHIP" and "LLC" not in nm else " Inc" if kind == "CORPORATION" else ""),
        entity_type=kind, filing_status="", city=c[0], state=c[1], poa_on_file="N", case_group="FILLER")
    ents.append((tok, kind))
    if kind == "CORPORATION" and rng.random() < 0.55:
        q = rng.choice(["202403", "202406", "202409", "202412", "202503"])
        add("tp_tax_module", module_id=f"{tok}-01-{q}", tin_token=tok, mft=1, tax_period=q, assessed_balance=rng.randrange(12000, 160000, 100),
            last_assessment_date="2025-06-30", csed="2035-06-30", module_status="26")
        add("tp_compliance_episode", episode_id=f"EP-{tok}-FC", tin_token=tok, episode_type="FIELD_COLLECTION", episode_subtype="Trust fund",
            opened_date="2025-08-15", closed_date="", status="OPEN", module_ids=f"{tok}-01-{q}")
corp_with_bal = {r["tin_token"] for r in T["tp_tax_module"] if r["mft"] == 1 and r["assessed_balance"] > 0}
partnerships = [t for t, k in ents if k == "PARTNERSHIP"]
corps = [t for t, k in ents if k == "CORPORATION"]

n_ind = 120
ep_n = 0
for i in range(1, n_ind + 1):
    tok = f"TK3{i:05d}"
    c = rng.choice(CITIES)
    fs = rng.choice(["S", "S", "MFJ", "MFJ", "HOH"])
    add("tp_taxpayer", tin_token=tok, tin_type="SSN", display_name=f"{rng.choice(FIRST)} {rng.choice(LAST)}", entity_type="INDIVIDUAL",
        filing_status=fs, city=c[0], state=c[1], poa_on_file=rng.choice("YNNN"), case_group="FILLER")
    nmods = rng.choice([0, 0, 1, 2, 3, 4])
    mids, total = [], 0
    for y in rng.sample(range(2017, 2024), nmods):
        bal = rng.randrange(1500, 60000, 5)
        total += bal
        mid = f"{tok}-30-{y}12"
        mids.append(mid)
        add("tp_tax_module", module_id=mid, tin_token=tok, mft=30, tax_period=f"{y}12", assessed_balance=bal,
            last_assessment_date=f"{y + 1}-06-01", csed=f"{y + 11}-06-01", module_status=rng.choice(["21", "22", "24", "26"]))
    mods = ";".join(mids)
    has_oic = has_pp = False
    if mids:
        if rng.random() < 0.45:
            add("tp_compliance_episode", episode_id=f"EP-{tok}-ACS", tin_token=tok, episode_type="ACS", episode_subtype="Status 22",
                opened_date="2025-07-01", closed_date="", status="OPEN", module_ids=mods)
        k = rng.choice([0, 0, 1, 2, 2])
        for j in range(k):
            closed = AS_OF - timedelta(days=rng.choice([120, 300, 500, 700, 900]))
            add("tp_compliance_episode", episode_id=f"EP-{tok}-IA{j + 1}", tin_token=tok, episode_type="IA", episode_subtype="Streamlined",
                opened_date=iso(closed - timedelta(days=200)), closed_date=iso(closed), status=rng.choice(["DEFAULTED", "DEFAULTED", "PAID_IN_FULL"]), module_ids=mods)
        if total > 65000 and rng.random() < 0.6:
            has_pp = True
            add("tp_compliance_episode", episode_id=f"EP-{tok}-PP", tin_token=tok, episode_type="PASSPORT", episode_subtype="IRC 7345",
                opened_date="2025-11-01", closed_date="", status="CERTIFIED", module_ids=mods)
        if rng.random() < 0.18:
            has_oic = True
            opened = AS_OF - timedelta(days=rng.randrange(30, 400))
            add("tp_compliance_episode", episode_id=f"EP-{tok}-OIC", tin_token=tok, episode_type="OIC", episode_subtype="Doubt as to collectibility",
                opened_date=iso(opened), closed_date="", status="INVESTIGATION", module_ids=mods)
            add("tp_procedural_overlay", overlay_id=f"OV-{tok}", tin_token=tok, episode_id=f"EP-{tok}-OIC", overlay_type="OIC_PENDING",
                effect="Levy barred; CSED suspended", authority="IRC 6331(k)", start_date=iso(opened), end_date="")
            for b in range(rng.choice([1, 2, 3])):
                add("tp_bank_account", account_id=f"BA-{tok}-{b}", tin_token=tok, institution=rng.choice(["Columbia Bank", "Spokane Teachers CU", "Umpqua", "Banner Bank", "Wheatland Bank"]),
                    account_type=rng.choice(["CHECKING", "SAVINGS"]), acct_last4=f"{rng.randrange(1000, 9999)}", balance=rng.randrange(200, 40000, 10),
                    source=rng.choice(["1099-INT", "Form 433-A", "Accurint"]), disclosed_on_433=rng.choice("YYYN"))
            # transfers: some related, some unrelated, some too early
            if rng.random() < 0.6:
                aid = f"AS-{tok}-T"
                fmv = rng.randrange(80000, 420000, 1000)
                add("tp_asset", asset_id=aid, owner_tin_token=tok, asset_type="REAL_PROPERTY", description="Transferred parcel", fmv=fmv, encumbrance=0,
                    equity=fmv, disclosed_on_433="N", source="County records", verified="Verified")
                to = rng.choice(partnerships)
                related = rng.random() < 0.6
                if related:
                    relate(tok, to, "MEMBER", rng.choice([20, 25, 50]), "2021-01-01", src="K-1")
                days_before = rng.choice([60, 200, 500, 900])
                add("tp_transfer", transfer_id=f"TR-{tok}", asset_id=aid, from_tin_token=tok, to_tin_token=to,
                    transfer_date=iso(opened - timedelta(days=days_before)), fmv_at_transfer=fmv,
                    consideration=rng.choice([0, 0, round(fmv * 0.05), fmv]), source="County records")
            # entity interest via K-1, sometimes not on the 433
            if rng.random() < 0.4:
                ent = rng.choice(partnerships)
                relate(tok, ent, "MEMBER", rng.choice([10, 33, 50]), "2022-01-01", src="K-1")
                ir(tok, 2024, "K-1 (1065)", "1", ent, "Partnership", rng.randrange(2000, 40000, 100))
                if rng.random() < 0.5:
                    add("tp_asset", asset_id=f"AS-{tok}-EI", owner_tin_token=tok, asset_type="ENTITY_INTEREST", description=f"Interest in {ent}",
                        fmv=rng.randrange(5000, 90000, 500), encumbrance=0, equity=0, disclosed_on_433="Y", source="Form 433-A", verified="Unverified")
    # responsible persons
    if rng.random() < 0.10:
        for ent in rng.sample(corps, rng.choice([1, 2, 2])):
            relate(tok, ent, "RESPONSIBLE_PERSON", "", "2020-01-01", src="Form 4180 interview")
    # a few returns through RVE
    if rng.random() < 0.17:
        sid = f"SN-{tok}-1"
        snapshot(sid, tok, "AS_FILED", "", "150", "2025-04-15", "MeF", "POSTED")
        line(sid, "1040", "1z", "", "wages", "WagesAmt", rng.randrange(30000, 160000, 100), "MEF", "N")
        rep = rng.random() < 0.3
        if rep:
            line(sid, "SCH_E", "43", "", "Real estate professional — net loss", "RealEstateProfessionalAmt", -rng.randrange(8000, 70000, 100), "MEF", "Y")
            sid2 = f"SN-{tok}-2"
            snapshot(sid2, tok, "RVE_WORKING", sid, "", "2026-07-01", "Examiner", "WORKING")
            line(sid2, "RVE_SUPP", "ELECTION_469_9G", "", "Aggregation election statement on file", "", rng.choice([0, 1]), "RVE_SUPPLEMENT", "Y", "CONFIRMED")
        if rng.random() < 0.5:
            amt = rng.randrange(300, 9000, 10)
            add("tp_rri_finding", finding_id=f"F-{tok}-1", snapshot_id=sid, tin_token=tok, tax_period="202412", source="IRP",
                item="1099-INT · Credit union", irp_amount=amt, return_ref="SCH_B 2", return_amount=0, delta=-amt, branch="A",
                disposition="UNREPORTED_INCOME", note="Payer not on Schedule B", variance_type="IRP_MISMATCH", root_cause="TAXPAYER_ISSUE", issue_code="IR03")
        else:
            add("tp_rri_finding", finding_id=f"F-{tok}-1", snapshot_id=sid, tin_token=tok, tax_period="202412", source="IRP",
                item="1099-B · Brokerage (noncovered)", irp_amount=12000, return_ref="F8949 1d", return_amount=12000, delta=0, branch="B",
                disposition="NOT_A_TAXPAYER_ISSUE", note="Basis reported on 8949", variance_type="IRP_MISMATCH", root_cause="IRP_LIMITATION", issue_code="IR18")

# ==============================================================================================
# CLOSED CASES (v0.2) + hero A 2024 closure + reference tables
# ==============================================================================================
add("tp_case_closure", episode_id="EP-A-EX24", tin_token=A, tax_period="202412", program="CORRESPONDENCE", selection_source="REFERRAL",
    outcome="AGREED", closed_date="2026-10-26", closing_tc="300", deficiency=H.A_DEFICIENCY, penalty_code="", penalty_amount=0,
    appeals_outcome="", agreed_ind="Y", total_hours=8.0, issue_count=2, adjusted_issue_count=2, aims_disposal_code="",
    computation_note="POC simplified engine, TY2024")
add("tp_tax_computation", episode_id="EP-A-EX24", tin_token=A, tax_period="202412", filing_status_filed="HOH", filing_status_examined="HOH",
    **{f"{k}_{v}": t[key] for v, t in (("filed", H.A_TAX_FILED), ("examined", H.A_TAX_ADJ)) for k, key in closed_cases.TAXCOMP},
    deficiency=H.A_DEFICIENCY, penalty_amount=0, computation_engine="POC simplified engine, TY2024 parameters",
    interest_note="Interest computed at assessment; not modeled")
cc_counts = closed_cases.generate(dict(add=add, rng=rng, AS_OF=AS_OF, iso=iso))
for code, v in ISSUE_CODES.items():
    add("tp_issue_code", issue_code=code, issue_name=v[0], category=v[1], program=v[2], source_form=v[3], irc_reference=v[4], reference_note=v[5])
    for i, (f, ln, el, eff, role, note) in enumerate(ISSUE_LINE_MAP[code], 1):
        add("tp_issue_line_map", issue_code=code, seq=i, form=f, line=ln, mef_element=el, effect=eff, role=role, note=note)
for r in LINE_CATALOG:
    add("tp_line_catalog", **dict(zip(COLS["tp_line_catalog"].split(","), r)))
for rc, (br, desc) in ROOT_CAUSES.items():
    add("tp_root_cause", root_cause=rc, branch=br, description=desc)

# ==============================================================================================
# ANSWER KEY: expected signals computed in Python (independent of the SQL rules)
# ==============================================================================================
def signals():
    out = set()
    ep = T["tp_compliance_episode"]
    open_oic = {e["tin_token"]: d(e["opened_date"]) for e in ep if e["episode_type"] == "OIC" and not e["closed_date"]}
    certified = {e["tin_token"] for e in ep if e["episode_type"] == "PASSPORT" and e["status"] == "CERTIFIED" and not e["closed_date"]}
    for b in T["tp_bank_account"]:
        if b["disclosed_on_433"] == "N" and b["tin_token"] in open_oic:
            out.add((b["tin_token"], "SG01_UNDISCLOSED_BANK_ACCOUNT"))
    pairs = {(r["from_id"], r["to_id"]) for r in T["tp_relationship"]}
    for t in T["tp_transfer"]:
        f, to = t["from_tin_token"], t["to_tin_token"]
        if f in open_oic and ((f, to) in pairs or (to, f) in pairs):
            gap = (open_oic[f] - d(t["transfer_date"])).days
            if 0 <= gap <= 730 and t["consideration"] < 0.10 * t["fmv_at_transfer"]:
                out.add((f, "SG02_RELATED_PARTY_TRANSFER_BEFORE_OFFER"))
    for t in certified & set(open_oic):
        out.add((t, "SG03_PASSPORT_REVERSAL_TRIGGER_ARMED"))
    for o in T["tp_procedural_overlay"]:
        if o["overlay_type"] == "OIC_PENDING" and not o["end_date"]:
            out.add((o["tin_token"], "SG04_LEVY_BARRED_OIC_PENDING"))
    from collections import Counter
    c = Counter(e["tin_token"] for e in ep if e["episode_type"] == "IA" and e["status"] == "DEFAULTED"
                and e["closed_date"] and (AS_OF - d(e["closed_date"])).days <= 730)
    for t, n in c.items():
        if n >= 2:
            out.add((t, "SG05_REPEAT_IA_DEFAULT"))
    for f in T["tp_rri_finding"]:
        if f["disposition"] == "UNREPORTED_INCOME" and int(f["tax_period"]) >= 202412:
            out.add((f["tin_token"], "SG06_IRP_INCOME_UNREPORTED"))
    snaps = {s["snapshot_id"]: s for s in T["tp_return_snapshot"]}
    rep = {snaps[l["snapshot_id"]]["tin_token"] for l in T["tp_return_line"]
           if l["form"] == "SCH_E" and l["line"] == "43" and l["amount"] != 0 and snaps[l["snapshot_id"]]["version_type"] == "AS_FILED"}
    elected = {snaps[l["snapshot_id"]]["tin_token"] for l in T["tp_return_line"] if l["line"] == "ELECTION_469_9G" and l["amount"] == 1}
    for t in rep - elected:
        out.add((t, "SG07_REP_CLAIM_NO_AGGREGATION_ELECTION"))
    rp = {}
    for r in T["tp_relationship"]:
        if r["rel_type"] == "RESPONSIBLE_PERSON" and (r["to_id"] in corp_with_bal or r["to_id"] == "TK900002"):
            rp.setdefault(r["from_id"], set()).add(r["to_id"])
    # TK900002 (Harborline) has a balance module; corp_with_bal was computed before heroes? include all MFT 01 balances
    bal01 = {m["tin_token"] for m in T["tp_tax_module"] if m["mft"] == 1 and m["assessed_balance"] > 0}
    rp = {}
    for r in T["tp_relationship"]:
        if r["rel_type"] == "RESPONSIBLE_PERSON" and r["to_id"] in bal01:
            rp.setdefault(r["from_id"], set()).add(r["to_id"])
    for p, es in rp.items():
        if len(es) >= 2:
            out.add((p, "SG08_RESPONSIBLE_PERSON_MULTIPLE_ENTITIES"))
    entity_assets = {(a["owner_tin_token"], a["description"].replace("Interest in ", "")) for a in T["tp_asset"] if a["asset_type"] == "ENTITY_INTEREST"}
    members = {(r["from_id"], r["to_id"]) for r in T["tp_relationship"] if r["rel_type"] == "MEMBER"}
    for i in T["tp_information_return"]:
        if i["form_type"].startswith("K-1") and i["tin_token"] in open_oic and (i["tin_token"], i["payer_tin_token"]) in members \
                and (i["tin_token"], i["payer_tin_token"]) not in entity_assets:
            out.add((i["tin_token"], "SG09_ENTITY_INTEREST_NOT_ON_433"))
    yrs = {}
    for i in T["tp_issue"]:
        if i["status"] == "ADJUSTED" and i["issue_code"]:
            yrs.setdefault((i["tin_token"], i["issue_code"]), set()).add(int(str(i["tax_period"])[:4]))
    for (t, code), ys in yrs.items():
        ys = sorted(ys)
        if any(b - a <= 5 for a, b in zip(ys, ys[1:])):
            out.add((t, "SG10_REPEAT_ISSUE"))
    return sorted(out)

SIG = signals()

# Give one filler a second responsible-person link to Harborline so SG08 also fires on a hero-graph node
# (R. Latimer is linked to Harborline only; add a second company for him to make the 3-hop story)
relate("TK100050", corps[0], "RESPONSIBLE_PERSON", "", "2021-01-01", src="Form 4180 interview")
if corps[0] not in {m["tin_token"] for m in T["tp_tax_module"] if m["mft"] == 1}:
    add("tp_tax_module", module_id=f"{corps[0]}-01-202412", tin_token=corps[0], mft=1, tax_period="202412", assessed_balance=41200,
        last_assessment_date="2025-05-19", csed="2035-05-19", module_status="26")
SIG = signals()

# ==============================================================================================
# WRITE
# ==============================================================================================
os.makedirs(DATA, exist_ok=True)
for name, rows in T.items():
    cols = COLS[name].split(",")
    with open(os.path.join(DATA, f"{name}.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="raise")
        w.writeheader()
        for r in rows:
            w.writerow({c: iso(r.get(c, "")) for c in cols})
with open(os.path.join(DATA, "tp_signal_answer_key.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["tin_token", "signal_id"])
    w.writerows(SIG)
with open(os.path.join(DATA, "tp_run_params.csv"), "w", newline="") as fh:
    fh.write("param,value\nas_of_date,%s\n" % H.AS_OF)

# ----------------------------------------------------------------------------------------------
# Scenario JSON for the walkthroughs
# ----------------------------------------------------------------------------------------------
def rows(table, **flt):
    return [r for r in T[table] if all(r.get(k) == v for k, v in flt.items())]

def neighborhood(center, hops=2):
    edges = T["tp_relationship"]
    names = {r["tin_token"]: r["display_name"] for r in T["tp_taxpayer"]}
    names.update({a["asset_id"]: a["description"] for a in T["tp_asset"]})
    nodes, frontier, keep = {center}, {center}, []
    for _ in range(hops):
        nxt = set()
        for e in edges:
            if e["from_id"] in frontier or e["to_id"] in frontier:
                if e not in keep:
                    keep.append(e)
                nxt |= {e["from_id"], e["to_id"]}
        frontier = nxt - nodes
        nodes |= nxt
    kinds = {r["tin_token"]: r["entity_type"] for r in T["tp_taxpayer"]}
    kinds.update({a["asset_id"]: "ASSET" for a in T["tp_asset"]})
    return dict(nodes=[dict(id=n, label=names.get(n, n), kind=kinds.get(n, ""), signals=[s for t, s in SIG if t == n]) for n in sorted(nodes)],
                edges=[dict(source=e["from_id"], target=e["to_id"], type=e["rel_type"], pct=e["pct"]) for e in keep])

def tax_table(f, a):
    return [dict(line=k.split(" ", 1)[0], desc=k.split(" ", 1)[1], filed=f[k], adjusted=a[k], delta=a[k] - f[k])
            for k, *_ in H.L1040]

def case_json(meta, tin, ep, sch, findings, idrs, dets, adjs, timeline, effects, tf, ta, deficiency, extra):
    sig_names = [s for t, s in SIG if t == tin]
    return dict(
        meta=meta, signals=sig_names, findings=[dict(zip(["id", "source", "item", "irp", "ref", "ret", "branch", "disposition", "note"], f)) for f in findings],
        snapshots=rows("tp_return_snapshot", tin_token=tin),
        lines={s["snapshot_id"]: rows("tp_return_line", snapshot_id=s["snapshot_id"]) for s in rows("tp_return_snapshot", tin_token=tin)},
        idrs=idrs, determinations=dets, adjustments=rows("tp_adjustment", tin_token=tin), timeline=timeline, effects=effects,
        tax=tax_table(tf, ta), deficiency=deficiency, episodes=rows("tp_compliance_episode", tin_token=tin),
        modules=rows("tp_tax_module", tin_token=tin), irp=rows("tp_information_return", tin_token=tin) + (rows("tp_information_return", tin_token="TK200002") if tin == B else []),
        clocks=rows("tp_statutory_clock", tin_token=tin), graph=neighborhood(tin, 3 if tin == A else 2),
        flags=[f for f in H.SME_FLAGS if meta["case_id"] in f[0]],
        prior=[dict(c, issues=[dict(code=i["issue_code"], name=ISSUE_CODES[i["issue_code"]][0], status=i["status"],
                                    sustained=i.get("amount_sustained", ""), how=i.get("detection_source", ""))
                               for i in rows("tp_issue", episode_id=c["episode_id"])])
               for c in sorted(rows("tp_case_closure", tin_token=tin), key=lambda c: str(c["tax_period"])) if c["episode_id"] not in (ep,)],
        **extra)

scen = dict(
    as_of=H.AS_OF,
    A=case_json(H.A, A, "EP-A-EX24", H.A_SCH, H.A_FINDINGS, H.A_IDR, H.A_DETERMINATIONS, H.A_ADJUSTMENTS, H.A_TIMELINE, H.A_EFFECTS,
                H.A_TAX_FILED, H.A_TAX_ADJ, H.A_DEFICIENCY,
                dict(accounts=rows("tp_bank_account", tin_token=A), assets=rows("tp_asset", owner_tin_token=A),
                     financial=rows("tp_financial_profile", tin_token=A), substantial=H.A_SUBSTANTIAL, agreed=True)),
    B=case_json(H.B, B, "EP-B-EX24", H.B_SCH, H.B_FINDINGS, H.B_IDR, H.B_DETERMINATIONS, H.B_ADJUSTMENTS, H.B_TIMELINE, H.B_EFFECTS,
                H.B_TAX_FILED, H.B_TAX_ADJ, H.B_DEFICIENCY,
                dict(props=[dict(zip(["sub", "addr", "rents", "exp", "net", "hours", "mgr"], p)) for p in H.B_PROPS],
                     assets=rows("tp_asset", owner_tin_token=B), substantial=H.B_SUBSTANTIAL,
                     penalty_if_asserted=H.B_PENALTY_IF_ASSERTED, agreed=False)),
    population=dict(taxpayers=len(T["tp_taxpayer"]), signals=len(SIG)),
)
os.makedirs(VIEWER, exist_ok=True)
with open(os.path.join(VIEWER, "scenarios.json"), "w") as fh:
    json.dump(scen, fh, indent=1, default=iso)

print({k: len(v) for k, v in T.items()})
from collections import Counter
print("signals:", Counter(s for _, s in SIG))
print("hero A:", [s for t, s in SIG if t == A])
print("hero B:", [s for t, s in SIG if t == B])
print("R. Latimer:", [s for t, s in SIG if t == "TK100050"])
print("closed cases:", cc_counts)
print("deficiency A", H.A_DEFICIENCY, "B", H.B_DEFICIENCY, "B substantial", H.B_SUBSTANTIAL)
