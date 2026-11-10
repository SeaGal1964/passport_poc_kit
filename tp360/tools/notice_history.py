"""Synthetic notice history for the TP360 POC (tp_contact_event).

Called by build_tp360_data.py after every other table is built. Uses its own random seed so the rest
of the synthetic data (and the signal answer key) does not change.

Notice sequences are illustrative and follow the general shape of each program. Item codes and
timing are SME to confirm before anything is shown as IRS practice:
  - Balance due (by module):  CP14 -> CP501 -> CP503 -> CP504, stopping when an installment
    agreement starts; then one final notice per taxpayer (LT11 for ACS, Letter 1058 for field
    collection) with a 30-day response window
  - Installment agreement default: CP523
  - Passport certification: CP508C            - Offer in compromise: Letter 3016
  - AUR: CP2000 (30 days) -> Letter 3219 statutory notice of deficiency when unanswered
  - Correspondence exam: Letter 566 -> Form 4549 report -> Letter 3219 when unanswered
  - Field exam: Letter 2205 -> Form 4564 IDRs -> Form 4549 or Letter 950 (30-day letter)
  - Exam assessment: CP22E;  no-change closings: Letter 590 (exam) / AUR no-change letter
statutory_flag = Y for notice and demand (CP14, CP22E), CP504, LT11/Letter 1058, CP523, CP508C and Letter 3219.
"""
import random
from datetime import date, timedelta

rng = random.Random(7345)


def _d(s):
    return date.fromisoformat(s) if s else None


