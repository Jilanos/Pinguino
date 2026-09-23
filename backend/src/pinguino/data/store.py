"""Local dataset store.

Bar files are immutable gzip CSV named by the hash of their content, so an identical
series imported twice is stored once. Manifests and quality findings are kept in SQLite
alongside the campaign ledger. Nothing here stores credentials or account identifiers.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from pinguino.data.quality import QualityFinding
from pinguino.domain.dataset import Bar, DatasetManifest
from pinguino.domain.enums import Symbol, Timeframe
from pinguino.domain.identity import content_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    status TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    findings_json TEXT NOT NULL,
    signal_file TEXT NOT NULL,
    execution_file TEXT NOT NULL,
    stored_at TEXT NOT NULL
);
"""

CSV_HEADER = ("open_time", "open", "high", "low", "close", "spread_points")


class StoredDataset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    manifest: DatasetManifest
    findings: tuple[QualityFinding, ...]
    signal_file: str
    execution_file: str
    stored_at: datetime


def _encode(bars: Sequence[Bar]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for bar in bars:
        writer.writerow(
            (bar.open_time.isoformat(), bar.open, bar.high, bar.low, bar.close, bar.spread_points)
        )
    # mtime=0 keeps the compressed bytes identical for identical content.
    return gzip.compress(buffer.getvalue().encode("utf-8"), mtime=0)


def _decode(payload: bytes) -> tuple[Bar, ...]:
    reader = csv.reader(io.StringIO(gzip.decompress(payload).decode("utf-8")))
    next(reader)
    return tuple(
        Bar.model_construct(
            open_time=datetime.fromisoformat(row[0]),
            open=Decimal(row[1]),
            high=Decimal(row[2]),
            low=Decimal(row[3]),
            close=Decimal(row[4]),
            spread_points=Decimal(row[5]),
        )
        for row in reader
    )


class DatasetStore:
    def __init__(self, data_dir: Path) -> None:
        self.bars_dir = data_dir / "bars"
        self.bars_dir.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(data_dir / "research.sqlite", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def _write_bars(self, bars: Sequence[Bar]) -> str:
        payload = _encode(bars)
        name = f"{content_hash([bar.model_dump(mode='json') for bar in bars])}.csv.gz"
        target = self.bars_dir / name
        if not target.exists():
            partial = target.with_suffix(".partial")
            partial.write_bytes(payload)
            partial.replace(target)
        return name

    def save(
        self,
        *,
        manifest: DatasetManifest,
        findings: Sequence[QualityFinding],
        signal_bars: Sequence[Bar],
        execution_bars: Sequence[Bar],
        stored_at: datetime,
    ) -> StoredDataset:
        signal_file = self._write_bars(signal_bars)
        execution_file = self._write_bars(execution_bars)
        stored = StoredDataset(
            dataset_id=manifest.dataset_id,
            manifest=manifest,
            findings=tuple(findings),
            signal_file=signal_file,
            execution_file=execution_file,
            stored_at=stored_at,
        )
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO datasets(dataset_id, symbol, timeframe, status,"
                " manifest_json, findings_json, signal_file, execution_file, stored_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    stored.dataset_id,
                    manifest.symbol.value,
                    manifest.timeframe.value,
                    manifest.status.value,
                    manifest.model_dump_json(),
                    json.dumps([finding.model_dump(mode="json") for finding in findings]),
                    signal_file,
                    execution_file,
                    stored_at.isoformat(),
                ),
            )
        return stored

    def list(self) -> list[StoredDataset]:
        with closing(self.connection.cursor()) as cursor:
            cursor.execute("SELECT * FROM datasets ORDER BY stored_at DESC")
            return [_row(row) for row in cursor.fetchall()]

    def get(self, dataset_id: str) -> StoredDataset | None:
        with closing(self.connection.cursor()) as cursor:
            cursor.execute("SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,))
            row = cursor.fetchone()
        return _row(row) if row is not None else None

    def load_bars(self, stored: StoredDataset) -> tuple[tuple[Bar, ...], tuple[Bar, ...]]:
        """Signal bars and M1 execution bars, restricted to usable (non-quarantined) ranges."""
        quarantined = stored.manifest.coverage.quarantined_ranges

        def usable(bars: tuple[Bar, ...]) -> tuple[Bar, ...]:
            if not quarantined:
                return bars
            return tuple(
                bar
                for bar in bars
                if not any(start <= bar.open_time < end for start, end in quarantined)
            )

        signal = _decode((self.bars_dir / stored.signal_file).read_bytes())
        execution = _decode((self.bars_dir / stored.execution_file).read_bytes())
        return usable(signal), usable(execution)


def _row(row: sqlite3.Row) -> StoredDataset:
    return StoredDataset(
        dataset_id=row["dataset_id"],
        manifest=DatasetManifest.model_validate_json(row["manifest_json"]),
        findings=tuple(
            QualityFinding.model_validate(item) for item in json.loads(row["findings_json"])
        ),
        signal_file=row["signal_file"],
        execution_file=row["execution_file"],
        stored_at=datetime.fromisoformat(row["stored_at"]),
    )


def dataset_key(stored: StoredDataset) -> tuple[Symbol, Timeframe]:
    return stored.manifest.symbol, stored.manifest.timeframe
