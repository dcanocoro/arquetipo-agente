"""Endpoint dummy de demostración que obtiene el estado de una aplicación"""

from app.repositories.sql_repository import get_app_status


class InternalAppService(object):
    """Clase de servicio dummy para obtener el status de una app"""

    @staticmethod
    async def get_status(application_id: int) -> str:
        """Devuelve el status de la app"""
        app = get_app_status(application_id)
        if not app:
            raise ValueError(f"User {application_id} not found")
        return app.status  # Return the actual status instead of True
