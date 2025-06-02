"""Endpoint dummy de demostración que obtiene el estado de una aplicación"""

from app.repositories.sql_repository import get_app_status


class InternalUserService(object):
    """Clase de servicio para obtener parámetros específicos de un usuario interno."""

    @staticmethod
    async def get_status(application_id: int) -> dict:
        """Devuelve el status de la app"""
        app = await get_app_status(application_id)
        if not app:
            raise ValueError(f"User {application_id} not found")
        return {

        }
