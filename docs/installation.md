# Installation, launch and limitations

Pinguino runs entirely on the local machine. It binds to loopback only, transmits no
order, changes no terminal setting and stores no broker credential.

## Prerequisites

- Windows 10/11 (deployment target). Linux and macOS run everything except MetaTrader 5
  ingestion, which reports a diagnostic instead of failing.
- [`uv`](https://docs.astral.sh/uv/) — installs the pinned Python 3.13 itself.
- Node.js 20 or later.
- For real history: the MetaTrader 5 terminal, already connected **manually** to a demo
  account, with EURUSD, GBPUSD and USDJPY visible in Market Watch.

## Install and launch (Windows, PowerShell)

```powershell
cd backend;  uv sync --all-extras          # includes the MetaTrader5 package on Windows
cd ..\frontend; npm ci; npx vite build     # the API serves the built UI
cd ..\backend; uv run python -m pinguino
```

Open <http://127.0.0.1:8787/>. The UI and the API share this origin; mutating requests
carry a per-launch token that the page obtains from `/api/session`. Data (immutable bar
files, SQLite ledger) lives in `data/` at the repository root, ignored by Git. Override
with `PINGUINO_DATA_DIR` and `PINGUINO_PORT`.

For UI development, run `npm run dev` in `frontend/` (it proxies `/api` to port 8787).

## Journey

1. **Configuration et source** — diagnoses the MT5 package, terminal, server connection
   and which supported pairs the terminal already lists. Nothing is added to Market Watch.
2. **Jeux de données** — import from MT5 (pair, H1/H4, UTC span) or generate a labelled
   synthetic fixture. Each dataset shows provenance, status (qualified, approximate,
   rejected), requested and obtained coverage, quarantined ranges and findings.
3. **Campagne** — select datasets, let the server propose a span that leaves the 200-bar
   warm-up, adjust budgets, costs and sizing, preview (mandatory), then start.
4. **Résultats** — progress, cancellation and resume; candidate comparison with verdict
   reasons and baselines; per-window replay of trades and equity; the one-time final
   evaluation; the export (`strategy.json`, `configuration.json`, `metrics.json`, trade
   and equity CSV, standalone `report.html`, `manifest.json`).

## Checks

```bash
cd backend && uv run ruff check . && uv run mypy && uv run pytest
cd frontend && npx tsc --noEmit && npx vitest run && npx vite build && npx playwright test
logics-manager i18n validate
```

`npx playwright test` builds nothing itself: run `npx vite build` first. It starts the
API on port 8799 with an empty store and drives the synthetic journey in Chromium.

The real-MT5 checks are opt-in and report missing prerequisites as skip reasons:

```powershell
$env:PINGUINO_MT5_LIVE = "1"; uv run pytest tests/test_mt5_live.py -rs
$env:PINGUINO_E2E_MT5_START = "2026-07-25T00:00"; $env:PINGUINO_E2E_MT5_END = "2026-09-19T00:00"
npx playwright test e2e/mt5.spec.ts
```

`scripts/windows-validation.ps1` runs the whole sequence and writes logs, versions,
durations and host details to `reports/windows-validation/<timestamp>/`.

## Known limitations

- **M1 depth is limited by the terminal.** With the default "Max bars in chart" of
  100,000, the terminal serves about three months of M1 bars; H1 and H4 reach five years.
  A five-year request keeps every signal bar, but only the span with M1 history can be
  evaluated: the dataset shows its "Couverture M1 exécutable" and the proposed campaign
  span stays inside it. Raise the limit yourself in the terminal for more M1 (Pinguino
  never changes terminal settings).
- **Missing bars exclude only what is missing.** An unexplained gap quarantines just the
  absent span. When the M1 bar at a signal close is missing, the entry happens at the
  first M1 open after it within the same session, and results carry the "entrée
  différée" approximation. A signal whose next M1 falls after a session close does not
  trade. A dataset is rejected only when no signal can be executed at all.
- **Timestamps are used as the terminal provides them**, without any shift. The weekly
  session is inferred from the M1 history in that same timeline (on MetaQuotes-Demo:
  Monday 00:00 to Saturday 00:00), and the rollover is placed at 00:00 of that timeline.
  Leverage and stop-out level are read from the terminal, with a named fallback when it
  does not expose them; all of this is recorded in the dataset source note.
- **Costs are an unsourced, versioned approximation**, so results are at best
  approximate. Bar spreads do not reconstruct an intraminute ask path.
- **Simulation is M1-bar based**, not tick based; drawdown uses M1 closes and fills.
- **Memory**: bars are held as Python objects. Importing five years of H1 plus three
  months of M1 peaked around 344 MB of Python allocations; very long M1 spans will need
  more.
- The account currency must be USD for the simulated demonstration account; the
  terminal's own account currency is not used.
