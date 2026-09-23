## req_001_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges - Adapt MT5 ingestion to provided timestamps and exclude only missing ranges
> From version: 1.0.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: General
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-09-23 14:13:07

# AI Context
- Summary: Apply the operator decisions of 2026-09-23 on MT5 timestamps and missing bars so real history is not lost to false gaps.
- Keywords: mt5, timestamps, session, quarantine, missing m1, delayed entry, coverage
- Use when: Changing how imported bars are qualified, quarantined or executed.
- Skip when: Working on strategy templates or the UI only.

# Needs
- Real MetaQuotes-Demo history was rejected or heavily quarantined: the weekly session assumed UTC while the terminal provides its own timeline, and one missing M1 minute rejected a whole dataset.
- Operator decision 1: adapt to the timestamps the terminal provides.
- Operator decision 2: exclude only the affected range, and find a workaround to avoid losing data.

# Context
- Evidence and before/after figures: `docs/windows-validation.md`. Decisions: `docs/decision-register.md`.
- Out of scope: converting terminal time to real UTC, changing terminal settings, sourcing costs.

# Acceptance criteria
- AC1: Imported MT5 timestamps are kept as provided; the weekly session is inferred from the M1 history and the rollover is placed in the same timeline, both recorded in the source note.
- AC2: An unexplained gap quarantines only the absent span; a missing M1 close minute delays the entry to the next in-session M1 open and is flagged; a signal whose next M1 falls after a session close does not trade.
- AC3: Partial M1 coverage keeps the covered span usable and campaign spans stay inside it; a dataset is rejected only when no signal can be executed.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_001_pinguino_major_forex_strategy_research_workbench`
- Architecture decision(s): `adr_001_local_research_architecture_and_deterministic_mvp_contracts`

# References
- `backend/src/pinguino/data/mt5_adapter.py`
- `backend/src/pinguino/data/quality.py`
- `backend/src/pinguino/engine/simulator.py`
- `backend/src/pinguino/research/service.py`

# Backlog
- `item_007_adapt_mt5_ingestion_to_provided_timestamps_and_exclude_only_missing_ranges`
