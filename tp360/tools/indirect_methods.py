"""Exam income probes and formal indirect methods (IRM 4.10.4), exam-side data only.

What this builds, all synthetic:
  tp_ref_ple               BLS-style personal living expense table (household size x region x year). SYNTHETIC
                           figures shaped like BLS Consumer Expenditure data; not BLS values.
  tp_fsa / tp_fsa_line     Financial status analysis (the Cash T, IRM 4.10.4.2.3.1): sources on the left,
                           applications on the right, each line tagged with where the exam got it.
  tp_indirect_method_gate  The IRC 7602(e) gate (IRM 4.10.4.5.1.1, 4.10.4.5.2.3-.2.4): the documented reasonable
                           indication, likely income source, method chosen, date documented, manager concurrence
                           (net worth only) and the date the result was first used.
  tp_bdce_line             Bank deposits and cash expenditures computation, 11 lines (IRM 4.10.4.5.4.6).
  tp_net_worth_item        Net worth statements and adjustments (IRM 4.10.4.5.7).

Sources are exam-side only: the return, information returns, internal IRS records, the initial interview and,
for business returns, bank records (IRM 4.10.4.2.3.7). No collection financial statement data is used.

Worked cases
  Marisol T. Vance 201912 (closed field exam EP-A-EX19): material Cash T imbalance -> gate documented -> bank
    deposits method -> corrected gross receipts exceed reported by $58,000, the amount sustained on the issue.
  Marcus Thornbury 202412 (open field exam EP-B-EX24): Cash T balances, so no formal method; the issue is legal.
  Three new open field exams on filler taxpayers:
    EP-OX1-EX Xena Jessup 202312-202412: material imbalance both years -> net worth method, manager concurrence.
    EP-OX2-EX Jonah Vance-Ortiz 202412: material imbalance, gate not yet documented (formal method not allowed yet).
    EP-OX3-EX Xena Faraday 202412: Cash T balances.

Materiality rule used for the POC (SME to confirm): MATERIAL when applications exceed sources by at least
$10,000 and by at least 10% of total sources.
"""
REGION = {"WA": "West", "OR": "West", "CA": "West", "NY": "Northeast", "TX": "South", "IL": "Midwest"}
BASE_2023 = {1: 38000, 2: 52000, 3: 58000, 4: 66000, 5: 72000}
REGION_F = {"West": 1.00, "Northeast": 1.00, "South": 0.88, "Midwest": 0.86}
MATERIAL_DOLLARS, MATERIAL_PCT = 10000, 0.10


def ple(year, region, hh):
    return round(BASE_2023[hh] * REGION_F[region] * 1.03 ** (year - 2023))


def material(sources, applications):
    gap = applications - sources
    return gap >= MATERIAL_DOLLARS and gap >= MATERIAL_PCT * sources


