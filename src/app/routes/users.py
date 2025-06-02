"""
Router público que contiene un endpoint de demostración que
1. obtiene datos de un servicio *interno*
2. llama al orquestador.
3. registra todo a través del logger de la arquitectura.
"""


from fastapi import APIRouter, Depends, HTTPException, Request
from app.services.internal_user_service import InternalUserService
from app.services.orchestrator_service import OrchestratorService
from app.settings import settings
from qgdiag_lib_arquitectura import CustomLogger
from qgdiag_lib_arquitectura import ResponseBody
# Ahora usaremos request tambien
from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers, get_application_id 
# setters de user y application ID

router = APIRouter(prefix="/users", tags=["Users"])
_logger = CustomLogger("users_router")


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
        # llamada dummy a un microservicio interno
        try:
            params = await InternalUserService().get_status(application_id)
            _logger.debug("Params para user %s: %s", application_id, params)
        except Exception as dummy_exc:
            _logger.warning("Dummy internal service call failed")
        # llamar al orquestador
        response = await OrchestratorService().ejecutar_prompt(prompt_id=prompt_id,
                                                               agent_id=agent_id,
                                                               headers=headers
                                                               )
        return response
    except Exception as exc:
        _logger.error("Processing failed", exc_infos=exc)
        raise HTTPException(status_code=500, detail=str(exc))