def generate(T, add, AS_OF, iso):
    tp = {r["tin_token"]: r for r in T["tp_taxpayer"]}
    eps = {r["episode_id"]: r for r in T["tp_compliance_episode"]}
    existing = {(r["tin_token"], r["item_code"]) for r in T["tp_contact_event"]}
    has_contacts = {r["episode_id"] for r in T["tp_contact_event"]}
    n = [len(T["tp_contact_event"])]
    added = [0]

    def periods(mods):
        return ";".join(m[-6:] for m in mods.split(";") if m)

    def notice(tin, mods, ep, ctype, code, src, stat, issued, due_days=None, recv=None, to=None):
        if issued > AS_OF:
            return
        n[0] += 1
        added[0] += 1
        to = to or "TAXPAYER"
        status = "UNDELIVERABLE" if rng.random() < 0.03 else "DELIVERED"
        due = issued + timedelta(days=due_days) if due_days else None
        if status == "UNDELIVERABLE":
            recv = None
        if recv and recv > AS_OF:
            recv = None
        add("tp_contact_event", contact_id=f"CE{n[0]:05d}", tin_token=tin, module_ids=mods, episode_id=ep or "",
            contact_type=ctype, item_code=code, source_system=src, statutory_flag=stat, issued_date=iso(issued),
            delivery_status=status, response_due=iso(due) if due else "", response_received=iso(recv) if recv else "",
            recipient=to, tax_periods=periods(mods))

    by_tin = {}
    for e in T["tp_compliance_episode"]:
        by_tin.setdefault(e["tin_token"], []).append(e)

    # ---- balance-due notice stream, by module ---------------------------------------------
    # a module whose balance came from a closed exam or AUR case already gets its assessment notice
    # (CP22E or CP14) from the case section below, so its stream starts at CP501
    case_assessed = {(c["tin_token"], str(c["tax_period"]), str(c["closed_date"])) for c in T["tp_case_closure"]}
    final_mods = {}
    for m in T["tp_tax_module"]:
        bal = float(m["assessed_balance"] or 0)
        if bal <= 0 or str(m["module_status"]) not in ("21", "22", "24", "26"):
            continue
        tin = m["tin_token"]
        a = _d(str(m["last_assessment_date"] or "")) or (_d(str(m["csed"])).replace(year=_d(str(m["csed"])).year - 10) if m["csed"] else None)
        if not a:
            continue
        ia_starts = sorted(_d(e["opened_date"]) for e in by_tin.get(tin, []) if e["episode_type"] == "IA" and _d(e["opened_date"]) > a)
        stop = ia_starts[0] if ia_starts else None
        seq = [("CP14", 0), ("CP501", 35), ("CP503", 70), ("CP504", 105)]
        if str(m["module_status"]) == "21":
            seq = seq[:2]
        if any(k[0] == tin and k[1] == str(m["tax_period"]) and _d(k[2]) and abs((_d(k[2]) - a).days) <= 30 for k in case_assessed):
            seq = seq[1:]
        for code, off in seq:
            when = a + timedelta(days=off + rng.randrange(0, 4))
            if stop and when >= stop:
                break
            notice(tin, m["module_id"], "", "NOTICE", code, "MASTER_FILE", "Y" if code in ("CP14", "CP504") else "N", when)
        if str(m["module_status"]) in ("22", "26"):
            f = final_mods.setdefault(tin, {"mods": [], "first": a, "status": str(m["module_status"])})
            f["mods"].append(m["module_id"])
            f["first"] = min(f["first"], a)
            if str(m["module_status"]) == "26":
                f["status"] = "26"

    for tin, f in final_mods.items():
        code, src = ("Letter 1058", "FIELD_COLLECTION") if f["status"] == "26" else ("LT11", "ACS")
        if (tin, "LT11") in existing or (tin, "Letter 1058") in existing:
            continue
        ia_ends = [_d(e["closed_date"]) for e in by_tin.get(tin, []) if e["episode_type"] == "IA" and e["closed_date"]]
        when = max([f["first"] + timedelta(days=160)] + [x + timedelta(days=45) for x in ia_ends])
        ep = next((e["episode_id"] for e in by_tin.get(tin, []) if e["episode_type"] in ("ACS", "FIELD_COLLECTION") and not e["closed_date"]), "")
        notice(tin, ";".join(sorted(f["mods"])), ep, "NOTICE", code, src, "Y", when, due_days=30)

    # ---- episode-level notices -----------------------------------------------------------
    for e in T["tp_compliance_episode"]:
        tin, ep, mods = e["tin_token"], e["episode_id"], e["module_ids"]
        if ep in has_contacts:
            continue
        o, c = _d(e["opened_date"]), _d(e["closed_date"])
        if e["episode_type"] == "IA" and e["status"] == "DEFAULTED" and c:
            notice(tin, mods, ep, "NOTICE", "CP523", "MASTER_FILE", "Y", c - timedelta(days=30), due_days=30)
        elif e["episode_type"] == "PASSPORT" and (tin, "CP508C") not in existing:
            notice(tin, mods, ep, "NOTICE", "CP508C", "PASSPORT", "Y", o)
        elif e["episode_type"] == "OIC":
            notice(tin, mods, ep, "LETTER", "Letter 3016 (offer processable)", "COIC", "N", o + timedelta(days=9),
                   to="POA" if tp.get(tin, {}).get("poa_on_file") == "Y" else "TAXPAYER")

    # ---- exam and AUR notices, from the closed cases ---------------------------------------
    for cc in T["tp_case_closure"]:
        ep = cc["episode_id"]
        if ep in has_contacts or ep not in eps:
            continue
        tin, prog, out = cc["tin_token"], cc["program"], cc["outcome"]
        mods = f"{tin}-30-{cc['tax_period']}"
        o, c = _d(eps[ep]["opened_date"]), _d(cc["closed_date"])
        if not o or not c:
            continue
        span = max((c - o).days, 60)
        at = lambda frac: o + timedelta(days=int(span * frac) + rng.randrange(0, 5))
        poa = "POA" if tp.get(tin, {}).get("poa_on_file") == "Y" else "TAXPAYER"
        defic = float(cc["deficiency"] or 0)
        if prog == "AUR":
            recv = None if out == "DEFAULTED_SNOD" else o + timedelta(days=rng.randrange(10, 29))
            notice(tin, mods, ep, "NOTICE", "CP2000", "AUR", "N", o, due_days=30, recv=recv)
            if out == "DEFAULTED_SNOD":
                notice(tin, mods, ep, "NOTICE", "Letter 3219", "AUR", "Y", at(0.45), due_days=90)
            if out == "NO_CHANGE":
                notice(tin, mods, ep, "LETTER", "AUR no-change letter", "AUR", "N", c)
            elif defic > 0:
                notice(tin, mods, ep, "NOTICE", "CP14", "MASTER_FILE", "Y", c + timedelta(days=21))
            continue
        if prog == "CORRESPONDENCE":
            recv = None if out == "DEFAULTED_SNOD" else o + timedelta(days=rng.randrange(12, 34))
            notice(tin, mods, ep, "LETTER", "Letter 566", "EXAM", "N", o, due_days=30, recv=recv, to=poa)
        else:
            notice(tin, mods, ep, "LETTER", "Letter 2205", "EXAM", "N", o, to=poa)
            for k in range(rng.choice([1, 2, 2, 3])):
                iss = at(0.1 + 0.15 * k)
                late = rng.random() < 0.15
                notice(tin, mods, ep, "IDR", "Form 4564", "EXAM", "N", iss, due_days=21,
                       recv=iss + timedelta(days=rng.randrange(24, 40) if late else rng.randrange(8, 21)), to=poa)
        if out == "NO_CHANGE":
            notice(tin, mods, ep, "LETTER", "Letter 590", "EXAM", "N", c, to=poa)
            continue
        if out in ("UNAGREED_APPEALS", "DEFAULTED_SNOD") and prog == "FIELD":
            iss = at(0.7)
            notice(tin, mods, ep, "LETTER", "Letter 950", "EXAM", "N", iss, due_days=30,
                   recv=iss + timedelta(days=rng.randrange(18, 29)) if out == "UNAGREED_APPEALS" else None, to=poa)
        else:
            iss = at(0.6)
            recv = None if out == "DEFAULTED_SNOD" else iss + timedelta(days=rng.randrange(7, 28))
            notice(tin, mods, ep, "REPORT", "Form 4549", "EXAM", "N", iss, due_days=30, recv=recv, to=poa)
        if out == "DEFAULTED_SNOD":
            notice(tin, mods, ep, "NOTICE", "Letter 3219", "EXAM", "Y", at(0.85), due_days=90)
        if defic > 0 and out != "UNAGREED_APPEALS":
            notice(tin, mods, ep, "NOTICE", "CP22E", "MASTER_FILE", "Y", c + timedelta(days=21))
    return added[0]
