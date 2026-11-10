"""Closed-case population for the TP360 / RVE POC (v0.2).

Generates closed AUR, correspondence and field exam cases (TY2019-2023) for ~260 synthetic
individuals, plus the hero back-fill (Marisol's 2019 exam and 2021 AUR; the Thornburys' prior
no-change). Every case:

  issue code  ->  source line(s) via tp_issue_line_map  ->  engine recompute  ->  1040 lines

so deficiencies are computed, not invented. Prior years are computed with TY2024 parameters for
illustration (one engine, consistent results); a production view would recompute each year under
its own law through the calculator behind RVE.
"""
import copy
from datetime import date, timedelta

from tax_engine_ty2024 import compute
from reference_tables import ISSUE_CODES, ISSUE_LINE_MAP
import hero_cases as H

FS_CODE = {"S": 1, "MFJ": 2, "HOH": 4}  # MeF filing status codes (1 single, 2 MFJ, 4 HOH)

# Line descriptions for the primary line of each issue
LINE_DESC = {
    "IR01": "Wages (W-2)", "IR03": "Interest — unreported payer", "IR04": "Dividends — unreported payer",
    "IR10": "IRA distributions, taxable", "IR12": "Gross receipts (1099-NEC)", "IR18": "Proceeds (1099-B)",
    "IR21": "Rents received", "IR23": "K-1 income", "IR30": "Gross receipts (1099-K)",
    "EX_SCHC_GROSS_RCPTS": "Gross receipts (bank deposits)", "EX_SCHC_VEHICLE": "Car and truck expenses",
    "EX_SCHC_TRAVEL_MEALS": "Travel", "EX_SCHC_OTHER_EXP": "Other expenses", "EX_SCHC_DEPR_179": "Depreciation and section 179",
    "EX_HOME_OFFICE": "Business use of home", "EX_HOBBY_LOSS": "Net profit or loss", "EX_RENTAL_EXP": "Rental expenses",
    "EX_PAL_469": "Rental income or loss allowed", "EX_REP_469C7": "Real estate professional amount",
    "EX_FILING_STATUS": "Filing status (MeF code)", "EX_DEPENDENT_CTC": "Dependents claimed (count)",
    "EX_CHARITABLE": "Noncash contributions", "EX_MORTGAGE_INT": "Home mortgage interest",
}

