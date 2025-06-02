import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.repositories.sql_repository import get_app_status


@pytest.mark.asyncio
async def test_get_app_status_not_found():
    # Simulate not found (None)
    with patch("app.repositories.sql_repository.sql_database.session") as mock_session:
        mock_context = mock_session.return_value.__aenter__.return_value
        mock_context.get = AsyncMock(return_value=None)

        result = await get_app_status(application_id=999)

        mock_context.get.assert_awaited_once()
        assert result is None
