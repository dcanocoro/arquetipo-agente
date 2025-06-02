import pytest
from unittest.mock import AsyncMock, patch
from app.services.internal_user_service import InternalUserService


@pytest.mark.asyncio
class TestInternalUserService:
    async def test_get_status_ok(self):
        # Mock the repository function to return dummy app data
        with patch("app.services.internal_user_service.get_app_status", new_callable=AsyncMock) as mock_get_app_status:
            mock_get_app_status.return_value = {"status": "running"}

            result = await InternalUserService.get_status(application_id=123)

            # Adapt based on your actual returned dictionary structure
            assert isinstance(result, dict)

    async def test_get_status_not_found(self):
        # Mock the repository to return None, simulating not found
        with patch("app.services.internal_user_service.get_app_status", new_callable=AsyncMock) as mock_get_app_status:
            mock_get_app_status.return_value = None

            with pytest.raises(ValueError, match="User 123 not found"):
                await InternalUserService.get_status(application_id=123)

