from __future__ import annotations
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from typing import Tuple

from app.agent.aicore_langchain import get_openai_compatible_chat


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
