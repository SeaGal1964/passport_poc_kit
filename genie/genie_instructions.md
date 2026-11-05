## Purpose
IRC 7345 passport certification analytics on synthetic IRS data. As-of date is 2026-10-23; never use today's date. tin_token is a synthetic token, not an SSN. Never use pp_answer_key.

## Where to look
- v_findings: one row per taxpayer per finding. Start here for "who has what problem."
- v_taxpayer_eval: one row per taxpayer; pre-aggregated balances and dates. Use directly; don't re-sum modules.
- v_module_eval: one row per module (tin_token + mft + tax_period). Use for any module-level detail or module balances.
- v_module_reversal_reason: one row per certified module with a reversal trigger, with its reversal_reason.
- v_appeals_cdp: one row per CDP case; source_systems shows ACDS, ACMS, or both.
- ref_threshold: threshold by year. ref_indicator: TC/AC meanings.

## Key rules
- Balances = unpaid assessed balance only; no accruals.
- Certified = TC 971 AC 641; reversed = TC 972 AC 641. Action window = 30 days; OVERDUE = >30 days since trigger.
- Don't recompute findings, timeliness, or pending/overdue; use the finding codes.
- days_since_trigger = trigger to as-of date. For REVERSED_TIMELY/LATE, days from trigger to final TC 972 = datediff(final_reversal_date, reversed_trigger_date) in v_taxpayer_eval.
- At-certification comparisons use the certification-year threshold (ref_threshold), not v_taxpayer_eval.threshold_amount.
- Never subtract taxpayer-level balances to get module amounts; query v_module_eval with filters and sum assessed_balance.
- Lacking predicate = certified_now AND (predicate_date IS NULL OR predicate_date > active_641_date).
- Levy vs lien (missed certs): per taxpayer, from eligible_now modules; levy if levy_predicate_date <= as_of, lien if lien_predicate_date <= as_of; report Levy only / Lien only / Both.
- For why a certified module needs reversal, use v_module_reversal_reason.reversal_reason (one row per certified module with a trigger). Don't derive reasons yourself.
- INFO_BELOW_THRESHOLD_STILL_CERTIFIED is NOT an error; dropping below threshold isn't a reversal condition.
- MISSED_CERTIFICATION = eligible but not currently certified (may have been certified before).
- "Currently certified" = v_taxpayer_eval.certified_modules > 0 (an active, unreversed TC 971 AC 641). A taxpayer remains certified until TC 972 AC 641 posts, even if decertification is due or overdue. Don't exclude taxpayers with a decert_trigger_date. If asked who should remain certified, that's a different question: exclude DECERT_DUE_* taxpayers.
- "Module needs reversal while taxpayer stays certified" = findings MODULE_REVERSAL_DUE_PENDING / MODULE_REVERSAL_DUE_OVERDUE in v_findings. If ALL certified modules need reversal, that is DECERT_DUE_PENDING / DECERT_DUE_OVERDUE (full decertification), not a module reversal. Never derive these from reversal_trigger_date yourself.
- Days overdue = days_since_trigger − 30.
