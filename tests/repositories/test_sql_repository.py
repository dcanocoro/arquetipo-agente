"""Tests para app.repositories.app_repository"""

from unittest.mock import MagicMock
from app.models.db_model import AppTable
from app.repositories.app_repository import get_app_status


def test_get_app_status_not_found():
    """Devuelve None si la aplicación no existe."""
    mock_session = MagicMock()
    mock_session.get.return_value = None

    result = get_app_status(application_id=999, db=mock_session)

    mock_session.get.assert_called_once_with(AppTable, 999)
    assert result is None
