## item_005_evaluate_chronological_robustness_and_protect_the_final_holdout - Evaluate chronological robustness and protect the final holdout
> From version: 1.0.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 80%
> Complexity: High
> Theme: Research validity
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-22 17:11:43

# AI Context
- Summary: Protect final evaluation from repeated selection and report robustness with uncertainty.
- Keywords: evaluate, chronological, robustness, protect, final, holdout
- Use when: Implementing chronological windows, stress checks and holdout access history.
- Skip when: Claiming profitability from a single in-sample ranking.

# Problem
- Repeated refinement can turn validation into training and produce false confidence.

# Scope
- In:
  - High priority; depends on tracked campaigns and deterministic simulation.
  - Version train/validation/final periods, warm-up handling, thresholds and access history.
  - Implement cost stress, neighboring-parameter checks, period stability and declared baselines.
  - Report inconclusive samples and comparison at consistent exposure.
  - Prioritize robustness across periods and controlled equity drawdown, then net return; thresholds and ranking mechanics follow the configurable engineering baseline in logics/discovery/mvp-development-contract.md.
  - Implement research policy v1 in logics/discovery/mvp-development-contract.md, including 60/20/20 splits, explicit heuristic eligibility, neighbor/cost stress and deterministic ranking excluding final holdout. Prerequisite: campaign ledger.
- Out:
  - A guarantee of future returns, automatic acceptance based only on headline profit.

# Acceptance criteria
- AC1: Final-holdout results do not feed search/ranking loops; inspection is logged and further tuning invalidates untouched status.
- AC2: Temporal boundaries prevent future leakage while allowing explicitly causal indicator warm-up.
- AC3: Reports contain net performance, equity drawdown, exposure, trades, costs and separate robustness verdicts.
- AC4: Insufficient observations or unavailable stress inputs yield an explicit inconclusive result.

- AC5: Candidate selection prioritizes robustness across periods and controlled equity drawdown before net return, using an explicit versioned policy with agreed thresholds; final-holdout results never participate in selection.

# AC Traceability
- request-AC5 -> This backlog slice. Proof: AC1: Final-holdout results do not feed search/ranking loops; inspection is logged and further tuning invalidates untouched status.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_001_pinguino_major_forex_strategy_research_workbench`
- Architecture decision(s): (none yet)
- Request: `req_000_establish_a_reproducible_major_forex_strategy_research_mvp`
- Primary task(s): `task_001_orchestrate_the_major_forex_strategy_research_mvp`

# Priority
- Priority: High
- Rationale: Chronological evaluation and holdout protection are required before interpreting search results.
