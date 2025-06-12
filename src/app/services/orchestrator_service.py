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

    async def stream_prompt(self,
                            request: Request,
                            prompt_id: str,
                            agent_id: str,
                            headers: Dict[str, str]) -> StreamingResponse:
        """
        Reenvía una solicitud POST con cuerpo al orquestador y retorna la respuesta como StreamingResponse.
        """
        # Lee el cuerpo de la solicitud original una vez
        body = await request.body()

        # Construye la URL completa del endpoint de streaming del orquestador
        orchestrator_streaming_url = f"http://{settings.ORCHESTRATOR_URL}:{settings.ORCHESTRATOR_PORT}/streaming/stream"

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(
                    orchestrator_streaming_url,
                    params={"promptid": prompt_id, "agentid": agent_id},
                    headers=headers,
                    content=body,
                    stream=True
                )

                # Si el orquestador devuelve un error (status HTTP >= 400), levantamos excepción
                response.raise_for_status()

                # Generador que pasa los chunks del orquestador directamente al cliente
                async def stream_generator():
                    async for chunk in response.aiter_bytes():
                        yield chunk

                return StreamingResponse(stream_generator(), media_type="text/event-stream")

        except httpx.HTTPStatusError as http_exc:
            # Captura errores HTTP con código de estado inválido
            content = await http_exc.response.aread()
            raise Exception(f"Orchestrator error {http_exc.response.status_code}: {content.decode('utf-8')}")
        except httpx.RequestError as conn_exc:
            # Captura errores de conexión (timeout, DNS, etc.)
            raise Exception(f"Failed to connect to orchestrator: {str(conn_exc)}")
        except Exception as general_exc:
            # Otros errores no previstos
            raise Exception(f"Unexpected streaming error: {str(general_exc)}")
