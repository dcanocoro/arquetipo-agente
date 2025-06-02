"""Wrapper entorno al cliente HTTP que envía datos al orquestador
   para ejecutar un prompt"""

from typing import Dict
from qgdiag_lib_arquitectura import RestClient, HTTPMethod
from qgdiag_lib_arquitectura import ResponseBody
from app.settings import settings


class OrchestratorService(object):
    """
    Wrapper entorno al RestClient para comunicarse con el orquestador.
    """
    _client = RestClient(
        url=settings.ORCHESTRATOR_URL,
        port=settings.ORCHESTRATOR_PORT
    )

    async def ejecutar_prompt(self,
                              prompt_id: str,
                              agent_id: str,
                              headers: Dict[str, str] | None = None
                              ) -> ResponseBody:
        """
        Llama a GET /ejecutar-prompt y devuelve lo que el orquestador haya retornado.
        """
        response = await self._client.rest_call(
            rest_call=HTTPMethod.GET,
            endpoint="/expose/ejecutar-prompt",
            headers=headers,
            params={
                "promptid": prompt_id,
                "agentid": agent_id,
            }
        )
        return ResponseBody.model_validate(response.json())
