# app/agent/ms_nodes/history_node.py
from __future__ import annotations
from typing import Dict, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.runtime import Runtime

from app.agent.ms_clients.history_client import HistoryClient
from app.agent.ms_clients.history_mapping import to_langchain, from_langchain
from app.agent.state import State

async def load_history(state: State, runtime: Runtime) -> Dict[str, List[BaseMessage]]:
    """
    Hydrate state with prior conversation (before this turn).
    """
    ctx = runtime.context
    if not ctx.conversation_id:
        return {"messages": []}

    client = HistoryClient(headers=ctx.headers)
    limit = getattr(ctx, "history_max_messages", None)
    raw_msgs = await client.get_messages(ctx.conversation_id, limit=limit)

    lc_msgs: List[BaseMessage] = [to_langchain(m) for m in raw_msgs]
    return {"messages": lc_msgs}

async def write_user(state: State, runtime: Runtime) -> Dict:
    """
    Persistence is disabled because no POST endpoint was provided.
    Left as a no-op to keep the graph shape unchanged.
    """
    return {}

async def write_ai(state: State, runtime: Runtime) -> Dict:
    """
    Persistence is disabled because no POST endpoint was provided.
    Left as a no-op to keep the graph shape unchanged.
    """
    return {}