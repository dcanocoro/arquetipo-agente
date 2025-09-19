from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage

from qgdiag_lib_arquitectura.schemas.response_body import ResponseBody
from qgdiag_lib_arquitectura.utilities.logging_conf import CustomLogger
from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers
from qgdiag_lib_arquitectura.exceptions.types import (
    ForbiddenException,
    InternalServerErrorException,
)
from openai import APIConnectionError

from app.settings import settings
from app.agent.graph import graph
from app.agent.context import Context
from app.agent.state import State
from app.agent.utils import get_message_text

# streaming addtions

from fastapi import Response
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
import asyncio
import json
from typing import AsyncIterator


# app/routes/agent.py (add this route)
from fastapi import Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Optional, AsyncIterator
import asyncio, json, time

from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers
from app.settings import settings
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


# --- Helper: safe string extraction from LC content ----
def _as_text(content) -> str:
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
        chunk = data.get("chunk")
        delta = ""

        # chunk can be an object (AIMessageChunk) or a dict
        # 1) Try attribute access
        if chunk is not None and hasattr(chunk, "content"):
            c = chunk.content
            # content can be str or list of content parts
            if isinstance(c, str):
                delta = c
            elif isinstance(c, list):
                # content parts may be dicts or objects with .get/.text
                parts = []
                for p in c:
                    if isinstance(p, str):
                        parts.append(p)
                    elif isinstance(p, dict):
                        parts.append(p.get("text") or "")
                    else:
                        # object with .text or .content?
                        txt = getattr(p, "text", None) or getattr(p, "content", None)
                        if isinstance(txt, str):
                            parts.append(txt)
                delta = "".join(parts)

        # 2) If chunk is a dict-like
        if not delta and isinstance(chunk, dict):
            c = chunk.get("content")
            if isinstance(c, str):
                delta = c
            elif isinstance(c, list):
                parts = []
                for p in c:
                    if isinstance(p, str):
                        parts.append(p)
                    elif isinstance(p, dict):
                        parts.append(p.get("text") or "")
                delta = "".join(parts)

        # 3) Final fallback: some providers put text directly in data["content"]
        if not delta and "content" in data:
            c = data["content"]
            if isinstance(c, str):
                delta = c

        return {
            "type": "token",
            "ts": ts,
            "run_id": run_id,
            "node": node_name,
            "data": {"delta": delta, "accumulated": False},
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
        out = data.get("output") or {}
        # Try to pull final text if available
        msgs = out.get("messages")
        if isinstance(msgs, list) and msgs:
            # last message content as text
            last = msgs[-1]
            final_text = _as_text(getattr(last, "content", None) or getattr(last, "text", None) or out.get("final_text"))
        else:
            final_text = _as_text(out.get("final_text"))

        return {
            "type": "graph_end",
            "ts": ts,
            "run_id": run_id,
            "node": node_name,
            "data": {"final_text": final_text},
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
                    line = _event_to_wire(ev)
                    if ev["event"] == "on_chat_model_stream":
                        wire_event = _event_to_wire(ev)
                        yield _json_line(wire_event)

                    yield _json_line(line).encode("utf-8")

            except Exception as e:
                # Emit error and stop
                yield _json_line({
                    "type": "error",
                    "ts": _now_iso(),
                    "data": {"message": str(e)}
                }).encode("utf-8")
                return

            # Ensure final marker
            yield _json_line({
                "type": "graph_end",
                "ts": _now_iso(),
                "data": {"final_text": None}
            }).encode("utf-8")

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