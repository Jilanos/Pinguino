from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from pinguino.api.app import REQUEST_TOKEN_HEADER, create_app
from pinguino.api.preview import preview_campaign
from pinguino.config import Settings
from pinguino.domain.campaign import CampaignBudget, CampaignConfig
from pinguino.domain.identity import canonical_json
from pinguino.fixtures import (
    fixture_cost_policy,
    fixture_eligibility_policy,
    fixture_sizing_policy,
    fixture_window_policy,
)

TOKEN = "test-token"
START = datetime(2020, 1, 1, tzinfo=UTC)
END = datetime(2025, 1, 1, tzinfo=UTC)


def _config(max_candidates: int = 192, max_evaluations: int = 2000) -> CampaignConfig:
    return CampaignConfig(
        config_version="v1",
        dataset_ids=("ds-a",),
        cost_policy=fixture_cost_policy(),
        sizing_policy=fixture_sizing_policy(),
        window_policy=fixture_window_policy(START.isoformat(), END.isoformat()),
        eligibility_policy=fixture_eligibility_policy(),
        budget=CampaignBudget(max_candidates=max_candidates, max_evaluations=max_evaluations),
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Settings(request_token=TOKEN)), base_url="http://127.0.0.1:8787")


class TestPreviewComputation:
    def test_the_full_grid_previews_one_hundred_and_ninety_two_candidates(self) -> None:
        preview, _ = preview_campaign(_config())
        assert preview.base_candidate_count == 192

    def test_the_evaluation_count_includes_robustness_work(self) -> None:
        preview, _ = preview_campaign(_config())
        # Five windows per candidate alone would be 960; stress and neighbours add more.
        assert preview.planned_evaluation_count > 192 * 5

    def test_the_evaluation_count_never_exceeds_the_declared_budget(self) -> None:
        preview, _ = preview_campaign(_config(max_evaluations=300))
        assert preview.planned_evaluation_count == 300

    def test_boundaries_are_resolved_to_explicit_ordered_instants(self) -> None:
        preview, split = preview_campaign(_config())
        assert preview.training_start == START
        assert preview.final_holdout_end == END
        assert preview.training_end == preview.validation_start
        assert preview.validation_end == preview.final_holdout_start
        assert len(split.validation_subwindows) == 3

    def test_the_same_configuration_previews_identically(self) -> None:
        first, _ = preview_campaign(_config())
        second, _ = preview_campaign(_config())
        assert first == second


class TestPreviewEndpoint:
    def test_preview_requires_the_per_launch_token(self, client: TestClient) -> None:
        response = client.post("/api/campaigns/preview", json={})
        assert response.status_code == 401

    def test_preview_returns_counts_and_subwindows(self, client: TestClient) -> None:
        import json

        response = client.post(
            "/api/campaigns/preview",
            headers={REQUEST_TOKEN_HEADER: TOKEN},
            json=json.loads(canonical_json(_config())),
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["preview"]["base_candidate_count"] == 192
        assert len(payload["validation_subwindows"]) == 3

    def test_an_invalid_configuration_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/campaigns/preview",
            headers={REQUEST_TOKEN_HEADER: TOKEN},
            json={"config_version": "v1"},
        )
        assert response.status_code == 422
