# app/agent/ms_clients/history_models.py  (new file)
from __future__ import annotations
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field

class MessageWire(BaseModel):
    message_id: str = Field(..., min_length=1)
    message_type: str = Field(..., min_length=1)  # "INPUT" | "RESPONSE"
    date_created: datetime
    insight_id: str = Field(..., min_length=1)
    message_text: str | None = None

class MessageWireList(BaseModel):
    # The endpoint returns a *flat list* (response_model=List[Message])
    __root__: List[MessageWire]
