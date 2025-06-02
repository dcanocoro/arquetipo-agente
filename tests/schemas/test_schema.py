from app.schemas.services.orchestrator import OrchestratorRequest
import pytest
from pydantic import ValidationError


class TestOrchestratorRequestSchema:
    """Cobertura básica del modelo Pydantic"""

    def test_valid_request(self):
        req = OrchestratorRequest(prompt_id="p", agent_id="a", app_id="b")
        assert req.prompt_id == "p"
        assert req.agent_id == "a"
        assert req.app_id == "b"

    def test_missing_field(self):
        with pytest.raises(ValidationError):
            OrchestratorRequest(prompt_id="only-prompt", agent_id="missing-app")