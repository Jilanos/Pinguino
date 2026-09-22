# MVP development contract v1

Date: 2026-09-22. This contract makes the requested corpus ready for development. It records assistant-selected, reversible engineering defaults, not additional user confirmations or real-money settings. User-confirmed choices remain in `logics/discovery/forex-research-mvp.md`. Changes to this contract require versioned policies and affected acceptance criteria before implementation changes.

## Delivery boundary

Windows local French browser application, one user, three major pairs (EURUSD, GBPUSD, USDJPY), H1/H4 closed-bar signals and M1 simulated execution. Generate trend, mean-reversion and breakout candidates, compare isolated backtests, evaluate chronological robustness and export evidence. No orders, EA export, shared-account portfolios, hosting or unrestricted genetic programs.

Milestone A is a runnable synthetic-data research workbench. Milestone B adds verified read-only Windows/MT5 ingestion. Both are part of the MVP; A does not prove B. No Windows host, broker account or history is currently verified. Their absence does not block portable development, but prevents final MT5 integration acceptance.

## Implementation choices

- Python domain engine and FastAPI local API, React/TypeScript browser UI. Choose compatible supported versions and commit dependency locks in the foundation slice; verify the chosen Python runtime against the Windows MT5 package before freezing it.
- SQLite stores datasets, campaigns, trial states and holdout-access events. Immutable compressed CSV bar files and canonical JSON manifests live in an ignored local data directory. Content hashes cover normalized data and metadata. Keep raw source provenance separately.
- Planned layout: `backend/src/pinguino/{domain,data,engine,research,api}`, `frontend/`, `tests/fixtures/`, `scripts/`, `docs/`. A small worker process executes one trial at a time; API remains responsive. No Redis, cloud service or GPU requirement.
- Versioned models: instrument contract, dataset manifest, strategy definition, cost/sizing policy, research-window policy, campaign, trial, fills, equity observations, metrics and evaluation access. Invalid inputs fail with stable error codes and French explanations at the UI boundary.
- Dataset status: qualified, approximate or rejected. Trial state: queued, running, completed, failed, cancelled or interrupted. Persist state transitions transactionally and reconcile running trials to interrupted on restart. Resume creates a linked new campaign; automatic mid-trial resume is deferred.
- API operations cover source diagnostics/import, datasets/quality, campaign preview/create/status/cancel, candidate metrics/trades/equity, final-evaluation access and export. Preview is required before starting; reject configuration changes after creation. Browser polls state; pagination bounds trade/result responses.
- Bind only to loopback. Serve built UI and API on the same origin; reject foreign Origin/Host mutation requests, require a per-launch request token, and expose no shell or arbitrary file-path API. No browser credential store or account login feature.

## Data and MT5 adapter

- Adapter boundary: inspect terminal availability, enumerate already available symbols/contracts and fetch historical bars. Do not import MT5 in the portable domain engine. Missing package/terminal produces a diagnostic, not failure of synthetic mode.
- Use the operator's already connected demo terminal; setup instructions explain manual connection and symbol selection. Never call order submission, change terminal settings, switch accounts or capture passwords. Read-only means market-data access, not a guarantee about what the user's terminal itself does.
- Direct MT5 bar timestamps are UTC: do not shift them again using broker timezone. Broker session/rollover metadata is separate. Preserve native H1/H4 bar boundaries and join them to M1 on UTC intervals; do not silently replace them with differently anchored aggregates.
- Native history is limited by terminal availability. Request five years, report actual coverage for every pair/timeframe and require an explicitly smaller requested range if five years are unavailable.
- Required bars: UTC open timestamp, bid OHLC, spread in points and provenance; contract: point/tick size, base/quote currencies, units per lot, min/max/step volume, margin model, sessions and rollover schedule. Import rejects nonfinite prices, invalid OHLC, duplicates, nonmonotonic times and undeclared timezone. Expected closed sessions are not missing bars; unexplained open-session gaps quarantine affected ranges.
- Require complete M1 execution coverage for the chosen evaluation intervals. Do not forward-fill tradable prices or fall back to H1/H4 execution. Drop incomplete current signal bars. Record warm-up coverage independently.
- Historical costs are assumptions unless sourced: present-day contract/spread/swap values are not proof of past conditions. Unknown required costs require an explicit versioned approximation profile; such results remain approximate. An explicitly entered zero is distinct from missing data.
- Bar spread cannot reconstruct an intraminute ask path. V1 models ask OHLC as bid OHLC plus declared per-bar spread, explicitly labelled approximate. Synthetic fixtures include known constant and variable spreads, gaps and rollover events.

