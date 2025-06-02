"""Tests para el endpoint de usuarios."""

from fastapi import status
from app.routes import users as users_router


class _SilentLogger(object):
    """Silencia el logger de la app para evitar spam en los tests."""
    def debug(self, *_, **__):
        """
        A placeholder method for debugging purposes.
        This method is currently empty and does not perform any operations.
        It is intended to be overridden or implemented in the future if debugging
        functionality is required.
        Parameters:
        *_: Variable-length positional arguments (not used).
        **__: Variable-length keyword arguments (not used).
        # Note: This method is empty because no specific debugging logic has been
        # defined yet. If debugging functionality is needed, implement the logic here.
        """
        pass

    def error(self, *_, **__):
        """
        A placeholder method for debugging purposes.
        This method is currently empty and does not perform any operations.
        It is intended to be overridden or implemented in the future if debugging
        functionality is required.
        Parameters:
        *_: Variable-length positional arguments (not used).
        **__: Variable-length keyword arguments (not used).
        # Note: This method is empty because no specific debugging logic has been
        # defined yet. If debugging functionality is needed, implement the logic here.
        """
        pass


def test_users_process_internal_error(client, monkeypatch):
    """Testea el endpoint /users/process para el caso de error interno."""

    monkeypatch.setattr(users_router, "_logger", _SilentLogger())

    async def boom(*_, **__):
        """Simula un error interno en el servicio de usuario."""
        raise RuntimeError("DB down")

    monkeypatch.setattr(
        "app.routes.users.InternalUserService.get_prompt_params",
        boom,
    )

    resp = client.post("/users/process?user_id=1")
    assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    # The router exposes the raw exception message
    assert resp.json()["detail"] == "DB down"
