"""Request schema para el orchestrator_service."""

from typing import Any, Dict
from pydantic import BaseModel


class OrchestratorRequest(BaseModel):
    """Request schema para el orchestrator_service."""
    prompt_id: str
    agent_id: str
    app_id: str
    # params: Dict[str, Any]
