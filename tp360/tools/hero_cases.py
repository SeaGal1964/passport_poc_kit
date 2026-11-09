"""The two hero cases for the TP360 / RVE POC. Fictional taxpayers, synthetic data, no FTI.

Case A  Marisol T. Vance, TY2024, head of household. The TP360 collection taxpayer, seen through
        the return: RVE snapshot, IRP match, Schedule C Part V IDR, agreed exam, effects on the
        OIC, Passport and the account.
Case B  Marcus and Elena Thornbury, TY2024, married filing jointly. Exam only: IRC 469(c)(7) real
        estate professional claim, no aggregation election, IDR for hours, unagreed, protest.

Every tax-law or procedure point an SME must confirm carries status 'question' in SME_FLAGS.
"""
from tax_engine_ty2024 import compute

AS_OF = "2026-11-06"

# ----------------------------------------------------------------------------------------------
# Return inputs (as filed and as adjusted) -> tax engine
# ----------------------------------------------------------------------------------------------
A_FILED = dict(status="HOH", wages=[], interest=412, stcg=2300,
               sch_c=[dict(owner="TK100001", net=88500)],
               sch_e_allowed=2155 + 31800, passive_income_in_e=2155 + 31800,
               itemized=0, ctc_children=1, odc_dependents=1, est_payments=2200)
A_ADJ = dict(A_FILED, interest=2252, sch_c=[dict(owner="TK100001", net=95100)])

B_FILED = dict(status="MFJ",
               wages=[dict(owner="TK200001", amount=182000, ss_wages=168600, fed_wh=29800)],
               interest=1150, stcg=0, sch_c=[dict(owner="TK200002", net=65000)],
               sch_e_allowed=-64000, passive_income_in_e=0, itemized=32600, est_payments=0)
B_ADJ = dict(B_FILED, sch_e_allowed=-14000)

A_TAX_FILED, A_TAX_ADJ = compute(A_FILED), compute(A_ADJ)
B_TAX_FILED, B_TAX_ADJ = compute(B_FILED), compute(B_ADJ)
A_DEFICIENCY = A_TAX_ADJ["24 total tax"] - A_TAX_FILED["24 total tax"]
B_DEFICIENCY = B_TAX_ADJ["24 total tax"] - B_TAX_FILED["24 total tax"]
B_SUBSTANTIAL = B_DEFICIENCY > max(0.10 * B_TAX_ADJ["24 total tax"], 5000)
A_SUBSTANTIAL = A_DEFICIENCY > max(0.10 * A_TAX_ADJ["24 total tax"], 5000)
B_PENALTY_IF_ASSERTED = round(0.20 * B_DEFICIENCY)

# 1040 line -> (form, line, element, modifiable)  Element names are illustrative; verify against
# the IRS1040 MeF schema before reuse.
L1040 = [
    ("1z wages", "1040", "1z", "WagesAmt", "N"),
    ("2b taxable interest", "1040", "2b", "TaxableInterestAmt", "N"),
    ("7 capital gain", "1040", "7", "CapitalGainLossAmt", "N"),
    ("8 Schedule 1 additional income", "1040", "8", "TotalAdditionalIncomeAmt", "N"),
    ("9 total income", "1040", "9", "TotalIncomeAmt", "N"),
    ("10 adjustments (half SE tax)", "1040", "10", "TotalAdjustmentsAmt", "N"),
    ("11 adjusted gross income", "1040", "11", "AdjustedGrossIncomeAmt", "N"),
    ("12 standard or itemized deduction", "1040", "12", "TotalItemizedOrStandardDedAmt", "N"),
    ("13 qualified business income deduction", "1040", "13", "QualifiedBusinessIncomeDedAmt", "N"),
    ("15 taxable income", "1040", "15", "TaxableIncomeAmt", "N"),
    ("16 tax", "1040", "16", "TaxAmt", "N"),
    ("19 child tax credit / credit for other dependents", "1040", "19", "CTCODCAmt", "N"),
    ("23 other taxes (SE, Additional Medicare, NIIT)", "1040", "23", "TotalOtherTaxesAmt", "N"),
    ("24 total tax", "1040", "24", "TotalTaxAmt", "N"),
    ("25d federal income tax withheld", "1040", "25d", "WithholdingTaxAmt", "N"),
    ("26 estimated tax payments", "1040", "26", "EstimatedTaxPaymentsAmt", "Y"),
    ("33 total payments", "1040", "33", "TotalPaymentsAmt", "N"),
    ("37 amount owed", "1040", "37", "OwedAmt", "N"),
]


