"""
Pruebas unitarias para el módulo de acceso a datos MySQL.
"""

import pytest


@pytest.mark.asyncio
async def test_get_user_by_id_found(monkeypatch):
    """
    Test para el caso en que el usuario existe en la base de datos.
    Se simula una base de datos con un objeto ficticio.
    """
    from app.repositories.mysql import get_user_by_id, sql_database

    fake_user = object()

    # --- build a minimal async session/context manager -----------------
    class DummySession(object):
        """Simula una sesión de base de datos."""
        @staticmethod
        async def get(model, pk):
            assert pk == 1
            return fake_user

    class DummyCtx(object):
        """Simula un contexto de sesión de base de datos."""
        async def __aenter__(self):
            return DummySession()

        async def __aexit__(self, exc_type, exc, tb):
            # This method is intentionally left empty because the DummyCtx class
            # is a mock context manager used for testing purposes. It does not
            # need to perform any cleanup or handle exceptions, as it is only
            # simulating the behavior of a real database session context manager.
            pass

    # --- patch the sql_database so no real DB is touched ---------------
    monkeypatch.setattr(sql_database, "session", lambda: DummyCtx())

    result = await get_user_by_id(1)
    assert result is fake_user


@pytest.mark.asyncio
async def test_get_user_by_id_not_found(monkeypatch):
    """
    Test para el caso en que el usuario no existe en la base de datos.
    """
    from app.repositories.mysql import get_user_by_id, sql_database

    class DummySession(object):
        """Simula una sesión de base de datos."""
        @staticmethod
        async def get(model, pk):
            return None

    class DummyCtx(object):
        """Simula un contexto de sesión de base de datos."""
        @staticmethod
        async def __aenter__(unused_param=None):
            # Simula la creación de una sesión de base de datos
            return DummySession()

        async def __aexit__(self, exc_type, exc, tb):
            # This method is intentionally left empty because the DummyCtx class
            # is a mock context manager used for testing purposes. It does not
            pass

    monkeypatch.setattr(sql_database, "session", lambda: DummyCtx())

    result = await get_user_by_id(999)
    assert result is None
