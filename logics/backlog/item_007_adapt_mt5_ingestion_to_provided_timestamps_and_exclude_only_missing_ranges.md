## item_007_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges - Adapt MT5 ingestion to provided timestamps and exclude only missing ranges
> From version: 1.0.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: High
> Theme: Operator workflow and runtime integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-23 14:13:08

# AI Context
- Summary: Keep MT5 timestamps as provided, infer the session, quarantine only absent spans, delay entries over missing minutes, keep partial M1 coverage usable.
- Keywords: adapt, mt5, ingestion, provided, timestamps, exclude, only, missing, ranges
- Use when: Changing qualification, quarantine or entry timing for imported bars.
- Skip when: Working on templates, ranking or UI layout only.

# Problem
Real MetaQuotes-Demo history was rejected or heavily quarantined: the weekly session assumed UTC while the terminal provides its own timeline, and one missing M1 minute rejected a whole dataset.
Operator decision 1: adapt to the timestamps the terminal provides.
Operator decision 2: exclude only the affected range, and find a workaround to avoid losing data.

# Scope
- In:
  - MT5 adapter session inference and rollover; quality quarantine and execution coverage; simulator entry timing; campaign span bounds; UI coverage display
- Out:
  - conversion of terminal time to real UTC, terminal settings, cost sourcing

# Acceptance criteria
- AC1: Imported MT5 timestamps are kept as provided; the weekly session is inferred from the M1 history and the rollover is placed in the same timeline, both recorded in the source note.
- AC2: An unexplained gap quarantines only the absent span; a missing M1 close minute delays the entry to the next in-session M1 open and is flagged; a signal whose next M1 falls after a session close does not trade.
- AC3: Partial M1 coverage keeps the covered span usable and campaign spans stay inside it; a dataset is rejected only when no signal can be executed.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Imported MT5 timestamps are kept as provided; the weekly session is inferred from the M1 history and the rollover is placed in the same timeline, both recorded in the source note.
- request-AC2 -> This backlog slice. Proof: AC2: An unexplained gap quarantines only the absent span; a missing M1 close minute delays the entry to the next in-session M1 open and is flagged; a signal whose next M1 falls after a session close does not trade.
- request-AC3 -> This backlog slice. Proof: AC3: Partial M1 coverage keeps the covered span usable and campaign spans stay inside it; a dataset is rejected only when no signal can be executed.

# Decision framing
- Product framing: Not needed
- Product signals: (none detected)
- Product follow-up: No product brief follow-up is expected based on current signals.
- Architecture framing: Not needed
- Architecture signals: (none detected)
- Architecture follow-up: No architecture decision follow-up is expected based on current signals.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_001_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges`
- Primary task(s): `task_002_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges`

# Priority
- Priority: High
- Rationale: Without it real MT5 history is rejected, which blocks research on broker data.

# Notes
- Hybrid rationale: Derived from request `req_001_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges` and kept bounded to one coherent delivery slice.
- Source file: `logics/request/req_001_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges.md`.
- Generated locally by logics-manager.
- Task `task_002_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges` was finished via `logics-manager flow finish task` on 2026-09-23.

# Tasks
- `task_002_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges`