def lines_1040(tax, origin_for_changed=None, prior=None):
    out = []
    for key, form, line, el, mod in L1040:
        origin = "MEF"
        if prior is not None:
            origin = "COMPUTED"
        out.append(dict(form=form, line=line, line_desc=key.split(" ", 1)[1], mef_element=el,
                        amount=tax[key], data_origin=origin, modifiable=mod, sub_id=""))
    return out


# ----------------------------------------------------------------------------------------------
# Case A  Marisol T. Vance
# ----------------------------------------------------------------------------------------------
A = dict(
    case_id="A", tin="TK100001", name="Marisol T. Vance", tin_display="XXX-XX-7214", tax_period="202412",
    filing_status="Head of household", city="Olympia", state="WA",
    poa="R. Okafor CPA (Form 2848)", title="Individual return through RVE — inside a collection case",
    selection=("Referral from the offer investigation: the financial analysis compared the TY2024 return "
               "with information returns and the Form 433-A (OIC). A K-1 and a 1099-INT payer appear in "
               "IRP data but not on the financial statement, and Schedule C 'other expenses' were supported "
               "only by a PDF statement."),
    selection_status="question",  # referral path to confirm
    team=[("Correspondence / field examiner", "A. Whitfield, GS-12", "Exam episode owner"),
          ("Group manager", "T. Navarro", "Approves RAR"),
          ("Offer examiner", "K. Brandt", "OIC episode owner — notified of results"),
          ("Representative", "R. Okafor CPA", "All contact through the POA (CAF)")],
)

A_SCH = {  # schedule-level lines as filed: (form, line, desc, element, amount, modifiable, sub_id)
    "filed": [
        ("SCH_C", "1", "Gross receipts — Vance Builders", "GrossReceiptsAmt", 246900, "Y", "VANCE_BUILDERS"),
        ("SCH_C", "11", "Contract labor", "ContractLaborAmt", 41200, "Y", "VANCE_BUILDERS"),
        ("SCH_C", "22", "Supplies and materials", "SuppliesAmt", 61800, "Y", "VANCE_BUILDERS"),
        ("SCH_C", "9", "Car and truck expenses", "CarAndTruckExpensesAmt", 9100, "Y", "VANCE_BUILDERS"),
        ("SCH_C", "15", "Insurance", "InsuranceAmt", 7600, "Y", "VANCE_BUILDERS"),
        ("SCH_C", "13", "Depreciation", "DepreciationAmt", 12300, "Y", "VANCE_BUILDERS"),
        ("SCH_C", "23", "Taxes and licenses", "TaxesAndLicensesAmt", 8000, "Y", "VANCE_BUILDERS"),
        ("SCH_C", "27a", "Other expenses (total only in MeF; detail on a PDF statement)", "OtherExpensesAmt", 18400, "Y", "VANCE_BUILDERS"),
        ("SCH_C", "28", "Total expenses", "TotalExpensesAmt", 158400, "N", "VANCE_BUILDERS"),
        ("SCH_C", "31", "Net profit", "NetProfitOrLossAmt", 88500, "N", "VANCE_BUILDERS"),
        ("SCH_B", "1", "Interest — Cascade Mutual Bank", "InterestAmt", 412, "Y", "CASCADE_MUTUAL"),
        ("SCH_B", "2", "Total interest", "TotalInterestAmt", 412, "N", ""),
        ("F8949", "1d", "Proceeds — Pinnacle Brokerage (box B, basis not reported)", "ProceedsSalesPriceAmt", 26400, "Y", "PINNACLE_BROKERAGE"),
        ("F8949", "1e", "Cost basis", "CostOrOtherBasisAmt", 24100, "Y", "PINNACLE_BROKERAGE"),
        ("SCH_D", "7", "Net short-term gain", "NetSTCapitalGainOrLossAmt", 2300, "N", ""),
        ("SCH_E", "3", "Rents received — 88 Ferncroft Rd", "RentsReceivedAmt", 25200, "Y", "88_FERNCROFT"),
        ("SCH_E", "12", "Mortgage interest — 88 Ferncroft Rd", "MortgageInterestPaidAmt", 9800, "Y", "88_FERNCROFT"),
        ("SCH_E", "16", "Taxes — 88 Ferncroft Rd", "TaxesAmt", 3100, "Y", "88_FERNCROFT"),
        ("SCH_E", "9", "Insurance — 88 Ferncroft Rd", "InsuranceAmt", 1400, "Y", "88_FERNCROFT"),
        ("SCH_E", "14", "Repairs — 88 Ferncroft Rd", "RepairsAmt", 2200, "Y", "88_FERNCROFT"),
        ("SCH_E", "18", "Depreciation — 88 Ferncroft Rd", "DepreciationOrDepletionAmt", 6545, "Y", "88_FERNCROFT"),
        ("SCH_E", "26", "Total rental real estate income", "TotalRentalRealEstateIncmAmt", 2155, "N", ""),
        ("SCH_E", "28", "K-1 — Latimer Grove Holdings LLC, passive income", "PassiveIncomeAmt", 31800, "Y", "LATIMER_GROVE"),
        ("SCH_E", "41", "Total Schedule E income", "TotalSupplementalIncomeAmt", 33955, "N", ""),
        ("SCH_SE", "12", "Self-employment tax", "SelfEmploymentTaxAmt", A_TAX_FILED["_se_tax"], "N", ""),
        ("SCH_8812", "14", "Child tax credit and credit for other dependents", "CTCODCAmt", 2500, "N", ""),
    ],
    # Part V detail captured from the PDF statement (RVE attachment extract, needs review)
    "part_v": [
        ("SCH_C", "48a", "Part V — subcontract labor", 6100, "VANCE_BUILDERS"),
        ("SCH_C", "48b", "Part V — cell phone", 2000, "VANCE_BUILDERS"),
        ("SCH_C", "48c", "Part V — conference travel", 4300, "VANCE_BUILDERS"),
        ("SCH_C", "48d", "Part V — miscellaneous", 6000, "VANCE_BUILDERS"),
    ],
}

