## item_001_settle_research_product_decisions_and_domain_contracts - Settle research product decisions and domain contracts
> From version: 1.0.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Product discovery
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-23 13:14:19

# AI Context
- Summary: Implement the portable foundation, explicit schemas and versioned MVP defaults.
- Keywords: settle, research, product, decisions, domain, contracts
- Use when: Starting the first implementation slice without requiring Windows/MT5 setup.
- Skip when: Changing accepted scope without recording the decision.

# Problem
- There is no runnable application or domain schema. The foundation must turn the recorded contract into testable code without assuming an available MT5 installation.

# Scope
- In:
  - Implement the foundation described in logics/discovery/mvp-development-contract.md: Python/FastAPI backend, React/TypeScript UI shell, dependency locks and a documented local launch command.
  - Implement validated schemas for datasets, strategies, policies, campaigns and results, with canonical identifiers and synthetic fixture configuration.
  - Initialize the French i18n contract before adding UI copy; expose unavailable-MT5 diagnostics without preventing synthetic mode.
  - Preserve confirmed user choices separately from configurable engineering defaults and unknown operator inputs.
- Out:
  - Broker selection, real account settings, backtest engine and live execution.

# Acceptance criteria
- AC1: The decision register records user choices with rationale and explicitly leaves unanswered choices provisional.
- AC2: Validated schemas and fixtures encode the development contract, reject missing required inputs and distinguish synthetic defaults from broker metadata.
- AC3: Data flow explicitly excludes order requests, credentials in source control and terminal mutations.

- AC4: A clean environment installs locked dependencies and starts the local API/UI shell in synthetic mode without the MT5 package.
- AC5: Schema tests cover invalid policies, stable content identifiers and no credentials in exported configuration; French UI source-language validation passes.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: The decision register records user choices with rationale and explicitly leaves unanswered choices provisional.

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
- Rationale: All implementation slices depend on explicit product, data and experiment contracts.

# Tasks
- `task_001_orchestrate_the_major_forex_strategy_research_mvp`

# Notes
- Task `task_001_orchestrate_the_major_forex_strategy_research_mvp` was finished via `logics-manager flow finish task` on 2026-09-23.
