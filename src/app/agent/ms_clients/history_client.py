# app/agent/ms_clients/history_client.py
from __future__ import annotations
from typing import Dict, List, Optional
from qgdiag_lib_arquitectura.clients.rest_client import RestClient
from qgdiag_lib_arquitectura.utilities.logging_conf import CustomLogger
from app.settings import settings
from app.schemas.history_schema import MessageWire, MessageWireList
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

ENDPOINT = "/qgdiag-ms-historial-de-conversacion/get-user-messages-by-conversation-id"
log = CustomLogger(name="history.client", log_type="Technical")


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
        port = settings.HIST_CONV_PORT if settings.HIST_CONV_PORT not in ("443", "80") else ""
        self._client = RestClient(
            url=settings.URL_HIST_CONV,
            port=port,
            timeout=30
        )
        self._headers = dict(headers)  # defensive copy

    async def get_messages(self, conversation_id: str, limit: Optional[int] = None) -> List[MessageWire]:
        log.info(f"Fetching history for conversation_id: {conversation_id} with limit: {limit}")
        params = {"conversation_id": conversation_id}

        # The endpoint returns a *flat list* of Message
        try:
            response = await self._client.get_call(
                endpoint=ENDPOINT,
                headers=self._headers,
                params=params,
            )
            response.raise_for_status()
            json_data = response.json()
            # The endpoint returns a flat list, so we validate it directly.
            res = [MessageWire.model_validate(item) for item in json_data]
            log.info(f"Found {len(res)} messages in history for conversation_id: {conversation_id}")
            return res
        except Exception:
            log.exception(f"Failed to fetch history for conversation_id: {conversation_id}")
            raise
