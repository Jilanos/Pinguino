## item_002_ingest_and_qualify_historical_forex_datasets - Ingest and qualify historical forex datasets
> From version: 1.0.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 60%
> Complexity: High
> Theme: Market data
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-22 17:11:43

# AI Context
- Summary: Qualify direct Windows MT5 history and broker metadata for three major pairs.
- Keywords: ingest, qualify, historical, forex, datasets
- Use when: Implementing source ingestion and data-quality gates.
- Skip when: Submitting orders or silently substituting market history.

# Problem
- Backtests cannot be trusted without provenance and consistent tradable history.

# Scope
- In:
  - High priority; depends on approved data contracts from the discovery slice.
  - Implement direct read-only MT5 historical ingestion on Windows behind a source adapter; qualify EURUSD/GBPUSD/USDJPY H1/H4 with a five-year coverage target where available.
  - Normalize UTC timestamps, sessions and symbol contracts; report gaps, duplicates, spread/cost coverage and usable windows.
  - Keep licensed history local and use distributable synthetic fixtures in the repository.
  - Qualify M1 execution history in addition to H1/H4 signal data; missing M1 coverage must block the confirmed simulation mode rather than silently falling back to H1/H4 execution.
  - Document and verify Windows/MT5 setup prerequisites before integration testing. Use synthetic fixtures for portable checks, and report real-terminal validation as pending until the environment exists.
  - Source contract and quality cases are specified in sections Data and MT5 adapter of logics/discovery/mvp-development-contract.md. Prerequisite: foundation schemas. Preserve MT5 UTC timestamps without double conversion.
- Out:
  - Live feeds, orders, automatic substitution of another broker's data.

# Acceptance criteria
- AC1: Importing a fixture yields a stable dataset fingerprint and complete provenance/coverage report.
- AC2: Fixtures with bad ordering, duplicates, invalid OHLC or unknown timezone are rejected or quarantined with reasons.
- AC3: Missing execution/cost history and insufficient requested coverage cannot be represented as a fully qualified dataset.
- AC4: Contract metadata includes account-currency conversion inputs, volume constraints and trading sessions.

- AC5: Dataset qualification reports aligned H1/H4 signal and M1 execution coverage; missing M1 data cannot silently fall back to coarser execution.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: AC1: Importing a fixture yields a stable dataset fingerprint and complete provenance/coverage report.

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
- Rationale: Qualified source data is required before simulation results can be trusted.
