# Pinguino research MVP discovery

This records user-confirmed choices and remaining operator inputs. The user requested a ready-to-develop MVP corpus on 2026-09-22; the implementation baseline and reversible defaults are defined in `logics/discovery/mvp-development-contract.md`. Application implementation has not started.
Last updated: 2026-09-22. User decisions override recommendations below.

## Confirmed scope

- Build a tool for generating, backtesting and refining diverse trading strategies.
- Start with major forex instruments; MT5 is the intended ecosystem.
- First delivery covers research and historical simulation only.
- Local browser application in French, with the research engine running on Windows and reading history directly from MT5.
- Explainable trend, mean-reversion and breakout families with bounded parameter search.
- Initial universe: EURUSD, GBPUSD and USDJPY on H1/H4, targeting five years of usable history where available.
- No demo or live order submission, account mutation, automatic capital allocation or EA deployment in this delivery.
- Prepare the development corpus now and refine product decisions with the user.

## Decision register

| ID | Decision | Current state | Recommendation and reason |
| --- | --- | --- | --- |
| D1 | Product surface and language | Confirmed by user, 2026-09-22 | Local browser UI in French. |
| D2 | Runtime and data acquisition | Confirmed by user, 2026-09-22 | Entire application runtime on Windows with direct read-only MT5 history ingestion. The current Linux development workspace is not the deployment target. |
| D3 | Generation freedom | Confirmed by user, 2026-09-22 | Explainable trend, mean-reversion and breakout templates with bounded parameter search. |
| D4 | Initial research universe | Confirmed by user, 2026-09-22 | EURUSD, GBPUSD, USDJPY on H1/H4; target five years where available; never silently accept shorter coverage. |
| D5 | Broker dataset and availability | No setup yet, confirmed by user 2026-09-22; broker and dataset remain open | Prepare Windows/MT5 and a demo data source before integration validation. No installed terminal, available account or usable history is assumed. Record anonymized symbol mapping, timezone, coverage and costs once available. |
| D6 | Research objective and comparison | Confirmed by user, 2026-09-22 | Prioritize robustness across periods and controlled equity drawdown, then net return. Engineering thresholds and ranking mechanics are specified in the development contract; they are configurable, not user-confirmed. |
| D7 | Hardware and campaign budget | Open; no setup yet | CPU, RAM and acceptable campaign duration are unspecified. Record them before promising throughput; use bounded search with previewed trial count. |
| D8 | Validation policy | Engineering baseline v1 | 60/20/20 chronology, three validation subwindows, versioned eligibility defaults and logged final-holdout reuse; see development contract. |
| D9 | Account and sizing assumptions | Engineering demo defaults; operator values unknown | USD 10,000, fixed 0.01 lot, illustrative 30:1 margin model; configurable and visibly synthetic. Broker costs require an explicit profile. |
| D10 | History depth and execution fidelity | Confirmed by user, 2026-09-22 | H1/H4 signals with simulated execution on M1 data and conservative ambiguity handling. Conservative fill rules are specified in the development contract; M1 OHLC is not tick-level evidence. |
| D11 | Individual or shared-account evaluation | Confirmed by user, 2026-09-22 | Evaluate and compare strategies individually in V1; shared-account portfolio simulation is deferred. |

Unconfirmed operator inputs remain unknown. Engineering defaults in the development contract unblock implementation without claiming user confirmation; changes must be reflected in versioned policies and acceptance criteria.

## Proposed workflow

1. Register a dataset and inspect provenance, coverage, quality and instrument metadata.
2. Create a campaign: family, symbols, horizons, bounded parameters, seed, cost assumptions, sizing and compute budget.
3. Inspect the planned trial count and chronological research windows.
4. Run or cancel the campaign, preserving completed trials and recording failures.
5. Compare candidates using net performance, equity drawdown, trade count, cost sensitivity and validation results.
6. Inspect individual trades, rules, assumptions and rejection reasons.
7. Freeze a candidate version and evaluate the reserved final window under an explicit policy.
8. Export an auditable research report and portable strategy definition. Execution belongs to a later request.

