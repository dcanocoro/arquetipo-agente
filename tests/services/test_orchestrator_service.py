"""Tests para orchestrator service"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.orchestrator_service import OrchestratorService
import types
from contextlib import asynccontextmanager
from unittest.mock import MagicMock
import httpx
from fastapi.responses import StreamingResponse


 
 
@pytest.mark.asyncio
class TestOrchestratorService:
    """Tests unitarios de ejecutar_prompt"""
 
    async def _make_service(self):
        return OrchestratorService()
 
    # -----------   Happy path   ---------------
    async def test_ejecutar_prompt_ok(self):
        with patch.object(OrchestratorService, "_client") as mock_client, \
             patch("app.services.orchestrator_service.ResponseBody") as mock_response_body:
            
            # Simulación de la respuesta del orquestador
            mock_client.rest_call = AsyncMock(
                return_value=MagicMock(json=lambda: {"data": "👍"})
            )
            mock_response_body.model_validate = MagicMock(return_value="validated")
 
            service = await self._make_service()
            result = await service.ejecutar_prompt(
                prompt_id="p", agent_id="a", headers={"h": "1"}
            )
 
            mock_client.rest_call.assert_awaited_once_with(
                rest_call=mock_client.rest_call.call_args.kwargs["rest_call"],
                endpoint="/expose/ejecutar-prompt",
                headers={"h": "1"},
                params={"promptid": "p", "agentid": "a"},
            )
            mock_response_body.model_validate.assert_called_once_with({"data": "👍"})
            assert result == "validated"
 
    # -----------   Error path   -----------
    async def test_ejecutar_prompt_error(self):
        with patch.object(OrchestratorService, "_client") as mock_client:
            mock_client.rest_call = AsyncMock(side_effect=RuntimeError("down"))
            service = await self._make_service()
 
            with pytest.raises(RuntimeError):
                await service.ejecutar_prompt(
                    prompt_id="p", agent_id="a", headers={}
                )


# ---------- Fakes auxiliares ----------

class _FakeRequest:
    """Imita fastapi.Request solo con body()"""
    async def body(self):
        return b'{"content": "hola"}'


class _FakeResponseOK:
    """Imita httpx.Response en caso de éxito con dos chunks."""
    def __init__(self):
        self._chunks = [b"chunk1", b"chunk2"]

    # no lanza excepciones 2xx
    def raise_for_status(self):
        pass

    async def aiter_raw(self):
        for chunk in self._chunks:
            yield chunk


def _make_http_error(url: str):
    """Crea una httpx.HTTPStatusError 500 genérica."""
    req = httpx.Request("POST", url)
    resp = httpx.Response(status_code=500, request=req)
    return httpx.HTTPStatusError("boom", request=req, response=resp)


# ---------- AsyncClient fake genérico ----------

def _patch_async_client_ok(monkeypatch):
    """Parchea httpx.AsyncClient para devolver chunks correctamente."""

    @asynccontextmanager
    async def _fake_stream(*_a, **_kw):
        yield _FakeResponseOK()

    class _FakeClient:
        def __init__(self, *_, **__):
            """Empty method for creating a Fake client"""
            pass

        async def __aenter__(self):
            """Empty method for creating a Fake client"""
            return self

        async def __aexit__(self, *exc):
            """Empty method for creating a Fake client"""
            return False

        # .stream devuelve el context-manager fake
        def stream(self, *_a, **_kw):
            return _fake_stream()

    monkeypatch.setattr(
        "app.services.orchestrator_service.httpx.AsyncClient",
        _FakeClient,
    )


def _patch_async_client_http_error(monkeypatch):
    """Parchea AsyncClient para que levante HTTPStatusError en raise_for_status."""

    url = "http://127.0.0.1:8000/streaming/stream"

    @asynccontextmanager
    async def _fake_stream(*_a, **_kw):
        fake_resp = _FakeResponseOK()
        # sobre-escribimos raise_for_status para que lance la excepción
        fake_resp.raise_for_status = types.MethodType(
            lambda self: (_ for _ in ()).throw(_make_http_error(url)), fake_resp
        )
        yield fake_resp

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *exc): return False
        def stream(self, *_a, **_kw): return _fake_stream()

    monkeypatch.setattr(
        "app.services.orchestrator_service.httpx.AsyncClient",
        _FakeClient,
    )


# ---------- TESTS ----------

@pytest.mark.asyncio
async def test_stream_prompt_ok(monkeypatch):
    """
    Debe retornar un StreamingResponse y reenviar los chunks tal cual.
    """
    _patch_async_client_ok(monkeypatch)

    service = OrchestratorService()
    request = _FakeRequest()

    resp = await service.stream_prompt(
        request=request,
        headers={"h": "1"},
    )

    assert isinstance(resp, StreamingResponse)
    # Leemos todos los chunks emitidos por body_iterator
    received = []
    async for c in resp.body_iterator:
        received.append(c)

    assert received == [b"chunk1", b"chunk2"]
