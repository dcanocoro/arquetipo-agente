from datetime import UTC, datetime
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime

from agent.context import Context
from agent.state import InputState, State
from agent.tools import TOOLS
from agent.utils import load_chat_model

async def call_model(state: State, runtime: Runtime[Context]) -> Dict[str, List[AIMessage]]:
    model = load_chat_model(
        runtime.context.model,
        headers=runtime.context.headers,
        base_url=runtime.context.base_url,
    ).bind_tools(TOOLS)

    system_message = runtime.context.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    response = cast(
        AIMessage,
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
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

builder = StateGraph(State, input_schema=InputState, context_schema=Context)
builder.add_node(call_model)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_edge("__start__", "call_model")

def route_model_output(state: State) -> Literal["__end__", "tools"]:
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(f"Expected AIMessage, got {type(last_message).__name__}")
    return "__end__" if not last_message.tool_calls else "tools"

builder.add_conditional_edges("call_model", route_model_output)
builder.add_edge("tools", "call_model")

graph = builder.compile(name="ReAct Agent")