## Domain and simulation contract to resolve

- Distinguish an economic instrument, its broker symbol and its trading contract.
- Direct MT5 API timestamps already represent UTC; preserve them without a second timezone conversion. Convert only explicitly non-UTC sources; display timezone never affects calculations.
- Check ordering, duplicates, gaps, missing bid/ask or spread information, OHLC consistency and expected sessions.
- Never synthesize tradable bars across closed sessions or silently fill missing prices.
- Separate dataset timezone metadata from broker trading sessions and rollover conventions.
- Closed-bar signals must not execute before the next available executable price.
- Define market, pending, stop and target semantics before supporting each order type.
- Declare how same-bar stop/target ambiguity, weekend gaps, spread, commission, swap and slippage are handled.
- Include conversion into account currency, lot steps/minimums, tick values and insufficient-margin handling.
- If required execution or cost data is absent, reject the run or label an explicit approximation; never claim parity or profitability.
- Confirmed: isolated candidate backtests and comparison in V1; concurrent portfolio/account replay is deferred.
- Exported strategy rules must be executable definitions, not only prose or indicator screenshots.

## Validation contract

- Separate adjustable training/validation data from a final evaluation dataset that does not guide candidate refinement.
- Version every dataset, strategy, parameter set, engine, policy and research window; record every attempt including rejected candidates.
- Fixed inputs and seed must reproduce trades and metric values under the documented numerical tolerance.
- Record final-holdout access. Further tuning after inspection invalidates the untouched-holdout claim.
- Test causality with boundary fixtures: future bars must not change earlier decisions.
- Compare with simple declared baselines under the same costs, exposure and windows.
- Report equity drawdown including open positions, not only closed-trade balance drawdown.
- Report net return, trade count, turnover, exposure, cost breakdown and stability; any annualization states its assumptions.
- Insufficient sample size is an inconclusive result, not a pass.
- Stress parameter neighborhoods, execution costs and chronological windows. Acceptance thresholds are versioned and agreed before selection.
- No target return, guaranteed edge or capital recommendation is part of product acceptance.

## Environment preparation

- User confirmed on 2026-09-22 that nothing is set up yet. This does not establish whether a Windows machine is already available.
- Before direct integration testing, identify the Windows host, install/configure MT5, connect a user-selected demo data source, and inspect symbol/history availability. Setup and broker selection remain future work; no credentials are requested or stored in this corpus.
- Portable engine development can use distributable synthetic fixtures. Synthetic tests do not establish Windows/MT5 compatibility or real historical coverage.
- CPU/RAM, acceptable campaign duration, simulated account currency and initial balance remain unspecified.

## Proposed delivery sequence

1. Apply confirmed decisions D1-D4 and collect D5/D7/D9 inputs; specify conservative M1 fill rules and quantitative evaluation thresholds; apply confirmed D6/D10/D11 choices.
2. Freeze domain/data contracts and produce small causal reference fixtures.
3. Build dataset validation and deterministic reference backtesting.
4. Add bounded generation, reproducible campaign tracking and cancellation.
5. Add chronological evaluation and robustness checks.
6. Deliver comparison, drill-down and report export.
7. Demonstrate end-to-end reproduction and document limitations.

## Follow-up questions

- Which Windows host and demo data source should be prepared for direct MT5 ingestion? No setup is currently available.
- Which host will run research, with how many CPU cores and how much RAM?
- Is a campaign expected to take minutes, an hour, or an overnight run?
- Which robustness thresholds and equity-drawdown limit should operationalize the confirmed selection priorities?
- Revisit engineering fill defaults only through a versioned contract change.
- What account currency and representative simulated balance should examples use?
- Review the engineering eligibility thresholds after initial measurements; they do not establish statistical confidence.

## Deferred capabilities

Live/demo orders, terminal trade permissions, EA compilation/deployment, crypto, hosted multi-user accounts, subscriptions, unrestricted genetic programs, tick scalping, concurrent portfolio simulation and automatic strategy replacement are not included in this first request.
