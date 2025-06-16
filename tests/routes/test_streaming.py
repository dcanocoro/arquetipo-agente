"""Tests para Orchestrator router (POST /stream)"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from qgdiag_lib_arquitectura.exceptions.types import InternalServerErrorException

TEST_TOKEN = "test.token"


@pytest.fixture
def fastapi_app():
    """
    Devuelve una instancia de FastAPI con el router real y
    las dependencias de autenticación sobreescritas.
    """
    from app.routes import call_orchestrator as call_orch_router
    from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers

    app = FastAPI()

    # Mock de las cabeceras autenticadas
    def mock_get_authenticated_headers():
        return {"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"}

    app.dependency_overrides[get_authenticated_headers] = mock_get_authenticated_headers
    app.include_router(call_orch_router.router)
    return app


class TestProxyStreamRouter:
    """Tests del endpoint POST /call_orchestrator/stream"""

    # ---------- Happy path ----------
    @patch("app.routes.call_orchestrator.OrchestratorService")
    def test_proxy_stream_success(self, mock_orchestrator_cls, fastapi_app):
        client = TestClient(fastapi_app)

        # Stub del método stream_prompt
        mock_orch_instance = mock_orchestrator_cls.return_value
        mock_orch_instance.stream_prompt = AsyncMock(
            return_value={"result": "ok"}  # FastAPI lo serializa a JSONResponse
        )

        # Ejecución de la petición
        resp = client.post(
            "/call_orchestrator/stream",
            params={"promptid": "prompt-1", "agentid": "agent-A"},
            json={"input": "hola"},
            headers={"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"},
        )

        # --- Aserciones de respuesta ---
        assert resp.status_code == 200
        assert resp.json() == {"result": "ok"}

        # --- Aserciones de interacción con el servicio ---
        mock_orch_instance.stream_prompt.assert_awaited_once()
        call_kwargs = mock_orch_instance.stream_prompt.call_args.kwargs

        assert call_kwargs["prompt_id"] == "prompt-1"
        assert call_kwargs["agent_id"] == "agent-A"
        assert call_kwargs["headers"] == {
            "Token": TEST_TOKEN,
            "IAG-App-Id": "test-app-id",
        }
        # El request real viaja como argumento; basta con verificar su presencia
        assert "request" in call_kwargs
