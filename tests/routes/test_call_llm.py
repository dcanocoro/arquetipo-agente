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

    def mock_get_authenticated_headers():
        return {"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"}

    app.dependency_overrides[get_authenticated_headers] = mock_get_authenticated_headers
    app.include_router(call_orch_router.router)
    return app


class TestCallLLMStreamRouter:
    """Tests del endpoint POST /call_orchestrator/call-llm-test"""

    @patch("app.routes.call_orchestrator.retrieve_credentials", new_callable=AsyncMock)
    @patch("aicore.AIServerClient")
    @patch("app.routes.call_orchestrator.httpx.AsyncClient")
    def test_call_llm_success(self, mock_httpx_client_cls, mock_aiserver_cls, mock_retrieve_cls, fastapi_app):
        mock_retrieve.return_value = ("key1", "secret2")
        
        fake_server = Mock()
        fake_server.cookies = {"session": "abc"}
        mock_aiserver_cls.return_value = fake_server

        
        fake_httpx = Mock()
        mock_httpx_client_cls.return_value = fake_httpx

       
        with patch("your_module.routes.AsyncOpenAI") as mock_openai_cls:
            fake_openai = Mock()
            async def fake_create(model, messages, max_tokens):
                return {"choices":[{"message":{"content":"¡respuesta larga!"}}]}
            fake_openai.chat = Mock(completions=Mock(create=fake_create))
            mock_openai_cls.return_value = fake_openai

            client = TestClient(app)

            
            resp = client.post("/call-llm-test")

            
            assert resp.status_code == 200

            mock_retrieve.assert_awaited_once_with(headers={"Authorization": "Bearer tok", "IAG-App-Id": "app-id"})
            mock_aiserver_cls.assert_called_once_with(
                access_key="key1",
                secret_key="secret2",
                base="https://aicorepru.unicajasc.corp/Monolith/api"
            )

            mock_httpx_client_cls.assert_called_once()
            _, kwargs = mock_httpx_client_cls.call_args
            assert "event_hooks" in kwargs
            hooks = kwargs["event_hooks"]
            assert isinstance(hooks["request"][0], type(lambda: None))
            assert isinstance(hooks["response"][0], type(lambda: None))

            mock_openai_cls.assert_called_once_with(
                api_key="key1:secret2",
                base_url="https://aicorepru.unicajasc.corp/Monolith/api/model/openai",
                http_client=fake_httpx
            )

