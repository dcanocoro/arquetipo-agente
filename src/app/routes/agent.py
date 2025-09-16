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