"""Base agent class to eliminate boilerplate across all agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .. import llm


class Agent(ABC):
    """Base class for all ProductPilot agents."""
    
    role: str
    prompt: str
    
    def run(self, state: dict) -> dict:
        model = llm.get_llm(self.role)
        payload = self.build_payload(state)
        response = llm.ask_json(model, self.prompt, llm.to_json(payload))
        return self.parse_response(response, state)
    
    @abstractmethod
    def build_payload(self, state: dict) -> dict:
        """Build the JSON payload for the LLM call."""
        pass
    
    @abstractmethod
    def parse_response(self, response: dict, state: dict) -> dict:
        """Parse the LLM response into state updates."""
        pass


def to_json(payload: dict) -> str:
    """Convenience function for JSON serialization."""
    return llm.to_json(payload)