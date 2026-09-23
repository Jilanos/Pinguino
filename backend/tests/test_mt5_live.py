"""Opt-in smoke test against a real, already connected MetaTrader 5 terminal.

Run on a prepared Windows machine with ``PINGUINO_MT5_LIVE=1``. Every missing
prerequisite is reported as the skip reason rather than as a failure.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pinguino.data import mt5_adapter
from pinguino.data.importer import import_mt5
from pinguino.data.store import DatasetStore
from pinguino.domain.enums import DataProvenance, DatasetStatus, Symbol, Timeframe


def _prerequisite_gap() -> str | None:
    if os.environ.get("PINGUINO_MT5_LIVE") != "1":
        return "PINGUINO_MT5_LIVE=1 is not set"
    if sys.platform != "win32":
        return f"MetaTrader 5 requires Windows, this is {sys.platform}"
    if importlib.util.find_spec("MetaTrader5") is None:
        return "the MetaTrader5 package is not installed (uv sync --extra mt5)"
    diagnostic = mt5_adapter.diagnose_source()
    if not diagnostic.terminal_available:
        return f"terminal not reachable: {diagnostic.detail}"
    if not diagnostic.terminal_connected:
        return "terminal is not connected to a server"
    if "EURUSD" not in diagnostic.available_symbols:
        return "EURUSD is not present in the terminal"
    return None


GAP = _prerequisite_gap()
pytestmark = pytest.mark.skipif(GAP is not None, reason=GAP or "")

START = datetime.fromisoformat(os.environ.get("PINGUINO_MT5_START", "2026-07-25T00:00:00+00:00"))
END = datetime.fromisoformat(os.environ.get("PINGUINO_MT5_END", "2026-09-19T00:00:00+00:00"))


def test_the_connected_terminal_is_diagnosed_read_only() -> None:
    diagnostic = mt5_adapter.diagnose_source()
    assert diagnostic.synthetic_mode_only is False
    assert diagnostic.terminal_connected is True
    assert diagnostic.package_version


def test_real_history_imports_with_terminal_provenance(tmp_path: Path) -> None:
    store = DatasetStore(tmp_path)
    stored = import_mt5(
        store,
        symbol=Symbol.EURUSD,
        timeframe=Timeframe.H1,
        start=START.astimezone(UTC),
        end=END.astimezone(UTC),
    )
    manifest = stored.manifest
    assert manifest.provenance is DataProvenance.MT5_TERMINAL
    assert manifest.contract.provenance is DataProvenance.MT5_TERMINAL
    assert manifest.coverage.bar_count > 0
    # Costs are an unsourced approximation, so the best status reachable is approximate.
    assert manifest.status is not DatasetStatus.QUALIFIED
    signal, execution = store.load_bars(stored)
    assert signal and execution
    assert all(bar.open_time.utcoffset() is not None for bar in signal[:10])
