"""Web research (Tavily). Mock mode returns deterministic canned results so the
'competitive response' and 'saturated market' evals run offline.
"""
from __future__ import annotations

import json
import os

from .. import config

_MOCK_RESULTS: list[dict] = [
    {"title": "competitor ACME launches similar onboarding assistant (2026)", "url": "https://example.com/acme", "snippet": "ACME ships an onboarding copilot covering trial activation, pricing per seat."},
    {"title": "competitor BETA adds onboarding playbooks", "url": "https://example.com/beta", "snippet": "BETA's newest release automates onboarding emails and in-app checklists."},
    {"title": "competitor GAMMA claims AI setup wizard", "url": "https://example.com/gamma", "snippet": "GAMMA announced an AI setup wizard for new accounts."},
    {"title": "market report: activation tools 2026 landscape", "url": "https://example.com/report", "snippet": "The activation tooling market is crowded; differentiation is now about depth of analysis."},
]


def web_search(query: str, max_results: int = 5) -> list[dict]:
    if config.MOCK or not os.getenv("TAVILY_API_KEY"):
        return [dict(r) for r in _MOCK_RESULTS[:max_results]]
    try:
        from tavily import TavilyClient
    except ImportError:
        return [dict(r) for r in _MOCK_RESULTS[:max_results]]
    try:
        resp = TavilyClient(api_key=os.getenv("TAVILY_API_KEY")).search(
            query=query, max_results=max_results, search_depth="advanced"
        )
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
            for r in resp.get("results", [])
        ]
    except Exception:
        return [dict(r) for r in _MOCK_RESULTS[:max_results]]
