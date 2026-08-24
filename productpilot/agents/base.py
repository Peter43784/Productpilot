"""Base agent class to eliminate boilerplate across all agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain_core.tools import BaseTool

from .. import llm


class Agent(ABC):
    """Base class for all ProductPilot agents."""
    
    role: str
    prompt: str
    output_json: bool = True
    tools: list[BaseTool] = []  # Override for tool-calling agents
    
    def run(self, state: dict) -> dict:
        model = llm.get_llm(self.role)
        
        if self.tools:
            # Tool-calling agent (ReAct style)
            from langgraph.prebuilt import create_react_agent
            agent = create_react_agent(model, self.tools, prompt=self.prompt)
            # Initial state for the agent
            agent_input = {"messages": [{"role": "user", "content": llm.to_json(self.build_payload(state))}]}
            result = agent.invoke(agent_input)
            # Last AI message contains the final response
            response = result["messages"][-1].content
        else:
            # Simple prompt-only agent
            payload = self.build_payload(state)
            if self.output_json:
                response = llm.ask_json(model, self.prompt, llm.to_json(payload))
            else:
                response = llm.ask(model, self.prompt, llm.to_json(payload))
        
        return self.parse_response(response, state)
    
    @abstractmethod
    def build_payload(self, state: dict) -> dict:
        """Build the JSON payload for the LLM call."""
        pass
    
    @abstractmethod
    def parse_response(self, response: Any, state: dict) -> dict:
        """Parse the LLM response into state updates."""
        pass


def to_json(payload: dict) -> str:
    """Convenience function for JSON serialization."""
    return llm.to_json(payload)