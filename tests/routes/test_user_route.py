"""Tests para Orchestrator router (GET version)"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

TEST_TOKEN = "test.token"


@pytest.fixture
def fastapi_app():
    """Fixture para la aplicación FastAPI con overrides"""
    from app.routes import call_orchestrator as call_orch_router
    from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers

    app = FastAPI()

    # Mock de las cabeceras autenticadas con el nuevo nombre de header
    def mock_get_authenticated_headers():
        return {"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"}

    app.dependency_overrides[get_authenticated_headers] = mock_get_authenticated_headers
    app.include_router(call_orch_router.router)
    return app


class TestCallOrchestratorRouter:
    """Tests del endpoint GET /call_orchestrator/process"""

    @patch("app.routes.call_orchestrator.InternalAppService")
    @patch("app.routes.call_orchestrator.OrchestratorService")
    def test_process_user_success(
        self,
        mock_orchestrator_cls,
        mock_internal_service_cls,
        fastapi_app,
    ):
        """Happy path del endpoint"""

        client = TestClient(fastapi_app)

        # Mock del servicio interno
        mock_internal_instance = mock_internal_service_cls.return_value
        mock_internal_instance.get_status = AsyncMock(return_value="active")

        # Mock del orquestador
        mock_orchestrator_instance = mock_orchestrator_cls.return_value
        mock_orchestrator_instance.ejecutar_prompt = AsyncMock(
            return_value={"data": "todo OK"}
        )

        # Ejecución de la petición GET
        resp = client.get(
            "/call_orchestrator/process",
            params={"prompt_id": "prompt-123", "agent_id": "agent-abc"},
            headers={"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"},
        )

        # Validaciones
        assert resp.status_code == 200
        assert resp.json()["data"] == "todo OK"

        expected_headers = {
            "Token": TEST_TOKEN,
            "IAG-App-Id": "test-app-id",
        }

        mock_internal_instance.get_status.assert_awaited_once_with("test-app-id")
        mock_orchestrator_instance.ejecutar_prompt.assert_awaited_once_with(
            prompt_id="prompt-123",
            agent_id="agent-abc",
            headers=expected_headers,
        )
