from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pinguino.api.app import REQUEST_TOKEN_HEADER, create_app
from pinguino.config import Settings
from pinguino.domain.errors import ErrorCode

TOKEN = "test-token"


@pytest.fixture
def client() -> TestClient:
    settings = Settings(request_token=TOKEN)
    return TestClient(create_app(settings), base_url="http://127.0.0.1:8787")


class TestLocalGuards:
    def test_health_starts_without_the_mt5_package(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_source_diagnostic_reports_synthetic_mode_instead_of_failing(
        self, client: TestClient
    ) -> None:
        payload = client.get("/api/source/diagnostic").json()
        assert payload["package_available"] is False
        assert payload["synthetic_mode_only"] is True
        assert payload["code"] == ErrorCode.MT5_PACKAGE_UNAVAILABLE.value
        assert "synthétique" in payload["message"]

    def test_non_loopback_host_is_rejected(self, client: TestClient) -> None:
        response = client.get("/api/health", headers={"host": "example.com"})
        assert response.status_code == 403
        assert response.json()["code"] == ErrorCode.FOREIGN_ORIGIN_REJECTED.value

    def test_mutation_without_a_token_is_rejected(self, client: TestClient) -> None:
        response = client.post("/api/health")
        assert response.status_code == 401
        assert response.json()["code"] == ErrorCode.REQUEST_TOKEN_INVALID.value

    def test_foreign_origin_mutation_is_rejected_before_the_token_check(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/health",
            headers={"origin": "http://evil.example", REQUEST_TOKEN_HEADER: TOKEN},
        )
        assert response.status_code == 403


class TestSettings:
    def test_non_loopback_bind_is_refused(self) -> None:
        with pytest.raises(ValueError, match="loopback"):
            Settings(host="0.0.0.0")

    def test_default_token_is_generated_per_launch(self) -> None:
        assert Settings().request_token != Settings().request_token


class TestNoOrderSubmissionSurface:
    def test_adapter_module_exposes_no_order_capability(self) -> None:
        from pathlib import Path

        source = Path("src/pinguino/data/mt5_adapter.py").read_text(encoding="utf-8")
        for forbidden in ("order_send", "order_check", "login", "password"):
            assert forbidden not in source

    def test_routes_expose_no_shell_or_filesystem_path(self, client: TestClient) -> None:
        paths = {route.path for route in client.app.routes}  # type: ignore[attr-defined]
        assert all("{path" not in path and "file" not in path for path in paths)
