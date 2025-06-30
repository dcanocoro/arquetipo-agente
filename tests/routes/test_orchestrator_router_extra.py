"""Extra tests for src/app/routes/call_orchestrator.py."""
 
import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import AsyncMock, MagicMock, patch
 
# real dependencies we need to override
from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers
from app.repositories.db_dependencies import get_db_app
 
TEST_TOKEN = "test.token"
 
 
# --------------------------------------------------------------------------- #
#                            Shared helper fixtures                           #
# --------------------------------------------------------------------------- #
def _build_app(headers_override: dict):
    """
    Helper that returns a FastAPI app instance whose dependency overrides
    produce *exactly* the headers supplied in ``headers_override``.
    """
    from app.routes import call_orchestrator as call_orch_router
 
    app = FastAPI()
 
    # override authentication / DB dependencies
    app.dependency_overrides[get_authenticated_headers] = lambda: headers_override
    app.dependency_overrides[get_db_app] = lambda: MagicMock(spec=Session)
 
    app.include_router(call_orch_router.router)
    return app
 
 
@pytest.fixture
def default_app():
    """App whose auth headers DO include IAG-App-Id (happy path)."""
    return _build_app({"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"})
 
 
@pytest.fixture
def app_without_app_id():
    """App whose auth headers DO **NOT** include IAG-App-Id (error path)."""
    return _build_app({"Token": TEST_TOKEN})
 
 
# --------------------------------------------------------------------------- #
#                                 Test cases                                  #
# --------------------------------------------------------------------------- #
class DummyInternalError(HTTPException):
    """Lightweight replacement for InternalServerErrorException used in tests."""
 
    def __init__(self, detail: str = "internal error"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )
 
 
@patch("app.routes.call_orchestrator.InternalAppService")
@patch("app.routes.call_orchestrator.OrchestratorService")
def test_internal_service_failure_does_not_break_flow(
    mock_orchestrator_cls,
    mock_internal_cls,
    default_app,
):
    """
    If the *internal* service blows up, the router should only log a warning
    and still return the orchestrator's response (status 200).
    """
    client = TestClient(default_app)
 
    # Internal service crashes ⟶ caught by router, but request continues
    internal_inst = mock_internal_cls.return_value
    internal_inst.get_status = AsyncMock(side_effect=RuntimeError("DB down ❌"))
 
    orch_inst = mock_orchestrator_cls.return_value
    orch_inst.ejecutar_prompt = AsyncMock(return_value={"data": "all-good ✅"})
 
    resp = client.get(
        "/call_orchestrator/process",
        params={"prompt_id": "p-1", "agent_id": "a-1"},
        headers={"Token": TEST_TOKEN, "IAG-App-Id": "test-app-id"},
    )
 
    assert resp.status_code == 200
    assert resp.json() == {"data": "all-good ✅"}
 
    internal_inst.get_status.assert_awaited_once()
    orch_inst.ejecutar_prompt.assert_awaited_once()
 
