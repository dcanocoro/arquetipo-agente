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
