from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class AgentObservation(BaseModel):
    output: Optional[str] = Field(None, description="Primary textual response from the agent")
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Recorded tool calls and arguments")
    tool_call_count: int = Field(0, description="Total number of tool calls observed")
    retry_count: int = Field(0, description="Total number of retries triggered")
    latency_ms: float = Field(0.0, description="Monotonic execution time in milliseconds")
    token_usage: Optional[Dict[str, Any]] = Field(None, description="Observed prompt, completion, total tokens")
    error: Optional[str] = Field(None, description="Execution error message if failed")
    raw_response: Optional[Dict[str, Any]] = Field(None, description="Raw normalized response object")


class BaseAgentAdapter(ABC):
    """Abstract Base Class for connecting to AI agents."""

    def __init__(self, agent_id: str, config: Optional[Dict[str, Any]] = None):
        self.agent_id = agent_id
        self.config = config or {}

    @abstractmethod
    def execute_task(
        self,
        task_prompt: str,
        system_prompt: Optional[str] = None,
        mock_tools: Optional[List[Dict[str, Any]]] = None,
        timeout_seconds: float = 30.0,
    ) -> AgentObservation:
        """
        Send a task and context to the target agent and return normalized observations.
        """
        pass
