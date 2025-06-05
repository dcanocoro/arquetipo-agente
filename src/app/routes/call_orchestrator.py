"""
Router público que contiene un endpoint de demostración que
1. obtiene datos de un servicio *interno*
2. llama al orquestador.
3. registra todo a través del logger de la arquitectura.
"""


from fastapi import APIRouter, Depends, Request
from app.services.internal_service import InternalAppService
from app.services.orchestrator_service import OrchestratorService
from app.settings import settings
from qgdiag_lib_arquitectura import CustomLogger, ResponseBody, InternalServerErrorException
from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers, get_application_id 


router = APIRouter(prefix="/call_orchestrator", tags=["call orchestrator"])
_logger = CustomLogger("call_orchestratorr")


@router.post("/process", response_model=ResponseBody)
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
        application_id = get_application_id(request)
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
