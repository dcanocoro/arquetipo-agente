import pytest
from unittest.mock import patch, MagicMock
from app.services.internal_service import InternalAppService


@pytest.mark.asyncio
class TestInternalAppService:
    async def test_get_status_ok(self):
        # Mock object with .status attribute
        mock_app = MagicMock()
        mock_app.status = "running"

        with patch("app.services.internal_service.get_app_status", return_value=mock_app) as mock_get_app_status:
            result = await InternalAppService.get_status(application_id=123)

            mock_get_app_status.assert_called_once_with(123)
            assert result == "running"

    async def test_get_status_not_found(self):
        with patch("app.services.internal_service.get_app_status", return_value=None) as mock_get_app_status:
            with pytest.raises(ValueError, match="User 123 not found"):
                await InternalAppService.get_status(application_id=123)

            mock_get_app_status.assert_called_once_with(123)
