# tests/test_call_orchestrator_stream.py
 
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
 
 
@pytest.fixture
def fastapi_app():
    """
    Crea una instancia de FastAPI con el router real (`call_orchestrator`)
    y con dependencias de autenticación mockeadas.
    """
    from app.routes import call_orchestrator as call_orch_router
    from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers
 
    app = FastAPI()
 
    def _fake_auth_headers() -> dict:
        return {"Token": "unit-test-token", "IAG-App-Id": "testing-app"}
 
    app.dependency_overrides[get_authenticated_headers] = _fake_auth_headers
    app.include_router(call_orch_router.router)
    return app
 
 
class TestProxyStreamEndpoint:
    """Tests para el endpoint POST /call_orchestrator/stream"""
 
    @patch("app.routes.call_orchestrator.OrchestratorService")
    def test_stream_success(self, mock_orchestrator_cls, fastapi_app):
        """Caso exitoso: el orquestador devuelve una StreamingResponse."""
 
        async def _mock_gen():
            yield b"chunk-1"
            yield b"chunk-2"
 
        mock_instance = mock_orchestrator_cls.return_value
        mock_instance.stream_prompt = AsyncMock(
            return_value=StreamingResponse(_mock_gen())
        )
 
        client = TestClient(fastapi_app)
        resp = client.post("/call_orchestrator/stream", json={"foo": "bar"})
 
        assert resp.status_code == 200
        assert resp.content == b"chunk-1chunk-2"
 
        mock_orchestrator_cls.assert_called_once()
        mock_instance.stream_prompt.assert_awaited_once()
        assert mock_instance.stream_prompt.call_args.kwargs["headers"] == {
            "Token": "unit-test-token",
            "IAG-App-Id": "testing-app"
        }
 
    @patch("app.routes.call_orchestrator.OrchestratorService")
    def test_stream_raises_internal_server_error(self, mock_orchestrator_cls, fastapi_app):
        """Si ocurre una excepción, debe traducirse a HTTP 500."""
 
        mock_instance = mock_orchestrator_cls.return_value
        mock_instance.stream_prompt = AsyncMock(side_effect=RuntimeError("failure!"))
 
        # ⚠️ Aquí es importante parchear la excepción exacta del módulo donde está
        from app.routes import call_orchestrator as call_orch_router
 
        class DummyInternalServerError(HTTPException):
            def __init__(self, detail: str):
                super().__init__(status_code=500, detail=detail)
 
        with patch.object(call_orch_router, "InternalServerErrorException", DummyInternalServerError):
            client = TestClient(fastapi_app)
            resp = client.post("/call_orchestrator/stream", json={"foo": "bar"})
 
        assert resp.status_code == 500
        assert resp.json() == {"detail": "failure!"}
