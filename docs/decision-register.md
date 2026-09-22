# Decision register — implementation mapping

Three kinds of setting are kept apart on purpose and must not drift into one another.

- **User-confirmed choices** are recorded in `logics/discovery/forex-research-mvp.md`
  (D1–D11). They are not re-decided in code.
- **Engineering defaults** are versioned, visible and configurable before a campaign.
  They are assistant-selected and reversible, sourced from
  `logics/discovery/mvp-development-contract.md`.
- **Unknown operator inputs** stay provisional: nothing in code invents a value for
  them, and the fixture stand-in is always labelled synthetic.

## Where each decision lives

| ID | Kind | Implemented in |
| --- | --- | --- |
| D1 Product surface and language | User-confirmed | `logics/i18n/contract.json` (source locale `fr`), `frontend/src/i18n/fr.json` |
| D2 Windows runtime, read-only MT5 ingestion | User-confirmed | `backend/src/pinguino/data/mt5_adapter.py` — inspection only, no order or settings call |
| D3 Bounded explainable templates | User-confirmed | `FAMILY_AXES` and `StrategyDefinition` in `backend/src/pinguino/domain/strategy.py` |
| D4 Universe and target depth | User-confirmed | `Symbol`, `SIGNAL_TIMEFRAMES` in `backend/src/pinguino/domain/enums.py`; `CoverageReport` reports actual coverage rather than assuming the request was met |
| D5 Broker and dataset | **Provisional** | No broker profile exists. `DataProvenance` separates `synthetic_fixture` from `mt5_terminal`, and a contract's provenance is part of its identifier |
| D6 Robustness before return | User-confirmed | Ranking is implemented in the evaluation slice; thresholds live in `EligibilityPolicy` and are configurable |
| D7 Hardware and campaign budget | **Provisional** | `CampaignBudget` carries engineering budgets, not throughput promises. Measured values are recorded once a Windows host exists |
| D8 Validation policy v1 | Engineering default | `ResearchWindowPolicy`, `EligibilityPolicy` in `backend/src/pinguino/domain/policy.py` |
| D9 Account and sizing assumptions | Engineering default over **provisional** operator values | `SizingPolicy` defaults and `backend/src/pinguino/fixtures/` — fixture constants are never reused silently for broker history |
| D10 H1/H4 signals, M1 execution | User-confirmed | `Timeframe`, and `StrategyDefinition` rejects an M1 signal timeframe |
| D11 Individual evaluation only | User-confirmed | One position per candidate, enforced by `SizingPolicy.max_open_positions_per_candidate` |

## Still unanswered

D5 and D7 have no operator answer. Until a Windows host, a demo account and real
history exist, Milestone B (verified MT5 ingestion) cannot be accepted, and any
performance figure is a measurement of synthetic fixtures only.
