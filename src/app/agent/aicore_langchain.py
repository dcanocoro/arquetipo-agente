from __future__ import annotations
import httpx
from typing import Dict
from langchain_openai import ChatOpenAI
from qgdiag_lib_arquitectura.utilities.ai_core import ai_core
from qgdiag_lib_arquitectura.utilities.ai_core.ai_core import retrieve_credentials

def get_openai_compatible_chat(*, headers: Dict[str, str], base_url: str, engine_id: str) -> ChatOpenAI:
    """
    Build a ChatOpenAI instance against AI Server's OpenAI-compatible endpoint.
    - Retrieves credentials via your standard flow (headers → keys)
    - Logs into AI Server to get cookies and reuses them on the http_client
    - Returns a ChatOpenAI bound to <base_url>/model/openai with model=<engine_id>
    """
    # 1) Get keys from your microservice
    access_key, secret_key = ai_core.retrieve_credentials(headers) if hasattr(ai_core, "retrieve_credentials") else None
    if access_key is None:
        # fallback to explicit import if needed (some versions expose retrieve_credentials elsewhere)
        access_key, secret_key = retrieve_credentials(headers)

    # 2) Login to AI Server to get cookie session
    server = ai_core.AIServerClient(access_key=access_key, secret_key=secret_key, base=base_url)

    http_client = httpx.Client()
    http_client.cookies = server.cookies

    openai_api_key = f"{access_key}:{secret_key}"
    openai_endpoint = f"{base_url}/model/openai"

    # 3) Return LangChain chat model using OpenAI-compatible endpoint
    return ChatOpenAI(
        openai_api_key=openai_api_key,
        model=engine_id,         # ENGINE_ID, not a public model name
        base_url=openai_endpoint,
        http_client=http_client,
    )
