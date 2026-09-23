# Windows validation evidence — 2026-09-23

Evidence for Milestone A (synthetic workbench) and Milestone B (read-only MT5 ingestion)
on the target platform. Raw logs are local, in `reports/windows-validation/` (ignored);
this file records what they showed.

## Host and versions

| Item | Value |
| --- | --- |
| OS | Windows 11 Professionnel 10.0.26200 |
| CPU / RAM | Intel Core i7-12700H, 20 logical processors / 15.6 GiB |
| Python | 3.13.15 (installed by uv 0.12.3) |
| Node.js / Git | v24.19.0 / 2.55.0.windows.3 |
| MetaTrader5 package | 5.0.6180 (wheel available for Python 3.13) |
| MT5 terminal | build 6182, `C:\Program Files\MetaTrader 5`, connected to MetaQuotes-Demo, demo account (trade mode 0), algorithmic trading disabled in the terminal, "Max bars in chart" 100,000 |

No account identifier or credential was read or stored.

## Full sequence (`scripts/windows-validation.ps1`, run 20260923-130408)

| Step | Exit | Seconds |
| --- | --- | --- |
| `uv sync --all-extras` | 0 | 0.0 |
| `ruff check` | 0 | 0.1 |
| `mypy` (strict) | 0 | 0.6 |
| `pytest` with `PINGUINO_MT5_LIVE=1` — 145 passed, 0 skipped (includes both real-terminal tests) | 0 | 185.0 |
| `npm ci` | 0 | 6.1 |
| `tsc --noEmit` | 0 | 10.1 |
| `vitest` — 7 passed | 0 | 28.9 |
| `vite build` | 0 | 1.8 |
| `playwright install chromium` | 0 | 1.8 |
| Playwright — 2 passed | 0 | 87.8 |

Browser journeys (Chromium, API and built UI served on one loopback origin, worker in a
separate process):

| Journey | Result | Measured |
| --- | --- | --- |
| Synthetic fixture: import, preview, 4-candidate campaign, compare, trade/equity replay, final evaluation, export zip | passed | 32.2 s |
| Real MT5: diagnostic, EURUSD H1 import 2026-07-25 → 2026-09-19, 32-candidate campaign, compare, replay, export zip | passed | 51.0 s total; import 9.1 s; campaign 32.6 s as seen by the browser |

A repeat of the two journeys after the memory probe fix recorded, from the worker process
itself: MT5 campaign 29.5 s, 160 evaluations, peak working set 164.1 MB; synthetic
campaign (4 candidates) 4.7 s, 250.5 MB.

## Real MT5 history

| Request | Result |
| --- | --- |
| EURUSD H1, 5 years (2021-09-19 → 2026-09-19) | 30,839 H1 bars and 95,516 M1 bars read in 77.3 s, peak 344 MB of Python allocations. Status **rejected**: 28,528 H1 closes have no M1 bar, because M1 starts at 2026-06-18 03:01 UTC. H1 (31,110 bars) and H4 (7,789 bars) reach five years; a single 5-year M1 request is refused by the terminal (`-2 Invalid params`), so M1 is read in 20-day chunks. |
| EURUSD H1, 92 days (2026-06-19 → 2026-09-19) | Status **rejected**: one H1 close without M1 bar, 2026-07-24 16:00 UTC. The same minute is missing for GBPUSD and USDJPY. |
| EURUSD H1, 2026-07-25 → 2026-09-19 (browser journey) | Status **approximate**: 953 H1 bars, 14 quarantined open-session ranges, unsourced cost profile. Contract read from the terminal: 5 digits, tick 0.00001, 100,000 units per lot, volume 0.01–500 step 0.01, leverage 100, stop-out 30 %, triple swap Wednesday. |

Campaign on this dataset: 32 of 32 trials completed, 160 evaluations, all 32 candidates
**inconclusive** (fewer trades than the eligibility thresholds over about six weeks). The
final holdout was opened once for one candidate; a second candidate is refused.

## No order-submission path

- The adapter calls only `initialize`, `shutdown`, `last_error`, `terminal_info`,
  `symbols_get`, `symbol_info`, `account_info` (leverage and stop-out level only) and
  `copy_rates_range`. A strict stand-in module in `tests/test_mt5_adapter.py` fails on
  any other attribute, and the adapter source contains no `order_send`, `order_check`,
  `positions_`, `login` or `password`.
- No route exposes a shell or a file path; the API binds to loopback, rejects foreign
  Host/Origin and requires the per-launch token on mutations.

## Rerun after the operator decisions (run 20260923-140602)

Rules changed on 2026-09-23 (see `docs/decision-register.md`): timestamps used as the
terminal provides them with the weekly session inferred from M1, quarantine limited to
the absent span, delayed entry at the next in-session M1 when the close minute is missing,
partial M1 coverage kept usable.

| Step | Exit | Seconds |
| --- | --- | --- |
| `ruff`, `mypy` | 0 | 1.5, 1.4 |
| `pytest` with `PINGUINO_MT5_LIVE=1` — 151 passed, 0 skipped | 0 | 172.8 |
| `tsc`, `vitest` (7 passed), `vite build` | 0 | 10.5, 29.2, 2.0 |
| Playwright — 2 passed | 0 | 119.3 |

| Real MT5 request (EURUSD H1) | Before | After |
| --- | --- | --- |
| 5 years | rejected, 285 quarantined ranges | approximate: 31,110 H1 bars kept, 34 quarantined ranges, H1 closes outside the M1 history reported as one range finding, 1 delayed execution; read in 46.4 s |
| 92 days (2026-06-19 → 2026-09-19) | rejected (missing 2026-07-24 16:00 minute) | approximate: 1,584 H1 bars, 1 quarantined range (the missing minute), 1 delayed execution; read in 28.7 s |

Inferred session on MetaQuotes-Demo, terminal timeline: Monday 00:00 to Saturday 00:00;
rollover at 00:00.

Browser journeys: synthetic 33.6 s; real MT5 on the 92-day span 80.1 s (import 9.6 s,
campaign 59.5 s as seen by the browser). Worker measurements: MT5 campaign 57.0 s, 32/32
trials, 160 evaluations, peak working set 255.9 MB, all 32 candidates inconclusive, 4 of
them carrying the delayed-entry approximation; synthetic campaign 6.1 s, 250.7 MB.

## Reservations

These do not change the results above; they qualify them.

- The first run's rules (UTC-labelled default session, whole-dataset rejection for one
  missing minute) are superseded by the operator decisions; its figures are kept as the
  before state.
- Durations are single measurements on one host, not throughput figures.
