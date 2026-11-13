"""Case C  Priya N. Halvorsen: one TY2024 return through every version RVE keeps.

    AS_FILED      TC 150 original return (Schedule C design studio, home office on Form 8829)
    AS_AMENDED    Form 1040-X claim: adds car and truck expenses, asks for a refund
    RVE_WORKING   exam of the claim and the original return (claim referral)
    PROPOSED      30-day letter: claim denied, unreported 1099-NEC added, home office disallowed
    AS_EXAMINED   partial agreement: agreed issues assessed (TC 300); home office goes to Appeals
    AS_APPEALED   Appeals settles home office at 50% (TC 300)

Illustrative facts and amounts. Partial-agreement assessment and Appeals settlement mechanics are
SME to confirm.
"""
from tax_engine_ty2024 import compute

C = "TK500001"
EP = "EP-C-EX24"
NAME = "Priya N. Halvorsen"
BASE = dict(status="S", wages=[], interest=600, stcg=0, est_payments=14000)

# Schedule C by version: gross receipts, car and truck, home office (line 30). Other expenses never change.
OTHER = [("8", "Advertising", "AdvertisingAmt", 6500), ("13", "Depreciation", "DepreciationAmt", 9300),
         ("15", "Insurance", "InsuranceAmt", 3200), ("18", "Office expense", "OfficeExpenseAmt", 9800),
         ("22", "Supplies", "SuppliesAmt", 14000), ("25", "Utilities", "UtilitiesAmt", 2000),
         ("27a", "Other expenses (software subscriptions)", "OtherExpensesAmt", 7000)]
VERSIONS = [  # snapshot, version, basis, tc, created, by, status, receipts, car_truck, home_office
    ("SN-C1", "AS_FILED", "", "150", "2025-04-15", "MeF", "POSTED", 132000, 0, 6200),
    ("SN-C2", "AS_AMENDED", "SN-C1", "", "2025-09-18", "Form 1040-X", "CLAIM_REFERRED", 132000, 9400, 6200),
    ("SN-C3", "RVE_WORKING", "SN-C2", "", "2026-01-20", "J. Moreau", "WORKING", 132000, 9400, 6200),
    ("SN-C4", "PROPOSED", "SN-C3", "", "2026-04-10", "J. Moreau", "ISSUED", 136800, 0, 0),
    ("SN-C5", "AS_EXAMINED", "SN-C4", "300", "2026-06-22", "Master File", "POSTED", 136800, 0, 6200),
    ("SN-C6", "AS_APPEALED", "SN-C5", "300", "2026-10-02", "Appeals", "POSTED", 136800, 0, 3100),
]


def net(receipts, car, home):
    return receipts - car - sum(x[3] for x in OTHER) - home


