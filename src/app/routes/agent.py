from __future__ import annotations

from datetime import datetime, timezone
import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain_core.messages import HumanMessage
from openai import APIConnectionError

from qgdiag_lib_arquitectura.schemas.response_body import ResponseBody
from qgdiag_lib_arquitectura.utilities.logging_conf import CustomLogger
from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers
from qgdiag_lib_arquitectura.exceptions.types import (
    ForbiddenException,
    InternalServerErrorException,
)

from app.settings import settings
from app.agent.graph import graph
from app.agent.context import Context
from app.agent.state import State
from app.agent.utils import get_message_text
from app.agent.aicore_langchain import get_openai_compatible_chat

router = APIRouter(prefix="/agent", tags=["agent"])
log = CustomLogger(name="agent.react.endpoint", log_type="Technical")

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str

@router.post("/react-run", response_model=ResponseBody)
async def react_run_endpoint(
    feature: str,
    model_id: str,
    version: str,
    req: ChatRequest,
    headers: Dict[str, str] = Depends(get_authenticated_headers),
) -> ResponseBody:
    """
    Execute a ReAct loop using LangGraph:
    - Builds an OpenAI-compatible Chat model against AI Server (LangChain interface)
    - Runs the graph (model <-> tools) for a single user turn
    - Returns { answer, state } in ResponseBody
    """
    log.info("Inicio de ejecución de /agent/react-run")
    try:

        # 1) Build runtime context for the graph. Assuming Context has an async factory/build method.
        ctx = Context(
            engine_id=settings.ENGINE_ID,
            headers=headers,
            base_url=settings.AICORE_URL,
            base_url_history=settings.URL_HIST_CONV,
            conversation_id=req.session_id,
        )

        # Prepare input messages for this turn
        input_state: State = {"messages": [HumanMessage(content=req.message)]}

        # Run graph with a small recursion cap (agent will stop before infinite tool loops)
        final_result = await graph.ainvoke(
            input_state,
            context=ctx,
            recursion_limit=4,
        )

        # Ensure the final state is a State object, not a dict
        final: State = final_result if isinstance(final_result, State) else State(**final_result)

        ai_text = ""
        if final.messages:
            ai_text = get_message_text(final.messages[-1]) or ""

        log.info("Fin de ejecución de /agent/react-run")
        return ResponseBody(data={"answer": ai_text, "state": {"messages": [m.dict() for m in final.messages]}})

    except APIConnectionError:
        raise  # bubble up to your global handling
    except ForbiddenException:
        raise
    except Exception as e:
        log.exception("Error inesperado al ejecutar /agent/react-run")
        raise InternalServerErrorException(str(e)) from e


# --- Helper utilities for streaming payloads ----

def _as_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return content.get("text", "") or ""
    # list of content parts
    try:
        parts = []
        for c in content:
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, dict):
                parts.append(c.get("text") or "")
        return "".join(parts)
    except Exception:
        return str(content)


def _as_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return {k: v for k, v in obj.items() if v is not None}
    if hasattr(obj, "dict"):
        try:
            return {k: v for k, v in obj.dict(exclude_none=True).items()}
        except Exception:  # pragma: no cover - defensive
            pass
    if hasattr(obj, "model_dump"):
        try:
            return {k: v for k, v in obj.model_dump(exclude_none=True).items()}
        except Exception:  # pragma: no cover - defensive
            pass
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if v is not None and not k.startswith("_")}
    return {}


def _chunk_text(chunk: Any) -> str:
    if chunk is None:
        return ""
    if hasattr(chunk, "content"):
        return _as_text(getattr(chunk, "content"))
    chunk_dict = _as_dict(chunk)
    if "content" in chunk_dict:
        return _as_text(chunk_dict.get("content"))
    return ""


