from datetime import UTC, datetime
import json
from typing import Any, Dict, List, Literal, cast

from langchain_core.messages import AIMessage, AIMessageChunk
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime

from app.agent.context import Context
from app.agent.state import InputState, State
from app.agent.tools import TOOLS
from app.agent.aicore_langchain import get_openai_compatible_chat
from app.agent.ms_nodes.history_node import load_history, write_user, write_ai
from app.agent.utils import normalize_ai_toolcalls

from langchain_core.runnables import RunnableConfig
 
# --------- Nodos -------------
 
def _chunk_to_text(chunk: AIMessageChunk) -> str:
    """Best-effort extraction of textual deltas from a streamed chunk."""

    content = getattr(chunk, "content", None)
    if not content:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, dict):
        text = content.get("text")
        return text or ""

    # Lists of content parts (LangChain V1 structured output)
    if isinstance(content, list):
        pieces: List[str] = []
        for part in content:
            if isinstance(part, str):
                pieces.append(part)
            elif isinstance(part, dict):
                txt = part.get("text") or ""
                if isinstance(txt, str):
                    pieces.append(txt)
            else:
                txt = getattr(part, "text", None) or getattr(part, "content", None)
                if isinstance(txt, str):
                    pieces.append(txt)
        return "".join(pieces)

    return ""


def _coerce_tool_delta(delta: Any) -> Dict[str, Any]:
    """Convert any tool-call fragment into a plain dict for accumulation."""

    if delta is None:
        return {}
    if isinstance(delta, dict):
        return {k: v for k, v in delta.items() if v is not None}
    if hasattr(delta, "dict"):
        try:
            return {k: v for k, v in delta.dict(exclude_none=True).items() if v is not None}
        except Exception:  # pragma: no cover - defensive
            pass
    if hasattr(delta, "model_dump"):
        try:
            return {k: v for k, v in delta.model_dump(exclude_none=True).items() if v is not None}
        except Exception:  # pragma: no cover - defensive
            pass
    if hasattr(delta, "__dict__"):
        return {k: v for k, v in vars(delta).items() if v is not None}
    return {}


def _merge_arguments(existing: Dict[str, Any], new_value: Any) -> Any:
    """Merge streaming argument payloads (dicts or partial JSON strings)."""

    if new_value is None:
        return existing

    if isinstance(new_value, dict):
        current = existing if isinstance(existing, dict) else {}
        current.update(new_value)
        return current

    if isinstance(new_value, str):
        prior = existing if isinstance(existing, str) else ""
        combined = prior + new_value
        try:
            return json.loads(combined)
        except Exception:
            # keep accumulating raw string; caller can retry on next delta
            return combined

    return new_value


def _accumulate_tool_call(partials: Dict[str, Dict[str, Any]], delta: Dict[str, Any]) -> None:
    """Update the partial tool-call cache with a new streamed fragment."""

    if not delta:
        return

    call_id = delta.get("id") or delta.get("tool_call_id")

    # OpenAI-style {"type": "function", "function": {...}}
    function_payload = delta.get("function")
    if isinstance(function_payload, dict):
        if not call_id:
            call_id = function_payload.get("id")
        name = function_payload.get("name")
        args = function_payload.get("arguments")
    else:
        name = delta.get("name")
        args = delta.get("args")

    if not call_id:
        # use deterministic key to keep ordering stable
        call_id = f"call_{len(partials)}"

    current = partials.setdefault(call_id, {"id": call_id})

    call_type = delta.get("type")
    if call_type:
        current["type"] = call_type

    if name:
        current["name"] = name

    current_args = current.get("args")
    merged_args = _merge_arguments(current_args, args)
    if merged_args is not None:
        current["args"] = merged_args

    # Preserve original OpenAI shape for compatibility if present
    if isinstance(function_payload, dict):
        current["function"] = {
            k: v
            for k, v in function_payload.items()
            if v is not None
        }


async def call_model(state: State, config: RunnableConfig, runtime: Runtime[Context]) -> Dict[str, List[AIMessage]]:
    chat = await get_openai_compatible_chat(
        headers=runtime.context.headers,
        base_url=runtime.context.base_url,
        engine_id=runtime.context.engine_id,
    )
    model = chat.bind_tools(TOOLS)
 
    system_message = runtime.context.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )
    messages = [{"role": "system", "content": system_message}, *state.messages]
 
    # ← this is the key: pass `config` (NOT runtime)
    parts: List[str] = []
    partial_tool_calls: Dict[str, Dict[str, Any]] = {}
    last_additional_kwargs: Dict[str, Any] = {}
    last_metadata: Dict[str, Any] = {}
    message_id: str | None = None
    message_name: str | None = None

    async for ch in model.astream(messages, config=config):
        if not isinstance(ch, AIMessageChunk):
            continue

        delta_text = _chunk_to_text(ch)
        if delta_text:
            parts.append(delta_text)

        for tc in getattr(ch, "tool_calls", []) or []:
            _accumulate_tool_call(partial_tool_calls, _coerce_tool_delta(tc))

        for tc in getattr(ch, "tool_call_chunks", []) or []:
            _accumulate_tool_call(partial_tool_calls, _coerce_tool_delta(tc))

        fc = (getattr(ch, "additional_kwargs", {}) or {}).get("function_call")
        if fc:
            # function_call is always a dict with {name, arguments}
            payload = {"type": "function", "function": fc}
            _accumulate_tool_call(partial_tool_calls, payload)

        if getattr(ch, "additional_kwargs", None):
            last_additional_kwargs = cast(Dict[str, Any], ch.additional_kwargs)

        if getattr(ch, "response_metadata", None):
            last_metadata.update(cast(Dict[str, Any], ch.response_metadata))

        if getattr(ch, "id", None):
            message_id = cast(str, ch.id)

        if getattr(ch, "name", None):
            message_name = cast(str, ch.name)

    final_text = "".join(parts)

    tool_calls: List[Dict[str, Any]] = []
    for call in partial_tool_calls.values():
        cleaned = dict(call)
        raw_args = cleaned.get("args")
        if isinstance(raw_args, str):
            try:
                cleaned["args"] = json.loads(raw_args)
            except Exception:
                # leave as string if it isn't valid JSON yet
                pass
        tool_calls.append(cleaned)

    ai_message = AIMessage(
        content=final_text,
        tool_calls=tool_calls,
        additional_kwargs=last_additional_kwargs,
        response_metadata=last_metadata,
        id=message_id,
        name=message_name,
    )

    normalized = normalize_ai_toolcalls(ai_message)
    return {"messages": [normalized]}
 
# ------------------ Aristas ----------------------
 
def route_model_output(state: State) -> Literal["__end__", "tools"]:
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(f"Expected AIMessage, got {type(last_message).__name__}")
    return "__end__" if not last_message.tool_calls else "tools"
 
# ------------------- Grafo ------------------------
builder = StateGraph(State, input_schema=InputState, context_schema=Context)
 
# Nodos
builder.add_node("load_history", load_history)
builder.add_node("write_user", write_user)
builder.add_node("call_model", call_model)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_node("write_ai", write_ai)
 
# aristas
builder.add_edge("__start__", "load_history")
builder.add_edge("load_history", "write_user")
builder.add_edge("write_user", "call_model")
builder.add_conditional_edges("call_model", route_model_output)
builder.add_edge("tools", "call_model")
builder.add_edge("write_ai", "__end__")
 
graph = builder.compile(name="ReAct Agent with History")
 
