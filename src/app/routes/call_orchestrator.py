"""
Router público que contiene un endpoint de demostración que
1. obtiene datos de un servicio *interno*
2. llama al orquestador.
3. registra todo a través del logger de la arquitectura.
"""


from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from qgdiag_lib_arquitectura import CustomLogger, ResponseBody
from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers
from qgdiag_lib_arquitectura.exceptions.types import InternalServerErrorException
from app.services.internal_service import InternalAppService
from app.services.orchestrator_service import OrchestratorService
from app.repositories.db_dependencies import get_db_app
from app.settings import settings

import os
from qgdiag_lib_arquitectura.utilities.ai_core import ai_core
from dotenv import load_dotenv
from qgdiag_lib_arquitectura.utilities.ai_core.control_gastos import alogging_gastos, amake_check_blocked
from qgdiag_lib_arquitectura.utilities.ai_core.ai_core import retrieve_credentials
import asyncio
import httpx as httpx
from openai import AsyncOpenAI, OpenAI
from qgdiag_lib_arquitectura.exceptions.types import ForbiddenException
import asyncio


router = APIRouter(prefix="/call_orchestrator", tags=["call orchestrator"])
_logger = CustomLogger("call_orchestratorr")


@router.get("/process", response_model=ResponseBody)
async def process_user(request: Request,
                       prompt_id: str,
                       agent_id: str,
                       headers: dict = Depends(get_authenticated_headers),
                       db: Session = Depends(get_db_app)
                       ):
    """
    Endpoint de demostración que envía informacion al orquestador.
    """
    try:
        application_id = headers["IAG-App-Id"]

        try:
            app_status = await InternalAppService().get_status(application_id, db)
            if not app_status:
                _logger.warning(f"Application ID {application_id} not found")
            else:
                _logger.debug(f"Application ID {application_id} has status: {app_status}")
        except Exception as dummy_exc:
            _logger.warning(f"Dummy internal service call failed: {dummy_exc}")

        response = await OrchestratorService().ejecutar_prompt(prompt_id=prompt_id,
                                                               agent_id=agent_id,
                                                               headers=headers)
        return response
    except Exception as e:
        _logger.error("Processing failed", exc_info=e)
        raise InternalServerErrorException(str(e))


@router.post("/stream")
async def proxy_stream(request: Request,
                       headers: dict = Depends(get_authenticated_headers)):
    """
    Proxy endpoint that forwards the request to the orchestrator and streams the response.
    """
    try:
        orchestrator_service = OrchestratorService()
        return await orchestrator_service.stream_prompt(request=request, headers=headers)
    
    except Exception as e:
        raise InternalServerErrorException(str(e))


@router.post("/call-llm-test")
async def call_llm(request: Request, headers: dict = Depends(get_authenticated_headers)):
    """
    Endpoint para hacer pruebas simulando llamadas sencillas de un escalado.
    """
    BASE_URL = "https://aicorepru.unicajasc.corp/Monolith/api"
    ENGINE_ID = "1ccb0725-fad1-453e-a673-c350c8fd5bc0"
    async def retrieve():
        return await retrieve_credentials(headers=headers)

    def login():
        try:
            return ai_core.AIServerClient(
                access_key=ACCESS_KEY,
                secret_key=SECRET_KEY,
                base=BASE_URL,
            )
        except Exception as e:
           raise InternalServerErrorException(str(e))

    async def get_response(client):
        try:
            response = await client.chat.completions.create(
                model=ENGINE_ID,
                messages=[
                    {"role": "developer", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Dame una respuesta muy larga"},
                ],
                max_tokens=300,
            )
        except Exception as e:
            raise ForbiddenException(f"Error en la llamada a OpenAI: {str(e)}") 
    try:
        access_key, secret_key = asyncio.run(retrieve())
        server_connection = login()
        http_client = httpx.AsyncClient(event_hooks={"request": [amake_check_blocked(headers=headers)], "response": [alogging_gastos]}) 
        http_client.cookies=server_connection.cookies
        api_key = ACCESS_KEY + ":" + SECRET_KEY
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=BASE_URL + "/model/openai",
            http_client=http_client
        )
        asyncio.run(get_response())
    except Exception as e:
        raise InternalServerErrorException(str(e))



