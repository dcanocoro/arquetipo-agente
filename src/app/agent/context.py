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

    # Keep your original shape, but we will pass "openai-compatible/<ENGINE_ID>"
    # model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
    #     default="anthropic/claude-3-5-sonnet-20240620",
    #     metadata={"description": "Provider/model string."},
    # )

    max_search_results: int = field(
        default=10,
        metadata={"description": "Max Tavily results."},
    )

    # NEW: authenticated headers for credential retrieval and cookie session reuse
    headers: Dict[str, str] = field(default_factory=dict)

    # NEW: AI Core base URL (no trailing slash)
    base_url: Optional[str] = field(default=None)

    def __post_init__(self) -> None:
        for f in fields(self):
            if not f.init:
                continue
            if getattr(self, f.name) == f.default:
                setattr(self, f.name, os.environ.get(f.name.upper(), f.default))
