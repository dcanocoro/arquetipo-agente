from typing import Any, Callable, List, Optional, cast
from langchain_tavily import TavilySearch
from langgraph.runtime import get_runtime
from app.agent.context import Context

# async def search(query: str) -> Optional[dict[str, Any]]:
#     """Search for general web results"""

#     runtime = get_runtime(Context)
#     wrapped = TavilySearch(max_results=runtime.context.max_search_results)
#     return cast(dict[str, Any], await wrapped.ainvoke({"query": query}))

async def get_horoscope(sign: str) -> str:
    """Return a playful horoscope string for the given sign."""
    return f"{sign}: Next Tuesday you will befriend a baby otter."

TOOLS: List[Callable[..., Any]] = [get_horoscope]
