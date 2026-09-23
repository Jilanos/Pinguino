"""The browser journey, driven through the local API on a synthetic fixture.

Import, qualify, preview, run, compare, inspect, open the final evaluation once and
export. The fixture is short, so every candidate stays inconclusive: this proves the
workflow and its guards, not a strategy.
"""

from __future__ import annotations

import io
import json
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pinguino.api.app import REQUEST_TOKEN_HEADER, create_app
from pinguino.config import Settings
from pinguino.domain.errors import ErrorCode
from pinguino.research.export import replay_inputs

TOKEN = "journey-token"
HEADERS = {REQUEST_TOKEN_HEADER: TOKEN}


def _client(data_dir: Path, *, worker_process: bool = False) -> TestClient:
    settings = Settings(
        request_token=TOKEN, data_dir=data_dir, ui_dir=None, worker_process=worker_process
    )
    return TestClient(create_app(settings), base_url="http://127.0.0.1:8787")


def _import_fixture(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/datasets/import/fixture",
        json={"symbol": "EURUSD", "timeframe": "H1"},
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def _small_config(client: TestClient, dataset_id: str, candidates: int = 4) -> dict[str, Any]:
    config: dict[str, Any] = client.get(
        "/api/campaigns/suggested-config", params={"dataset_id": dataset_id}
    ).json()
    config["budget"] = config["budget"] | {"max_candidates": candidates}
    return config


def _wait(client: TestClient, campaign_id: str, timeout: float = 120) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload: dict[str, Any] = client.get(f"/api/campaigns/{campaign_id}").json()
        if payload["state"] not in ("queued", "running"):
            return payload
        time.sleep(0.2)
    raise AssertionError("campaign did not finish in time")


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return _client(tmp_path)


class TestDatasetImport:
    def test_a_fixture_import_is_labelled_synthetic_and_approximate(
        self, client: TestClient
    ) -> None:
        dataset = _import_fixture(client)
        manifest = dataset["manifest"]
        assert manifest["provenance"] == "synthetic_fixture"
        assert manifest["status"] == "approximate"
        assert dataset["finding_counts"] == {"missing_cost_component": 1}
        assert client.get("/api/datasets").json()[0]["dataset_id"] == dataset["dataset_id"]

    def test_the_same_fixture_imports_to_the_same_fingerprint(self, client: TestClient) -> None:
        first, second = _import_fixture(client), _import_fixture(client)
        assert first["manifest"]["content_hash"] == second["manifest"]["content_hash"]

    def test_mt5_import_without_the_package_reports_a_french_diagnostic(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A None entry makes the import fail even where the package is installed.
        monkeypatch.setitem(sys.modules, "MetaTrader5", None)
        response = client.post(
            "/api/datasets/import/mt5",
            json={
                "symbol": "EURUSD",
                "timeframe": "H1",
                "start": "2024-01-01T00:00:00Z",
                "end": "2024-02-01T00:00:00Z",
            },
            headers=HEADERS,
        )
        assert response.status_code == 503
        assert response.json()["code"] == ErrorCode.MT5_PACKAGE_UNAVAILABLE.value
        assert "synthétique" in response.json()["message"]


class TestCampaignJourney:
    def test_the_full_journey_runs_and_exports_a_replayable_record(
        self, client: TestClient
    ) -> None:
        dataset = _import_fixture(client)
        config = _small_config(client, dataset["dataset_id"])

        preview = client.post("/api/campaigns/preview", json=config, headers=HEADERS).json()
        assert preview["preview"]["base_candidate_count"] == 4
        assert preview["startable"] is True

        created = client.post("/api/campaigns", json=config, headers=HEADERS)
        assert created.status_code == 200, created.text
        campaign_id = created.json()["campaign_id"]
        status = _wait(client, campaign_id)
        assert status["state"] == "completed"
        assert status["trial_counts"] == {"completed": 4}
        assert status["duration_seconds"] > 0
        assert status["baselines"][0]["cash"] == {"net_return": "0", "max_drawdown": "0"}

        candidates = client.get(f"/api/campaigns/{campaign_id}/candidates").json()
        assert len(candidates) == 4
        # Short synthetic history cannot reach the evidence thresholds.
        assert {item["verdict"] for item in candidates} == {"inconclusive"}
        assert all(item["rank"] is None for item in candidates)
        assert [w["label"] for w in candidates[0]["windows"]] == [
            "training",
            "validation",
            "validation_1",
            "validation_2",
            "validation_3",
        ]

        candidate_id = candidates[0]["candidate_id"]
        detail = client.get(
            f"/api/campaigns/{campaign_id}/candidates/{candidate_id}/windows/validation",
            params={"limit": 5},
        ).json()
        assert detail["trade_total"] == candidates[0]["windows"][1]["trade_count"]
        assert len(detail["trades"]) <= 5
        assert 0 < len(detail["equity"]) <= 401

        exported = client.get(f"/api/campaigns/{campaign_id}/candidates/{candidate_id}/export")
        assert exported.status_code == 200
        archive = zipfile.ZipFile(io.BytesIO(exported.content))
        assert set(archive.namelist()) == {
            "strategy.json",
            "configuration.json",
            "metrics.json",
            "trades_training.csv",
            "trades_validation.csv",
            "equity_validation.csv",
            "report.html",
            "manifest.json",
        }
        replayed = replay_inputs(archive.read("strategy.json").decode("utf-8"))
        assert replayed["definition"].candidate_id == candidate_id
        assert replayed["dataset_hashes"] == (dataset["manifest"]["content_hash"],)
        report = archive.read("report.html").decode("utf-8")
        assert "inconclusive" in report
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["dataset_provenance"] == "synthetic_fixture"

    def test_a_campaign_cannot_start_without_a_preview(self, client: TestClient) -> None:
        dataset = _import_fixture(client)
        config = _small_config(client, dataset["dataset_id"])
        response = client.post("/api/campaigns", json=config, headers=HEADERS)
        assert response.status_code == 409
        assert response.json()["code"] == ErrorCode.PREVIEW_REQUIRED.value

    def test_an_existing_campaign_cannot_be_recreated(self, client: TestClient) -> None:
        dataset = _import_fixture(client)
        config = _small_config(client, dataset["dataset_id"], candidates=1)
        client.post("/api/campaigns/preview", json=config, headers=HEADERS)
        campaign_id = client.post("/api/campaigns", json=config, headers=HEADERS).json()[
            "campaign_id"
        ]
        _wait(client, campaign_id)
        again = client.post("/api/campaigns", json=config, headers=HEADERS)
        assert again.status_code == 409
        assert again.json()["code"] == ErrorCode.CAMPAIGN_IMMUTABLE.value

    def test_coverage_shorter_than_the_warm_up_is_refused(self, client: TestClient) -> None:
        dataset = _import_fixture(client)
        config = _small_config(client, dataset["dataset_id"])
        config["window_policy"]["requested_start"] = "2024-01-08T00:00:00Z"
        response = client.post("/api/campaigns/preview", json=config, headers=HEADERS)
        assert response.status_code == 400
        assert response.json()["code"] == ErrorCode.DATASET_COVERAGE_INSUFFICIENT.value


class TestFinalHoldout:
    def test_the_final_holdout_opens_once_for_one_candidate_and_never_reranks(
        self, client: TestClient
    ) -> None:
        dataset = _import_fixture(client)
        config = _small_config(client, dataset["dataset_id"], candidates=2)
        client.post("/api/campaigns/preview", json=config, headers=HEADERS)
        campaign_id = client.post("/api/campaigns", json=config, headers=HEADERS).json()[
            "campaign_id"
        ]
        _wait(client, campaign_id)
        first, second = (
            item["candidate_id"]
            for item in client.get(f"/api/campaigns/{campaign_id}/candidates").json()
        )
        base = f"/api/campaigns/{campaign_id}/candidates"

        hidden = client.get(f"{base}/{first}/windows/final_holdout")
        assert hidden.status_code == 403

        opened = client.post(
            f"{base}/{first}/final-evaluation", json={"reason": "frozen"}, headers=HEADERS
        )
        assert opened.status_code == 200
        assert opened.json()["access"]["candidate_id"] == first
        assert client.get(f"{base}/{first}/windows/final_holdout").status_code == 200

        refused = client.post(
            f"{base}/{second}/final-evaluation", json={"reason": "second"}, headers=HEADERS
        )
        assert refused.status_code == 403
        assert refused.json()["code"] == ErrorCode.HOLDOUT_ACCESS_DENIED.value
        after = client.get(base).json()
        assert all(item["rank"] is None for item in after)


class TestInterruption:
    def test_a_run_left_active_by_a_dead_process_is_marked_interrupted_on_restart(
        self, tmp_path: Path
    ) -> None:
        client = _client(tmp_path)
        dataset = _import_fixture(client)
        config = _small_config(client, dataset["dataset_id"], candidates=1)
        client.post("/api/campaigns/preview", json=config, headers=HEADERS)
        campaign_id = client.post("/api/campaigns", json=config, headers=HEADERS).json()[
            "campaign_id"
        ]
        _wait(client, campaign_id)

        import sqlite3

        connection = sqlite3.connect(tmp_path / "research.sqlite")
        with connection:
            connection.execute("UPDATE campaign_runs SET state = 'running'")
            connection.execute("UPDATE trials SET state = 'running'")
        connection.close()

        restarted = _client(tmp_path)
        assert restarted.get(f"/api/campaigns/{campaign_id}").json()["state"] == "interrupted"
        resumed = restarted.post(f"/api/campaigns/{campaign_id}/resume", headers=HEADERS)
        assert resumed.status_code == 200
        linked = resumed.json()
        assert linked["config"]["resumed_from_campaign_id"] == campaign_id
        assert _wait(restarted, linked["campaign_id"])["state"] == "completed"


class TestWorkerProcess:
    def test_a_campaign_runs_in_a_separate_process_and_can_be_cancelled(
        self, tmp_path: Path
    ) -> None:
        client = _client(tmp_path, worker_process=True)
        dataset = _import_fixture(client)
        config = _small_config(client, dataset["dataset_id"], candidates=32)
        client.post("/api/campaigns/preview", json=config, headers=HEADERS)
        campaign_id = client.post("/api/campaigns", json=config, headers=HEADERS).json()[
            "campaign_id"
        ]
        # The API answers while the worker runs.
        assert client.get("/api/health").status_code == 200
        deadline = time.monotonic() + 60
        while client.get(f"/api/campaigns/{campaign_id}").json()["state"] != "running":
            assert time.monotonic() < deadline
            time.sleep(0.1)
        cancel = client.post(f"/api/campaigns/{campaign_id}/cancel", headers=HEADERS)
        assert cancel.json()["cancel_requested"] is True
        final = _wait(client, campaign_id)
        assert final["state"] == "cancelled"
        assert final["trial_counts"].get("completed", 0) < 32
