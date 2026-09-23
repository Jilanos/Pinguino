## task_002_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges - Adapt MT5 ingestion to provided timestamps and exclude only missing ranges
> From version: 1.0.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: paul.mondou@circle-mobility.com
> Indicators reviewed: 2026-09-23 14:13:07

# AI Context
- Summary: Implement the operator decisions on MT5 timestamps and missing bars, validated on Windows with real history.
- Keywords: adapt, mt5, ingestion, provided, timestamps, exclude, only, missing, ranges
- Use when: Tracing why imported MT5 data is quarantined, delayed or bounded.
- Skip when: Working on strategy templates or ranking.

# Definition of Done (DoD)
- [x] The backlog scope is implemented.
- [x] Acceptance criteria are covered.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# Backlog
- `item_007_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges`

# AC Traceability
- request-AC1 -> This task. Proof: `infer_session` and terminal-timeline rollover in `backend/src/pinguino/data/mt5_adapter.py`; `tests/test_mt5_adapter.py::TestSessionInference`; real MetaQuotes-Demo import inferred Monday 00:00 to Saturday 00:00 (`docs/windows-validation.md`).
- request-AC2 -> This task. Proof: `tests/test_data_quality.py` (missing-span quarantine, delayed execution) and `tests/test_engine_simulator.py` (delayed entry flagged, no entry across a session close); real 92-day import keeps 1,584 H1 bars with one quarantined minute.
- request-AC3 -> This task. Proof: `tests/test_data_quality.py::TestQualification::test_partial_m1_history_keeps_the_covered_span_usable`; campaign span bounded by `execution_start`/`execution_end` in `backend/src/pinguino/research/service.py`; real 5-year import now approximate instead of rejected.

# Acceptance criteria
- AC1: Imported MT5 timestamps are kept as provided; the weekly session is inferred from the M1 history and the rollover is placed in the same timeline, both recorded in the source note.
- AC2: An unexplained gap quarantines only the absent span; a missing M1 close minute delays the entry to the next in-session M1 open and is flagged; a signal whose next M1 falls after a session close does not trade.
- AC3: Partial M1 coverage keeps the covered span usable and campaign spans stay inside it; a dataset is rejected only when no signal can be executed.

# Plan
- [x] Use `python3 -m logics_manager flow progress task task_002_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges.md --progress <n>%` during multi-wave work.
- [x] Run `python3 -m logics_manager flow finish task task_002_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges.md` after implementation.

# Validation
- 2026-09-23 Linux: ruff, mypy (linux and win32), pytest 149 passed / 2 live skipped, tsc, vitest 7 passed, vite build, Playwright synthetic journey passed.
- 2026-09-23 Windows 11 run 20260923-140602: all steps exit 0; pytest 151 passed with live MT5; Playwright synthetic (33.6 s) and real MT5 92-day journey (80.1 s) passed. Evidence in `docs/windows-validation.md`.
- Windows 11 run 20260923-140602: 151 backend tests incl. live MT5, 7 component tests, synthetic and real MT5 92-day Playwright journeys passed; docs/windows-validation.md
- Finish workflow executed on 2026-09-23.
- Linked backlog/request close verification passed.

# Report
- MT5 adapter keeps terminal timestamps unshifted, infers the weekly session from M1 pauses of a day or more (most frequent boundary), places rollover at 00:00 of that timeline and records it in the source note.
- Quality quarantines only the absent span, reports `delayed_execution` when the close minute is missing but a later in-session M1 exists, groups closes outside the M1 history into one range finding, records execution coverage and rejects only without any executable overlap. Manifest version 1.1.0.
- Simulator enters at the first M1 open at or after the signal close within the same session and flags `delayed_entry`; it records a rejected signal when a session closure intervenes.
- Suggested and validated campaign spans stay inside the M1 execution coverage; the UI shows it.
- Finished on 2026-09-23.
- Linked backlog item(s): `item_007_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges`
- Related request(s): `req_001_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges`

# Links
- Request: `req_001_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
