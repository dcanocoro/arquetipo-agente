from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Any, Dict, Optional

from qgdiag_lib_arquitectura.schemas.response_body import ResponseBody
from qgdiag_lib_arquitectura.utilities.logging_conf import CustomLogger
from qgdiag_lib_arquitectura.security.authentication import get_authenticated_headers
from qgdiag_lib_arquitectura.exceptions.types import (
    ForbiddenException,
    InternalServerErrorException,
)
from openai import APIConnectionError

from app.settings import settings
from agent.graph import graph
from agent.context import Context
from agent.state import State
from langchain_core.messages import HumanMessage

router = APIRouter(prefix="/agent", tags=["agent"])
log = CustomLogger(name="agent.react.endpoint", log_type="Technical")


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


@router.post("/react-run", response_model=ResponseBody)
async def react_run_endpoint(
    feature: str,
    model_id: str,   # ENGINE_ID from AI Server
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
        # Build runtime context for the graph (tiny change: we pass headers/base_url)
        ctx = Context(
            # keep your prompt, or override per-feature if needed
            # system_prompt=prompts.SYSTEM_PROMPT,
            model=f"openai-compatible/{model_id}",
            headers=headers,
            base_url=settings.AI_CORE_BASE_URL,
        )

        # Prepare input messages for this turn
        input_state = {"messages": [HumanMessage(content=req.message)]}

        # Run graph with a small recursion cap (agent will stop before infinite tool loops)
        final: State = await graph.ainvoke(
            input_state,
            context=ctx,
            recursion_limit=4,
        )

        # Extract the last AI text safely
        from agent.utils import get_message_text
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