## Account and execution rules

- Demonstration defaults only: USD 10,000 initial balance, fixed 0.01 lot per trade, one position per candidate, illustrative 30:1 margin model. All are visible and configurable before a campaign. Default currency support is USD; additional account currencies require supplied conversion-series support and are deferred. Real broker contracts override fixture constants.
- Synthetic contract: 100,000 base units per lot; tick size 0.00001 for EURUSD/GBPUSD and 0.001 for USDJPY; volume step/minimum 0.01. Illustrative spreads: 10, 15 and 10 points respectively; zero commission/swap only in labelled fixtures. Never reuse this profile silently for broker history.
- Signals use only completed H1/H4 bars. Entries are market orders at the next M1 open at or after the signal close. Reject the signal if its next tradable M1 is unavailable in the declared session. One decision per closed signal bar; ignore new signals while positioned and no same-bar reversal.
- Buy at ask, sell at bid; close long at bid, short at ask. Adverse slippage is a declared nonnegative point amount, default one point in fixtures, applied to market and stop fills. Limit take-profit fills use the target price without favorable gap improvement.
- Protective stop and target are fixed at entry from ATR distance. Round buy stops down/sell stops up to tick size; targets round away from entry. Reject invalid distances, out-of-range volume and insufficient margin; never silently round volume upward.
- At an M1 open process an existing gap stop first at the worse executable open plus adverse slippage; then a gap target at its target price. Within an M1 bar where both stop and target are reachable, use stop first and mark ambiguity. On an entry bar process entry at open, then protective exits under the same conservative rule. Report ambiguity count.
- Time exit: after 20 completed signal bars since entry, close at next executable M1 open. Protective exits at that open precede time exits. At a research-window end close at the last available M1 close with costs and record forced liquidation; never carry trades into another split.
- Quote PnL = signed price difference times base units. EURUSD/GBPUSD quote PnL is USD. USDJPY converts JPY using the contemporaneous simulated bid/ask: positive JPY proceeds divide by ask, negative liabilities by bid. Account equity is realized balance plus liquidation-valued open PnL; no future conversion rates.
- Margin approximation is base notional converted to USD divided by leverage; require free margin at entry. If equity reaches the declared stop-out fraction of used margin (fixture default 50%), liquidate at the next observed M1 open. Document this approximation; no tick-accurate liquidation claim.
- Apply commission on each fill and swap at declared broker rollover instants with long/short and triple-day rules from the cost profile. Missing history remains approximate. Fixtures prove each charge exactly once.
- Record M1-close equity and fill-time equity; report maximum peak-to-trough drawdown on these observations, explicitly not tick-level maximum drawdown. Reject nonpositive equity as failed research eligibility. Use integer price ticks and decimal money; serialize rounding policy and require identical fills plus money tolerance <= USD 0.01 on replay.

## Bounded strategy generation

Three versioned templates, using closed bid signal bars. Indicators use sufficient prior warm-up, never a future value. ATR(14) and RSI(14) use Wilder smoothing seeded by the first 14 simple averages; SMA is the arithmetic trailing mean. Do not emit signals while a required value is undefined.

| Family | Entry rule | Parameter grid |
| --- | --- | --- |
| Trend | SMA fast crosses above slow: long; below: short; previous and current completed bars establish the crossing | fast 10/20; slow 50/100 |
| Mean reversion | RSI crosses back above lower threshold: long; back below upper threshold: short | lower/upper 25/75 or 30/70 |
| Breakout | Close exceeds the maximum high of the preceding N bars: long; below minimum low: short; exclude current bar from range | N 20/50 |

All templates use ATR stop multiples 1.5/2.0 and reward/risk multiples 1.0/2.0, fixed 20-bar time exit and symmetric long/short logic. Trend has 16 variants, mean reversion 8, breakout 8: 32 per pair/timeframe, 192 across the six pair/timeframe combinations. Store expanded parameter definitions, family version and canonical candidate IDs; no executable generated code.

Default campaign: one worker, seed 42, maximum 192 base candidates, maximum 30 minutes of active work. These are adjustable engineering budgets, not throughput promises. Preview full candidate count and evaluation count including robustness work. Use a deterministic seeded permutation before truncating a grid; preserve planned order and every attempted outcome. Default total evaluation cap 2,000 includes split, stress and neighborhood replays. Exhausted budgets yield partial/inconclusive results, not failures of unrun candidates.

Cancellation is checked between candidates and at least every 1,000 M1 bars within a trial. Cancelled partial trials never enter rankings; completed trials stay accessible. Wall-clock limits can change how many trials finish but not an individual completed trial's deterministic replay.

