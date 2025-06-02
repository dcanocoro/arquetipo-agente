"""
Test para la clase OrchestratorService
"""

import pytest
from qgdiag_lib_arquitectura import ResponseBody
from app.services.orchestrator_service import OrchestratorService


@pytest.mark.asyncio
async def test_ejecutar_prompt(monkeypatch):
    """
    The wrapper should return a ResponseBody created from the JSON
    in the HTTP response delivered by RestClient.
    """

    # ---------- fake HTTP response object ---------------------------
    class FakeResp(object):
        """Simula la respuesta de un cliente HTTP."""
        @staticmethod
        def json():
            # Whatever structure your real orchestrator returns
            return {"data": {"result": "ok"}}

    async def fake_call(*args, **kwargs):
        """Simula la llamada a un cliente HTTP."""
        # Simulate RestClient.rest_call(...)
        return FakeResp()

    # Patch RestClient.rest_call so no real network traffic happens
    monkeypatch.setattr(
        "app.services.orchestrator_service.RestClient.rest_call",
        fake_call,
    )

    # Act
    res = await OrchestratorService().ejecutar_prompt(
        prompt_id="prompt-123",
        agent_id="agent-A",
        app_id="app-X",
    )

    # Assert
    assert isinstance(res, ResponseBody)
    assert res.data["result"] == "ok"
