"""Analyst — theme clustering, RAG recall, sourced RICE, contradiction detection,
compliance dependencies. Produces the research synthesis for PM approval.
"""
from __future__ import annotations

from .base import Agent
from .. import prompts
from ..memory.stores import vector_store


class AnalystAgent(Agent):
    role = "analyst"
    prompt = prompts.ANALYST
    
    def build_payload(self, state: dict) -> dict:
        memory_hits = []
        try:
            query = state.get("pm_input", "")
            if query:
                hits = vector_store().search(query, k=5)
                memory_hits = [
                    {
                        "title": h["title"], "doc_type": h["doc_type"], "source": h["source"],
                        "score": h["score"], "snippet": h["text"][:400],
                    }
                    for h in hits
                ]
        except Exception:
            memory_hits = []
        
        return {
            "pm_input": state.get("pm_input", ""),
            "org_name": state.get("org_name", ""),
            "request_type": state.get("request_type", "standard"),
            "research_notes": state.get("research_notes", []),
            "web_results": state.get("web_results", []),
            "memory_hits": memory_hits,
            "pm_feedback": state.get("pm_synthesis_feedback", ""),
            "revision": state.get("synthesis_revisions", 0),
        }
    
    def parse_response(self, response: dict, state: dict) -> dict:
        return {
            "themes": response.get("themes", []),
            "options": response.get("options", []),
            "contradictions": response.get("contradictions", []),
            "memory_hits": self.build_payload(state)["memory_hits"],
            "compliance_dependencies": response.get("compliance_dependencies", []),
            "synthesis": response.get("synthesis_markdown", ""),
            "status": "analysis_done",
        }


analyst = AnalystAgent()
run = analyst.run