## Research policy v1

- Split the requested chronological calendar span 60% training, 20% validation, 20% final holdout; resolve boundaries to explicit UTC timestamps at campaign preview and persist them. Last segment is hidden from selection. Reserve pre-window warm-up (at least 200 completed signal bars); no warm-up trades contribute metrics.
- Evaluate every candidate on training and validation; partition validation into three chronological subwindows, each starting flat with prior-bar warm-up. The final holdout is opened only for one frozen candidate per campaign and policy. Log access before execution; later refinement marks the dataset/window lineage as reused, including new campaigns. No local mechanism prevents an operator reading their own files; this is an audit guarantee.
- Engineering eligibility defaults, adjustable only before campaign start: at least 100 training trades and 30 validation trades overall, at least 10 trades in each validation subwindow, positive net return in at least two subwindows, and equity drawdown <= 15% in each validation subwindow and whole validation. These are heuristic screening settings, not statistical confidence or profitability guarantees. Insufficient samples are inconclusive.
- Stress eligible candidates with spread and commission multiplied by 1.5 and slippage doubled, keeping all other assumptions fixed. Require positive net validation return and drawdown <= 15% under this stress. Evaluate immediate available neighbors on each ordered template parameter axis, one axis at a time; require at least half of the distinct neighbors to pass base validation eligibility. No neighbors or exhausted budget yields inconclusive stability.
- Rank eligible candidates lexicographically by positive validation-subwindow count descending, worst-subwindow equity drawdown ascending, then whole-validation net return descending, with candidate ID as stable tie-break. Expose component metrics and verdict reasons. Final-holdout performance never reorders candidates.
- Baselines: cash/no trades and fixed-size always-long exposure over the same windows and cost profile. Mark risk/exposure differences; compare within the same symbol/timeframe by default, do not imply fixed lots equalize risk across pairs.
- Report net return, equity drawdown, exposure time, trade count, win rate, profit factor, turnover, cost breakdown, per-window results, ambiguity count and approximation flags. Undefined ratios are null with reasons, never infinity. Report absolute returns first; annualization, if added, must disclose elapsed-calendar-time convention.
- Fixture runs shorter than evidence thresholds still complete the product workflow but remain synthetic and inconclusive. A no-eligible-candidate campaign is a valid outcome.

## User journey and evidence

French UI screens: setup/source diagnostic; dataset import and quality; campaign configuration/preview; progress/cancellation; candidate comparison; trade/equity detail; explicit final-evaluation action; export. Include empty, unavailable-MT5, rejected-data, cancelled, interrupted and no-candidate states. Initialize the French i18n contract before interface copy. No mock performance presented as real.

Export canonical strategy/configuration JSON, metrics JSON, trades/equity CSV and standalone HTML report with identifiers, assumptions, chronological windows, verdicts and limitations. Reports reference local dataset hashes; do not bundle licensed history or credentials. End-to-end fixture evidence replays a candidate from its export.

| Slice | Depends on | Required proof |
| --- | --- | --- |
| 1 Foundation/contracts | This contract | Locked runnable backend/UI skeleton, validated schemas, synthetic fixture and config; missing MT5 does not prevent startup |
| 2 Data | 1 | Import/quality/hash tests, UTC and alignment fixtures, read-only adapter tests; separate actual Windows terminal evidence |
| 3 Reference engine | 1 and qualified fixture from 2 | Hand-calculated fills/costs/FX/margin/gap tests, causality, deterministic replay |
| 4 Campaigns | 3 | Exact grid counts, persisted all-attempt ledger, budgets, cancellation and crash recovery |
| 5 Evaluation | 4 | Split-boundary causality, no holdout ranking/access bypass, heuristic verdict and stress/neighbor fixtures |
| 6 Interface/export | 4 and 5; UI shell starts in 1 | Browser journey, export replay, French states, Windows launch and measured resource use |

Tests: Python unit/integration tests, frontend component checks where useful, one automated browser fixture journey, Linux portable CI and Windows portable CI. Actual MT5 smoke test is opt-in on a prepared Windows machine and reports skipped prerequisites accurately. Record duration, peak memory, CPU/RAM and versions; no performance target is accepted without measurement. Full MVP closeout requires real Windows/MT5 source diagnostics and history import in addition to synthetic evidence.

## Technical sources checked

- https://fastapi.tiangolo.com/ — Python API framework reference; selected for typed local API boundaries, not benchmark claims.
- https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py — UTC bar timestamps, returned spread fields and terminal history limits. A returned bar spread is not an intraminute execution record.
