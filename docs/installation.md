# Installation and local launch

Pinguino runs entirely on the local machine. It binds to loopback only, transmits no
order, and stores no broker credential.

## Prerequisites

- Python 3.13 (pinned in `backend/.python-version`; `uv` installs it for you)
- Node.js 20 or later
- [`uv`](https://docs.astral.sh/uv/)

Windows is the deployment target. Linux and macOS run everything except MetaTrader 5
ingestion, which stays unavailable and reports a diagnostic instead of failing.

## Install

```bash
cd backend && uv sync --all-extras
cd ../frontend && npm ci
```

On Windows, add the MetaTrader 5 package:

```powershell
cd backend; uv sync --all-extras --extra mt5
```

## Run

```bash
cd backend && uv run uvicorn pinguino.api.app:app --host 127.0.0.1 --port 8787
cd frontend && npm run dev
```

The API answers on <http://127.0.0.1:8787> and the UI dev server proxies `/api` to it.
`GET /api/health` returns the version and source locale; `GET /api/source/diagnostic`
reports whether MetaTrader 5 is usable. Without it, the application still starts in
synthetic mode.

## Checks

```bash
cd backend && uv run pytest && uv run ruff check . && uv run mypy
cd frontend && npx tsc --noEmit && npx vitest run && npx vite build
logics-manager i18n validate
```

## What is not covered yet

No Windows host, broker account or real history has been verified. Installation on
Windows and real MT5 history import remain unproven, and no performance figure has been
measured.