def generate(T, add):
    for y in range(2019, 2026):
        for region in REGION_F:
            for hh in BASE_2023:
                add("tp_ref_ple", tax_year=y, region=region, household_size=hh, annual_ple=ple(y, region, hh),
                    source="SYNTHETIC — shaped like BLS Consumer Expenditure tables; not BLS figures")

    tp = {r["tin_token"]: r for r in T["tp_taxpayer"]}
    results = {}

    def fsa(fid, tin, ep, period, rclass, hh, coh, prepared, by, sources, applications, note=""):
        region = REGION[tp[tin]["state"]]
        yr = int(period[:4])
        applications = [("Personal living expenses", f"BLS-style table, household of {hh}, {region}",
                          ple(yr, region, hh), "BLS_TABLE", "tp_ref_ple")] + applications
        s, a = sum(x[2] for x in sources), sum(x[2] for x in applications)
        concl = "MATERIAL_IMBALANCE" if material(s, a) else "INCOME_SUPPORTS_EXPENDITURES"
        add("tp_fsa", fsa_id=fid, tin_token=tin, episode_id=ep, tax_period=period, return_class=rclass, household_size=hh,
            region=region, prepared_date=prepared, prepared_by=by, cash_on_hand_begin=coh[0], cash_on_hand_end=coh[1],
            coh_established_date=coh[2], conclusion=concl, note=note)
        n = 0
        for side, rows in (("SOURCE", sources), ("APPLICATION", applications)):
            for cat, desc, amt, basis, ref in rows:
                n += 1
                add("tp_fsa_line", fsa_id=fid, seq=n, side=side, category=cat, description=desc, amount=amt, basis=basis, reference=ref)
        results[fid] = (s, a, concl)

    # ---- Marisol 201912: business return (Schedule C), closed field exam -----------------------
    # Ties to the closed case: reported gross receipts 196,000 (ADJ-CC00001), Schedule 1 business income 70,400,
    # interest 380, sustained understatement 58,000. Exam opened 2021-03-15; Form 4549 issued 2021-08-20.
    fsa("FSA-A-2019", "TK100001", "EP-A-EX19", "201912", "BUSINESS", 3, (500, 500, "2021-04-06"), "2021-04-08", "R. Okonkwo",
        [("Schedule C gross receipts", "Sign shop receipts as reported", 196000, "RETURN", "SCH_C 1"),
         ("Interest income", "Savings interest as reported", 380, "RETURN", "1040 2b"),
         ("Gift (nontaxable)", "Gift from parent, verified with donor", 3000, "INTERVIEW", "Initial interview 2021-04-06"),
         ("Federal refund (nontaxable)", "2018 refund received 2019", 1150, "INTERNAL", "IDRS TC 846")],
        [("Business expenses paid", "Schedule C expenses excluding depreciation of $4,000", 121600, "RETURN", "SCH_C 28 less 13"),
         ("Estimated tax payments", "2019 estimated payments", 2200, "RETURN", "1040 26"),
         ("Asset purchase", "Vehicle bought 2019, cash down payment", 24500, "THIRD_PARTY", "State title and dealer records"),
         ("Increase in bank balances", "Savings account up for the year", 24600, "BANK_RECORDS", "Bank account analysis, IRM 4.10.4.2.3.7")],
        "Business return: bank account analysis is a minimum income probe.")
    s_, a_, _ = results["FSA-A-2019"]
    add("tp_indirect_method_gate", gate_id="G-A-2019", episode_id="EP-A-EX19", tin_token="TK100001", tax_periods="201912",
        method="BANK_DEPOSITS",
        triggers="Cash T material imbalance; deposits to personal savings exceed reported gross receipts; most expenses paid by check or card",
        reasonable_indication=f"Cash T applications exceed sources by ${a_ - s_:,} ({(a_ - s_) / s_:.0%}). Bank account analysis shows recurring "
                              "deposits to a personal savings account with the inherent appearance of sign-shop receipts.",
        likely_income_source="Schedule C sign-shop receipts deposited to a personal savings account and not recorded in the books",
        documented_date="2021-05-10", manager_concurrence_date="", result_used_date="2021-07-30", status="RESULT_USED")
    bd = [(1, "Total deposits, all accounts (business and personal)", 276330, "Three accounts; adjusted to current-year receipts"),
          (2, "Less nontaxable and nonbusiness deposits", -19330, "Transfers 14,800; gift 3,000; 2018 refund 1,150; interest 380"),
          (3, "Net deposited receipts", 257000, "Line 1 plus line 2"),
          (4, "Business expenses paid in cash", 2600, "Claimed expenses not paid by check or card"),
          (5, "Capital items paid in cash", 0, ""),
          (6, "Personal expenses paid in cash", 4800, "Living expenses not paid by check or card"),
          (7, "Cash accumulated during the year", 0, "Cash on hand $500 at both year ends, established at the initial interview"),
          (8, "Less nontaxable cash used for lines 4-7", -10400, "Cash withdrawn from accounts already counted in line 1"),
          (9, "Change in accounts receivable", 0, "Cash-basis taxpayer"),
          (10, "Change in accounts payable", 0, "Cash-basis taxpayer"),
          (11, "Corrected gross receipts", 254000, "Lines 3 through 10"),
          (12, "Gross receipts reported", 196000, "SCH_C 1"),
          (13, "Understatement of gross receipts", 58000, "Line 11 less line 12; the amount sustained on issue I-CC00001")]
    assert bd[2][2] == bd[0][2] + bd[1][2] and bd[10][2] == bd[2][2] + sum(x[2] for x in bd[3:10]) and bd[12][2] == bd[10][2] - bd[11][2]
    for ln, label, amt, note in bd:
        add("tp_bdce_line", episode_id="EP-A-EX19", tin_token="TK100001", tax_period="201912", line_no=ln, line_label=label, amount=amt, note=note)

    # ---- Thornbury 202412: business return (Elena's Schedule C), open field exam, Cash T balances -----
    fsa("FSA-B-2024", "TK200001", "EP-B-EX24", "202412", "BUSINESS", 2, (0, 0, "2026-05-19"), "2026-05-21", "D. Brennan",
        [("Wages", "Marcus, Lumenfield Software (gross)", 182000, "RETURN", "W2 1"),
         ("Schedule C gross receipts", "Elena, real estate commissions", 96000, "RETURN", "SCH_C 1"),
         ("Rents received", "Three rental properties", 107000, "RETURN", "SCH_E 3"),
         ("Interest income", "Sound Credit Union", 1150, "RETURN", "SCH_B 1")],
        [("Business expenses paid", "Schedule C expenses", 31000, "RETURN", "SCH_C 28"),
         ("Rental expenses paid", "Schedule E expenses excluding depreciation of $46,000", 125000, "RETURN", "SCH_E 20 less depreciation"),
         ("Income tax withheld", "Federal withholding", 29800, "RETURN", "1040 25d"),
         ("Social Security and Medicare withheld", "W-2 withholding at 7.65%", 13923, "RETURN", "W-2 boxes 4 and 6"),
         ("Itemized expenses paid", "Mortgage interest, state and local taxes, cash gifts", 32600, "RETURN", "SCH_A 17"),
         ("Debt reduction", "Rental mortgage principal", 27000, "THIRD_PARTY", "Lender statements"),
         ("Increase in bank balances", "Joint and business accounts", 41000, "BANK_RECORDS", "Bank account analysis, IRM 4.10.4.2.3.7")],
        "Sources exceed applications; no indication of unreported income. The open issue is the real estate professional claim, a legal question.")

    # ---- New open field exams on filler taxpayers --------------------------------------------
    opens = [("EP-OX1-EX", "TK300006", "2026-07-14", ["202312", "202412"]),
             ("EP-OX2-EX", "TK300010", "2026-09-22", ["202412"]),
             ("EP-OX3-EX", "TK300013", "2026-08-03", ["202412"])]
    for ep, tin, opened, periods in opens:
        mods = ";".join(f"{tin}-30-{p}" for p in periods)
        add("tp_compliance_episode", episode_id=ep, tin_token=tin, episode_type="EXAM", episode_subtype="Field",
            opened_date=opened, closed_date="", status="IN_PROCESS", module_ids=mods)
        add("tp_treatment_assignment", episode_id=ep, function="EXAM", assignee="Field Exam — Revenue Agent", start_date=opened, end_date="")
        for p in periods:
            add("tp_tax_module", module_id=f"{tin}-30-{p}", tin_token=tin, mft=30, tax_period=p, assessed_balance=0,
                last_assessment_date=f"{int(p[:4]) + 1}-04-15", csed=f"{int(p[:4]) + 11}-04-15", module_status="10")

    fsa("FSA-OX1-2023", "TK300006", "EP-OX1-EX", "202312", "BUSINESS", 3, (1000, 1000, "2026-07-21"), "2026-07-28", "K. Lindqvist",
        [("Schedule C gross receipts", "Landscaping receipts as reported", 88000, "RETURN", "SCH_C 1")],
        [("Business expenses paid", "Schedule C expenses excluding depreciation", 22000, "RETURN", "SCH_C 28 less 13"),
         ("Asset purchase", "Boat, paid in full", 34000, "THIRD_PARTY", "State vessel registration"),
         ("Asset purchase", "Landscaping equipment", 7000, "RETURN", "Form 4562"),
         ("Debt reduction", "Mortgage and truck loan principal", 14000, "THIRD_PARTY", "Lender statements"),
         ("Federal tax paid", "Balance due paid with return", 6800, "INTERNAL", "IDRS"),
         ("Increase in bank balances", "Personal and business accounts", 9000, "BANK_RECORDS", "Bank account analysis")])
    fsa("FSA-OX1-2024", "TK300006", "EP-OX1-EX", "202412", "BUSINESS", 3, (1000, 1000, "2026-07-21"), "2026-07-28", "K. Lindqvist",
        [("Schedule C gross receipts", "Landscaping receipts as reported", 91000, "RETURN", "SCH_C 1"),
         ("Inheritance (nontaxable)", "From an aunt's estate, verified with estate records", 15000, "INTERVIEW", "Initial interview; probate records"),
         ("Decrease in bank balances", "Personal and business accounts", 3000, "BANK_RECORDS", "Bank account analysis")],
        [("Business expenses paid", "Schedule C expenses excluding depreciation", 23000, "RETURN", "SCH_C 28 less 13"),
         ("Asset purchase", "Brokerage account opened", 25000, "IRP", "Form 1099-B / brokerage statements"),
         ("Debt reduction", "Mortgage and truck loan principal", 14000, "THIRD_PARTY", "Lender statements"),
         ("Federal tax paid", "Balance due paid with return", 7100, "INTERNAL", "IDRS")])
    add("tp_indirect_method_gate", gate_id="G-OX1", episode_id="EP-OX1-EX", tin_token="TK300006", tax_periods="202312;202412",
        method="NET_WORTH",
        triggers="Cash T material imbalance in both years; books inadequate (no receipts journal); significant asset purchases",
        reasonable_indication="Cash T applications exceed sources in 2023 and 2024. A boat and a brokerage account were bought "
                              "with no reported source; the taxpayer keeps no receipts journal and deposits only part of receipts.",
        likely_income_source="Landscaping receipts paid in cash and not deposited",
        documented_date="2026-09-08", manager_concurrence_date="2026-09-10", result_used_date="", status="COMPUTED_NOT_PROPOSED")
    nw = {"2022-12-31": [("ASSET", "Bank accounts", 12000), ("ASSET", "Cash on hand", 1000), ("ASSET", "Residence (cost)", 310000),
                         ("ASSET", "Vehicles (cost)", 28000), ("ASSET", "Equipment (cost)", 15000),
                         ("LIABILITY", "Mortgage", 240000), ("LIABILITY", "Truck loan", 18000)],
          "2023-12-31": [("ASSET", "Bank accounts", 21000), ("ASSET", "Cash on hand", 1000), ("ASSET", "Residence (cost)", 310000),
                         ("ASSET", "Vehicles and boat (cost)", 62000), ("ASSET", "Equipment (cost)", 22000),
                         ("LIABILITY", "Mortgage", 233000), ("LIABILITY", "Truck loan", 11000)],
          "2024-12-31": [("ASSET", "Bank accounts", 18000), ("ASSET", "Cash on hand", 1000), ("ASSET", "Residence (cost)", 310000),
                         ("ASSET", "Vehicles and boat (cost)", 62000), ("ASSET", "Equipment (cost)", 22000),
                         ("ASSET", "Brokerage account", 25000), ("LIABILITY", "Mortgage", 226000), ("LIABILITY", "Truck loan", 4000)]}
    for dt, items in nw.items():
        for kind, item, amt in items:
            add("tp_net_worth_item", episode_id="EP-OX1-EX", tin_token="TK300006", tax_period="", as_of_date=dt, item_type=kind,
                item=item, amount=amt, basis="Third-party records and interview" if "Cash" not in item else "Initial interview 2026-07-21")
    for p, rows in {"202312": [("NONDEDUCTIBLE", "Personal living expenses (BLS-style table)", ple(2023, "West", 3)),
                               ("NONDEDUCTIBLE", "Federal tax paid", 6800), ("REPORTED_INCOME", "Adjusted gross income as reported", 61300)],
                    "202412": [("NONDEDUCTIBLE", "Personal living expenses (BLS-style table)", ple(2024, "West", 3)),
                               ("NONDEDUCTIBLE", "Federal tax paid", 7100), ("NONTAXABLE", "Inheritance, verified", 15000),
                               ("REPORTED_INCOME", "Adjusted gross income as reported", 63900)]}.items():
        for kind, item, amt in rows:
            add("tp_net_worth_item", episode_id="EP-OX1-EX", tin_token="TK300006", tax_period=p, as_of_date="", item_type=kind,
                item=item, amount=amt, basis="BLS-style table" if "BLS" in item else ("Return" if kind == "REPORTED_INCOME" else "Interview and records"))
    nwv = {dt: sum(a if k == "ASSET" else -a for k, _, a in items) for dt, items in nw.items()}
    for p, prev, cur in (("202312", "2022-12-31", "2023-12-31"), ("202412", "2023-12-31", "2024-12-31")):
        rows = [r for r in T["tp_net_worth_item"] if r["episode_id"] == "EP-OX1-EX" and r["tax_period"] == p]
        nd = sum(r["amount"] for r in rows if r["item_type"] == "NONDEDUCTIBLE")
        nt = sum(r["amount"] for r in rows if r["item_type"] == "NONTAXABLE")
        rep = sum(r["amount"] for r in rows if r["item_type"] == "REPORTED_INCOME")
        corrected = nwv[cur] - nwv[prev] + nd - nt
        for kind, item, amt in (("NW_INCREASE", f"Increase in net worth {prev[:4]} to {cur[:4]}", nwv[cur] - nwv[prev]),
                                ("CORRECTED_INCOME", "Corrected adjusted gross income", corrected),
                                ("UNDERSTATEMENT", "Understatement of income", corrected - rep)):
            add("tp_net_worth_item", episode_id="EP-OX1-EX", tin_token="TK300006", tax_period=p, as_of_date="", item_type=kind,
                item=item, amount=amt, basis="Computed")
        results[f"NW-OX1-{p}"] = (corrected, rep, corrected - rep)

    fsa("FSA-OX2-2024", "TK300010", "EP-OX2-EX", "202412", "BUSINESS", 1, (300, 300, "2026-10-01"), "2026-10-06", "M. Ferreira",
        [("Schedule C gross receipts", "Food truck receipts as reported", 64000, "RETURN", "SCH_C 1")],
        [("Business expenses paid", "Schedule C expenses excluding depreciation", 31000, "RETURN", "SCH_C 28 less 13"),
         ("Debt payments", "Food truck loan", 9600, "THIRD_PARTY", "Lender statements"),
         ("Increase in bank balances", "Business account", 6500, "BANK_RECORDS", "Bank account analysis")],
        "Formal indirect method not yet allowed: the 7602(e) gate has not been documented.")
    fsa("FSA-OX3-2024", "TK300013", "EP-OX3-EX", "202412", "BUSINESS", 4, (0, 0, "2026-08-12"), "2026-08-14", "K. Lindqvist",
        [("Schedule C gross receipts", "Consulting receipts as reported", 142000, "RETURN", "SCH_C 1"),
         ("Wages", "Spouse wages (gross)", 61000, "RETURN", "W2 1"),
         ("Interest income", "Savings", 800, "RETURN", "SCH_B 1")],
        [("Business expenses paid", "Schedule C expenses excluding depreciation", 38000, "RETURN", "SCH_C 28 less 13"),
         ("Income and payroll tax withheld", "Spouse W-2", 14500, "RETURN", "W-2"),
         ("Estimated tax payments", "2024 estimated payments", 18000, "RETURN", "1040 26"),
         ("Debt reduction", "Mortgage principal", 9000, "THIRD_PARTY", "Lender statements"),
         ("Retirement contributions", "SEP-IRA", 12000, "RETURN", "Schedule 1"),
         ("Increase in bank balances", "Joint and business accounts", 22000, "BANK_RECORDS", "Bank account analysis")])
    expected = {"FSA-A-2019": "MATERIAL_IMBALANCE", "FSA-B-2024": "INCOME_SUPPORTS_EXPENDITURES",
                "FSA-OX1-2023": "MATERIAL_IMBALANCE", "FSA-OX1-2024": "MATERIAL_IMBALANCE",
                "FSA-OX2-2024": "MATERIAL_IMBALANCE", "FSA-OX3-2024": "INCOME_SUPPORTS_EXPENDITURES"}
    for k, v in expected.items():
        assert results[k][2] == v, (k, results[k])
    return results
