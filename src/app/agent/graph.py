from datetime import UTC, datetime
import json
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple, cast

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
from qgdiag_lib_arquitectura.utilities.logging_conf import CustomLogger

from langchain_core.runnables import RunnableConfig
 
# --------- Nodos -------------

stream_log = CustomLogger(name="agent.react.graph", log_type="Technical")


def _to_serializable(obj: Any) -> Any:
    """Return a JSON-serialisable representation for logging/debugging."""

    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items() if v is not None}

    if isinstance(obj, (list, tuple, set)):
        return [_to_serializable(item) for item in obj]

    for attr in ("model_dump", "dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return _to_serializable(fn(exclude_none=True))
            except Exception:  # pragma: no cover - defensive
                pass

    if hasattr(obj, "__dict__"):
        return _to_serializable({k: v for k, v in vars(obj).items() if not k.startswith("_")})

    try:
        return str(obj)
    except Exception:  # pragma: no cover - defensive
        return repr(obj)


def _extract_text(content: Any) -> str:
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, dict):
        for key in ("text", "content", "message"):
            if key in content:
                text = _extract_text(content.get(key))
                if text:
                    return text
        return ""

    if isinstance(content, (list, tuple, set)):
        pieces: List[str] = []
        for item in content:
            piece = _extract_text(item)
            if piece:
                pieces.append(piece)
        return "".join(pieces)

    for attr in ("text", "content", "message"):
        if hasattr(content, attr):
            candidate = getattr(content, attr)
            text = _extract_text(candidate)
            if text:
                return text

    serialised = _to_serializable(content)
    if isinstance(serialised, dict):
        return _extract_text(serialised)
    if isinstance(serialised, list):
        return _extract_text(serialised)

    return ""


def _chunk_to_text(chunk: AIMessageChunk) -> str:
    """Best-effort extraction of textual deltas from a streamed chunk."""

    for candidate in (
        getattr(chunk, "content", None),
        getattr(chunk, "delta", None),
        getattr(chunk, "message", None),
    ):
        text = _extract_text(candidate)
        if text:
            return text

    return _extract_text(_to_serializable(chunk))


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


def _iter_tool_sources(chunk: Any) -> Iterable[Any]:
    if chunk is None:
        return []

    sources: List[Any] = [getattr(chunk, "tool_calls", None), getattr(chunk, "tool_call_chunks", None)]

    delta = getattr(chunk, "delta", None)
    if delta is not None:
        sources.extend(
            [
                getattr(delta, "tool_calls", None),
                getattr(delta, "tool_call_chunks", None),
            ]
        )

    chunk_dict = _to_serializable(chunk)
    if isinstance(chunk_dict, dict):
        sources.extend(chunk_dict.get(key) for key in ("tool_calls", "tool_call_chunks"))

    return sources


def _extract_function_payload(chunk: Any) -> Optional[Dict[str, Any]]:
    if chunk is None:
        return None

    candidates: List[Any] = []
    for attr in ("additional_kwargs", "delta"):
        value = getattr(chunk, attr, None)
        if value:
            candidates.append(value)

    serialised = _to_serializable(chunk)
    if isinstance(serialised, dict):
        candidates.append(serialised)

    for candidate in candidates:
        if candidate is None:
            continue

        if isinstance(candidate, dict):
            if "function_call" in candidate and candidate["function_call"]:
                return _coerce_tool_delta({"type": "function", "function": candidate["function_call"]})
            if "function" in candidate and "arguments" in candidate:
                return _coerce_tool_delta(
                    {
                        "type": "function",
                        "function": {
                            "name": candidate.get("function"),
                            "arguments": candidate.get("arguments"),
                        },
                    }
                )

        if hasattr(candidate, "function_call"):
            fc = getattr(candidate, "function_call")
            if fc:
                return _coerce_tool_delta({"type": "function", "function": fc})

    return None


