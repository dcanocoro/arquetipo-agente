"""Wrapper entorno al cliente HTTP que envía datos al orquestador
   para ejecutar un prompt"""

from typing import Dict
from fastapi import Request
from fastapi.responses import StreamingResponse
import httpx
import os
from qgdiag_lib_arquitectura import RestClient, HTTPMethod, CustomLogger
from qgdiag_lib_arquitectura import ResponseBody
from app.settings import settings
from qgdiag_lib_arquitectura.exceptions.types import InternalServerErrorException

ENDPOINT_STREAMING = "/qgdiag-ms-orquestador-iag/streaming/stream"

_logger=CustomLogger("Microservicio Python")

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
        
    async def stream_prompt(
            self,
            request: Request,
            headers: Dict[str, str],
        ) -> StreamingResponse:
            """
            Envía un POST al orquestador y reenvía su respuesta como flujo SSE.
            """
            # Cuerpo original (no se puede leer dos veces)
            body = await request.body()

            url= f"{settings.ORCHESTRATOR_URL}:{settings.ORCHESTRATOR_PORT}{ENDPOINT_STREAMING}"
            # url = "http://127.0.0.1:8000/streaming/stream"
            _logger.info(f"Iniciando streaming hacia el orquestador: {url}")

            async def stream_generator():
                try:
                    async with httpx.AsyncClient(timeout=None) as client:
                        # Use the *stream* context-manager API
                        async with client.stream(
                            "POST",
                            url,
                            headers=headers,
                            content=body,
                        ) as resp:
                            
                            _logger.info(f"Conectando al orquestador")
                            # Propaga errores HTTP (>399) como excepciones
                            resp.raise_for_status()

                            # Relay raw chunks to the caller
                            async for chunk in resp.aiter_raw():
                                yield chunk
                except Exception as e:
                    _logger.error("Error durante el streaming desde el orquestador")
                    raise InternalServerErrorException(str(e))
                

            # FastAPI will stream whatever the generator yields
            return StreamingResponse(stream_generator(), media_type="text/event-stream")

