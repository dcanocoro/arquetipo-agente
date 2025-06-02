"""Tests unitarios para el InternalUserService."""

import pytest
from app.services.internal_user_service import InternalUserService


@pytest.mark.asyncio
async def test_get_prompt_params_success(monkeypatch):
    """Test para el InternalUserService.get_prompt_params()"""
    dummy_user = type(
        "Dummy",
        (),
        {"id": 42, "email": "foo@bar.com", "full_name": "Foo Bar"},
    )()

    async def fake_get_user_by_id(user_id: int):
        """Simula la búsqueda de un usuario en la base de datos."""
        return dummy_user

    monkeypatch.setattr(
        "app.services.internal_user_service.get_user_by_id",
        fake_get_user_by_id,
    )

    params = await InternalUserService().get_prompt_params(42)
    assert params == {"name": "Foo Bar", "email": "foo@bar.com"}


@pytest.mark.asyncio
async def test_get_prompt_params_not_found(monkeypatch):
    """
    Test para el InternalUserService.get_prompt_params()
    cuando no se encuentra el usuario
    """
    async def fake_get_user_by_id(user_id: int):
        """Simula que no se encuentra el usuario."""
        return None

    monkeypatch.setattr(
        "app.services.internal_user_service.get_user_by_id",
        fake_get_user_by_id,
    )

    with pytest.raises(ValueError):
        await InternalUserService().get_prompt_params(99)