def _finalise_tool_calls(partials: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    ordered_calls: List[Dict[str, Any]] = []
    issues: List[str] = []

    for call in partials.values():
        cleaned = dict(call)

        raw_args = cleaned.get("args")
        parsed_args: Dict[str, Any] | None = None
        string_args: str | None = None

        if isinstance(raw_args, dict):
            parsed_args = raw_args
            string_args = json.dumps(raw_args, ensure_ascii=False)
        elif isinstance(raw_args, str):
            string_args = raw_args
            try:
                parsed = json.loads(raw_args)
                if isinstance(parsed, dict):
                    parsed_args = parsed
            except Exception:
                issues.append(f"invalid_json_arguments(id={cleaned.get('id')})")
        elif raw_args is not None:
            try:
                parsed_args = dict(raw_args)
                string_args = json.dumps(parsed_args, ensure_ascii=False)
            except Exception:
                issues.append(
                    f"unsupported_args_type(id={cleaned.get('id')}, type={type(raw_args).__name__})"
                )

        function_payload = cleaned.get("function") or {}
        name = function_payload.get("name") or cleaned.get("name")
        if not name:
            issues.append(f"missing_name(id={cleaned.get('id')})")

        if string_args is None:
            if parsed_args is not None:
                string_args = json.dumps(parsed_args, ensure_ascii=False)
            else:
                string_args = "{}"

        ordered_calls.append(
            {
                "id": cleaned.get("id"),
                "type": cleaned.get("type") or "function",
                "function": {
                    "name": name,
                    "arguments": string_args,
                },
                "name": name,
                "args": parsed_args or {},
            }
        )

    return ordered_calls, issues


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

    parts: List[str] = []
    partial_tool_calls: Dict[str, Dict[str, Any]] = {}
    last_additional_kwargs: Dict[str, Any] = {}
    last_metadata: Dict[str, Any] = {}
    message_id: Optional[str] = None
    message_name: Optional[str] = None
    chunk_index = 0
    debug_snapshots: List[Dict[str, Any]] = []

    async for ch in model.astream(messages, config=config):
        if not isinstance(ch, AIMessageChunk):
            continue

        chunk_index += 1

        delta_text = _chunk_to_text(ch)
        if delta_text:
            parts.append(delta_text)

        tool_delta_found = False
        for source in _iter_tool_sources(ch):
            if not source:
                continue
            for tc in source or []:
                tool_delta_found = True
                _accumulate_tool_call(partial_tool_calls, _coerce_tool_delta(tc))

        fc_payload = _extract_function_payload(ch)
        if fc_payload:
            tool_delta_found = True
            _accumulate_tool_call(partial_tool_calls, fc_payload)

        if getattr(ch, "additional_kwargs", None):
            last_additional_kwargs = cast(Dict[str, Any], ch.additional_kwargs)

        if getattr(ch, "response_metadata", None):
            last_metadata.update(cast(Dict[str, Any], ch.response_metadata))

        if getattr(ch, "id", None):
            message_id = cast(str, ch.id)

        if getattr(ch, "name", None):
            message_name = cast(str, ch.name)

        snapshot = {
            "chunk_index": chunk_index,
            "text_delta_len": len(delta_text or ""),
            "has_tool_delta": tool_delta_found,
            "partial_tool_call_ids": list(partial_tool_calls.keys()),
            "response_metadata": _to_serializable(getattr(ch, "response_metadata", None)),
            "raw_chunk": _to_serializable(ch),
        }
        debug_snapshots.append(snapshot)

        if not delta_text and not tool_delta_found:
            payload_json = json.dumps(snapshot["raw_chunk"], ensure_ascii=False, default=str)
            stream_log.warning(
                f"Empty streaming chunk from model | chunk_index={chunk_index} | payload={payload_json}"
            )

    final_text = "".join(parts)

    tool_calls, tool_issues = _finalise_tool_calls(partial_tool_calls)

    if tool_issues:
        details = json.dumps(
            {"issues": tool_issues, "partials": _to_serializable(partial_tool_calls)},
            ensure_ascii=False,
            default=str,
        )
        stream_log.warning(
            f"Issues while reconstructing tool calls | details={details}"
        )

    ai_message = AIMessage(
        content=final_text,
        tool_calls=tool_calls,
        additional_kwargs=last_additional_kwargs,
        response_metadata=last_metadata,
        id=message_id,
        name=message_name,
    )

    if not getattr(ai_message, "tool_calls", None):
        normalized = normalize_ai_toolcalls(ai_message)
    else:
        normalized = ai_message

    summary = json.dumps(
        {
            "final_text_length": len(final_text or ""),
            "tool_calls_count": len(tool_calls),
            "message_id": message_id,
            "chunks_received": chunk_index,
        },
        ensure_ascii=False,
        default=str,
    )
    stream_log.info(f"Finished call_model streaming | summary={summary}")

    if chunk_index:
        limited_debug = debug_snapshots[: min(5, len(debug_snapshots))]
        samples_json = json.dumps(limited_debug, ensure_ascii=False, default=str)
        stream_log.info(
            f"Streaming chunk diagnostics (first {len(limited_debug)} of {chunk_index}) | samples={samples_json}"
        )

    if not final_text and not tool_calls:
        diagnostics = json.dumps(
            {
                "message_id": message_id,
                "metadata": _to_serializable(last_metadata),
                "additional_kwargs": _to_serializable(last_additional_kwargs),
                "chunks_received": chunk_index,
            },
            ensure_ascii=False,
            default=str,
        )
        stream_log.error(
            f"Model returned no text or tool calls | diagnostics={diagnostics}"
        )

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
 