# Weighted issue mix by program
MIX = {
    "AUR": [("IR12", 22), ("IR03", 14), ("IR10", 14), ("IR18", 12), ("IR30", 12), ("IR01", 10), ("IR04", 8), ("IR23", 5), ("IR21", 3)],
    "CORRESPONDENCE": [("EX_SCHC_OTHER_EXP", 18), ("EX_SCHC_VEHICLE", 14), ("EX_DEPENDENT_CTC", 14), ("EX_FILING_STATUS", 12),
                       ("EX_CHARITABLE", 12), ("EX_SCHC_TRAVEL_MEALS", 10), ("EX_HOME_OFFICE", 8), ("EX_MORTGAGE_INT", 6), ("EX_RENTAL_EXP", 6)],
    "FIELD": [("EX_SCHC_GROSS_RCPTS", 16), ("EX_SCHC_OTHER_EXP", 14), ("EX_SCHC_VEHICLE", 10), ("EX_SCHC_DEPR_179", 10), ("EX_HOBBY_LOSS", 8),
              ("EX_RENTAL_EXP", 10), ("EX_PAL_469", 10), ("EX_REP_469C7", 6), ("EX_HOME_OFFICE", 6), ("EX_SCHC_TRAVEL_MEALS", 6), ("EX_CHARITABLE", 4)],
}
OUTCOMES = {
    "AUR": [("AGREED", 55), ("DEFAULTED_SNOD", 25), ("NO_CHANGE", 20)],
    "CORRESPONDENCE": [("AGREED", 50), ("DEFAULTED_SNOD", 18), ("NO_CHANGE", 16), ("PARTIALLY_AGREED", 8), ("UNAGREED_APPEALS", 8)],
    "FIELD": [("AGREED", 48), ("NO_CHANGE", 14), ("PARTIALLY_AGREED", 14), ("UNAGREED_APPEALS", 16), ("DEFAULTED_SNOD", 8)],
}
# Recompute-variance patterns (illustrative, from the RVE variance work): root_cause -> [(form, line, item)]
VARIANCE_PATTERNS = {
    "MEF_DATA_GAP": [("SCH_C", "27a", "Part V other-expense detail only on an attachment"),
                     ("SCH_C", "13", "Form 4562 asset detail aggregated in MeF"),
                     ("SCH_E", "18", "Rental depreciation detail on a PDF statement"),
                     ("SCH_E", "21", "Form 8582 worksheets not carried in MeF"),
                     ("1040", "13", "Form 8995 QBI component detail missing")],
    "CALCULATOR_DEFECT": [("SCH_E", "21", "Form 8582 passive loss allocation recomputed differently"),
                          ("1040", "13", "QBI flag not applied to a plug asset"),
                          ("SCH_D", "7", "Wash-sale adjustment code not honored")],
    "KEYING_ARTIFACT": [("SCH_C", "13", "Depreciation override field ignored by the calculator"),
                        ("SCH_E", "18", "Plug asset keyed as a single amount")],
    "INTERPRETIVE_POSITION": [("SCH_E", "21", "Rental treated as trade or business by the taxpayer"),
                              ("SCH_C", "30", "Simplified vs. actual home office method")],
}
# How each issue was found (illustrative): issue_code -> weighted detection sources
DETECTION = {
    "EX_SCHC_GROSS_RCPTS": [("BANK_DEPOSITS_ANALYSIS", 80), ("THIRD_PARTY_RECORDS", 20)],
    "EX_SCHC_OTHER_EXP": [("RVE_ATTACHMENT_EXTRACT", 45), ("IDR_RESPONSE", 55)],
    "EX_SCHC_DEPR_179": [("RRI_RECOMPUTE_VARIANCE", 50), ("IDR_RESPONSE", 50)],
    "EX_PAL_469": [("RRI_RECOMPUTE_VARIANCE", 70), ("IDR_RESPONSE", 30)],
    "EX_REP_469C7": [("RRI_RECOMPUTE_VARIANCE", 40), ("IDR_RESPONSE", 60)],
    "EX_FILING_STATUS": [("THIRD_PARTY_RECORDS", 60), ("IDR_RESPONSE", 40)],
    "EX_DEPENDENT_CTC": [("THIRD_PARTY_RECORDS", 55), ("IDR_RESPONSE", 45)],
    "EX_HOBBY_LOSS": [("EXAMINER_INTERVIEW", 70), ("IDR_RESPONSE", 30)],
}
DEFAULT_DETECTION = [("IDR_RESPONSE", 75), ("EXAMINER_INTERVIEW", 25)]
SELECTION = {"AUR": [("IRP_MATCH", 100)],
             "CORRESPONDENCE": [("DIF_SCORE", 55), ("CAMPAIGN", 25), ("PRIOR_EXAM_REPEAT", 10), ("REFERRAL", 10)],
             "FIELD": [("DIF_SCORE", 45), ("CAMPAIGN", 20), ("REFERRAL", 15), ("RELATED_PICKUP", 10), ("PRIOR_EXAM_REPEAT", 10)]}
HOURS = {"AUR": (0.5, 3), "CORRESPONDENCE": (2, 10), "FIELD": (18, 90)}


def detection(rng, code):
    if code.startswith("IR"):
        return "IRP_MATCH"
    return pick(rng, DETECTION.get(code, DEFAULT_DETECTION))


ROOT_WEIGHTS = [("MEF_DATA_GAP", 35), ("CALCULATOR_DEFECT", 20), ("KEYING_ARTIFACT", 15), ("INTERPRETIVE_POSITION", 10), ("TAXPAYER_ISSUE", 20)]


