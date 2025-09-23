from datetime import UTC, datetime
from typing import Dict, List, Literal, cast
 
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
 
from typing import Dict, List
from langchain_core.runnables import RunnableConfig
from datetime import UTC, datetime
 
from datetime import UTC, datetime
from typing import Dict, List, Literal
from langchain_core.messages import AIMessage, AIMessageChunk
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime
 
from app.agent.context import Context
from app.agent.state import InputState, State
from app.agent.tools import TOOLS
from app.agent.aicore_langchain import get_openai_compatible_chat
from app.agent.ms_nodes.history_node import load_history, write_user, write_ai
from app.agent.utils import parse_forced_tool_or_answer, build_forced_tool_prompt
 
from langchain_core.runnables import RunnableConfig
 
# --------- Nodo: llamada al modelo -------------
 
async def call_model(state: State, config: RunnableConfig, runtime: Runtime[Context]) -> Dict[str, List[AIMessage]]:
    """
    Llama al chat vía AI Core en streaming, fuerza protocolo de tool-calling por texto,
    y al terminar convierte en AIMessage con tool_calls (si procede).
    """
    chat = await get_openai_compatible_chat(
        headers=runtime.context.headers,
        base_url=runtime.context.base_url,
        engine_id=runtime.context.engine_id,
    )
 
    # IMPORTANTE: NO usamos .bind_tools() aquí, para evitar que AI Core rompa tool_calls JSON.
    # Forzamos el protocolo vía system prompt.
    forced_prompt = build_forced_tool_prompt(TOOLS)
    print(f"###FORCED PROMPT###: {forced_prompt}")
    # system_message = forced_prompt.format(system_time=datetime.now(tz=UTC).isoformat())
    messages = [{"role": "system", "content": forced_prompt}, *state.messages]
 
    # Consumimos streaming, acumulando el texto.
    parts: List[str] = []
 
    async for ch in chat.astream(messages, config=config):
        if isinstance(ch, AIMessageChunk):
            c = getattr(ch, "content", None)
            if isinstance(c, str) and c:
                parts.append(c)
                # logging voluntario
                print(f"[Δ] {c!r}")
 
    final_text = "".join(parts).strip()
    print(f"###PARTS###: {parts}")
    print(f"###FINAL TEXT###: {final_text}")
 
    # Parseamos el protocolo forzado -> AIMessage con tool_calls o respuesta final.
    ai_msg = parse_forced_tool_or_answer(final_text)
    print(f"###AI MSG###: {ai_msg}")
 
    return {"messages": [ai_msg]}
 
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
