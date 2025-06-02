"""Wrapper entorno al cliente HTTP que envía datos al orquestador
   para ejecutar un prompt"""

from typing import Dict
from qgdiag_lib_arquitectura import RestClient, HTTPMethod
from qgdiag_lib_arquitectura import ResponseBody
from app.config import settings


class OrchestratorService(object):
    """
    Wrapper entorno al RestClient para comunicarse con el orquestador.
    """
    _client = RestClient(
        url=settings.ORCHESTRATOR_URL,
        port=None
    )

    async def ejecutar_prompt(
        self,
        prompt_id: str,
        agent_id: str,
        app_id: str,
        extra_headers: Dict[str, str] | None = None,
    ) -> ResponseBody:
        """
        Llama a GET /ejecutar-prompt?promptid=...&agentid=...&app_id=...

        Devuelve
        -------
        OrchestratorResponse
            .data será lo que el orquestador haya retornado.
        """
        headers = {"Accept": "application/json"}
        if extra_headers:
            headers.update(extra_headers)

        response = await self._client.rest_call(
            rest_call=HTTPMethod.GET,
            endpoint="/ejecutar-prompt",
            headers=headers,
            params={
                "promptid": prompt_id,
                "agentid": agent_id,
                "app_id": app_id,
            },
        )

        return ResponseBody.model_validate(response.json())