def pick(rng, weighted):
    tot = sum(w for _, w in weighted)
    x = rng.uniform(0, tot)
    for v, w in weighted:
        x -= w
        if x <= 0:
            return v
    return weighted[-1][0]


def profile(rng, tin):
    """A plausible as-filed return (engine inputs) plus the source-line values exam issues act on."""
    st = pick(rng, [("S", 40), ("MFJ", 40), ("HOH", 20)])
    kids = rng.choice([0, 0, 1, 2]) if st != "S" else 0
    p = dict(status=st, wages=[], interest=rng.randrange(0, 1500, 10), stcg=0, sch_c=[], sch_e_allowed=0,
             passive_income_in_e=0, itemized=0, ctc_children=kids, odc_dependents=0, est_payments=0)
    if rng.random() < 0.65:
        w = rng.randrange(28000, 120000, 100)
        p["wages"].append(dict(owner=tin, amount=w, ss_wages=w, fed_wh=round(w * rng.uniform(0.08, 0.14))))
    if rng.random() < 0.6:
        net = rng.randrange(-15000, 85000, 100)
        p["sch_c"].append(dict(owner=tin, net=net))
        p["est_payments"] = max(0, round(max(net, 0) * rng.uniform(0, 0.15), -2))
    if rng.random() < 0.35:
        p["sch_e_allowed"] = rng.randrange(-22000, 18000, 100)
        p["passive_income_in_e"] = max(0, p["sch_e_allowed"])
    if rng.random() < 0.4:
        p["itemized"] = rng.randrange(18000, 42000, 100)
    if not p["wages"] and not p["sch_c"]:
        p["sch_c"].append(dict(owner=tin, net=rng.randrange(20000, 70000, 100)))
    src = dict(sch_c_gross=rng.randrange(60000, 240000, 100), vehicle=rng.randrange(4000, 16000, 100),
               travel=rng.randrange(2000, 12000, 100), other=rng.randrange(5000, 26000, 100),
               depr=rng.randrange(4000, 30000, 100), home=rng.randrange(2000, 9000, 100),
               rent_exp=rng.randrange(12000, 60000, 100), charity=rng.randrange(3000, 15000, 100),
               mort=rng.randrange(9000, 24000, 100))
    return p, src


OVERRIDE = {}  # issue_code -> fixed proposed amount (hero back-fill)
SCALE = {"v": 1.0}  # field exams develop larger issues than correspondence / AUR


