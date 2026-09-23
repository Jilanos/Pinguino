## task_001_orchestrate_the_major_forex_strategy_research_mvp - Orchestrate the major forex strategy research MVP
> From version: 1.0.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-09-23 13:14:18
> Owner: paul.mondou@circle-mobility.com

# AI Context
- Summary: Sequence six research slices with data correctness before search and no order submission.
- Keywords: orchestrate, major, forex, strategy, research, mvp
- Use when: Starting implementation from the versioned MVP development contract.
- Skip when: Treating scaffold completion as completed application delivery.

# Context
- Deliver the historical research MVP through six linked slices using the versioned engineering baseline in `logics/discovery/mvp-development-contract.md`. Corpus preparation is complete only as a planning artifact; application delivery has not started.

# Plan
- [x] 1. Wave 0: Implement the foundation and versioned contracts from logics/discovery/mvp-development-contract.md: locked backend/frontend setup, schemas, synthetic fixtures, French shell and absent-MT5 diagnostics. No operator setup is required to begin.
- [x] 2. Wave 1: Implement data qualification and the deterministic M1 reference engine using hand-calculated and future-data fixtures. Build the isolated Windows adapter; record real-terminal verification as pending until setup exists.
- [x] 3. Wave 2: Implement the 192-candidate template grid, persisted trial ledger, budgets, cancellation and interrupted-run recovery.
- [x] 4. Wave 3: Implement versioned chronological screening, stress/neighborhood checks and final-holdout access audit.
- [x] 5. Wave 4: Complete the French browser journey and exports; reproduce a synthetic campaign end to end, then verify installation and real MT5 history ingestion on Windows before full MVP closeout.
- [x] 6. At each wave update affected docs and evidence; only close implementation slices after their acceptance criteria are proven. Preserve operator control over commits.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_001_settle_research_product_decisions_and_domain_contracts`
- `item_002_ingest_and_qualify_historical_forex_datasets`
- `item_003_implement_a_deterministic_causal_backtest_reference_engine`
- `item_004_generate_bounded_strategies_and_track_research_campaigns`
- `item_005_evaluate_chronological_robustness_and_protect_the_final_holdout`
- `item_006_deliver_campaign_review_and_auditable_research_exports`

# Definition of Done (DoD)
- [x] Versioned domain/data contracts and explicit engineering defaults are implemented; actual operator inputs are recorded before Windows integration acceptance.
- [x] All six backlog slices meet their acceptance criteria with linked evidence.
- [x] A Windows end-to-end fixture campaign reproduces results, exports an auditable report and demonstrates no order-submission path.
- [x] Causality, costs, dataset quality, holdout protection and cancellation checks pass.
- [x] User documentation records installation, assumptions, limitations and measured performance.
- [x] Logics lint, audit and request-chain validation pass; the handoff context reflects delivered evidence.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_001_settle_research_product_decisions_and_domain_contracts`. Proof deferred to slice closeout.
- request-AC2 -> `item_002_ingest_and_qualify_historical_forex_datasets`. Proof deferred to slice closeout.
- request-AC3 -> `item_003_implement_a_deterministic_causal_backtest_reference_engine`. Proof deferred to slice closeout.
- request-AC4 -> `item_004_generate_bounded_strategies_and_track_research_campaigns`. Proof deferred to slice closeout.
- request-AC5 -> `item_005_evaluate_chronological_robustness_and_protect_the_final_holdout`. Proof deferred to slice closeout.
- request-AC6 -> `item_006_deliver_campaign_review_and_auditable_research_exports`. Proof deferred to slice closeout.
- request-AC7 -> `item_006_deliver_campaign_review_and_auditable_research_exports`. Proof deferred to slice closeout.
- request-AC1 -> This task. Proof: `docs/decision-register.md` separates user-confirmed, engineering-default and open items; no order route exists (`tests/test_mt5_adapter.py::TestNoOrderSurface`, `tests/test_api_shell.py::TestNoOrderSubmissionSurface`).
- request-AC2 -> This task. Proof: `backend/src/pinguino/data/{quality,store,importer,mt5_adapter}.py`; `tests/test_data_quality.py`, `tests/test_mt5_adapter.py`, `tests/test_api_journey.py::TestDatasetImport`; real MT5 imports on Windows reported coverage and rejected a 5-year span lacking M1 (`docs/windows-validation.md`).
- request-AC3 -> This task. Proof: `tests/test_engine_simulator.py` hand-calculated fills, costs, FX, margin and causality; replay from export in `tests/test_end_to_end_campaign.py` and `tests/test_api_journey.py`.
- request-AC4 -> This task. Proof: Ledger persists every attempt; worker process, budgets, cancellation, restart reconciliation and linked resume in `tests/test_research_campaign.py` and `tests/test_api_journey.py::{TestWorkerProcess,TestInterruption}`.
- request-AC5 -> This task. Proof: Screening, stress, neighbourhood, ranking and one-time holdout in `tests/test_research_evaluation.py` and `tests/test_api_journey.py::TestFinalHoldout`; holdout never reranks.
- request-AC6 -> This task. Proof: French browser journey (Playwright `frontend/e2e/journey.spec.ts`, and `e2e/mt5.spec.ts` on real MT5) passed on Windows 11: import, quality, campaign, comparison, trade/equity replay, export.
- request-AC7 -> This task. Proof: Windows run 20260923-130408: 145 backend tests (incl. live MT5), 7 component tests, 2 browser journeys passed; limitations and single measured durations in `docs/installation.md` and `docs/windows-validation.md`.

