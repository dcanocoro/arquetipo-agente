# agent/history_nodes.py
from __future__ import annotations
from typing import Dict, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from app.agent.ms_clients.history_client import HistoryClient, to_langchain, from_langchain
from app.agent.state import State
from langgraph.runtime import Runtime

async def load_history(state: State, runtime: Runtime) -> Dict[str, List[BaseMessage]]:
    """
    Hidrata el estado con el historial almacenado (previo a este turno).
    No duplica el mensaje humano que ya viene en state.messages (el actual).
    """
    ctx = runtime.context
    if not ctx.conversation_id:
        # Sin conversation_id no podemos hidratar; sigue flujo
        return {"messages": []}

    client = HistoryClient(base_url=ctx.base_url_history, headers=ctx.headers)
    limit = getattr(ctx, "history_max_messages", None)
    raw_msgs = await client.get_messages(ctx.conversation_id, limit=limit)

    # Mapear MS -> LangChain y ordenar por fecha si el MS no garantiza orden
    lc_msgs: List[BaseMessage] = [to_langchain(m) for m in raw_msgs]

    # Protege de duplicados: el input del turno ya trae un HumanMessage final
    # Dejamos historial previo, y el HumanMessage actual queda al final (ya en state)
    return {"messages": lc_msgs}

async def write_user(state: State, runtime: Runtime) -> Dict:
    """
    Persiste el mensaje humano del turno actual en el MS (INPUT).
    Debe ejecutarse después de hidratar y antes del call_model.
    """
    ctx = runtime.context
    if not ctx.conversation_id:
        return {}
    # Último mensaje del estado tras carga + input es el del usuario en este turno
    if not state.messages:
        return {}
    last = state.messages[-1]
    if not isinstance(last, HumanMessage):
        return {}
    client = HistoryClient(base_url=ctx.base_url_history, headers=ctx.headers)
    payload = from_langchain(last, ctx.conversation_id)
    await client.append_message(payload)
    return {}

async def write_ai(state: State, runtime: Runtime) -> Dict:
    """
    Persiste la respuesta del asistente (RESPONSE) cuando ya no hay tool_calls.
    """
    ctx = runtime.context
    if not ctx.conversation_id:
        return {}
    if not state.messages:
        return {}
    last = state.messages[-1]
    if not isinstance(last, AIMessage):
        return {}
    client = HistoryClient(base_url=ctx.base_url_history, headers=ctx.headers)
    payload = from_langchain(last, ctx.conversation_id)
    await client.append_message(payload)
    return {}
