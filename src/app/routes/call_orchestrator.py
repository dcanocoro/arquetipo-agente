"""
Router público que contiene un endpoint de demostración que
1. obtiene datos de un servicio *interno*
2. llama al orquestador.
3. registra todo a través del logger de la arquitectura.
"""


from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from app.services.internal_service import InternalAppService
from app.services.orchestrator_service import OrchestratorService
from app.settings import settings
from qgdiag_lib_arquitectura import CustomLogger, ResponseBody
from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers, get_application_id 
from qgdiag_lib_arquitectura.exceptions.types import InternalServerErrorException



router = APIRouter(prefix="/call_orchestrator", tags=["call orchestrator"])
_logger = CustomLogger("call_orchestratorr")


@router.get("/process", response_model=ResponseBody)
async def process_user(request: Request,
                       prompt_id: str,
                       agent_id: str,
                       headers: dict = Depends(get_authenticated_headers)
                       ):
    """
    Endpoint de demostración que envía informacion al orquestador.
    """
    try:
        # obtenemos application_id del certificado
        application_id = headers["IAG-App-Id"]

        # llamada de ejemplo a un microservicio interno
        try:
            app_status = await InternalAppService().get_status(application_id)
            if not app_status:
                _logger.warning(f"Application ID {application_id} not found")
            else:
                _logger.debug(f"Application ID {application_id} has status: {app_status}")
        except Exception as dummy_exc:
            _logger.warning(f"Dummy internal service call failed: {dummy_exc}")

        # llamar al orquestador sin importar el resultado de app_status
        response = await OrchestratorService().ejecutar_prompt(prompt_id=prompt_id,
                                                               agent_id=agent_id,
                                                               headers=headers
                                                               )
        return response
    except Exception as e:
        _logger.error("Processing failed", excs_info=e)
        raise InternalServerErrorException(str(e))


@router.post("/stream")
async def proxy_stream(promptid: str, agentid: str, request: Request,
                       headers: dict = Depends(get_authenticated_headers)):
    """
    Proxy endpoint that forwards the request to the orchestrator and streams the response.
    """
    try:
        orchestrator_service = OrchestratorService()
        return await orchestrator_service.stream_prompt(request=request,
                                                      prompt_id=promptid,
                                                      agent_id=agentid,
                                                      headers=headers
                                                      )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy streaming failed: {str(e)}")
