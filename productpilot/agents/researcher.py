"""Researcher — ingests raw sources, gathers web context, flags prompt injection.

Uses function-calling to invoke ingestion and web search tools.
The model decides when to call tools and how to synthesize results.
"""
from __future__ import annotations

from .base import Agent
from .. import prompts
from ..tools.agent_tools import RESEARCHER_TOOLS


class ResearcherAgent(Agent):
    role = "researcher"
    prompt = prompts.RESEARCHER
    tools = RESEARCHER_TOOLS
    
    def build_payload(self, state: dict) -> dict:
        return {
            "source_paths": state.get("source_paths", []),
            "pm_input": state.get("pm_input", ""),
            "org_name": state.get("org_name", ""),
            "request_type": state.get("request_type", "standard"),
        }
    
    def parse_response(self, response: str, state: dict) -> dict:
        import json, re
        text = response if isinstance(response, str) else str(response)
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)
        else:
            start, end = text.find('{'), text.rfind('}')
            if start != -1 and end > start:
                text = text[start:end+1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        return {
            "research_notes": data.get("research_notes", []),
            "web_results": data.get("web_results", ""),
            "injection_flags": data.get("injection_flags", []),
            "status": "research_done",
        }


researcher = ResearcherAgent()
run = researcher.run