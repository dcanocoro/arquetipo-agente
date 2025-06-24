import pytest
import asyncio
from fastapi import Request
from starlette.datastructures import Headers
from app.main import call_llm, get_authenticated_headers
from app.main import InternalServerErrorException, ForbiddenException
import app.main as main_module

@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch):
    async def fake_retrieve_credentials(headers):
        return ("test_access_key", "test_secret_key")
    monkeypatch.setattr(main_module, 'retrieve_credentials', fake_retrieve_credentials)

    def fake_run(coro):
        return asyncio.get_event_loop().run_until_complete(coro)
    monkeypatch.setattr(asyncio, 'run', fake_run)

    yield

class DummyServerClient:
    def __init__(self, access_key, secret_key, base):
        self.cookies = {'session': 'dummy'}

class DummyChat:
    def __init__(self):
        self.completions = self
n
class DummyAsyncOpenAI:
    def __init__(self, api_key, base_url, http_client):
        self.chat = DummyChat()
        self.client_args = (api_key, base_url, http_client)

    class completions:
        @staticmethod
        async def create(model, messages, max_tokens):
            return {"id": "response_id", "choices": [{"message": {"content": "OK"}}]}

@pytest.mark.asyncio
async def test_successful_call(monkeypatch):
    monkeypatch.setattr(main_module.ai_core, 'AIServerClient', DummyServerClient)
    monkeypatch.setattr(main_module, 'AsyncOpenAI', DummyAsyncOpenAI)

    scope = {"type": "http", "headers": []}
    request = Request(scope)
    headers = {}

    result = await call_llm(request, headers)
    assert result is None

@pytest.mark.asyncio
async def test_login_raises_internal_error(monkeypatch):
    def bad_init(access_key, secret_key, base):
        raise ValueError("init failure")
    monkeypatch.setattr(main_module.ai_core, 'AIServerClient', bad_init)
    monkeypatch.setattr(main_module, 'AsyncOpenAI', DummyAsyncOpenAI)

    scope = {"type": "http", "headers": []}
    request = Request(scope)
    headers = {}

    with pytest.raises(InternalServerErrorException) as excinfo:
        await call_llm(request, headers)
    assert "init failure" in str(excinfo.value)

@pytest.mark.asyncio
async def test_forbidden_in_get_response(monkeypatch)
    monkeypatch.setattr(main_module.ai_core, 'AIServerClient', DummyServerClient)
    class BadAsyncOpenAI(DummyAsyncOpenAI):
        class completions:
            @staticmethod
            async def create(model, messages, max_tokens):
                raise RuntimeError("api error")
    monkeypatch.setattr(main_module, 'AsyncOpenAI', BadAsyncOpenAI)

    scope = {"type": "http", "headers": []}
    request = Request(scope)
    headers = {}

    with pytest.raises(ForbiddenException) as excinfo:
        await call_llm(request, headers)
    assert "Error en la llamada a OpenAI" in str(excinfo.value)

@pytest.mark.asyncio
async def test_missing_client_header(monkeypatch):
   
    async def fake_get_headers():
        raise main_module.ForbiddenException("no headers")
    monkeypatch.setattr(main_module, 'get_authenticated_headers', fake_get_headers)

    scope = {"type": "http", "headers": []}
    request = Request(scope)

    with pytest.raises(ForbiddenException):
        await call_llm(request)
