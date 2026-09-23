## item_006_deliver_campaign_review_and_auditable_research_exports - Deliver campaign review and auditable research exports
> From version: 1.0.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: High
> Theme: Research experience
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-23 13:14:19

# AI Context
- Summary: Expose campaigns and evidence in a French local browser UI on Windows.
- Keywords: deliver, campaign, review, auditable, research, exports
- Use when: Delivering candidate comparison, trade inspection and reproducible reports.
- Skip when: Hosted accounts, subscriptions or broker execution.

# Problem
- Users need to understand why a candidate succeeds or fails and reproduce the evidence.

# Scope
- In:
  - Medium priority; depends on campaign and evaluation contracts; confirmed local browser UI in French on Windows.
  - Single-user local browser UI in French for campaign creation, progress/cancellation, dataset diagnostics, comparisons and trade inspection. Bind to loopback by default and initialize the project-owned source-language contract before adding interface copy.
  - Export assumptions, dataset/strategy/engine identifiers, periods, metrics, verdicts and limitations.
  - Record end-to-end reproduction, absence of order submission and measured throughput on declared hardware.
  - Compare individually evaluated strategies; the V1 interface must not imply shared-account portfolio performance.
  - Implement the eight-screen journey and JSON/CSV/HTML exports in logics/discovery/mvp-development-contract.md. Prerequisites: campaigns/evaluation; UI shell begins in slice 1. Full MVP closeout requires actual Windows/MT5 evidence.
- Out:
  - Hosted authentication, subscriptions, production broker execution and profitability promises.

# Acceptance criteria
- AC1: Through the agreed surface a user imports a fixture, runs a campaign, inspects a candidate and exports its research record.
- AC2: Rejected and inconclusive results are visible and are not styled as verified winners.
- AC3: A clean environment reproduces the reference campaign using documented commands and fixture inputs.
- AC4: Validation demonstrates no order-submission path and reports measured run duration without extrapolated throughput claims.

- AC5: Comparison reports retain individual-strategy assumptions and results without presenting combined shared-account portfolio metrics.

# AC Traceability
- request-AC6 -> This backlog slice. Proof: AC1: Through the agreed surface a user imports a fixture, runs a campaign, inspects a candidate and exports its research record.
- request-AC7 -> This backlog slice. Proof: AC2: Rejected and inconclusive results are visible and are not styled as verified winners.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_001_pinguino_major_forex_strategy_research_workbench`
- Architecture decision(s): (none yet)
- Request: `req_000_establish_a_reproducible_major_forex_strategy_research_mvp`
- Primary task(s): `task_001_orchestrate_the_major_forex_strategy_research_mvp`

# Priority
- Priority: Medium
- Rationale: The review interface follows stable campaign and evaluation contracts; it remains required for MVP delivery.

# Tasks
- `task_001_orchestrate_the_major_forex_strategy_research_mvp`

# Notes
- Task `task_001_orchestrate_the_major_forex_strategy_research_mvp` was finished via `logics-manager flow finish task` on 2026-09-23.