A_FINDINGS = [  # finding_id, source, item, irp_amount, return_ref, return_amount, branch, disposition, note
    ("F-A1", "IRP", "1099-INT · Harbor Trust Savings", 1840, "SCH_B 1", 0, "A", "UNREPORTED_INCOME",
     "Payer not on Schedule B. Resolved from data: propose the adjustment; the IDR asks for an explanation."),
    ("F-A2", "IRP", "1099-B · Pinnacle Brokerage (noncovered)", 26400, "F8949 1d", 26400, "B", "NOT_A_TAXPAYER_ISSUE",
     "Gross proceeds match. Basis was not reported to the IRS (noncovered), so an IRP-only check would overstate the gain. Never an IDR."),
    ("F-A3", "IRP", "1099-NEC (4 payers) + 1099-K · Schedule C receipts", 241500, "SCH_C 1", 246900, "B", "NOT_A_TAXPAYER_ISSUE",
     "Reported receipts exceed information returns by $5,400. No underreporting indicated."),
    ("F-A4", "RVE", "Schedule C line 27a · other expenses", None, "SCH_C 27a", 18400, "C", "IDR_REQUIRED",
     "MeF carries only the total. RVE captured the four Part V lines from the PDF statement, so the IDR asks for exactly those."),
    ("F-A5", "IRP", "Schedule K-1 (1065) · Latimer Grove Holdings LLC, box 2", 31800, "SCH_E 28", 31800, "A", "MATCHED",
     "Matched to Schedule E Part II. The entity is a related party in the TP360 graph — see the transfer signal."),
    ("F-A6", "IRP", "1098 · Pinnacle Home Loans (residence)", 11260, "1040 12", 21900, "B", "NOT_A_TAXPAYER_ISSUE",
     "Standard deduction claimed; mortgage interest not needed for the computation."),
]

A_IDR = [dict(idr_id="IDR-A1", form="Form 4564", issued="2026-08-17", due="2026-09-16", response="2026-09-12",
              to="R. Okafor CPA (POA)", status="RESPONDED",
              items=["Substantiation for Schedule C Part V: miscellaneous $6,000; cell phone $2,000 with business-use percentage; conference travel $4,300 (receipts, agenda, business purpose)",
                     "Explanation of $1,840 interest reported by Harbor Trust Savings that is not on Schedule B",
                     "Confirm whether subcontract labor ($6,100) duplicates line 11 contract labor"])]