# Validation
- 2026-09-22 corpus readiness: lint --require-status passed; audit has no blocking findings (seven acceptance proofs deferred to implementation closeout); flow validate reports zero findings; health reports zero issue signals. Six implementation slices and a versioned development contract are ready. No application or Windows/MT5 integration tests have run.
- 2026-09-23 Linux (WSL): `ruff check`, `mypy --strict` (linux and win32 platforms), `pytest` 143 passed / 2 live-MT5 skipped by design, `tsc`, `vitest` 7 passed, `vite build`, Playwright synthetic journey passed, `logics-manager i18n validate` valid.
- 2026-09-23 Windows 11 (`scripts/windows-validation.ps1`, run 20260923-130408): all steps exit 0; `pytest` 145 passed with `PINGUINO_MT5_LIVE=1`; Playwright synthetic journey 32.2 s and real MT5 journey 51.0 s passed. Evidence: `docs/windows-validation.md`.
- Windows 11 run 20260923-130408: 145 backend tests incl. live MT5, 7 component tests, 2 Playwright journeys (synthetic and real MT5) passed; see docs/windows-validation.md
- Linux: ruff, mypy strict, pytest 143 passed + 2 live skipped, tsc, vitest, vite build, Playwright synthetic journey, i18n validate
- Finish workflow executed on 2026-09-23.
- Linked backlog/request close verification passed.

# Report
- Git: anchored the data ignore rules to `/data/` and `/backend/data/`; `backend/src/pinguino/data/` (quality, store, importer, MT5 adapter) is now tracked.
- API: datasets (MT5 and fixture import, quality), suggested configuration, mandatory preview, campaign create/status/cancel/resume, candidates, per-window replay with paginated trades and bounded equity, one-time final evaluation, zip export, same-origin built UI, per-launch session token. One campaign at a time in a spawned worker process; dead runs reconcile to interrupted.
- MT5: read-only adapter resolves symbols already in the terminal, reads the broker contract and bars (M1 in 20-day chunks because the terminal refuses larger requests), stores provenance and approximations in the source note.
- UI: French screens for source, datasets, campaign, runs and results, with synthetic, rejected, cancelled, interrupted and no-candidate states; heuristic verdicts are not styled as winners.
- Open operator questions (code applies the contract as written): MT5 raw weekly boundaries look like broker server time rather than UTC; one missing in-session M1 minute (2026-07-24 16:00 UTC on the demo server) rejects a whole dataset; M1 depth is limited to about three months by the terminal's bar limit.
- Finished on 2026-09-23.
- Linked backlog item(s): `item_001_settle_research_product_decisions_and_domain_contracts`, `item_002_ingest_and_qualify_historical_forex_datasets`, `item_003_implement_a_deterministic_causal_backtest_reference_engine`, `item_004_generate_bounded_strategies_and_track_research_campaigns`, `item_005_evaluate_chronological_robustness_and_protect_the_final_holdout`, `item_006_deliver_campaign_review_and_auditable_research_exports`
- Related request(s): `req_000_establish_a_reproducible_major_forex_strategy_research_mvp`

# Links
- Request: `req_000_establish_a_reproducible_major_forex_strategy_research_mvp`
- Product brief(s): `prod_001_pinguino_major_forex_strategy_research_workbench`
- Architecture decision(s): (none yet)
