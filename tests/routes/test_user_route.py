import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

@pytest.fixture
def fastapi_app():
    from app.routes import call_orchestrator as call_orch_router
    from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers

    app = FastAPI()

    # Mock authentication headers
    def mock_get_authenticated_headers():
        return {"Token": "test.token", "Application-Id": "test-app-id"}

    app.dependency_overrides[get_authenticated_headers] = mock_get_authenticated_headers
    app.include_router(call_orch_router.router)
    return app


class TestCallOrchestratorRouter:
    """Tests del endpoint POST /call_orchestrator/process"""

    @patch("app.routes.call_orchestrator.get_application_id")
    @patch("app.routes.call_orchestrator.InternalAPPService")
    @patch("app.routes.call_orchestrator.OrchestratorService")
    def test_process_user_success(self, mock_orchestrator_cls, mock_internal_service_cls, mock_get_app_id, fastapi_app):
        client = TestClient(fastapi_app)

        # Mock application ID
        mock_get_app_id.return_value = "test-app-id"

        # Mock internal service call
        mock_internal_instance = mock_internal_service_cls.return_value
        mock_internal_instance.get_status = AsyncMock(return_value="active")

        # Mock orchestrator call
        mock_orchestrator_instance = mock_orchestrator_cls.return_value
        mock_orchestrator_instance.ejecutar_prompt = AsyncMock(return_value={"data": "todo OK"})

        # Execution
        resp = client.post(
            "/call_orchestrator/process",
            params={"prompt_id": "prompt-123", "agent_id": "agent-abc"},
            headers={"Token": "test.token", "Application-Id": "test-app-id"}
        )

        # Assertions
        assert resp.status_code == 200
        assert resp.json()["data"] == "todo OK"

        expected_headers = {
            "Token": "test.token",
            "Application-Id": "test-app-id"
        }

        mock_internal_instance.get_status.assert_awaited_once_with("test-app-id")
        mock_orchestrator_instance.ejecutar_prompt.assert_awaited_once_with(
            prompt_id="prompt-123",
            agent_id="agent-abc",
            headers=expected_headers,
        )

    @patch("app.routes.call_orchestrator.get_application_id")
    @patch("app.routes.call_orchestrator.InternalAppService")
    @patch("app.routes.call_orchestrator.OrchestratorService")
    def test_process_user_failure(self, mock_orchestrator_cls, mock_internal_service_cls, mock_get_app_id, fastapi_app):
        client = TestClient(fastapi_app)

        mock_get_app_id.return_value = "test-app-id"

        # Internal service dummy failure should not block
        mock_internal_instance = mock_internal_service_cls.return_value
        mock_internal_instance.get_status = AsyncMock(side_effect=Exception("dummy fails"))

        # Orchestrator failure triggers HTTP 500
        mock_orchestrator_instance = mock_orchestrator_cls.return_value
        mock_orchestrator_instance.ejecutar_prompt = AsyncMock(side_effect=Exception("boom!"))

        resp = client.post(
            "/call_orchestrator/process",
            params={"prompt_id": "prompt-x", "agent_id": "agent-y"},
            headers={"Token": "test.token", "Application-Id": "test-app-id"}
        )

        assert resp.status_code == 500
        assert resp.json()["detail"] == "boom!"
