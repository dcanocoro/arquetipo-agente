from __future__ import annotations
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from typing import Tuple

from .aicore_langchain import get_openai_compatible_chat  # NEW helper


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
