## task_001_orchestrate_the_major_forex_strategy_research_mvp - Orchestrate the major forex strategy research MVP
> From version: 1.0.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 40%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-09-22 17:11:43
> Owner: paul.mondou@circle-mobility.com

# AI Context
- Summary: Sequence six research slices with data correctness before search and no order submission.
- Keywords: orchestrate, major, forex, strategy, research, mvp
- Use when: Starting implementation from the versioned MVP development contract.
- Skip when: Treating scaffold completion as completed application delivery.

# Context
- Deliver the historical research MVP through six linked slices using the versioned engineering baseline in `logics/discovery/mvp-development-contract.md`. Corpus preparation is complete only as a planning artifact; application delivery has not started.

# Plan
- [ ] 1. Wave 0: Implement the foundation and versioned contracts from logics/discovery/mvp-development-contract.md: locked backend/frontend setup, schemas, synthetic fixtures, French shell and absent-MT5 diagnostics. No operator setup is required to begin.
- [ ] 2. Wave 1: Implement data qualification and the deterministic M1 reference engine using hand-calculated and future-data fixtures. Build the isolated Windows adapter; record real-terminal verification as pending until setup exists.
- [ ] 3. Wave 2: Implement the 192-candidate template grid, persisted trial ledger, budgets, cancellation and interrupted-run recovery.
- [ ] 4. Wave 3: Implement versioned chronological screening, stress/neighborhood checks and final-holdout access audit.
- [ ] 5. Wave 4: Complete the French browser journey and exports; reproduce a synthetic campaign end to end, then verify installation and real MT5 history ingestion on Windows before full MVP closeout.
- [ ] 6. At each wave update affected docs and evidence; only close implementation slices after their acceptance criteria are proven. Preserve operator control over commits.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_001_settle_research_product_decisions_and_domain_contracts`
- `item_002_ingest_and_qualify_historical_forex_datasets`
- `item_003_implement_a_deterministic_causal_backtest_reference_engine`
- `item_004_generate_bounded_strategies_and_track_research_campaigns`
- `item_005_evaluate_chronological_robustness_and_protect_the_final_holdout`
- `item_006_deliver_campaign_review_and_auditable_research_exports`

# Definition of Done (DoD)
- [ ] Versioned domain/data contracts and explicit engineering defaults are implemented; actual operator inputs are recorded before Windows integration acceptance.
- [ ] All six backlog slices meet their acceptance criteria with linked evidence.
- [ ] A Windows end-to-end fixture campaign reproduces results, exports an auditable report and demonstrates no order-submission path.
- [ ] Causality, costs, dataset quality, holdout protection and cancellation checks pass.
- [ ] User documentation records installation, assumptions, limitations and measured performance.
- [ ] Logics lint, audit and request-chain validation pass; the handoff context reflects delivered evidence.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_001_settle_research_product_decisions_and_domain_contracts`. Proof deferred to slice closeout.
- request-AC2 -> `item_002_ingest_and_qualify_historical_forex_datasets`. Proof deferred to slice closeout.
- request-AC3 -> `item_003_implement_a_deterministic_causal_backtest_reference_engine`. Proof deferred to slice closeout.
- request-AC4 -> `item_004_generate_bounded_strategies_and_track_research_campaigns`. Proof deferred to slice closeout.
- request-AC5 -> `item_005_evaluate_chronological_robustness_and_protect_the_final_holdout`. Proof deferred to slice closeout.
- request-AC6 -> `item_006_deliver_campaign_review_and_auditable_research_exports`. Proof deferred to slice closeout.
- request-AC7 -> `item_006_deliver_campaign_review_and_auditable_research_exports`. Proof deferred to slice closeout.

# Validation
- 2026-09-22 corpus readiness: lint --require-status passed; audit has no blocking findings (seven acceptance proofs deferred to implementation closeout); flow validate reports zero findings; health reports zero issue signals. Six implementation slices and a versioned development contract are ready. No application or Windows/MT5 integration tests have run.

# Report
- Not started.

# Links
- Request: `req_000_establish_a_reproducible_major_forex_strategy_research_mvp`
- Product brief(s): `prod_001_pinguino_major_forex_strategy_research_workbench`
- Architecture decision(s): (none yet)
