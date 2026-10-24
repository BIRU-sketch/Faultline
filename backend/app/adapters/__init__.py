from typing import Dict, Any, Optional
from .base_agent import BaseAgentAdapter, AgentObservation
from .mock_agent import MockAgentAdapter
from .http_agent import HttpAgentAdapter
from .openai_agent import OpenAIAgentAdapter
from .custom_agent import CustomAgentAdapter


def get_adapter(adapter_type: str, agent_id: str, config: Optional[Dict[str, Any]] = None) -> BaseAgentAdapter:
    """Factory function to instantiate agent adapters."""
    adapter_type_lower = adapter_type.lower()
    if adapter_type_lower == "mock":
        return MockAgentAdapter(agent_id=agent_id, config=config)
    elif adapter_type_lower == "http":
        return HttpAgentAdapter(agent_id=agent_id, config=config)
    elif adapter_type_lower == "openai":
        return OpenAIAgentAdapter(agent_id=agent_id, config=config)
    elif adapter_type_lower == "custom":
        return CustomAgentAdapter(agent_id=agent_id, config=config)
    else:
        raise ValueError(f"Unsupported adapter type: '{adapter_type}'. Supported: mock, http, openai, custom.")


__all__ = [
    "BaseAgentAdapter",
    "AgentObservation",
    "MockAgentAdapter",
    "HttpAgentAdapter",
    "OpenAIAgentAdapter",
    "CustomAgentAdapter",
    "get_adapter",
]
