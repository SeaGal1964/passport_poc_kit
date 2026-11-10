"""Simplified TY2024 Form 1040 engine for the TP360 / RVE POC.

Illustrative only. It covers what the two POC returns need: wages, interest, short-term
gain, Schedule C (with SE tax), Schedule E (allowed amount), standard or itemized
deduction, the section 199A deduction below the threshold, the child tax credit and
credit for other dependents, Additional Medicare Tax and NIIT checks.

It uses the rate schedules, not the Tax Table, so results can differ from a filed return
by a few dollars below $100,000 of taxable income. The production recompute is the
calculator behind RVE (Thomson Reuters today, FYT in future), never this file.
"""

STD = {"S": 14600, "MFJ": 29200, "HOH": 21900}
BRACKETS = {
    "S":   [(11600, .10), (47150, .12), (100525, .22), (191950, .24), (243725, .32), (609350, .35), (None, .37)],
    "MFJ": [(23200, .10), (94300, .12), (201050, .22), (383900, .24), (487450, .32), (731200, .35), (None, .37)],
    "HOH": [(16550, .10), (63100, .12), (100500, .22), (191950, .24), (243700, .32), (609350, .35), (None, .37)],
}
SS_WAGE_BASE = 168600
ADDL_MED_THRESHOLD = {"S": 200000, "HOH": 200000, "MFJ": 250000}
NIIT_THRESHOLD = {"S": 200000, "HOH": 200000, "MFJ": 250000}
CTC_PHASEOUT = {"S": 200000, "HOH": 200000, "MFJ": 400000}
QBI_THRESHOLD = {"S": 191950, "HOH": 191950, "MFJ": 383900}


def r(x):
    """IRS whole-dollar rounding (50 cents and up rounds up)."""
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def bracket_tax(ti, status):
    tax, low = 0.0, 0
    for top, rate in BRACKETS[status]:
        if top is None or ti <= top:
            return tax + (ti - low) * rate
        tax += (top - low) * rate
        low = top
    return tax


def compute(ret):
    """ret keys: status, wages[{owner,amount,ss_wages,fed_wh}], interest, stcg,
    sch_c[{owner,net,qbi}], sch_e_allowed, passive_income_in_e, itemized,
    ctc_children, odc_dependents, est_payments; optional dividends (nonqualified), ira_taxable.  Returns an ordered dict of 1040 lines."""
    st = ret["status"]
    wages = sum(w["amount"] for w in ret.get("wages", []))
    fed_wh = sum(w["fed_wh"] for w in ret.get("wages", []))

    # Schedule SE per owner
    se_total, half_se_by_owner = 0, {}
    for c in ret.get("sch_c", []):
        nese = r(c["net"] * 0.9235)
        if nese < 400:
            half_se_by_owner[c["owner"]] = 0
            continue
        ss_wages = sum(w["ss_wages"] for w in ret.get("wages", []) if w["owner"] == c["owner"])
        ss = r(0.124 * min(nese, max(0, SS_WAGE_BASE - ss_wages)))
        med = r(0.029 * nese)
        se = ss + med
        se_total += se
        half_se_by_owner[c["owner"]] = r(se / 2)
    half_se = sum(half_se_by_owner.values())

    sch_c_net = sum(c["net"] for c in ret.get("sch_c", []))
    sch_e = ret.get("sch_e_allowed", 0)
    sch1_additional = sch_c_net + sch_e
    dividends, ira = ret.get("dividends", 0), ret.get("ira_taxable", 0)
    total_income = wages + ret.get("interest", 0) + dividends + ira + ret.get("stcg", 0) + sch1_additional
    agi = total_income - half_se

    deduction = max(STD[st], ret.get("itemized", 0))
    ti_before_qbi = max(0, agi - deduction)
    # Above the threshold the W-2 wage / UBIA limits apply; with no W-2 wages or UBIA modeled, the deduction is
    # treated as fully limited (0). Simplification for illustration, stated in the README.
    over_threshold = ti_before_qbi > QBI_THRESHOLD[st]
    qbi = 0 if over_threshold else sum(max(0, c["net"] - half_se_by_owner.get(c["owner"], 0)) for c in ret.get("sch_c", []) if c.get("qbi", True))
    qbi_ded = r(min(0.20 * qbi, 0.20 * ti_before_qbi))  # no net capital gain in POC returns
    ti = max(0, ti_before_qbi - qbi_ded)
    tax = r(bracket_tax(ti, st))

    # Credits (nonrefundable portion only; POC returns have enough tax to absorb them)
    credit = 2000 * ret.get("ctc_children", 0) + 500 * ret.get("odc_dependents", 0)
    over = max(0, agi - CTC_PHASEOUT[st])
    credit = max(0, credit - 50 * -(-over // 1000))
    credit = min(credit, tax)

    # Other taxes
    se_earnings = sum(r(c["net"] * 0.9235) for c in ret.get("sch_c", []) if c["net"] * 0.9235 >= 400)
    addl_med = r(0.009 * max(0, wages + se_earnings - ADDL_MED_THRESHOLD[st]))
    nii = ret.get("interest", 0) + dividends + ret.get("stcg", 0) + ret.get("passive_income_in_e", 0)
    niit = r(0.038 * min(max(0, nii), max(0, agi - NIIT_THRESHOLD[st])))
    other_taxes = se_total + addl_med + niit

    total_tax = tax - credit + other_taxes
    payments = fed_wh + ret.get("est_payments", 0)
    return {
        "1z wages": wages,
        "2b taxable interest": ret.get("interest", 0),
        "3b ordinary dividends": dividends,
        "4b taxable IRA distributions": ira,
        "7 capital gain": ret.get("stcg", 0),
        "8 Schedule 1 additional income": sch1_additional,
        "9 total income": total_income,
        "10 adjustments (half SE tax)": half_se,
        "11 adjusted gross income": agi,
        "12 standard or itemized deduction": deduction,
        "13 qualified business income deduction": qbi_ded,
        "15 taxable income": ti,
        "16 tax": tax,
        "19 child tax credit / credit for other dependents": credit,
        "23 other taxes (SE, Additional Medicare, NIIT)": other_taxes,
        "24 total tax": total_tax,
        "25d federal income tax withheld": fed_wh,
        "26 estimated tax payments": ret.get("est_payments", 0),
        "33 total payments": payments,
        "37 amount owed": total_tax - payments,
        "_se_tax": se_total,
        "_addl_medicare": addl_med,
        "_niit": niit,
    }
