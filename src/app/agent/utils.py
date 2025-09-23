from __future__ import annotations
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from typing import Tuple
import json
import re
from typing import Any, Dict, List, Tuple, Optional
from langchain_core.messages import AIMessage

from app.agent.aicore_langchain import get_openai_compatible_chat

_TOOLCALL_ARRAY_RE = re.compile(r"\[{\s*\"id\".*?}\]", re.DOTALL)


def get_message_text(msg: BaseMessage) -> str:
    content = msg.content
    if isinstance(content, str):
        return content
    elif isinstance(content, dict):
        return content.get("text", "")
    else:
        txts = [c if isinstance(c, str) else (c.get("text") or "") for c in content]
        return "".join(txts).strip()


def load_chat_model(fully_specified_name: str, *, headers=None, base_url=None) -> BaseChatModel:
    """
    Load a chat model from a fully specified name.
    Supports your special provider 'openai-compatible/<ENGINE_ID>' routed through AI Server.
    Otherwise, it falls back to LangChain's init_chat_model(provider/model).
    """
    provider, model = fully_specified_name.split("/", maxsplit=1)
    if provider == "openai-compatible":
        if headers is None or base_url is None:
            raise ValueError("openai-compatible requires headers and base_url")
        return get_openai_compatible_chat(headers=headers, base_url=base_url, engine_id=model)
    return init_chat_model(model, model_provider=provider)


def _try_extract_json_array(s: str) -> Optional[str]:
    """
    Finds the first top-level JSON array substring that looks like a tool-call list.
    Handles cases where the whole content is the stringified JSON, or content embeds it.
    """
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        return s
    m = _TOOLCALL_ARRAY_RE.search(s)
    return m.group(0) if m else None

def normalize_ai_toolcalls(ai: AIMessage) -> AIMessage:
    """
    If ai.content is a stringified array of OpenAI-style function calls, convert it
    into LangChain's tool_calls structure on the message.
    """
    if not isinstance(ai.content, str):
        return ai

    raw = _try_extract_json_array(ai.content)
    if not raw:
        return ai

    try:
        payload = json.loads(raw)
        calls = []
        for item in payload:
            # Expected shape (from your example):
            # { "id": "call_...", "type": "function", "name": "get_horoscope", "arguments": "{\"sign\":\"Virgo\"}" }
            name = item.get("name")
            if not name:
                continue
            args_raw = item.get("arguments", "{}")
            args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
            calls.append({
                "id": item.get("id"),
                "name": name,
                "args": args,
                # LangChain uses simple dicts; we don't need to carry vendor-specific fields
            })
        if not calls:
            return ai

        # Build a new AIMessage that ToolNode will recognize
        return AIMessage(
            content="",            # no human-readable content; it's a pure tool call
            tool_calls=calls,      # <-- key bit ToolNode reads
            additional_kwargs=ai.additional_kwargs,
            response_metadata=ai.response_metadata,
            id=ai.id,
            name=ai.name
        )
    except Exception:
        # If parsing fails, just return the original message
        return ai


from __future__ import annotations
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from typing import Tuple
import json
import re
from typing import Any, Dict, List, Tuple, Optional
from langchain_core.messages import AIMessage

from app.agent.aicore_langchain import get_openai_compatible_chat

import re, json
from uuid import uuid4
from typing import Any, Dict, List, Optional, Tuple
from langgraph.runtime import get_runtime
from app.agent.context import Context
from langchain_core.messages import AIMessage

_TOOLCALL_ARRAY_RE = re.compile(r"\[{\s*\"id\".*?}\]", re.DOTALL)

def get_message_text(msg: BaseMessage) -> str:
    content = msg.content
    if isinstance(content, str):
        return content
    elif isinstance(content, dict):
        return content.get("text", "")
    else:
        txts = [c if isinstance(c, str) else (c.get("text") or "") for c in content]
        return "".join(txts).strip()

def load_chat_model(fully_specified_name: str, *, headers=None, base_url=None) -> BaseChatModel:
    """
    Load a chat model from a fully specified name.
    Supports your special provider 'openai-compatible/<ENGINE_ID>' routed through AI Server.
    Otherwise, it falls back to LangChain's init_chat_model(provider/model).
    """
    provider, model = fully_specified_name.split("/", maxsplit=1)
    if provider == "openai-compatible":
        if headers is None or base_url is None:
            raise ValueError("openai-compatible requires headers and base_url")
        return get_openai_compatible_chat(headers=headers, base_url=base_url, engine_id=model)
    return init_chat_model(model, model_provider=provider)

def _try_extract_json_array(s: str) -> Optional[str]:
    """
    Finds the first top-level JSON array substring that looks like a tool-call list.
    Handles cases where the whole content is the stringified JSON, or content embeds it.
    """
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        return s
    m = _TOOLCALL_ARRAY_RE.search(s)
    return m.group(0) if m else None

