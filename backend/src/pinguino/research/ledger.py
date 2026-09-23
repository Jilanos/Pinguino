"""SQLite ledger for campaigns, trials and final-holdout access.

Every attempted trial is persisted, including the ones that fail or are cancelled, so a
campaign can always account for what it tried. State transitions are written inside a
transaction, and trials still marked running at startup are reconciled to interrupted:
the process that owned them is gone, so their partial work cannot be trusted.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pinguino.domain.campaign import CampaignConfig, HoldoutAccessEvent, Trial
from pinguino.domain.enums import TrialState
from pinguino.domain.identity import canonical_json
from pinguino.domain.strategy import StrategyDefinition

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trials (
    trial_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(campaign_id),
    candidate_id TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    state TEXT NOT NULL,
    planned_order INTEGER NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    failure_reason TEXT
);
CREATE INDEX IF NOT EXISTS trials_by_campaign ON trials(campaign_id, planned_order);
CREATE TABLE IF NOT EXISTS trial_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id TEXT NOT NULL REFERENCES trials(trial_id),
    state TEXT NOT NULL,
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS holdout_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    window_policy_id TEXT NOT NULL,
    dataset_ids TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    reused_lineage INTEGER NOT NULL,
    reason TEXT NOT NULL
);
"""


class Ledger:
    """Durable campaign state. One connection, one writer, one trial at a time."""

    def __init__(self, database: Path | str, *, shared: bool = False) -> None:
        # ``shared`` lets the API's worker threads read through one connection.
        self.connection = sqlite3.connect(
            database, isolation_level=None, check_same_thread=not shared, timeout=30
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise
        self.connection.execute("COMMIT")

    def create_campaign(self, config: CampaignConfig, *, now: datetime | None = None) -> str:
        moment = (now or datetime.now(UTC)).isoformat()
        with self._transaction() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO campaigns(campaign_id, config_json, created_at)"
                " VALUES (?, ?, ?)",
                (config.campaign_id, canonical_json(config), moment),
            )
        return config.campaign_id

    def enqueue(self, campaign_id: str, definitions: list[StrategyDefinition]) -> list[str]:
        """Persist the whole planned order before any trial runs."""
        trial_ids: list[str] = []
        with self._transaction() as connection:
            for order, definition in enumerate(definitions):
                trial_id = f"{campaign_id}:{order:04d}"
                trial_ids.append(trial_id)
                connection.execute(
                    "INSERT OR IGNORE INTO trials(trial_id, campaign_id, candidate_id,"
                    " definition_json, state, planned_order) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        trial_id,
                        campaign_id,
                        definition.candidate_id,
                        canonical_json(definition),
                        TrialState.QUEUED.value,
                        order,
                    ),
                )
                connection.execute(
                    "INSERT INTO trial_transitions(trial_id, state, at) VALUES (?, ?, ?)",
                    (trial_id, TrialState.QUEUED.value, datetime.now(UTC).isoformat()),
                )
        return trial_ids

    def transition(
        self,
        trial_id: str,
        state: TrialState,
        *,
        now: datetime | None = None,
        failure_reason: str | None = None,
    ) -> None:
        moment = (now or datetime.now(UTC)).isoformat()
        with self._transaction() as connection:
            if state is TrialState.RUNNING:
                connection.execute(
                    "UPDATE trials SET state = ?, started_at = ? WHERE trial_id = ?",
                    (state.value, moment, trial_id),
                )
            else:
                connection.execute(
                    "UPDATE trials SET state = ?, ended_at = ?, failure_reason = ?"
                    " WHERE trial_id = ?",
                    (state.value, moment, failure_reason, trial_id),
                )
            connection.execute(
                "INSERT INTO trial_transitions(trial_id, state, at) VALUES (?, ?, ?)",
                (trial_id, state.value, moment),
            )

    def reconcile_interrupted(self, *, now: datetime | None = None) -> list[str]:
        """Mark every trial left running by a dead process as interrupted."""
        moment = (now or datetime.now(UTC)).isoformat()
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(
                "SELECT trial_id FROM trials WHERE state = ?", (TrialState.RUNNING.value,)
            )
            stale = [row["trial_id"] for row in cursor.fetchall()]
        for trial_id in stale:
            self.transition(trial_id, TrialState.INTERRUPTED, now=datetime.fromisoformat(moment))
        return stale

    def trials(self, campaign_id: str) -> list[Trial]:
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(
                "SELECT * FROM trials WHERE campaign_id = ? ORDER BY planned_order",
                (campaign_id,),
            )
            rows = cursor.fetchall()
        return [
            Trial(
                trial_id=row["trial_id"],
                campaign_id=row["campaign_id"],
                definition=StrategyDefinition.model_validate_json(row["definition_json"]),
                state=TrialState(row["state"]),
                planned_order=row["planned_order"],
                started_at=_parse(row["started_at"]),
                ended_at=_parse(row["ended_at"]),
                failure_reason=row["failure_reason"],
            )
            for row in rows
        ]

    def state_counts(self, campaign_id: str) -> dict[TrialState, int]:
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(
                "SELECT state, COUNT(*) AS total FROM trials WHERE campaign_id = ? GROUP BY state",
                (campaign_id,),
            )
            return {TrialState(row["state"]): row["total"] for row in cursor.fetchall()}

    def record_holdout_access(self, event: HoldoutAccessEvent) -> None:
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO holdout_access(campaign_id, candidate_id, window_policy_id,"
                " dataset_ids, requested_at, reused_lineage, reason)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event.campaign_id,
                    event.candidate_id,
                    event.window_policy_id,
                    canonical_json(list(event.dataset_ids)),
                    event.requested_at.isoformat(),
                    int(event.reused_lineage),
                    event.reason,
                ),
            )

    def holdout_accesses(self, campaign_id: str) -> list[sqlite3.Row]:
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(
                "SELECT * FROM holdout_access WHERE campaign_id = ? ORDER BY id",
                (campaign_id,),
            )
            return cursor.fetchall()

    def lineage_was_used(self, window_policy_id: str, dataset_ids: tuple[str, ...]) -> bool:
        """True when this dataset and window lineage was already opened, even elsewhere."""
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(
                "SELECT 1 FROM holdout_access WHERE window_policy_id = ? AND dataset_ids = ?"
                " LIMIT 1",
                (window_policy_id, canonical_json(list(dataset_ids))),
            )
            return cursor.fetchone() is not None


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
