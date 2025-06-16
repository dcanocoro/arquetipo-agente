"""Tests para app.services.internal_service (nueva versión)"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.services.internal_service import InternalAppService
from qgdiag_lib_arquitectura.exceptions.types import InternalServerErrorException

ROUTE = "app.services.internal_service.get_app_status"

@pytest.mark.asyncio
class TestInternalAppService:
    """Tests del método InternalAppService.get_status"""

    async def test_get_status_ok(self):
        """Devuelve el estado cuando la app existe."""
        mock_db = MagicMock(spec=Session)

        with patch(
            ROUTE,
            return_value="running",
        ) as mock_get_app_status:
            result = await InternalAppService.get_status(
                application_id=123, db=mock_db
            )

            mock_get_app_status.assert_called_once_with(123, mock_db)
            assert result == "running"

    async def test_get_status_returns_none(self):
        """Devuelve None si la app no existe (no se lanza excepción)."""
        mock_db = MagicMock(spec=Session)

        with patch(
            ROUTE,
            return_value=None,
        ) as mock_get_app_status:
            result = await InternalAppService.get_status(
                application_id=123, db=mock_db
            )

            mock_get_app_status.assert_called_once_with(123, mock_db)
            assert result is None

    async def test_get_status_internal_error(self):
        """Propaga InternalServerErrorException si ocurren errores internos."""
        mock_db = MagicMock(spec=Session)

        with patch(
            ROUTE,
            side_effect=RuntimeError("DB down"),
        ) as mock_get_app_status:
            with pytest.raises(InternalServerErrorException) as exc:
                await InternalAppService.get_status(application_id=123, db=mock_db)

            mock_get_app_status.assert_called_once_with(123, mock_db)
            assert "DB down" in str(exc.value)
