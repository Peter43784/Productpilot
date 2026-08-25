"""PRD Writer — builds the structured, spec-quality PRD from the approved synthesis."""
from __future__ import annotations

from .base import Agent
from .. import prompts


class WriterAgent(Agent):
    role = "writer"
    prompt = prompts.WRITER
    output_json = False  # Writer outputs markdown, not JSON
    
    def build_payload(self, state: dict) -> dict:
        return {
            "pm_input": state.get("pm_input", ""),
            "org_name": state.get("org_name", ""),
            "request_type": state.get("request_type", "standard"),
            "synthesis": state.get("synthesis", ""),
            "themes": state.get("themes", []),
            "options": state.get("options", []),
            "contradictions": state.get("contradictions", []),
            "compliance_dependencies": state.get("compliance_dependencies", []),
            "memory_hits": state.get("memory_hits", []),
            "critic_feedback": state.get("critic_feedback", []),
            "pm_prd_feedback": state.get("pm_prd_feedback", ""),
            "revision": state.get("revisions", 0),
        }
    
    def parse_response(self, response: str, state: dict) -> dict:
        return {"prd_draft": response, "status": "drafted"}


writer = WriterAgent()
run = writer.run