def build(add, snapshot, line, lines_from_tax, iso, closed_cases):
    add("tp_taxpayer", tin_token=C, tin_type="SSN", display_name=NAME, entity_type="INDIVIDUAL", filing_status="S",
        city="Tacoma", state="WA", poa_on_file="N", case_group="HERO_C")
    taxes = {}
    for sid, ver, basis, tc, created, by, status, rec, car, home in VERSIONS:
        add("tp_return_snapshot", snapshot_id=sid, tin_token=C, mft=30, tax_period="202412", version_type=ver,
            basis_snapshot_id=basis, source_tc=tc, created_date=created, created_by=by, status=status)
        n = net(rec, car, home)
        tax = compute(dict(BASE, sch_c=[dict(owner=C, net=n)]))
        taxes[ver] = tax
        changed = sid != "SN-C1"
        org = lambda same: "MEF" if sid in ("SN-C1",) or same else (
            "TAXPAYER_AMENDMENT" if ver == "AS_AMENDED" else "EXAMINER_ADJUSTMENT")
        lines_from_tax(sid, tax, "MEF" if sid == "SN-C1" else ("TAXPAYER_AMENDMENT" if ver == "AS_AMENDED" else "COMPUTED"))
        first = VERSIONS[0]
        line(sid, "SCH_B", "1", "BAYVIEW_CU", "Interest — Bayview Credit Union", "InterestAmt", 600, "MEF", "Y")
        line(sid, "SCH_B", "2", "", "Total interest", "TotalInterestAmt", 600, "MEF", "N")
        line(sid, "SCH_C", "1", "HALVORSEN_STUDIO", "Gross receipts — Halvorsen Studio", "GrossReceiptsAmt", rec, org(rec == first[7]), "Y")
        line(sid, "SCH_C", "9", "HALVORSEN_STUDIO", "Car and truck expenses", "CarAndTruckExpensesAmt", car, org(car == first[8]), "Y")
        for ln, desc, el, amt in OTHER:
            line(sid, "SCH_C", ln, "HALVORSEN_STUDIO", desc, el, amt, "MEF", "Y")
        tot = car + sum(x[3] for x in OTHER)
        line(sid, "SCH_C", "28", "HALVORSEN_STUDIO", "Total expenses", "TotalExpensesAmt", tot,
             "MEF" if tot == first[8] + sum(x[3] for x in OTHER) else "COMPUTED", "N")
        line(sid, "SCH_C", "29", "HALVORSEN_STUDIO", "Tentative profit", "TentativeProfitOrLossAmt", rec - tot,
             "MEF" if rec - tot == first[7] - first[8] - sum(x[3] for x in OTHER) else "COMPUTED", "N")
        line(sid, "SCH_C", "30", "HALVORSEN_STUDIO", "Business use of home (Form 8829)", "HomeBusinessExpenseAmt", home,
             org(home == first[9]), "Y")
        line(sid, "SCH_C", "31", "HALVORSEN_STUDIO", "Net profit", "NetProfitOrLossAmt", n,
             "MEF" if n == net(*first[7:10]) else "COMPUTED", "N")
        line(sid, "F8829", "36", "HALVORSEN_STUDIO", "Allowable home office expense", "AllowableHomeOfficeExpnsAmt", home,
             org(home == first[9]), "Y")
        line(sid, "SCH_SE", "12", "", "Self-employment tax", "SelfEmploymentTaxAmt", tax["_se_tax"],
             "MEF" if sid == "SN-C1" or tax["_se_tax"] == taxes["AS_FILED"]["_se_tax"] else "COMPUTED", "N")
    if True:  # RVE supplement captured during the exam
        line("SN-C3", "RVE_SUPP", "MILEAGE_LOG", "", "Contemporaneous mileage log provided (1 = yes, 0 = no)", "", 0,
             "RVE_SUPPLEMENT", "Y", "CONFIRMED")
        line("SN-C3", "RVE_SUPP", "HOME_OFFICE_EXCLUSIVE_USE", "", "Office space used exclusively for business (1 = yes, 0 = no)",
             "", 0, "RVE_SUPPLEMENT", "Y", "CONFIRMED")

    filed, final = taxes["AS_FILED"], taxes["AS_APPEALED"]
    deficiency = final["24 total tax"] - filed["24 total tax"]
    add("tp_tax_module", module_id=f"{C}-30-202412", tin_token=C, mft=30, tax_period="202412", assessed_balance=0,
        last_assessment_date="2026-10-02", csed="2036-06-22", module_status="12")
    add("tp_compliance_episode", episode_id=EP, tin_token=C, episode_type="EXAM", episode_subtype="Correspondence",
        opened_date="2026-01-12", closed_date="2026-10-02", status="UNAGREED_APPEALS", module_ids=f"{C}-30-202412")
    add("tp_case_closure", episode_id=EP, tin_token=C, tax_period="202412", program="CORRESPONDENCE",
        selection_source="CLAIM", outcome="UNAGREED_APPEALS", closed_date="2026-10-02", closing_tc="300",
        deficiency=deficiency, penalty_code="", penalty_amount=0, appeals_outcome="SETTLED", agreed_ind="N",
        total_hours=31.5, issue_count=3, adjusted_issue_count=3, aims_disposal_code="",
        computation_note="Claim denied; agreed issues assessed on partial agreement; home office settled at Appeals")
    add("tp_tax_computation", episode_id=EP, tin_token=C, tax_period="202412", filing_status_filed="S",
        filing_status_examined="S", **{f"{k}_{v}": t[key] for v, t in (("filed", filed), ("examined", final))
                                       for k, key in closed_cases.TAXCOMP},
        deficiency=deficiency, penalty_amount=0, computation_engine="POC simplified engine, TY2024 parameters",
        interest_note="Interest computed at assessment; not modeled")
    issues = [  # id, code, desc, ref, claimed, proposed, sustained, detection, hours
        ("I-C1", "EX_SCHC_VEHICLE", "Car and truck expenses claimed on Form 1040-X; no mileage log", "SCH_C 9", 9400, -9400, -9400, "CLAIM_REVIEW", 9.0),
        ("I-C2", "IR12", "1099-NEC from Cedar Loop Media not in gross receipts", "SCH_C 1", 132000, 4800, 4800, "IRP_MATCH", 4.5),
        ("I-C3", "EX_HOME_OFFICE", "Office space not used exclusively for business; settled at Appeals", "SCH_C 30", 6200, -6200, -3100, "IDR_RESPONSE", 18.0),
    ]
    for iid, code, desc, ref, claimed, prop, sust, how, hrs in issues:
        add("tp_issue", issue_id=iid, episode_id=EP, tin_token=C, tax_period="202412", issue_code=code, description=desc,
            return_ref=ref, amount_claimed=claimed, amount_proposed=prop, amount_sustained=sust, status="ADJUSTED",
            detection_source=how, hours_charged=hrs)
    add("tp_determination", determination_id="D-C1", episode_id=EP, issue_id="I-C3", tin_token=C,
        determination_type="APPEALS_SETTLEMENT", outcome="SETTLED", amount=3100, authority="IRC 280A(c)(1)",
        decided_date="2026-09-24", detail="Appeals settled the home office issue at 50% of the amount claimed (hazards of litigation)")
    add("tp_idr", idr_id="IDR-C1", episode_id=EP, tin_token=C, form="Form 4564", issued_date="2026-01-26", due_date="2026-02-25",
        response_date="2026-02-23", recipient="TAXPAYER", status="RESPONDED", item_count=2,
        items="Mileage log for the car and truck expenses claimed on Form 1040-X | Floor plan and description of how the office space is used")
    add("tp_information_return", ir_id="IR-C1", tin_token=C, tax_year=2024, form_type="1099-NEC", box="1",
        payer_tin_token="", payer_name="Cedar Loop Media", amount=4800, note="Not included in Schedule C gross receipts")
    findings = [  # id, src, item, irp, ref, ret_amt, branch, disposition, variance, root cause, code, note
        ("F-C1", "IRP", "1099-NEC · Cedar Loop Media", 4800, "SCH_C 1", 0, "A", "UNREPORTED_INCOME", "IRP_MISMATCH",
         "TAXPAYER_ISSUE", "IR12", "Payer not in gross receipts. Resolved from data: added to the proposal."),
        ("F-C2", "RVE", "Form 1040-X · car and truck expenses", None, "SCH_C 9", 9400, "C", "IDR_REQUIRED", "DATA_GAP",
         "MEF_DATA_GAP", "EX_SCHC_VEHICLE", "Claim adds $9,400 with no mileage detail; the IDR asks for the log."),
        ("F-C3", "RVE", "Form 8829 · business use of home", None, "SCH_C 30", 6200, "C", "IDR_REQUIRED", "DATA_GAP",
         "MEF_DATA_GAP", "EX_HOME_OFFICE", "Exclusive use cannot be seen in return data; the IDR asks for a floor plan."),
    ]
    for fid, src, item, irp, ref, ret_amt, br, disp, vt, rc, ic, note in findings:
        add("tp_rri_finding", finding_id=fid, snapshot_id="SN-C3", tin_token=C, tax_period="202412", source=src, item=item,
            irp_amount=irp if irp is not None else "", return_ref=ref, return_amount=ret_amt if ret_amt is not None else "",
            delta=(ret_amt - irp) if (irp is not None and ret_amt is not None) else "", branch=br, disposition=disp,
            variance_type=vt, root_cause=rc, issue_code=ic, note=note)
    # line adjustments, AS_FILED -> AS_APPEALED (what the closed case changed)
    n = 0
    for form, ln, desc, before, after, iid, code, how in [
            ("SCH_C", "1", "Gross receipts — Halvorsen Studio", 132000, 136800, "I-C2", "IR12", "IRP_MATCH"),
            ("SCH_C", "30", "Business use of home (Form 8829)", 6200, 3100, "I-C3", "EX_HOME_OFFICE", "IDR_RESPONSE")]:
        n += 1
        add("tp_adjustment", adjustment_id=f"ADJ-C{n:03d}", episode_id=EP, snapshot_id="SN-C6", tin_token=C, tax_period="202412",
            form=form, line=ln, line_desc=desc, as_filed=before, adjustment=after - before, as_adjusted=after,
            adjustment_kind="EXAMINER", issue_id=iid, issue_code=code, detection_source=how)
    import hero_cases as H
    for key, form, ln, el, mod in H.L1040:
        if filed[key] != final[key]:
            n += 1
            add("tp_adjustment", adjustment_id=f"ADJ-C{n:03d}", episode_id=EP, snapshot_id="SN-C6", tin_token=C,
                tax_period="202412", form=form, line=ln, line_desc=key.split(" ", 1)[1], as_filed=filed[key],
                adjustment=final[key] - filed[key], as_adjusted=final[key], adjustment_kind="COMPUTED",
                issue_id="", issue_code="", detection_source="")
    return {v: t["24 total tax"] for v, t in taxes.items()}, deficiency