A_DETERMINATIONS = [
    dict(det_id="D-A1", issue_id="I-A1", issue="Unreported interest — Harbor Trust Savings", outcome="ADJUSTED",
         amount=1840, authority="IRC 61(a)(4)", detail="Representative confirmed the account; interest omitted in error."),
    dict(det_id="D-A2", issue_id="I-A2", issue="Schedule C other expenses (Part V)", outcome="PARTIALLY_ALLOWED",
         amount=-6600, authority="IRC 162(a); IRC 274(d); IRC 6001",
         detail="Conference travel substantiated ($4,300). Cell phone 70% business use: $1,400 allowed, $600 disallowed. "
                "Miscellaneous: no records, $6,000 disallowed. Subcontract labor moved to line 11 — no tax effect."),
]

A_ADJUSTMENTS = [  # form, line, desc, as_filed, as_adjusted
    ("SCH_B", "2", "Taxable interest", 412, 2252),
    ("SCH_C", "11", "Contract labor (Part V subcontract labor reclassified)", 41200, 47300),
    ("SCH_C", "27a", "Other expenses", 18400, 5700),
    ("SCH_C", "31", "Net profit", 88500, 95100),
]

A_TIMELINE = [
    ("2025-04-14", "RVE", "TY2024 return posts (TC 150); balance paid with the return (TC 610)", "Master File"),
    ("2026-05-24", "OIC", "Offer deemed processable — levy barred under IRC 6331(k)", "OIC episode"),
    ("2026-08-10", "EXAM", "Exam opened on TY2024 from the offer investigation referral", "Exam episode"),
    ("2026-08-12", "RVE", "Working snapshot created; Part V detail captured from the PDF statement", "RVE"),
    ("2026-08-17", "EXAM", "IDR-A1 (Form 4564) issued to the POA", "Contact event"),
    ("2026-09-12", "EXAM", "IDR-A1 response received", "Contact event"),
    ("2026-09-30", "EXAM", "Form 4549 (RAR) issued — proposed deficiency", "Contact event"),
    ("2026-10-09", "EXAM", "Form 4549 signed — agreed", "Determination"),
    ("2026-10-26", "RVE", "As-examined snapshot; TC 300 assessed; CP22E issued", "Master File"),
]

A_EFFECTS = [
    ("Account", f"TY2024 module re-opens with a ${A_DEFICIENCY:,} TC 300 assessment plus statutory interest; a new CSED starts at assessment.", "cited"),
    ("Offer in compromise", "The new TY2024 liability must be brought into the offer, and the Harbor Trust ($28,400) and Meridian ($6,750) balances added to net realizable equity before RCP is recomputed.", "question"),
    ("Passport", "Certification stays in place; the debt grows. Acceptance of the offer would still be a reversal trigger under IRC 7345(c).", "cited"),
    ("ACS", "Enforcement stays suspended — levy remains barred while the offer is pending (IRC 6331(k)).", "cited"),
    ("Penalty", f"Understatement ${A_DEFICIENCY:,} is below the substantial understatement floor; negligence under IRC 6662(b)(1) considered but not asserted.", "question"),
]

# ----------------------------------------------------------------------------------------------
# Case B  Marcus and Elena Thornbury
# ----------------------------------------------------------------------------------------------
B = dict(
    case_id="B", tin="TK200001", name="Marcus & Elena Thornbury", tin_display="XXX-XX-3308", tax_period="202412",
    filing_status="Married filing jointly", city="Seattle", state="WA",
    poa="None", title="Individual exam through RVE — real estate professional claim",
    selection=("Classified for field exam: Schedule E claims $64,000 of rental losses as nonpassive under "
               "the real estate professional rule on a return with $182,000 of W-2 wages. No Form 8582 was filed."),
    selection_status="question",  # selection source to confirm
    team=[("Revenue agent", "D. Castellanos, GS-12", "Exam episode owner"),
          ("Group manager", "S. Imura", "Approves RAR and any penalty (IRC 6751(b))"),
          ("Taxpayers", "Marcus & Elena Thornbury", "No representative")],
)

B_PROPS = [  # sub_id, address, rents, expenses_incl_depr, net, elena_hours, managed_by
    ("R1_ALKI", "Alki duplex", 38000, 52000, -14000, 520, "Self-managed"),
    ("R2_DELRIDGE", "Delridge single-family", 24000, 41000, -17000, 90, "Pugetview Property Management"),
    ("R3_BURIEN", "Burien triplex", 45000, 78000, -33000, 60, "Pugetview Property Management"),
]