def _sanitize_for_json(value: Any) -> Any:
    """Best effort conversion to JSON-serialisable primitives."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, list):
        return [_sanitize_for_json(item) for item in value]

    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            sanitized[key] = _sanitize_for_json(item)
        return sanitized

    if hasattr(value, "model_dump"):
        try:
            return _sanitize_for_json(value.model_dump())
        except Exception:  # pragma: no cover - defensive
            pass

    if hasattr(value, "dict"):
        try:
            return _sanitize_for_json(value.dict())
        except Exception:  # pragma: no cover - defensive
            pass

    if hasattr(value, "__dict__"):
        try:
            data = {k: v for k, v in vars(value).items() if not k.startswith("_")}
            return _sanitize_for_json(data)
        except Exception:  # pragma: no cover - defensive
            pass

    # Fallback to string representation for unknown objects
    return str(value)


def _store_if_meaningful(target: Dict[str, Any], key: str, value: Any) -> None:
    sanitized = _sanitize_for_json(value)
    if sanitized is None:
        return
    if isinstance(sanitized, (list, dict)) and not sanitized:
        return
    if isinstance(sanitized, str) and not sanitized.strip():
        return
    target[key] = sanitized


def _collect_tool_call_payloads(source: Any) -> List[Dict[str, Any]]:
    """Collect any `tool_calls`-like entries from a nested payload."""

    collected: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _ingest(candidate: Any) -> None:
        if not candidate:
            return

        items = candidate if isinstance(candidate, list) else [candidate]
        for item in items:
            coerced = _as_dict(item)
            if not coerced:
                continue
            sanitized = _sanitize_for_json(coerced)
            identifier = coerced.get("id") or coerced.get("tool_call_id")
            if not identifier:
                try:
                    identifier = json.dumps(sanitized, sort_keys=True, ensure_ascii=False)
                except TypeError:
                    identifier = repr(sanitized)
            if identifier in seen:
                continue
            seen.add(identifier)
            collected.append(sanitized if isinstance(sanitized, dict) else _sanitize_for_json(coerced))

    def _walk(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, (str, int, float, bool)):
            return
        if isinstance(value, list):
            for element in value:
                _walk(element)
            return
        if isinstance(value, dict):
            if "tool_calls" in value:
                _ingest(value.get("tool_calls"))
            if "tool_call_chunks" in value:
                _ingest(value.get("tool_call_chunks"))
            if "delta" in value:
                _walk(value.get("delta"))
            if "additional_kwargs" in value:
                _walk(value.get("additional_kwargs"))
            for element in value.values():
                _walk(element)
            return

        # For arbitrary objects fall back to dict conversion
        _walk(_as_dict(value))

    _walk(source)
    return collected


def _chunk_tool_deltas(chunk: Any) -> List[Dict[str, Any]]:
    deltas: List[Dict[str, Any]] = []

    def _extend(candidate: Any) -> None:
        if not candidate:
            return
        items = candidate if isinstance(candidate, list) else [candidate]
        for item in items:
            coerced = _as_dict(item)
            if coerced:
                deltas.append(coerced)

    if chunk is not None:
        _extend(getattr(chunk, "tool_call_chunks", None))
        _extend(getattr(chunk, "tool_calls", None))
        additional = getattr(chunk, "additional_kwargs", None)
        if isinstance(additional, dict):
            _extend(additional.get("tool_calls"))
            delta = additional.get("delta")
            if isinstance(delta, (dict, list)):
                _extend(delta)

    chunk_dict = _as_dict(chunk)
    _extend(chunk_dict.get("tool_call_chunks"))
    _extend(chunk_dict.get("tool_calls"))

    additional_dict = chunk_dict.get("additional_kwargs")
    if isinstance(additional_dict, dict):
        _extend(additional_dict.get("tool_calls"))
        delta = additional_dict.get("delta")
        if isinstance(delta, (dict, list)):
            _extend(delta)

    delta_field = chunk_dict.get("delta")
    if isinstance(delta_field, (dict, list)):
        _extend(delta_field)

    return deltas


def _chunk_function_call(chunk: Any) -> Optional[Dict[str, Any]]:
    candidate = None
    if chunk is not None and hasattr(chunk, "additional_kwargs"):
        candidate = getattr(chunk, "additional_kwargs")

    chunk_dict = _as_dict(chunk)

    if not isinstance(candidate, dict):
        if not isinstance(candidate, dict):
            candidate = chunk_dict.get("additional_kwargs")
        if not candidate and "function_call" in chunk_dict:
            fc = chunk_dict.get("function_call")
            if fc:
                return _as_dict(fc)

    # Look into delta payloads for OpenAI-compatible streams
    delta_field = chunk_dict.get("delta")
    if isinstance(delta_field, dict) and "function_call" in delta_field:
        fc = delta_field.get("function_call")
        if fc:
            return _as_dict(fc)

    if isinstance(candidate, dict):
        fc = candidate.get("function_call")
        if fc:
            if isinstance(fc, str):
                return {"arguments": fc}
            return _as_dict(fc)

    return None

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _json_line(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"

def _event_to_wire(ev: dict) -> dict:
    """
    Map LangGraph event to our NDJSON envelope.
    """
    ev_type = ev.get("event") or ""
    node_name = ev.get("name")
    run_id = ev.get("run_id")
    data = ev.get("data") or {}
    ts = _now_iso()


    if ev_type == "on_chat_model_stream":
        chunk = data.get("chunk") or data
        chunk_dict = _as_dict(chunk)
        delta_text = _chunk_text(chunk)
        tool_deltas = _chunk_tool_deltas(chunk)
        function_delta = _chunk_function_call(chunk)
        response_meta = None
        if chunk is not None and hasattr(chunk, "response_metadata"):
            response_meta = getattr(chunk, "response_metadata")
        if not isinstance(response_meta, dict):
            response_meta = _as_dict(data.get("response_metadata"))

        payload: Dict[str, Any] = {"delta": delta_text or "", "accumulated": False}
        if tool_deltas:
            payload["tool_calls_delta"] = tool_deltas
        if function_delta:
            payload["function_call_delta"] = function_delta
        if response_meta:
            payload["response_metadata"] = response_meta

        debug_info: Dict[str, Any] = {}
        chunk_tool_payloads = _collect_tool_call_payloads(chunk_dict)
        if chunk_tool_payloads:
            debug_info["chunk_tool_calls"] = chunk_tool_payloads

        event_tool_payloads = _collect_tool_call_payloads(data)
        if event_tool_payloads and event_tool_payloads != chunk_tool_payloads:
            debug_info["event_tool_calls"] = event_tool_payloads

        additional_kwargs = _as_dict(chunk_dict.get("additional_kwargs"))
        if additional_kwargs:
            additional_debug: Dict[str, Any] = {}
            _store_if_meaningful(additional_debug, "tool_calls", additional_kwargs.get("tool_calls"))
            _store_if_meaningful(additional_debug, "function_call", additional_kwargs.get("function_call"))
            if additional_debug:
                debug_info["additional_kwargs"] = additional_debug

        delta_field = _as_dict(chunk_dict.get("delta"))
        if delta_field:
            delta_debug: Dict[str, Any] = {}
            _store_if_meaningful(delta_debug, "tool_calls", delta_field.get("tool_calls"))
            _store_if_meaningful(delta_debug, "function_call", delta_field.get("function_call"))
            if delta_debug:
                debug_info["delta"] = delta_debug

        if debug_info:
            payload["debug"] = debug_info
            try:
                log.info(
                    "Tool-call debug snapshot captured",
                    extra={"tool_call_debug": json.dumps(debug_info, ensure_ascii=False)},
                )
            except Exception:  # pragma: no cover - logging is best-effort
                log.info("Tool-call debug snapshot captured: %s", debug_info)

        return {
            "type": "token",
            "ts": ts,
            "run_id": run_id,
            "node": node_name,
            "data": payload,
        }

    if ev_type == "on_chat_model_end":
        data_dict = _as_dict(data)
        tool_payloads = _collect_tool_call_payloads(data_dict)
        payload: Dict[str, Any] = {
            "raw_output": _sanitize_for_json(data_dict),
            "tool_calls": tool_payloads or None,
        }

        if not payload["tool_calls"]:
            payload.pop("tool_calls")

        return {
            "type": "chat_model_end",
            "ts": ts,
            "run_id": run_id,
            "node": node_name,
            "data": payload,
        }

    # Tool lifecycle
    if ev_type == "on_tool_start":
        return {
            "type": "tool_start",
            "ts": ts,
            "run_id": run_id,
            "node": node_name,
            "data": {
                "tool_name": data.get("name") or node_name or "unknown_tool",
                "input": data.get("input"),
            },
        }

    if ev_type == "on_tool_end":
        return {
            "type": "tool_end",
            "ts": ts,
            "run_id": run_id,
            "node": node_name,
            "data": {
                "tool_name": data.get("name") or node_name or "unknown_tool",
                "output": data.get("output"),
            },
        }

    # Node lifecycle
    if ev_type == "on_node_start":
        return {
            "type": "node_start",
            "ts": ts,
            "run_id": run_id,
            "node": node_name,
            "data": {"node_name": node_name},
        }

    if ev_type == "on_node_end":
        return {
            "type": "node_end",
            "ts": ts,
            "run_id": run_id,
            "node": node_name,
            "data": {"node_name": node_name},
        }

    # Graph end
    if ev_type == "on_graph_end":
        final_text = None
        final_tool_calls: List[Dict[str, Any]] = []
        out = data.get("output") or {}

        msgs = out.get("messages")
        if isinstance(msgs, list) and msgs:
            last = msgs[-1]
            last_dict = _as_dict(last)
            final_text = _as_text(last_dict.get("content")) or _as_text(last_dict.get("text")) or _as_text(out.get("final_text"))
            tool_call_items = last_dict.get("tool_calls") or []
            if isinstance(tool_call_items, list):
                for item in tool_call_items:
                    coerced = _as_dict(item)
                    if coerced:
                        final_tool_calls.append(coerced)
        else:
            final_text = _as_text(out.get("final_text"))

        return {
            "type": "graph_end",
            "ts": ts,
            "run_id": run_id,
            "node": node_name,
            "data": {"final_text": final_text, "tool_calls": final_tool_calls or None},
        }

    # Fallback: info
    return {
        "type": "info",
        "ts": ts,
        "run_id": run_id,
        "node": node_name,
        "data": {"raw_event": ev_type},
    }

class ChatStreamRequest(BaseModel):
    session_id: Optional[str] = None
    message: str

@router.post("/react-stream")
async def react_stream_endpoint(
    feature: str,
    model_id: str,
    version: str,
    req: ChatStreamRequest,
    headers: Dict[str, str] = Depends(get_authenticated_headers),
) -> StreamingResponse:
    """
    Stream LangGraph events as NDJSON lines (no SSE).
    """
    log.info("Inicio de streaming /agent/react-stream")
    try:
        ctx = Context(
            engine_id=settings.ENGINE_ID,
            headers=headers,
            base_url=settings.AICORE_URL,
            base_url_history=settings.URL_HIST_CONV,
            conversation_id=req.session_id,
        )
        input_state: State = {"messages": [HumanMessage(content=req.message)]}

        async def event_generator() -> AsyncIterator[bytes]:
            # Optional: initial info line to unblock buffering proxies
            yield _json_line({
                "type": "info",
                "ts": _now_iso(),
                "data": {"status": "stream_started"}
            }).encode("utf-8")

            try:
                async for ev in graph.astream_events(
                    input_state,
                    context=ctx,
                    recursion_limit=4,
                ):
                    log.info(f"GRAPH EVENT RECEIVED: type={ev['event']}, node={ev.get('name')}")
                    wire_event = _event_to_wire(ev)
                    if not wire_event:
                        continue
                    yield _json_line(wire_event).encode("utf-8")

            except Exception as e:
                # Emit error and stop
                yield _json_line({
                    "type": "error",
                    "ts": _now_iso(),
                    "data": {"message": str(e)}
                }).encode("utf-8")
                return

        # Headers that play nice with gateways
        headers_out = {
            "Content-Type": "application/x-ndjson; charset=utf-8",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Transfer-Encoding": "chunked",
            # Some gateways buffer without this:
            "X-Accel-Buffering": "no",
        }
        return StreamingResponse(event_generator(), headers=headers_out)
    except ForbiddenException:
        raise
    except Exception as e:
        log.exception("Error inesperado en /agent/react-stream")
        raise InternalServerErrorException(str(e)) from e



def _jsonl(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")

class StreamProbeRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None

@router.post("/agent/debug-openai-stream-direct")
async def debug_openai_stream_direct(
    feature: str,
    model_id: str,
    version: str,
    req: StreamProbeRequest,
    headers: Dict[str, str] = Depends(get_authenticated_headers),
) -> StreamingResponse:

    async def gen() -> AsyncIterator[bytes]:
        start_ts = time.time()
        yield _jsonl({"type": "info", "ts": start_ts, "data": {"status": "probe_started"}})

        try:
            chat = await get_openai_compatible_chat(
                headers=headers,
                base_url=settings.AICORE_URL,
                engine_id=settings.ENGINE_ID,  # or model_id
            )

            # Force a multi-chunk answer
            messages = [{"role": "user", "content": req.prompt}]

            got_any_chunk = False
            assembled: list[str] = []

            # Native LangChain async stream (no callbacks involved)
            async for chunk in chat.astream(messages):
                # chunk is typically an AIMessageChunk
                delta = getattr(chunk, "content", None)
                if delta:
                    got_any_chunk = True
                    assembled.append(delta)
                    yield _jsonl({
                        "type": "token",
                        "ts": time.time(),
                        "data": {"delta": delta}
                    })

            final_text = "".join(assembled) if assembled else None
            yield _jsonl({
                "type": "model_end",
                "ts": time.time(),
                "data": {"final_text": final_text, "got_any_chunk": got_any_chunk}
            })

        except Exception as e:
            yield _jsonl({"type": "error", "ts": time.time(), "data": {"message": str(e)}})

    headers_out = {
        "Content-Type": "application/x-ndjson; charset=utf-8",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "X-Accel-Buffering": "no",
        "Transfer-Encoding": "chunked",
    }
    return StreamingResponse(gen(), headers=headers_out)
