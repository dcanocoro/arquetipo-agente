import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.orchestrator_service import OrchestratorService
 
 
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
