"""Lógica de negocio para obtener parámetros específicos de un usuario interno"""

from app.repositories.mysql import get_user_by_id


class InternalUserService(object):
    """Clase de servicio para obtener parámetros específicos de un usuario interno."""

    @staticmethod
    async def get_prompt_params(user_id: int) -> dict:
        """Devuelve el diccionario que se pasará al prompt."""
        user = await get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Example template params required by PROMPT_ID
        return {
            "name": user.full_name or user.email.split("@")[0],
            "email": user.email,
        }
