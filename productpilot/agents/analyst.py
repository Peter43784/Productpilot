"""Analyst — theme clustering, RAG recall, sourced RICE, contradiction detection,
compliance dependencies. Produces the research synthesis for PM approval.

Uses function-calling to search memory and calculate RICE scores.
"""
from __future__ import annotations

from .base import Agent
from .. import prompts
from ..tools.agent_tools import ANALYST_TOOLS


class AnalystAgent(Agent):
    role = "analyst"
    prompt = prompts.ANALYST
    tools = ANALYST_TOOLS
    
    def build_payload(self, state: dict) -> dict:
        return {
            "pm_input": state.get("pm_input", ""),
            "org_name": state.get("org_name", ""),
            "request_type": state.get("request_type", "standard"),
            "research_notes": state.get("research_notes", []),
            "web_results": state.get("web_results", ""),
            "pm_feedback": state.get("pm_synthesis_feedback", ""),
            "revision": state.get("synthesis_revisions", 0),
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
            "themes": data.get("themes", []),
            "options": data.get("options", []),
            "contradictions": data.get("contradictions", []),
            "memory_hits": data.get("memory_hits", []),
            "compliance_dependencies": data.get("compliance_dependencies", []),
            "synthesis": data.get("synthesis_markdown", ""),
            "status": "analysis_done",
        }


analyst = AnalystAgent()
run = analyst.run
