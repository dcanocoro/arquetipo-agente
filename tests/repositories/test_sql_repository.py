import pytest
from unittest.mock import MagicMock, patch
from app.models.db_model import AppTable
from app.repositories.sql_repository import get_app_status


def test_get_app_status_not_found():
    # Simulate not found (None)
    with patch("app.repositories.sql_repository.sql_database.session") as mock_session:
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__.return_value.get.return_value = None
        mock_session.return_value = mock_context_manager

        result = get_app_status(application_id=999)

        mock_context_manager.__enter__.return_value.get.assert_called_once_with(
            AppTable, 999  # Note: AppTable is not patched here, so it's None
        )
        assert result is None
