"""Tests del endpoint GET /call_orchestrator/process (nueva versión)"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Dependencias a sobre-escribir
from qgdiag_lib_arquitectura.security.authentication import (
    get_authenticated_headers,
)
from app.repositories.db_dependencies import get_db_app

TEST_TOKEN = "test.token"


@pytest.fixture
def fastapi_app():
    """Crea una app FastAPI con overrides de dependencias."""
    from app.routes import call_orchestrator as call_orch_router

    app = FastAPI()

    # --- override de cabeceras autenticadas ---
    def mock_get_authenticated_headers():
        return {"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"}

    app.dependency_overrides[get_authenticated_headers] = mock_get_authenticated_headers

    # --- override del proveedor de sesión DB ---
    mock_db = MagicMock(spec=Session)
    app.dependency_overrides[get_db_app] = lambda: mock_db

    # --- incluye el router real ---
    app.include_router(call_orch_router.router)

    # Devolvemos la app y el mock de DB para las aserciones
    return app, mock_db


class TestCallOrchestratorRouter:
    """Happy-path y verificación de dependencias"""

    @patch("app.routes.call_orchestrator.OrchestratorService")
    @patch("app.routes.call_orchestrator.InternalAppService")
    def test_process_user_success(
        self,
        mock_internal_cls,          # se cambia el orden respecto al parcheo
        mock_orchestrator_cls,
        fastapi_app,
    ):
        app, mock_db = fastapi_app
        client = TestClient(app)

        # --- mock de InternalAppService.get_status(application_id, db) ---
        mock_internal_inst = mock_internal_cls.return_value
        mock_internal_inst.get_status = AsyncMock(return_value="active")

        # --- mock de OrchestratorService.ejecutar_prompt(...) ---
        mock_orchestrator_inst = mock_orchestrator_cls.return_value
        mock_orchestrator_inst.ejecutar_prompt = AsyncMock(
            return_value={"data": "todo OK"}
        )

        resp = client.get(
            "/call_orchestrator/process",
            params={"prompt_id": "prompt-123", "agent_id": "agent-abc"},
            headers={"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"},
        )

        # --- verificaciones ---
        assert resp.status_code == 200
        assert resp.json()["data"] == "todo OK"

        expected_headers = {"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"}

        mock_internal_inst.get_status.assert_awaited_once_with(
            "test-app-id", mock_db
        )
        mock_orchestrator_inst.ejecutar_prompt.assert_awaited_once_with(
            prompt_id="prompt-123",
            agent_id="agent-abc",
            headers=expected_headers,
        )