def apply_issue(rng, p, src, code, tin, frac=1.0):
    """Mutate engine inputs for one issue, sustaining `frac` of the proposed change.
    Returns (form, line, as_filed_line_value, as_adjusted_line_value, irp_amount_or_None)."""
    form, line = ISSUE_LINE_MAP[code][0][0], ISSUE_LINE_MAP[code][0][1]
    if not p["sch_c"] and code.startswith(("EX_SCHC", "EX_HOME", "EX_HOBBY")) or (not p["sch_c"] and code in ("IR12", "IR30")):
        p["sch_c"].append(dict(owner=tin, net=rng.randrange(10000, 50000, 100)))
    c = p["sch_c"][0] if p["sch_c"] else None
    sc = lambda x: round(x * frac)
    if code in ("IR03", "IR04", "IR10", "IR01", "IR21", "IR23"):
        amt = {"IR03": rng.randrange(300, 6000, 10), "IR04": rng.randrange(400, 8000, 10), "IR10": rng.randrange(3000, 30000, 100),
               "IR01": rng.randrange(4000, 26000, 100), "IR21": rng.randrange(3000, 18000, 100), "IR23": rng.randrange(2000, 25000, 100)}[code]
        amt = round(amt * SCALE["v"])
        a = sc(amt)
        if code == "IR03": p["interest"] += a
        if code == "IR04": p["dividends"] = p.get("dividends", 0) + a
        if code == "IR10": p["ira_taxable"] = p.get("ira_taxable", 0) + a
        if code == "IR01" and a: p["wages"] = p["wages"] + [dict(owner=tin, amount=a, ss_wages=a, fed_wh=0)]
        if code in ("IR21", "IR23"):
            p["sch_e_allowed"] += a; p["passive_income_in_e"] += a
        return form, line, 0, a, amt
    if code == "IR18":
        proceeds = round(rng.randrange(2000, 30000, 100) * SCALE["v"])
        gain = round(proceeds * rng.uniform(0.1, 0.6))
        p["stcg"] += sc(gain)
        return form, line, 0, sc(proceeds), proceeds
    if code in ("IR12", "IR30", "EX_SCHC_GROSS_RCPTS"):
        amt = OVERRIDE.get(code, round(rng.randrange(3000, 40000, 100) * SCALE["v"]))
        c["net"] += sc(amt)
        return form, line, src["sch_c_gross"], src["sch_c_gross"] + sc(amt), (amt if code != "EX_SCHC_GROSS_RCPTS" else None)
    key = {"EX_SCHC_VEHICLE": "vehicle", "EX_SCHC_TRAVEL_MEALS": "travel", "EX_SCHC_OTHER_EXP": "other",
           "EX_SCHC_DEPR_179": "depr", "EX_HOME_OFFICE": "home"}.get(code)
    if key:
        claimed = src[key]
        dis = sc(OVERRIDE.get(code, round(claimed * rng.uniform(0.25, 1.0), -2)))
        c["net"] += dis
        return form, line, claimed, claimed - dis, None
    if code == "EX_HOBBY_LOSS":
        if c["net"] >= 0:
            c["net"] = -round(rng.randrange(6000, 30000, 100) * SCALE["v"])
        loss = c["net"]
        c["net"] = loss - sc(loss)
        return form, line, loss, c["net"], None
    if code == "EX_RENTAL_EXP":
        claimed = src["rent_exp"]
        dis = sc(round(claimed * rng.uniform(0.15, 0.6), -2))
        p["sch_e_allowed"] += dis
        return form, line, claimed, claimed - dis, None
    if code in ("EX_PAL_469", "EX_REP_469C7"):
        if p["sch_e_allowed"] >= -5000:
            p["sch_e_allowed"] = -round(rng.randrange(15000, 70000, 100) * SCALE["v"])
        loss = p["sch_e_allowed"]
        allowed = 0 if code == "EX_PAL_469" else round(loss * rng.uniform(0, 0.5), -2)
        p["sch_e_allowed"] = loss + sc(allowed - loss)
        return form, line, loss, p["sch_e_allowed"], None
    if code == "EX_FILING_STATUS":
        if frac > 0: p["status"] = "S"
        return form, line, FS_CODE["HOH"], FS_CODE[p["status"]], None
    if code == "EX_DEPENDENT_CTC":
        before = p["ctc_children"]
        if frac > 0: p["ctc_children"] = max(0, before - 1)
        return form, line, before, p["ctc_children"], None
    if code in ("EX_CHARITABLE", "EX_MORTGAGE_INT"):
        claimed = src["charity" if code == "EX_CHARITABLE" else "mort"]
        dis = sc(round(claimed * rng.uniform(0.3, 1.0), -2))
        p["itemized"] -= dis
        return form, line, claimed, claimed - dis, None
    raise ValueError(code)


def eligible(code, p):
    if code == "EX_FILING_STATUS": return p["status"] == "HOH"
    if code == "EX_DEPENDENT_CTC": return p["ctc_children"] > 0
    return True


