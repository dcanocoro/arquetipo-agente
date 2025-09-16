# app/agent/ms_clients/history_client.py  (replace previous httpx client)
from __future__ import annotations
from typing import Dict, List, Optional
from qgdiag_lib_arquitectura.clients.rest import RestClient  # your corporate client
from app.settings import settings
from app.schemas.history_schema import MessageWire, MessageWireList
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage


def to_langchain(m: MessageWire) -> BaseMessage:
    content = m.message_text or ""
    meta = {
        "message_id": m.message_id,
        "insight_id": m.insight_id,
        "date_created": m.date_created.isoformat() if isinstance(m.date_created, datetime) else str(m.date_created),
        "source": "history-ms",
    }
    if (m.message_type or "").upper() == "INPUT":
        return HumanMessage(content=content, response_metadata=meta)
    return AIMessage(content=content, response_metadata=meta)

def from_langchain(msg: BaseMessage, conversation_id: str) -> MessageWire:
    # Kept for future POST support
    mt = "INPUT" if isinstance(msg, HumanMessage) else "RESPONSE"
    now = datetime.now(timezone.utc)
    return MessageWire(
        message_id=(getattr(msg, "response_metadata", {}) or {}).get("message_id", ""),
        message_type=mt,
        date_created=(getattr(msg, "response_metadata", {}) or {}).get("date_created", now),
        insight_id=conversation_id,
        message_text=getattr(msg, "content", ""),
    )


class HistoryClient:
    """
    History MS client using corporate RestClient.
    Only GET is implemented because you provided only the read endpoint.
    """

    def __init__(self, headers: Dict[str, str]):
        # RestClient will add IAG-App-Id from env if missing.
        self._client = RestClient(
            url=settings.URL_HIST_CONV,
            port=settings.HIST_CONV_PORT,
            timeout=30
        )
        self._headers = dict(headers)  # defensive copy

    async def get_messages(self, conversation_id: str, limit: Optional[int] = None) -> List[MessageWire]:
        params = {"conversation_id": conversation_id}
        # The backend signature doesn’t include limit in the router, so only add if your service supports it
        if limit is not None:
            params["limit"] = str(limit)

        # The endpoint returns a *flat list* of Message
        res = await self._client.get_call(
            endpoint=settings.HISTORY_PATH_USER_MESSAGES,
            headers=self._headers,
            params=params,
            response_model=MessageWireList
        )
        return res.__root__

    # --- Future write APIs (left as placeholders) ----------------------------
    # async def append_message(self, m: MessageWire) -> None:
    #     raise NotImplementedError("POST /user-messages not provided yet by the MS")
