"""
Router público que contiene un endpoint de demostración que
1. obtiene datos de un servicio *interno*
2. los envía al orquestador
3. registra todo a través del logger de la arquitectura
"""


from fastapi import APIRouter, Depends, HTTPException
from app.services.internal_user_service import InternalUserService
from app.services.orchestrator_service import OrchestratorService
from app.schemas.services.orchestrator import OrchestratorRequest
from app.config import settings
from qgdiag_lib_arquitectura import Authenticator
from qgdiag_lib_arquitectura import CustomLogger
from qgdiag_lib_arquitectura import ResponseBody


router = APIRouter(prefix="/users", tags=["Users"])

_logger = CustomLogger("users_router")
_auth = Authenticator(jwt_secret_key="test_secret", jwt_algorithm="HS256", security_enabled=True)


@router.post(
    "/process",
    response_model=ResponseBody,
    dependencies=[Depends(_auth.authenticate_token)],
)
async def process_user(user_id: int):
    """
    Endpoint de demostración.
    Obtiene información de usuario y la envía al orquestador.
    """
    try:
        # 1 - obtener parámetros
        params = await InternalUserService().get_prompt_params(user_id)
        _logger.debug("Params for user %s: %s", user_id, params)

        # 2 - construir payload
        payload = OrchestratorRequest(
            prompt_id=settings.PROMPT_ID,
            agent_id=settings.AGENT_ID,
            app_id=settings.APP_ID,
            params=params,
        )

        # 3 - llamar al orquestador (unpacking the model into arguments)
        response = await OrchestratorService().ejecutar_prompt(**payload.dict())
        return response

    except Exception as exc:
        _logger.error("Processing failed", exc_info=exc)
        raise HTTPException(status_code=500, detail=str(exc))
