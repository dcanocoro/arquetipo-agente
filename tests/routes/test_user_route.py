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
 
    return app, mock_db
 
 
class TestCallOrchestratorRouter:
    """Happy-path y verificación de dependencias, más casos de error y ramas inactivas."""
 
    @patch("app.routes.call_orchestrator.OrchestratorService")
    @patch("app.routes.call_orchestrator.InternalAppService")
    def test_process_user_success(
        self,
        mock_internal_cls,
        mock_orchestrator_cls,
        fastapi_app,
    ):
        app, mock_db = fastapi_app
        client = TestClient(app)
 
        # Happy‐path: InternalAppService.get_status devuelve "active"
        mock_internal_inst = mock_internal_cls.return_value
        mock_internal_inst.get_status = AsyncMock(return_value="active")
 
        mock_orch_inst = mock_orchestrator_cls.return_value
        mock_orch_inst.ejecutar_prompt = AsyncMock(return_value={"data": "todo OK"})
 
        resp = client.get(
            "/call_orchestrator/process",
            params={"prompt_id": "prompt-123", "agent_id": "agent-abc"},
            headers={"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == "todo OK"
 
        mock_internal_inst.get_status.assert_awaited_once_with("test-app-id", mock_db)
        mock_orch_inst.ejecutar_prompt.assert_awaited_once_with(
            prompt_id="prompt-123",
            agent_id="agent-abc",
            headers={"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"},
        )
 
    @patch("app.routes.call_orchestrator.OrchestratorService")
    @patch("app.routes.call_orchestrator.InternalAppService")
    def test_process_user_status_falsy_calls_orchestrator(
        self,
        mock_internal_cls,
        mock_orchestrator_cls,
        fastapi_app,
    ):
        app, mock_db = fastapi_app
        client = TestClient(app)
 
        # get_status devuelve None → rama de warning, pero sigue
        mock_internal_cls.return_value.get_status = AsyncMock(return_value=None)
        mock_orch_inst = mock_orchestrator_cls.return_value
        mock_orch_inst.ejecutar_prompt = AsyncMock(return_value={"data": "ok even if no status"})
 
        resp = client.get(
            "/call_orchestrator/process",
            params={"prompt_id": "p1", "agent_id": "a1"},
            headers={"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == "ok even if no status"
 
        mock_internal_cls.return_value.get_status.assert_awaited_once()
        mock_orch_inst.ejecutar_prompt.assert_awaited_once()
 
    @patch("app.routes.call_orchestrator.OrchestratorService")
    @patch("app.routes.call_orchestrator.InternalAppService")
    def test_process_user_internal_service_error_still_calls_orchestrator(
        self,
        mock_internal_cls,
        mock_orchestrator_cls,
        fastapi_app,
    ):
        app, mock_db = fastapi_app
        client = TestClient(app)
 
        # get_status lanza excepción → atrapada internamente
        mock_internal_cls.return_value.get_status = AsyncMock(side_effect=Exception("fail internal"))
        mock_orch_inst = mock_orchestrator_cls.return_value
        mock_orch_inst.ejecutar_prompt = AsyncMock(return_value={"data": "orch ok"})
 
        resp = client.get(
            "/call_orchestrator/process",
            params={"prompt_id": "p2", "agent_id": "a2"},
            headers={"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == "orch ok"
 
        mock_internal_cls.return_value.get_status.assert_awaited_once()
        mock_orch_inst.ejecutar_prompt.assert_awaited_once()
 
    @patch("app.routes.call_orchestrator.OrchestratorService")
    @patch("app.routes.call_orchestrator.InternalAppService")
    def test_process_user_orchestrator_raises_internal_server_error(
        self,
        mock_internal_cls,
        mock_orchestrator_cls,
        fastapi_app,
    ):
        app, mock_db = fastapi_app
        client = TestClient(app)
 
        # get_status funciona bien
        mock_internal_cls.return_value.get_status = AsyncMock(return_value="active")
        # ejecutar_prompt lanza excepción → provoca 500
        mock_orchestrator_cls.return_value.ejecutar_prompt = AsyncMock(side_effect=Exception("orch fail"))
 
        resp = client.get(
            "/call_orchestrator/process",
            params={"prompt_id": "x", "agent_id": "y"},
            headers={"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"},
        )
        assert resp.status_code == 500
        assert "orch fail" in resp.text
