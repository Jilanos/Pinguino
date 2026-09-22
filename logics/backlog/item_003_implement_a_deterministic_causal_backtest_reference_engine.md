## item_003_implement_a_deterministic_causal_backtest_reference_engine - Implement a deterministic causal backtest reference engine
> From version: 1.0.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 20%
> Complexity: High
> Theme: Simulation correctness
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-22 17:11:43

# AI Context
- Summary: Prove causal fills, costs and open-position equity before increasing search volume.
- Keywords: implement, deterministic, causal, backtest, reference, engine
- Use when: Building or verifying reference simulation semantics.
- Skip when: Tuning performance ahead of correctness or executing real orders.

# Problem
- A fast search amplifies incorrect fills and look-ahead before users can detect them.

# Scope
- In:
  - High priority; requires qualified data and agreed order/sizing contracts.
  - Build a simple reference engine with explicit closed-bar signal timing, fills, costs and open-position equity.
  - Declare policies for same-bar stop/target ambiguity, gaps, swaps, slippage, lot rounding and margin.
  - Use one versioned strategy representation; no execution connector.
  - Use closed H1/H4 bars for signals and M1 bars for simulated execution, with explicit conservative ambiguity rules. Evaluate each strategy on an isolated simulated account; shared-account portfolio replay is deferred.
  - Execution, sizing, spread, gap, margin, rollover, conversion and rounding policies are specified in logics/discovery/mvp-development-contract.md. Prerequisites: foundation and qualified synthetic M1/H1/H4 fixtures.
- Out:
  - Performance optimization ahead of correctness, tick scalping, portfolio-wide shared margin.

# Acceptance criteria
- AC1: Hand-calculated fixtures verify entry timing, spread/commission, stops/targets, gap handling and account-currency PnL.
- AC2: Changing future bars leaves earlier decisions and fills unchanged.
- AC3: Replaying identical inputs yields identical trades and metrics within a documented numerical tolerance.
- AC4: Equity drawdown includes unrealized PnL; approximations and insufficient inputs are visible.

- AC5: Fixtures demonstrate closed H1/H4 signal timing with M1 execution and documented conservative treatment of ambiguous bars; reports identify M1 simulation as an approximation rather than tick-level evidence.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC1: Hand-calculated fixtures verify entry timing, spread/commission, stops/targets, gap handling and account-currency PnL.

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
- Rationale: Causal fills and costs must be proven before automated search amplifies errors.
