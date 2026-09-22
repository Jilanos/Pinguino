## prod_001_pinguino_major_forex_strategy_research_workbench - Pinguino major forex strategy research workbench
> Date: 2026-09-22
> Status: Active
> Related request: `req_000_establish_a_reproducible_major_forex_strategy_research_mvp`
> Related backlog: `item_001_settle_research_product_decisions_and_domain_contracts`, `item_002_ingest_and_qualify_historical_forex_datasets`, `item_003_implement_a_deterministic_causal_backtest_reference_engine`, `item_004_generate_bounded_strategies_and_track_research_campaigns`, `item_005_evaluate_chronological_robustness_and_protect_the_final_holdout`, `item_006_deliver_campaign_review_and_auditable_research_exports`
> Related task: `task_001_orchestrate_the_major_forex_strategy_research_mvp`
> Related architecture: adr_001_local_research_architecture_and_deterministic_mvp_contracts
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
A local French browser workbench running on Windows, reading MT5 history directly, to generate and backtest explainable trend, mean-reversion and breakout strategies on EURUSD/GBPUSD/USDJPY H1/H4. Target five years where available. Historical research only. Prioritize robustness across periods and controlled equity drawdown, then net return; thresholds and ranking mechanics use configurable engineering defaults in the development contract. Confirmed simulation: H1/H4 signals, M1 execution with conservative ambiguity handling, and individual-strategy evaluation/comparison.

# Goals
- Make research reproducible from versioned market data to candidate report.
- Reject misleading results caused by look-ahead, missing costs, poor data or repeated holdout selection.
- Expose candidate trade-offs rather than promise profitable robots.
- Keep future execution adapters separate from the first historical-research delivery.

# Non-goals
- Live or demo trading, EA deployment and broker account changes.
- Crypto, multi-user hosting, billing and public performance claims.
- Unrestricted genetic search and concurrent portfolio replay in V1.

# Scope and guardrails
- Research on historical data only: ingestion, bounded generation, causal simulation, robustness evaluation and auditable exports.
- Run locally on Windows with a French browser UI and read-only MT5 data access.
- Keep source histories and terminal credentials outside the public repository; use synthetic fixtures for reproducible checks.
- This corpus is ready for development using `logics/discovery/mvp-development-contract.md`. Operator setup is a Windows integration gate; implementation has not started.

# Key product decisions
- Confirmed: local French browser UI, Windows runtime, direct MT5 history, explainable trend/mean-reversion/breakout families, EURUSD/GBPUSD/USDJPY H1/H4 and a five-year target where data permits.
- Confirmed selection objective: robustness across periods and controlled equity drawdown first, then net return.
- Engineering baseline: conservative M1 rules, chronological evaluation, demo sizing and bounded campaign budgets are specified in the development contract. Actual broker costs, hardware and operator account inputs remain unknown.
- Confirmed: H1/H4 signals with simulated M1 execution and conservative ambiguity handling. Evaluate and compare strategies individually; concurrent portfolio simulation is deferred.

- Environment: User confirmed that nothing is set up yet: Windows/MT5 integration prerequisites and demo data access must be established; CPU/RAM, campaign duration, simulation currency and balance are unspecified.

# Success signals
- Identical versioned inputs reproduce trades and metrics under the agreed tolerance.
- Data defects, approximation policies and insufficient evidence are visible before candidate acceptance.
- Users can compare candidates, inspect trades and export the assumptions needed to reproduce a result.
- Final evaluation is isolated from refinement, with access and subsequent reuse recorded.
- End-to-end Windows evidence demonstrates the research workflow and absence of order submission.

# Product flow
```mermaid
flowchart LR
    A[MT5 history] --> B[Qualified dataset]
    B --> C[Bounded generation]
    C --> D[Causal backtest]
    D --> E[Chronological validation]
    E --> F[Candidate review]
    F --> G[Reserved evaluation]
    G --> H[Research export]
```

# References
- Product back-reference: `req_000_establish_a_reproducible_major_forex_strategy_research_mvp`
- Task back-reference: `task_001_orchestrate_the_major_forex_strategy_research_mvp`
