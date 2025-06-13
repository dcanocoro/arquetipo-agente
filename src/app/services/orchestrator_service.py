"""Wrapper entorno al cliente HTTP que envía datos al orquestador
   para ejecutar un prompt"""

from typing import Dict
from fastapi import Request
from fastapi.responses import StreamingResponse
import httpx
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
        
    async def stream_prompt(
            self,
            request: Request,
            prompt_id: str,
            agent_id: str,
            headers: Dict[str, str],
        ) -> StreamingResponse:
            """
            Envía un POST al orquestador y reenvía su respuesta como flujo SSE.
            """
            # Cuerpo original (no se puede leer dos veces)
            body = await request.body()

            url = ("http://127.0.0.1:8000/streaming/stream")

            async def stream_generator():
                try:
                    async with httpx.AsyncClient(timeout=None) as client:
                        # Use the *stream* context-manager API
                        async with client.stream(
                            "POST",
                            url,
                            params={"promptid": prompt_id, "agentid": agent_id},
                            headers=headers,
                            content=body,
                        ) as resp:

                            # Propaga errores HTTP (>399) como excepciones
                            resp.raise_for_status()

                            # Relay raw chunks to the caller
                            async for chunk in resp.aiter_raw():
                                yield chunk

                except httpx.HTTPStatusError as http_exc:
                    err_body = await http_exc.response.aread()
                    raise Exception(
                        f"Orchestrator returned {http_exc.response.status_code}: "
                        f"{err_body.decode('utf-8', errors='ignore')}"
                    ) from http_exc
                except httpx.RequestError as conn_exc:
                    raise Exception(f"Connection error: {conn_exc}") from conn_exc
                except Exception as general_exc:
                    raise Exception(f"Unexpected streaming error: {general_exc}") from general_exc

            # FastAPI will stream whatever the generator yields
            return StreamingResponse(stream_generator(), media_type="text/event-stream")

