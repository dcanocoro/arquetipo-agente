"""Endpoint dummy de demostración que obtiene el estado de una aplicación"""

from sqlalchemy.orm import Session
from app.repositories.app_repository import get_app_status
from qgdiag_lib_arquitectura.exceptions.types import InternalServerErrorException

class InternalAppService:
    """Clase de servicio dummy para obtener el status de una app"""

    @staticmethod
    async def get_status(application_id: int, db: Session) -> str:
        """Devuelve el status de la app"""
        try:
            status = get_app_status(application_id, db)
            return status
        except Exception as e:
            raise InternalServerErrorException(str(e))
        
