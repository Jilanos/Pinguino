## req_000_establish_a_reproducible_major_forex_strategy_research_mvp - Establish a reproducible major forex strategy research MVP
> From version: 1.0.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Strategy research
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-09-22 17:07:55

# AI Context
- Summary: Implement the confirmed research scope using versioned engineering defaults; actual Windows/MT5 setup remains an integration gate.
- Keywords: establish, reproducible, major, forex, strategy, research, mvp
- Use when: Scoping historical generation and validation before any trading integration.
- Skip when: Implementing live execution or expanding markets.

# Needs
- Generate, backtest and refine diverse major-forex strategies with traceable evidence.
- Keep MT5 as the target market-data/execution ecosystem while limiting V1 to historical research.
- Separate confirmed scope from product decisions awaiting user feedback.

# Context
- The repository currently contains a Git/Logics bootstrap and an untracked HTML research report; there is no application, dependency manifest or test suite.
- Confirmed: major forex, intended MT5 ecosystem, generation and backtesting first; no order submission or deployment.
- User confirmed D1-D4: local French browser UI, Windows-only application runtime with direct read-only MT5 ingestion, explainable trend/mean-reversion/breakout families with bounded parameters, EURUSD/GBPUSD/USDJPY on H1/H4 with a five-year history target where available. D6 is confirmed: prioritize robustness across periods and controlled equity drawdown, then net return. D10 and D11 are confirmed: H1/H4 signals, simulated M1 execution with conservative ambiguity handling, and individual-strategy evaluation/comparison with shared-account portfolios deferred. D5 and operator values for D7/D9 remain unknown; engineering defaults for budgets, validation, sizing and fills are defined in the development contract in logics/discovery/forex-research-mvp.md.
- Broker identities are anonymized; credentials and licensed market histories must never enter the public repository.
- The user requested a ready-to-develop MVP corpus. Engineering defaults now unblock portable implementation; Windows/MT5 setup remains an integration-delivery dependency. No execution or deployment feature is included.

- User confirmed that nothing is set up yet: Windows/MT5 integration prerequisites and demo data access must be established; CPU/RAM, campaign duration, simulation currency and balance are unspecified.

- Implementation baseline: `logics/discovery/mvp-development-contract.md`; demo defaults are not broker settings.

# Acceptance criteria
- AC1: A versioned product decision record distinguishes confirmed scope, provisional defaults and unresolved implementation choices; V1 has no order-submission or deployment capability.
- AC2: Historical datasets have immutable identity, source provenance, coverage, timezone/session metadata, broker contract and cost assumptions, plus an explicit quality report; invalid or insufficient data cannot silently pass.
- AC3: A deterministic causal reference backtest records orders, fills, trades, open-position equity and costs using a documented execution and sizing contract; future data cannot affect earlier decisions.
- AC4: Bounded strategy generation records family, parameters, seed, planned trials and completed/failed/cancelled attempts, and can reproduce an individual result.
- AC5: Chronological validation, a controlled final holdout, cost/parameter stress and inconclusive-sample verdicts produce explainable candidate assessments without using final evaluation to refine candidates.
- AC6: A single user can create a campaign, inspect data quality, compare candidates, drill into trades and export a reproducible report through the agreed interface.
- AC7: End-to-end evidence reproduces results from a versioned fixture, confirms that research cannot submit orders, and documents data, model and throughput limitations.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_001_pinguino_major_forex_strategy_research_workbench`
- Architecture decision(s): (none yet)

# References
- README.md
- logics/discovery/forex-research-mvp.md

# Backlog
- `item_001_settle_research_product_decisions_and_domain_contracts`
- `item_002_ingest_and_qualify_historical_forex_datasets`
- `item_003_implement_a_deterministic_causal_backtest_reference_engine`
- `item_004_generate_bounded_strategies_and_track_research_campaigns`
- `item_005_evaluate_chronological_robustness_and_protect_the_final_holdout`
- `item_006_deliver_campaign_review_and_auditable_research_exports`
