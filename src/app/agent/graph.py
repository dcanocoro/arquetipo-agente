from datetime import UTC, datetime
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime

from app.agent.context import Context
from app.agent.state import InputState, State
from app.agent.tools import TOOLS
from app.agent.aicore_langchain import get_openai_compatible_chat
from app.agent.ms_nodes.history_nodes import load_history, write_user, write_ai

# --------- Nodos -------------

async def call_model(state: State, runtime: Runtime[Context]) -> Dict[str, List[AIMessage]]:
    chat = await get_openai_compatible_chat(
        headers=runtime.context.headers,
        base_url=runtime.context.base_url,
        engine_id=runtime.context.engine_id
    )

    model = chat.bind_tools(TOOLS)

    system_message = runtime.context.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    response = cast(
        AIMessage,
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    response: AIMessage = await model.ainvoke(
        [{"role": "system", "content": system_message}, *state.messages]
    )

    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }
    return {"messages": [response]}


# ------------------ Vértices ----------------------

def route_model_output(state: State) -> Literal["__end__", "tools"]:
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(f"Expected AIMessage, got {type(last_message).__name__}")
    return "__end__" if not last_message.tool_calls else "tools"

# ------------------- Grafo ------------------------
builder = StateGraph(State, input_schema=InputState, context_schema=Context)

# NODOS
builder.add_node("load_history", load_history)  # hidrata antes del turno
builder.add_node("write_user", write_user)      # persiste INPUT del turno
builder.add_node("call_model", call_model)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_node("write_ai", write_ai)          # persiste RESPONSE final

# ARISTAS
builder.add_edge("__start__", "load_history")
builder.add_edge("load_history", "write_user")
builder.add_edge("write_user", "call_model")
builder.add_conditional_edges("call_model", route_model_output)
builder.add_edge("tools", "call_model")  # sigue bucle herramienta->modelo
builder.add_edge("write_ai", "__end__")

graph = builder.compile(name="ReAct Agent with History")