"""Web research (Tavily). Requires TAVILY_API_KEY."""
from __future__ import annotations

import os

from .. import config


def web_search(query: str, max_results: int = 5) -> list[dict]:
    if not os.getenv("TAVILY_API_KEY"):
        raise RuntimeError("TAVILY_API_KEY missing. Set it in .env for web search.")
    try:
        from tavily import TavilyClient
    except ImportError as exc:
        raise RuntimeError("tavily-python not installed. Run `pip install -r requirements.txt`.") from exc
    resp = TavilyClient(api_key=os.getenv("TAVILY_API_KEY")).search(
        query=query, max_results=max_results, search_depth="advanced"
    )
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
        for r in resp.get("results", [])
    ]