def normalize_ai_toolcalls(ai: AIMessage) -> AIMessage:
    """
    If ai.content is a stringified array of OpenAI-style function calls, convert it
    into LangChain's tool_calls structure on the message.
    """
    if not isinstance(ai.content, str):
        return ai

    raw = _try_extract_json_array(ai.content)
    if not raw:
        return ai

    try:
        payload = json.loads(raw)
        calls = []
        for item in payload:
            # Expected shape (from your example):
            # { "id": "call_...", "type": "function", "name": "get_horoscope", "arguments": "{\"sign\":\"Virgo\"}" }
            name = item.get("name")
            if not name:
                continue
            args_raw = item.get("arguments", "{}")
            args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
            calls.append({
                "id": item.get("id"),
                "name": name,
                "args": args,
                # LangChain uses simple dicts; we don't need to carry vendor-specific fields
            })
        if not calls:
            return ai

        # Build a new AIMessage that ToolNode will recognize
        return AIMessage(
            content="",            # no human-readable content; it's a pure tool call
            tool_calls=calls,      # <-- key bit ToolNode reads
            additional_kwargs=ai.additional_kwargs,
            response_metadata=ai.response_metadata,
            id=ai.id,
            name=ai.name
        )
    except Exception:
        # If parsing fails, just return the original message
        return ai

# === Forzado de tool-calling por texto (ReAct minimalista) ===

 
_ACTION_RE = re.compile(
    r"Action:\s*(?P<tool>[A-Za-z0-9_\.\-\:]+)\s*[\r\n]+Action Input:\s*(?P<input>.*)",
    re.DOTALL | re.IGNORECASE,
)
_FINAL_RE = re.compile(r"Final Answer:\s*(?P<answer>.+)", re.DOTALL | re.IGNORECASE)
 
def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # quita primera línea ```
        s = s.split("\n", 1)[1] if "\n" in s else s.strip("`")
    if s.endswith("```"):
        s = s.rsplit("\n", 1)[0]
    return s.strip()
 
def _best_effort_json(obj_text: str) -> Dict[str, Any]:
    """
    Intenta parsear un JSON 'action input'. Si falla, lo mete como {"input": "..."}.
    Recorta a la última '}' para cortar ruido posterior si viene pegado a texto.
    """
    t = _strip_code_fences(obj_text).strip()
    if t.startswith("{"):
        last = t.rfind("}")
        if last != -1:
            t = t[: last + 1]
    try:
        return json.loads(t)
    except Exception:
        return {"input": t}
 
def build_forced_tool_prompt(tools: List[Any]) -> str:
    """
    Construye un prompt de sistema que obliga al modelo a hablar SOLO en este protocolo:
      - Tool:      'Action:' + 'Action Input:' (JSON válido)
      - Respuesta: 'Final Answer:'
    """
    tool_names = []
    tool_descs = []
    for fn in tools:
        name = getattr(fn, "__name__", None) or getattr(fn, "name", None) or "tool"
        desc = (fn.__doc__ or "").strip() or "No description."
        tool_names.append(name)
        tool_descs.append(f"- {name}: {desc}")
 
    name_list = ", ".join(tool_names)
    desc_block = "\n".join(tool_descs)
 
    return f"""
            You are a precise tool-using assistant.
 
            You have access to these tools:
            {desc_block}
            
            RULES (obey strictly):
            - If you need a tool, answer with EXACTLY this format (no extra prose, no markdown):
            Action: <one of: {name_list}>
            Action Input: <a VALID JSON object with the arguments>
            
            - If you can answer directly, respond with EXACTLY:
            Final Answer: <your answer>
            
            - NEVER output anything before or after those lines. No explanations, no code fences, no commentary.
            - Use valid JSON for Action Input. Example: {{"param":"value"}}
            - Current ISO time: {{system_time}}
            """
 
def parse_forced_tool_or_answer(full_text: str) -> AIMessage:
    """
    Devuelve un AIMessage:
      - Si detecta 'Final Answer:', content=respuesta y sin tool_calls
      - Si detecta 'Action:' + 'Action Input:', content="" y tool_calls=[...]
      - Si no detecta nada, devuelve el texto como content (fallback)
    """
    txt = full_text.strip()
 
    # 1) Final Answer
    m_final = _FINAL_RE.search(txt)
    if m_final:
        answer = m_final.group("answer").strip()
        return AIMessage(content=answer)
 
    # 2) Action + Input
    m = _ACTION_RE.search(txt)
    if m:
        tool = m.group("tool").strip()
        args_raw = m.group("input").strip()
        args = _best_effort_json(args_raw)
        return AIMessage(
            content="",
            tool_calls=[{
                "id": f"call_{uuid4().hex[:8]}",
                "name": tool,
                "args": args
            }]
        )
 
    # 3) Fallback
    return AIMessage(content=txt)