B_SCH = {
    "filed": [
        ("W2", "1", "Wages — Marcus (Lumenfield Software)", "WagesAmt", 182000, "Y", "LUMENFIELD"),
        ("SCH_B", "1", "Interest — Sound Credit Union", "InterestAmt", 1150, "Y", "SOUND_CU"),
        ("SCH_C", "1", "Gross receipts — Elena, real estate commissions", "GrossReceiptsAmt", 96000, "Y", "NORTHBEAM"),
        ("SCH_C", "28", "Total expenses", "TotalExpensesAmt", 31000, "Y", "NORTHBEAM"),
        ("SCH_C", "31", "Net profit", "NetProfitOrLossAmt", 65000, "N", "NORTHBEAM"),
    ] + [x for p in B_PROPS for x in [
        ("SCH_E", "3", f"Rents received — {p[1]}", "RentsReceivedAmt", p[2], "Y", p[0]),
        ("SCH_E", "20", f"Total expenses incl. depreciation — {p[1]}", "TotalExpensesAmt", p[3], "Y", p[0]),
        ("SCH_E", "21", f"Income or loss — {p[1]}", "RentalIncomeOrLossAmt", p[4], "N", p[0]),
    ]] + [
        ("SCH_E", "26", "Total rental real estate loss", "TotalRentalRealEstateIncmAmt", -64000, "N", ""),
        ("SCH_E", "43", "Real estate professional — net loss from materially participated rentals", "RealEstateProfessionalAmt", -64000, "Y", ""),
        ("SCH_A", "8a", "Home mortgage interest (1098)", "HomeMortgageInterestAmt", 18600, "Y", ""),
        ("SCH_A", "5e", "State and local taxes (capped)", "StateAndLocalTaxAmt", 10000, "N", ""),
        ("SCH_A", "11", "Gifts by cash or check", "GiftsByCashOrCheckAmt", 4000, "Y", ""),
        ("SCH_A", "17", "Total itemized deductions", "TotalItemizedDeductionsAmt", 32600, "N", ""),
        ("SCH_SE", "12", "Self-employment tax — Elena", "SelfEmploymentTaxAmt", B_TAX_FILED["_se_tax"], "N", ""),
    ],
}

B_FINDINGS = [
    ("F-B1", "RVE", "Schedule E line 43 · real estate professional claim", None, "SCH_E 43", -64000, "C", "IDR_REQUIRED",
     "No Form 8582, no aggregation election in MeF or attachments, and no hours data anywhere in MeF. Each rental must be tested separately unless an election exists, so the IDR asks for hours and any election."),
    ("F-B2", "IRP", "1099-MISC · Pugetview Property Management (rents, R2 + R3)", 69000, "SCH_E 3", 69000, "A", "MATCHED",
     "Rents for the two managed properties match Schedule E."),
    ("F-B3", "IRP", "1099-NEC · Northbeam Realty", 96000, "SCH_C 1", 96000, "A", "MATCHED",
     "Commissions match Schedule C gross receipts."),
    ("F-B4", "IRP", "W-2 · Lumenfield Software", 182000, "1040 1z", 182000, "A", "MATCHED", "Wages and withholding match."),
    ("F-B5", "IRP", "1098 · residence mortgage interest", 18600, "SCH_A 8a", 18600, "B", "NOT_A_TAXPAYER_ISSUE",
     "Matches; SALT correctly capped at $10,000."),
]

B_IDR = [
    dict(idr_id="IDR-B1", form="Form 4564", issued="2026-05-11", due="2026-06-10", response="2026-06-08",
         to="Marcus & Elena Thornbury", status="RESPONDED",
         items=["Contemporaneous 2024 hours records for real estate brokerage and for each rental property",
                "Any statement electing to treat all interests in rental real estate as a single rental activity (Treas. Reg. 1.469-9(g)), filed with the 2024 or any prior return",
                "Property management agreements for each rental"]),
    dict(idr_id="IDR-B2", form="Form 4564", issued="2026-06-22", due="2026-07-13", response="2026-07-10",
         to="Marcus & Elena Thornbury", status="RESPONDED",
         items=["Pugetview Property Management activity records for Delridge and Burien (hours and services performed in 2024)"]),
]

