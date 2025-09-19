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
    for attr in ("content", "delta", "message", "text"):
        if hasattr(chunk, attr):
            text = _as_text(getattr(chunk, attr))
            if text:
                return text
    chunk_dict = _as_dict(chunk)
    for key in ("content", "delta", "message", "text"):
        if key in chunk_dict:
            text = _as_text(chunk_dict.get(key))
            if text:
                return text
    return ""


def _chunk_tool_deltas(chunk: Any) -> List[Dict[str, Any]]:
    deltas: List[Dict[str, Any]] = []
    sources: List[Any] = []

    def _collect(source: Any) -> None:
        if not source:
            return
        sources.append(source)

    if chunk is not None:
        _collect(getattr(chunk, "tool_call_chunks", None))
        _collect(getattr(chunk, "tool_calls", None))
        delta = getattr(chunk, "delta", None)
        if delta is not None:
            _collect(getattr(delta, "tool_call_chunks", None))
            _collect(getattr(delta, "tool_calls", None))
            delta_dict = _as_dict(delta)
            if isinstance(delta_dict, dict):
                _collect(delta_dict.get("tool_call_chunks"))
                _collect(delta_dict.get("tool_calls"))

    chunk_dict = _as_dict(chunk)
    if isinstance(chunk_dict, dict):
        _collect(chunk_dict.get("tool_call_chunks"))
        _collect(chunk_dict.get("tool_calls"))

    for maybe_list in sources:
        if not maybe_list:
            continue
        if isinstance(maybe_list, (list, tuple)):
            for item in maybe_list:
                coerced = _as_dict(item)
                if coerced:
                    deltas.append(coerced)
        else:
            coerced = _as_dict(maybe_list)
            if coerced:
                deltas.append(coerced)

    return deltas


def _chunk_function_call(chunk: Any) -> Optional[Dict[str, Any]]:
    candidates: List[Any] = []

    if chunk is not None:
        if hasattr(chunk, "additional_kwargs"):
            candidates.append(getattr(chunk, "additional_kwargs"))
        if hasattr(chunk, "delta"):
            candidates.append(getattr(chunk, "delta"))

    chunk_dict = _as_dict(chunk)
    if chunk_dict:
        candidates.append(chunk_dict)

    delta_dict = _as_dict(getattr(chunk, "delta", None))
    if delta_dict:
        candidates.append(delta_dict)

    for candidate in candidates:
        if not candidate:
            continue

        if isinstance(candidate, dict):
            fc = candidate.get("function_call")
            if fc:
                return {"type": "function", "function": _as_dict(fc)}
            if "function" in candidate and "arguments" in candidate:
                return {
                    "type": "function",
                    "function": {
                        "name": candidate.get("function"),
                        "arguments": candidate.get("arguments"),
                    },
                }

        if hasattr(candidate, "function_call"):
            fc_obj = getattr(candidate, "function_call")
            if fc_obj:
                return {"type": "function", "function": _as_dict(fc_obj)}

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

        return {
            "type": "token",
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
                token_index = 0
                async for ev in graph.astream_events(
                    input_state,
                    context=ctx,
                    recursion_limit=4,
                ):
                    log.info(f"GRAPH EVENT RECEIVED: type={ev['event']}, node={ev.get('name')}")
                    wire_event = _event_to_wire(ev)
                    if not wire_event:
                        continue

                    if wire_event.get("type") == "token":
                        token_index += 1
                        data_payload = wire_event.get("data", {}) or {}
                        summary = {
                            "token_index": token_index,
                            "node": wire_event.get("node"),
                            "delta_length": len(data_payload.get("delta") or ""),
                            "has_tool_delta": bool(data_payload.get("tool_calls_delta")),
                            "has_function_delta": bool(data_payload.get("function_call_delta")),
                        }
                        if data_payload.get("response_metadata"):
                            summary["response_metadata"] = data_payload.get("response_metadata")
                        log.info(
                            f"Streaming token summary | {json.dumps(summary, ensure_ascii=False, default=str)}"
                        )

                        ev_data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
                        chunk_payload = ev_data.get("chunk") if isinstance(ev_data, dict) else None
                        chunk_dump = _as_dict(chunk_payload) if chunk_payload is not None else {}
                        if not chunk_dump and isinstance(ev_data, dict):
                            chunk_dump = _as_dict(ev_data)

                        if not data_payload.get("delta") and not data_payload.get("tool_calls_delta") and not data_payload.get("function_call_delta"):
                            log.warning(
                                f"Streaming token without delta | {json.dumps({'token_index': token_index, 'node': wire_event.get('node'), 'chunk': chunk_dump}, ensure_ascii=False, default=str)}"
                            )
                        elif data_payload.get("tool_calls_delta") or data_payload.get("function_call_delta"):
                            log.info(
                                f"Tool call delta chunk | {json.dumps({'token_index': token_index, 'node': wire_event.get('node'), 'tool_calls_delta': data_payload.get('tool_calls_delta'), 'function_call_delta': data_payload.get('function_call_delta'), 'chunk': chunk_dump}, ensure_ascii=False, default=str)}"
                            )

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
