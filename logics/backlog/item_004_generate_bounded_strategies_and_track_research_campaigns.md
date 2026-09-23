## item_004_generate_bounded_strategies_and_track_research_campaigns - Generate bounded strategies and track research campaigns
> From version: 1.0.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: High
> Theme: Strategy generation
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-23 13:14:19

# AI Context
- Summary: Search three explainable families with bounded budgets and an auditable attempt ledger.
- Keywords: generate, bounded, strategies, track, research, campaigns
- Use when: Implementing campaign generation, reproducibility and cancellation.
- Skip when: Unrestricted generated code or automatic deployment.

# Problem
- Search needs explicit boundaries and full attempt history to avoid irreproducible selection.

# Scope
- In:
  - High priority; depends on a verified reference engine and confirmed generation policy.
  - Confirmed starting families: trend, mean reversion and breakout with bounded parameters.
  - Preview search size and compute budget; persist configuration, seed, all trials and failures.
  - Cancel a run without losing completed evidence; export a portable candidate definition.
  - Implement the exact three-family grid, 192 base candidates, all-evaluation budget and persisted cancellation/restart semantics in logics/discovery/mvp-development-contract.md. Prerequisite: verified reference engine.
- Out:
  - Arbitrary generated code, unbounded genetic evolution and automatic deployment.

# Acceptance criteria
- AC1: A campaign records family/parameter bounds, seed, budget and planned trial count before running.
- AC2: Every attempt has an outcome and provenance; rejected or failed attempts remain visible.
- AC3: Cancellation stops scheduling new work and preserves completed results.
- AC4: A selected trial can be rerun independently from saved inputs.

# AC Traceability
- request-AC4 -> This backlog slice. Proof: AC1: A campaign records family/parameter bounds, seed, budget and planned trial count before running.

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
- Rationale: Bounded, reproducible generation is a core MVP capability after engine validation.

# Tasks
- `task_001_orchestrate_the_major_forex_strategy_research_mvp`

# Notes
- Task `task_001_orchestrate_the_major_forex_strategy_research_mvp` was finished via `logics-manager flow finish task` on 2026-09-23.