B_DETERMINATIONS = [
    dict(det_id="D-B1", issue_id="I-B1", issue="Real estate professional status (Elena)", outcome="SUSTAINED",
         amount=0, authority="IRC 469(c)(7)(B)",
         detail="1,450 hours in real estate brokerage, her only work: more than half her personal services and more than 750 hours."),
    dict(det_id="D-B2", issue_id="I-B1", issue="Material participation, rental by rental", outcome="PARTIALLY_ALLOWED",
         amount=50000, authority="IRC 469(c)(7)(A); Treas. Reg. 1.469-9(e), (g); Treas. Reg. 1.469-5T(a)",
         detail="No aggregation election on file, so each rental is a separate activity. Alki 520 hours — material participation. "
                "Delridge 90 hours and Burien 60 hours, with the property manager doing more — not material participation. "
                "$50,000 of losses are passive."),
    dict(det_id="D-B3", issue_id="I-B1", issue="Passive loss limitation (Form 8582)", outcome="SUSPENDED",
         amount=50000, authority="IRC 469(a), (b), (i)",
         detail="No passive income. Modified AGI above $150,000, so no $25,000 allowance. $50,000 suspended and carried to 2025 (Delridge $17,000, Burien $33,000)."),
]

B_ADJUSTMENTS = [
    ("SCH_E", "21", "Delridge single-family — loss allowed", -17000, 0),
    ("SCH_E", "21", "Burien triplex — loss allowed", -33000, 0),
    ("SCH_E", "26", "Total rental real estate loss allowed", -64000, -14000),
    ("SCH_E", "43", "Real estate professional — materially participated rentals", -64000, -14000),
    ("F8582", "—", "Suspended passive loss carried to 2025", 0, 50000),
]

B_TIMELINE = [
    ("2025-04-15", "RVE", "TY2024 return posts (TC 150); $837 refunded (TC 846)", "Master File"),
    ("2026-05-04", "EXAM", "Field exam opened; initial contact letter (Letter 2205)", "Exam episode"),
    ("2026-05-06", "RVE", "Working snapshot created; election and hours fields added as RVE supplements", "RVE"),
    ("2026-05-11", "EXAM", "IDR-B1 (Form 4564) issued", "Contact event"),
    ("2026-06-08", "EXAM", "IDR-B1 response: hours logs, no election statement", "Contact event"),
    ("2026-06-22", "EXAM", "IDR-B2 issued for property manager records", "Contact event"),
    ("2026-07-10", "EXAM", "IDR-B2 response received", "Contact event"),
    ("2026-09-28", "EXAM", "30-day letter (Letter 950) with Form 4549 and Form 886-A", "Contact event"),
    ("2026-10-26", "EXAM", "Protest received — requests Appeals and late-election relief", "Contact event"),
]

B_EFFECTS = [
    ("Account", f"No assessment yet — the ${B_DEFICIENCY:,} deficiency is proposed, unagreed. The TC 150 refund of $837 stands until assessment.", "cited"),
    ("Future years", "$50,000 of suspended passive losses carry to TY2025 on Form 8582 and are released by passive income or a full disposition (IRC 469(b), (g)). RVE should carry the carryforward into the next year's snapshot.", "cited"),
    ("Appeals", "Protest raises late aggregation-election relief under Rev. Proc. 2011-34. If granted, the three rentals are one activity: 670 hours, material participation, and the adjustment falls away.", "question"),
    ("Statute", "ASED 15 Apr 2028. Appeals needs enough statute time remaining when the case arrives; consider Form 872 if the protest stalls.", "question"),
    ("Penalty", f"Understatement ${B_DEFICIENCY:,} exceeds the greater of 10% of correct tax or $5,000 — IRC 6662(d) threshold met (${B_PENALTY_IF_ASSERTED:,} if asserted). Needs written supervisory approval (IRC 6751(b)); reasonable cause to be weighed.", "question"),
]

SME_FLAGS = [
    ("A", "Referral path from an offer investigation to Exam for a year inside the offer period", "question"),
    ("A", "How a post-submission assessment is brought into a pending offer, and RCP treatment of the two undisclosed accounts", "question"),
    ("A", "Head of household vs the TP360 page's 'Single' filing status", "question"),
    ("A", "Negligence penalty not asserted on unsubstantiated miscellaneous expenses", "question"),
    ("B", "Selection source for an REP claim on a W-2 household", "question"),
    ("B", "Eligibility for Rev. Proc. 2011-34 late-election relief raised in the protest", "question"),
    ("B", "Assertion of the IRC 6662(d) penalty and supervisory approval timing", "question"),
    ("AB", "Rentals treated as not QBI (no section 199A trade-or-business position taken)", "design"),
]