def generate(ctx):
    """ctx: add, rng, AS_OF, iso, contact, ir(…) helpers from build_tp360_data."""
    add, rng, AS_OF, iso = ctx["add"], ctx["rng"], ctx["AS_OF"], ctx["iso"]
    n = {"case": 0, "iss": 0, "adj": 0, "f": 0}
    FIRST = "Abel Bree Cyrus Dana Emory Faye Gideon Hana Ivo Jun Kai Lena Milo Nia Orin Piper Rhea Soren Tamsin Uri Wren Yara Zane".split()
    LAST = "Alder Birch Cove Dell Esker Fenn Glade Holt Isle Jett Knoll Lark Moss Nettle Orr Pike Quarry Reed Sage Thorne Upton Vale Wynn".split()

    def run_case(tin, ty, program, outcome=None, issues=None, prof=None, opened=None, closed=None, ep_id=None, selection_src=None, detect=None):
        SCALE["v"] = 4.0 if (program == "FIELD" and not ep_id) else 1.0
        for attempt in range(25):
            p0, src = prof if (prof and attempt == 0) else (prof if prof else profile(rng, tin))
            if SCALE["v"] != 1.0 and not prof:
                src = {k: round(v * SCALE["v"]) for k, v in src.items()}
                for w in p0["wages"]:
                    w["amount"] = round(w["amount"] * 2); w["ss_wages"] = min(w["amount"], 168600); w["fed_wh"] = round(w["fed_wh"] * 2.4)
                for c in p0["sch_c"]:
                    c["net"] = round(c["net"] * 2.5)
                p0["est_payments"] = round(p0["est_payments"] * 2.5)
            p0 = copy.deepcopy(p0)
            codes = list(issues or [])
            if not codes:
                k = rng.choice([1, 1, 2, 2, 3]) if program != "AUR" else rng.choice([1, 1, 2])
                tries = 0
                while len(codes) < k and tries < 50:
                    tries += 1
                    cd = pick(rng, MIX[program])
                    if cd not in codes and eligible(cd, p0):
                        codes.append(cd)
            oc = outcome or pick(rng, OUTCOMES[program])
            keep, appeals = [1.0] * len(codes), ""
            if oc == "NO_CHANGE":
                keep = [0.0] * len(codes)
            elif oc == "PARTIALLY_AGREED":
                if len(codes) > 1: keep[rng.randrange(len(codes))] = 0.0
                else: keep = [0.6]
            elif oc == "UNAGREED_APPEALS":
                appeals = pick(rng, [("SUSTAINED", 35), ("SETTLED", 50), ("CONCEDED", 15)])
                f = {"SUSTAINED": 1.0, "SETTLED": round(rng.uniform(0.4, 0.8), 2), "CONCEDED": 0.0}[appeals]
                keep = [f] * len(codes)
            # make sure the as-filed return supports the issues (Sch C, itemized, rentals)
            for cd in codes:
                if cd in ("EX_CHARITABLE", "EX_MORTGAGE_INT") and p0["itemized"] < 15000:
                    p0["itemized"] = rng.randrange(26000, 42000, 100)
                if (cd.startswith(("EX_SCHC", "EX_HOME", "EX_HOBBY")) or cd in ("IR12", "IR30")) and not p0["sch_c"]:
                    p0["sch_c"].append(dict(owner=tin, net=rng.randrange(10000, 50000, 100)))
                if cd in ("EX_PAL_469", "EX_REP_469C7") and p0["sch_e_allowed"] >= -5000:
                    p0["sch_e_allowed"] = -rng.randrange(15000, 70000, 100); p0["passive_income_in_e"] = 0
                if cd == "EX_HOBBY_LOSS" and p0["sch_c"][0]["net"] >= 0:
                    p0["sch_c"][0]["net"] = -rng.randrange(6000, 30000, 100)
            p = copy.deepcopy(p0)
            try:
                filed = compute(p0)
                final_lines, proposed = [], []
                for cd, fr in zip(codes, keep):
                    st0 = rng.getstate()
                    proposed.append(apply_issue(rng, copy.deepcopy(p), src, cd, tin, 1.0))
                    rng.setstate(st0)
                    final_lines.append((cd,) + apply_issue(rng, p, src, cd, tin, fr))
                final = compute(p)
                sustained = any(fr > 0 for fr in keep)
                if sustained and final["24 total tax"] - filed["24 total tax"] <= 0:
                    prof = None if not ep_id else prof   # resample filler profiles; heroes keep theirs
                    if not ep_id:
                        continue
                break
            except ValueError:
                prof = None
                continue
        else:
            return None
        deficiency = final["24 total tax"] - filed["24 total tax"]
        n["case"] += 1
        ep = ep_id or f"EP-CC{n['case']:04d}"
        selection = selection_src or pick(rng, SELECTION[program])
        lo, hi = HOURS[program]
        total_hours = round(rng.uniform(lo, hi) * (1 + 0.3 * (len(codes) - 1)), 1)
        split = [rng.uniform(0.5, 1.5) for _ in codes]
        issue_hours = [round(total_hours * x / sum(split), 1) for x in split]
        if opened is None:
            opened = date(ty + 2, rng.randrange(1, 13), rng.randrange(1, 28))
            closed = opened + timedelta(days=rng.randrange(90, 260) if program == "AUR" else rng.randrange(120, 420))
            if oc == "UNAGREED_APPEALS": closed += timedelta(days=rng.randrange(180, 420))
            if closed >= AS_OF: closed = AS_OF - timedelta(days=rng.randrange(20, 200)); opened = min(opened, closed - timedelta(days=90))
        etype = "AUR" if program == "AUR" else "EXAM"
        add("tp_compliance_episode", episode_id=ep, tin_token=tin, episode_type=etype,
            episode_subtype={"AUR": "Underreporter", "CORRESPONDENCE": "Correspondence", "FIELD": "Field"}[program],
            opened_date=iso(opened), closed_date=iso(closed), status=oc, module_ids=f"{tin}-30-{ty}12")
        correct_tax = final["24 total tax"]
        pen_code, pen_amt = "", 0
        if deficiency > 0:
            substantial = deficiency > max(0.10 * correct_tax, 5000)
            if substantial and rng.random() < 0.75:
                pen_code, pen_amt = "IRC 6662(b)(2) substantial understatement", round(0.2 * deficiency)
            elif program != "AUR" and any(c.startswith("EX_SCHC") for c in codes) and rng.random() < 0.3:
                pen_code, pen_amt = "IRC 6662(b)(1) negligence", round(0.2 * deficiency)
        closing_tc = "" if oc == "NO_CHANGE" or deficiency == 0 else ("290" if program == "AUR" else "300")
        add("tp_case_closure", episode_id=ep, tin_token=tin, tax_period=f"{ty}12", program=program, outcome=oc,
            closed_date=iso(closed), closing_tc=closing_tc, deficiency=deficiency,
            penalty_code=pen_code, penalty_amount=pen_amt, appeals_outcome=appeals,
            agreed_ind="Y" if oc in ("AGREED", "PARTIALLY_AGREED") else "N", aims_disposal_code="",
            selection_source=selection, total_hours=total_hours,
            issue_count=len(codes), adjusted_issue_count=sum(1 for x in final_lines if x[4] != x[3]),
            computation_note="Computed with TY2024 parameters for illustration")
        add("tp_tax_computation", episode_id=ep, tin_token=tin, tax_period=f"{ty}12", filing_status_filed=p0["status"],
            filing_status_examined=p["status"], **{f"{k}_{v}": src_[key] for v, src_ in (("filed", filed), ("examined", final))
                                                  for k, key in TAXCOMP}, deficiency=deficiency, penalty_amount=pen_amt,
            computation_engine="POC simplified engine, TY2024 parameters", interest_note="Interest computed at assessment; not modeled")
        for idx, (cd, form, ln, before, after, irp) in enumerate(final_lines):
            n["iss"] += 1
            how = (detect or {}).get(cd) or detection(rng, cd)
            iid = f"I-CC{n['iss']:05d}"
            st = "ADJUSTED" if after != before else ("NO_CHANGE" if oc == "NO_CHANGE" else "CONCEDED")
            add("tp_issue", issue_id=iid, episode_id=ep, tin_token=tin, tax_period=f"{ty}12", issue_code=cd,
                description=ISSUE_CODES[cd][0], return_ref=f"{form} {ln}", amount_claimed=before, status=st,
                amount_proposed=proposed[idx][3] - proposed[idx][2], amount_sustained=after - before,
                detection_source=how, hours_charged=issue_hours[idx])
            if after != before:
                n["adj"] += 1
                add("tp_adjustment", adjustment_id=f"ADJ-CC{n['adj']:05d}", episode_id=ep, snapshot_id="", tin_token=tin,
                    tax_period=f"{ty}12", form=form, line=ln, line_desc=LINE_DESC[cd], as_filed=before, adjustment=after - before,
                    as_adjusted=after, adjustment_kind="EXAMINER", issue_id=iid, issue_code=cd, detection_source=how)
            # an RRI finding behind each IRP issue
            if irp is not None:
                n["f"] += 1
                disp = "UNREPORTED_INCOME" if after != before else "NOT_A_TAXPAYER_ISSUE"
                add("tp_rri_finding", finding_id=f"F-CC{n['f']:05d}", snapshot_id="", tin_token=tin, tax_period=f"{ty}12", source="IRP",
                    item=f"{ISSUE_CODES[cd][3]} · {ISSUE_CODES[cd][0].split(' — ')[0]}", irp_amount=irp, return_ref=f"{form} {ln}",
                    return_amount=0, delta=-irp, branch="A" if after != before else "B", disposition=disp,
                    note="Closed case" + ("" if after != before else " — taxpayer explained; reported elsewhere"),
                    variance_type="IRP_MISMATCH", root_cause="TAXPAYER_ISSUE" if after != before else "REPORTED_ELSEWHERE", issue_code=cd)
        for key, form, ln in [(k, f, l) for k, f, l in L1040_KEYS]:
            if final[key] != filed[key]:
                n["adj"] += 1
                add("tp_adjustment", adjustment_id=f"ADJ-CC{n['adj']:05d}", episode_id=ep, snapshot_id="", tin_token=tin,
                    tax_period=f"{ty}12", form=form, line=ln, line_desc=key.split(" ", 1)[1], as_filed=filed[key],
                    adjustment=final[key] - filed[key], as_adjusted=final[key], adjustment_kind="COMPUTED", issue_id="", issue_code="", detection_source="")
        # recompute variances on exam returns (not AUR)
        if program != "AUR":
            for _ in range(rng.choice([0, 1, 1, 2, 3])):
                rc = pick(rng, ROOT_WEIGHTS)
                n["f"] += 1
                if rc == "TAXPAYER_ISSUE":
                    cd = codes[0]; form, ln = ISSUE_LINE_MAP[cd][0][0], ISSUE_LINE_MAP[cd][0][1]
                    item, br, disp = f"Recompute variance on {form} {ln} — {ISSUE_CODES[cd][0]}", "C", "IDR_REQUIRED"
                else:
                    form, ln, item = rng.choice(VARIANCE_PATTERNS[rc]); cd = ""
                    br = ("A" if rng.random() < 0.6 else "C") if rc == "MEF_DATA_GAP" else "B"
                    disp = {"A": "RESOLVED_FROM_DATA", "B": "NOT_A_TAXPAYER_ISSUE", "C": "IDR_REQUIRED"}[br]
                amt = rng.randrange(150, 9000, 10) * rng.choice([1, -1])
                add("tp_rri_finding", finding_id=f"F-CC{n['f']:05d}", snapshot_id="", tin_token=tin, tax_period=f"{ty}12", source="RECOMPUTE",
                    item=item, irp_amount="", return_ref=f"{form} {ln}", return_amount="", delta=amt, branch=br, disposition=disp,
                    note="Closed case", variance_type="RECOMPUTE_VARIANCE", root_cause=rc, issue_code=cd)
        return dict(ep=ep, codes=codes, deficiency=deficiency, outcome=oc)

    # ---- hero back-fill -------------------------------------------------------------------
    A, B = H.A["tin"], H.B["tin"]
    a19 = dict(H.A_FILED, sch_c=[dict(owner=A, net=70400)], sch_e_allowed=0, passive_income_in_e=0, interest=380, stcg=0)
    src19 = dict(sch_c_gross=196000, vehicle=8800, travel=3000, other=21400, depr=9000, home=3000, rent_exp=0, charity=0, mort=0)
    rng_seed = rng.getstate()
    rng.seed(2019)
    OVERRIDE.update({"EX_SCHC_GROSS_RCPTS": 58000, "EX_SCHC_OTHER_EXP": 14200})
    r = run_case(A, 2019, "FIELD", outcome="AGREED", issues=["EX_SCHC_GROSS_RCPTS", "EX_SCHC_OTHER_EXP"], prof=(a19, src19),
                 opened=date(2021, 3, 15), closed=date(2021, 11, 30), ep_id="EP-A-EX19", selection_src="DIF_SCORE",
                 detect={"EX_SCHC_GROSS_RCPTS": "BANK_DEPOSITS_ANALYSIS", "EX_SCHC_OTHER_EXP": "IDR_RESPONSE"})
    OVERRIDE.clear()
    rng.seed(2021)
    a21 = dict(H.A_FILED, sch_c=[dict(owner=A, net=41300)], sch_e_allowed=0, passive_income_in_e=0, interest=290, stcg=0)
    run_case(A, 2021, "AUR", outcome="AGREED", issues=["IR12"], prof=(a21, src19),
             opened=date(2023, 3, 6), closed=date(2023, 9, 19), ep_id="EP-A-AUR21")
    rng.seed(20212)
    b21 = dict(H.B_FILED, sch_e_allowed=-21000, itemized=34100)
    run_case(B, 2021, "CORRESPONDENCE", outcome="NO_CHANGE", issues=["EX_CHARITABLE"], prof=(b21, dict(src19, charity=6200)),
             opened=date(2023, 2, 1), closed=date(2023, 6, 30), ep_id="EP-B-EX21", selection_src="DIF_SCORE",
             detect={"EX_CHARITABLE": "IDR_RESPONSE"})
    rng.setstate(rng_seed)

    # ---- population -----------------------------------------------------------------------
    taxpayers = []
    for i in range(1, 261):
        tok = f"TK4{i:05d}"
        add("tp_taxpayer", tin_token=tok, tin_type="SSN", display_name=f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            entity_type="INDIVIDUAL", filing_status="", city=rng.choice(["Spokane", "Tacoma", "Everett", "Olympia", "Salem", "Bend", "Boise"]),
            state=rng.choice(["WA", "WA", "OR", "ID"]), poa_on_file=rng.choice("YNNN"), case_group="CLOSED_CASES")
        taxpayers.append(tok)
    for tok in taxpayers:
        ty = rng.choice([2019, 2020, 2021, 2022, 2023])
        prog = pick(rng, [("AUR", 45), ("CORRESPONDENCE", 30), ("FIELD", 25)])
        r = run_case(tok, ty, prog)
        # ~15% get a later case; most repeat an issue
        if r and rng.random() < 0.16 and ty <= 2022:
            ty2 = rng.randrange(ty + 1, 2024)
            prog2 = prog if rng.random() < 0.7 else pick(rng, [("CORRESPONDENCE", 50), ("FIELD", 50)])
            repeat = [c for c in r["codes"] if c in dict(MIX[prog2])]
            issues2 = [repeat[0]] if repeat and rng.random() < 0.75 else None
            run_case(tok, ty2, prog2, issues=issues2, selection_src="PRIOR_EXAM_REPEAT" if issues2 and prog2 != "AUR" else None, outcome=None if issues2 is None else pick(rng, [("AGREED", 60), ("DEFAULTED_SNOD", 20)] + ([] if prog2 == "AUR" else [("UNAGREED_APPEALS", 20)])))
    return n


TAXCOMP = [("agi", "11 adjusted gross income"), ("taxable_income", "15 taxable income"), ("tax", "16 tax"),
           ("credits", "19 child tax credit / credit for other dependents"), ("other_taxes", "23 other taxes (SE, Additional Medicare, NIIT)"),
           ("total_tax", "24 total tax"), ("payments", "33 total payments")]
L1040_KEYS = [(k, f, l) for k, f, l, _, _ in H.L1040]
