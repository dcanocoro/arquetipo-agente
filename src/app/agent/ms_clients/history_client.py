# agent/ms_history_client.py
from __future__ import annotations
from typing import Dict, List, Optional, TypedDict, Literal
import httpx
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

class HistoryMsg(TypedDict, total=False):
    message_id: str
    message_type: Literal["INPUT", "RESPONSE"]
    date_created: str  # ISO
    insight_id: str
    message_text: Optional[str]

def is_user(m: HistoryMsg) -> bool:
    return (m.get("message_type") or "").upper() == "INPUT"

def is_ai(m: HistoryMsg) -> bool:
    return (m.get("message_type") or "").upper() == "RESPONSE"

def to_langchain(m: HistoryMsg) -> BaseMessage:
    content = m.get("message_text") or ""
    meta = {
        "message_id": m.get("message_id"),
        "insight_id": m.get("insight_id"),
        "date_created": m.get("date_created"),
        "source": "history-ms",
    }
    if is_user(m):
        return HumanMessage(content=content, additional_kwargs={}, response_metadata=meta)
    if is_ai(m):
        return AIMessage(content=content, additional_kwargs={}, response_metadata=meta)
    # fallback conservador
    return HumanMessage(content=content, additional_kwargs={}, response_metadata=meta)

def from_langchain(msg: BaseMessage, conversation_id: str) -> HistoryMsg:
    # Estándar: HumanMessage -> INPUT, AIMessage -> RESPONSE
    mt = "INPUT" if isinstance(msg, HumanMessage) else "RESPONSE"
    now_iso = datetime.utcnow().isoformat()
    return {
        "message_id": msg.response_metadata.get("message_id") if hasattr(msg, "response_metadata") else "",  # opcional
        "message_type": mt,
        "date_created": msg.response_metadata.get("date_created") if hasattr(msg, "response_metadata") else now_iso,
        "insight_id": conversation_id,
        "message_text": msg.content if hasattr(msg, "content") else "",
    }

class HistoryClient:
    """
    Cliente simple para el MS de historial.
    Requiere cabeceras autenticadas corporativas. Usa GET para leer y POST/PUT para persistir.
    """
    def __init__(self, base_url: str, headers: Dict[str, str]):
        self.base_url = base_url.rstrip("/")
        self.headers = headers

    async def get_messages(self, conversation_id: str, limit: Optional[int] = None) -> List[HistoryMsg]:
        url = f"{self.base_url}/qgdiag-ms-historial-de-conversacion/conversation-history/get-user-messages-by-conversation-id"  # ajusta al path real de URL_USER_MESSAGES
        params = {"conversation_id": conversation_id}
        # si existe soporte de “limit” en el MS, incluirlo (mejor para performance)
        if limit is not None:
            params["limit"] = str(limit)
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url, params=params, headers=self.headers)
            r.raise_for_status()
            data = r.json()
            # Si la respuesta es {"messages":[...]} o lista plana; adaptamos:
            if isinstance(data, dict) and "messages" in data:
                return data["messages"]
            if isinstance(data, list):
                return data
            return []

    async def append_message(self, m: HistoryMsg) -> None:
        url = f"{self.base_url}/user-messages"  # o el endpoint de creación
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, json=m, headers=self.headers)
            r.raise_for_status()

    async def ensure_conversation(self, raw_app_id: str) -> str:
        """
        Si ya traes conversation_id del cliente, no uses esto.
        Si quieres crear una nueva vía MS, llama a su endpoint (si existe).
        Como fallback, podrías usar AIServerClient (run_pixel), pero idealmente expón un POST /conversations en el MS.
        """
        url = f"{self.base_url}/conversations"
        payload = {"raw_app_id": raw_app_id}
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, json=payload, headers=self.headers)
            r.raise_for_status()
            data = r.json()
            # Espera {"conversation_id": "..."}
            return data["conversation_id"]
