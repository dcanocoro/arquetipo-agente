import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
import os
import asyncio

# Dependencias a sobre-escribir
from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers
from app.repositories.db_dependencies import get_db_app
import app.routes.call_orchestrator as call_module
from app.routes.call_orchestrator import router, InternalServerErrorException

# Fixture de la app con override de autenticación
@pytest.fixture
def fastapi_app():
    app = FastAPI()

    # Override de autenticación
    def mock_get_authenticated_headers():
        return {"Token": "test.token", "IAG-App-Id": "test-app-id"}
    app.dependency_overrides[get_authenticated_headers] = mock_get_authenticated_headers

    mock_db = MagicMock()
    app.dependency_overrides[get_db_app] = lambda: mock_db

    app.include_router(router)
    return TestClient(app)

class DummyServerClient:
    def __init__(self, access_key, secret_key, base):
        self.cookies = {'session': 'dummy'}

class DummyAsyncOpenAI:
    def __init__(self, api_key, base_url, http_client):
        self.chat = self

    class completions:
        @staticmethod
        async def create(model, messages, max_tokens):
            return {"id": "response_id", "choices": [{"message": {"content": "OK"}}]}

class TestCallLlmEndpoint:
    """Tests para POST /call_orchestrator/call-llm-test"""

    @pytest.fixture(autouse=True)
    def patch_common(self, monkeypatch):
        async def fake_retrieve(headers):
            return ("a_key", "s_key")
        monkeypatch.setattr(call_module, 'retrieve_credentials', fake_retrieve)
        monkeypatch.setattr(asyncio, 'run', lambda coro: asyncio.get_event_loop().run_until_complete(coro))
        monkeypatch.setenv('ACCESS_KEY', 'a_key')
        monkeypatch.setenv('SECRET_KEY', 's_key')

    @patch.object(call_module.ai_core, 'AIServerClient', new=DummyServerClient)
    @patch.object(call_module, 'AsyncOpenAI', new=DummyAsyncOpenAI)
    def test_call_llm_success(self, fastapi_app):
        client = fastapi_app
        response = client.post(
            "/call_orchestrator/call-llm-test",
            headers={"Token": "test.token", "IAG-App-Id": "test-app-id"}
        )
        assert response.status_code == 200
        assert response.content in (b"null", b"")

    @patch.object(call_module.ai_core, 'AIServerClient', side_effect=ValueError("init fail"))
    @patch.object(call_module, 'AsyncOpenAI', new=DummyAsyncOpenAI)
    def test_call_llm_login_error(self, fastapi_app, mock_client):
        client = fastapi_app
        response = client.post(
            "/call_orchestrator/call-llm-test",
            headers={"Token": "test.token", "IAG-App-Id": "test-app-id"}
        )
        assert response.status_code == 500
        assert "init fail" in response.json()["error"]

    @patch.object(call_module.ai_core, 'AIServerClient', new=DummyServerClient)
    def test_call_llm_api_error(self, fastapi_app, monkeypatch):
        class BadOpenAI(DummyAsyncOpenAI):
            class completions:
                @staticmethod
                async def create(model, messages, max_tokens):
                    raise RuntimeError("api err")
        monkeypatch.setattr(call_module, 'AsyncOpenAI', BadOpenAI)

        client = fastapi_app
        response = client.post(
            "/call_orchestrator/call-llm-test",
            headers={"Token": "test.token", "IAG-App-Id": "test-app-id"}
        )
        assert response.status_code == 500
        assert "api err" in response.json()["error"]
