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
 
# --------- Nodos -------------
 
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
    tool_calls: List[dict] = []
    
    async for ch in model.astream(messages, config=config):
    # === SIMPLE, VERBOSE-BUT-USEFUL LOGGING ===
    # 1) Text delta
        if isinstance(ch, AIMessageChunk):
            c = getattr(ch, "content", None)
            if isinstance(c, str) and c:
                print(f"[STREAM Δtext] {repr(c)}")
    
        # 2) Newer LC normalized tool-calls (can be partial/incremental)
        for tc in (getattr(ch, "tool_calls", None) or []):
            print(f"[STREAM Δtool] id={tc.get('id')} name={tc.get('name')} args_delta={tc.get('args')}")
    
        # 3) Legacy OpenAI function_call (single tool; also incremental)
        fc = (getattr(ch, "additional_kwargs", {}) or {}).get("function_call")
        if fc:
            print(f"[STREAM Δfunction_call] name={fc.get('name')} args_delta={fc.get('arguments')}")
 
    final_text = "".join(parts).strip()
    return {"messages": [AIMessage(content=final_text, tool_calls=tool_calls)]}
    #return {"messages": [AIMessage(content=final_text, tool_calls=tool_calls or None)]}
 
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
 
