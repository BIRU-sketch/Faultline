from typing import Dict, Any, Optional, List, Callable
from .base_agent import BaseAgentAdapter, AgentObservation


class CustomAgentAdapter(BaseAgentAdapter):
    """
    Adapter allowing in-process custom agent execution functions.
    Useful for testing agents directly in Python test benches.
    """

    def __init__(self, agent_id: str, handler: Optional[Callable] = None, config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_id, config)
        self.handler = handler

    def execute_task(
        self,
        task_prompt: str,
        system_prompt: Optional[str] = None,
        mock_tools: Optional[List[Dict[str, Any]]] = None,
        timeout_seconds: float = 30.0,
    ) -> AgentObservation:
        if not self.handler:
            return AgentObservation(
                output=None,
                error="Custom agent handler function was not provided.",
                latency_ms=0.0,
            )
        try:
            return self.handler(task_prompt, system_prompt, mock_tools)
        except Exception as e:
            return AgentObservation(
                output=None,
                error=f"Custom agent handler raised exception: {str(e)}",
                latency_ms=0.0,
            )
