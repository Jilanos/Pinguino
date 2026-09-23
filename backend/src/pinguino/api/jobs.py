"""Campaign worker supervision.

One campaign runs at a time in a separate process so the API stays responsive. The
worker owns its own SQLite connections; the API only reads. A worker that disappears
without writing its end state is detected on the next status read and marked
interrupted, the same way a restart reconciles it.
"""

from __future__ import annotations

import multiprocessing
import threading
from dataclasses import dataclass
from multiprocessing.synchronize import Event as ProcessEvent
from pathlib import Path
from typing import Protocol

from pinguino.domain.campaign import CampaignConfig
from pinguino.domain.errors import ErrorCode, PinguinoError
from pinguino.research.service import execute_campaign


class _Handle(Protocol):
    def is_alive(self) -> bool: ...


class _Flag(Protocol):
    def set(self) -> None: ...

    def is_set(self) -> bool: ...


def _worker(data_dir: str, config_json: str, cancel: ProcessEvent) -> None:
    execute_campaign(
        Path(data_dir),
        CampaignConfig.model_validate_json(config_json),
        is_cancelled=cancel.is_set,
    )


def _thread_worker(data_dir: str, config_json: str, cancel: threading.Event) -> None:
    try:
        execute_campaign(
            Path(data_dir),
            CampaignConfig.model_validate_json(config_json),
            is_cancelled=cancel.is_set,
        )
    except Exception:  # the failure is persisted as the run state; nothing to re-raise to
        pass


@dataclass
class _Active:
    campaign_id: str
    handle: _Handle
    cancel: _Flag


class CampaignJobs:
    def __init__(self, data_dir: Path, *, use_process: bool = True) -> None:
        self.data_dir = data_dir
        self.use_process = use_process
        self._active: _Active | None = None
        self._lock = threading.Lock()

    def running_id(self) -> str | None:
        with self._lock:
            if self._active is not None and not self._active.handle.is_alive():
                self._active = None
            return self._active.campaign_id if self._active else None

    def is_alive(self, campaign_id: str) -> bool:
        return self.running_id() == campaign_id

    def start(self, config: CampaignConfig) -> None:
        if self.running_id() is not None:
            raise PinguinoError(ErrorCode.CAMPAIGN_ALREADY_RUNNING)
        payload = config.model_dump_json()
        handle: _Handle
        cancel: _Flag
        if self.use_process:
            context = multiprocessing.get_context("spawn")
            process_cancel = context.Event()
            process = context.Process(
                target=_worker,
                args=(str(self.data_dir), payload, process_cancel),
                daemon=True,
                name=f"pinguino-{config.campaign_id}",
            )
            process.start()
            handle, cancel = process, process_cancel
        else:
            thread_cancel = threading.Event()
            thread = threading.Thread(
                target=_thread_worker,
                args=(str(self.data_dir), payload, thread_cancel),
                daemon=True,
            )
            thread.start()
            handle, cancel = thread, thread_cancel
        with self._lock:
            self._active = _Active(config.campaign_id, handle, cancel)

    def cancel(self, campaign_id: str) -> bool:
        with self._lock:
            if self._active is None or self._active.campaign_id != campaign_id:
                return False
            self._active.cancel.set()
            return True
