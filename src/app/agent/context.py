from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from typing import Annotated, Dict, Optional
from app.settings import settings


SYSTEM_PROMPT = """You are a helpful AI assistant"""

@dataclass(kw_only=True)
class Context:
    """The context for the agent."""

    system_prompt: str = field(
        default=SYSTEM_PROMPT,
        metadata={"description": "System prompt for the agent."},
    )
    engine_id: str = ""
    max_search_results: int = field(
        default=10,
        metadata={"description": "Max Tavily results."},
    )
    headers: Dict[str, str] = field(default_factory=dict)
    base_url: Optional[str] = field(default=None)
    base_url_history: Optional[str] = field(default=None)
    
    history_max_messages: int = field(default=40)
    conversation_id: Optional[str] = field(default=None)
    raw_app_id: Optional[str] = field(default=None)  # para validaciones del MS de historial

    def __post_init__(self) -> None:
        for f in fields(self):
            if not f.init:
                continue
            if getattr(self, f.name) == f.default:
                setattr(self, f.name, os.environ.get(f.name.upper(), f.default))
