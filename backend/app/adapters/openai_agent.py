import os
import time
from typing import Dict, Any, Optional, List
from .base_agent import BaseAgentAdapter, AgentObservation


class OpenAIAgentAdapter(BaseAgentAdapter):
    """
    Adapter for connecting to OpenAI-compatible chat completion endpoints.
    API keys are loaded securely from environment variables (e.g., OPENAI_API_KEY).
    """

    def __init__(self, agent_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_id, config)
        self.model = self.config.get("model", "gpt-4o-mini")
        self.base_url = self.config.get("base_url")

    def execute_task(
        self,
        task_prompt: str,
        system_prompt: Optional[str] = None,
        mock_tools: Optional[List[Dict[str, Any]]] = None,
        timeout_seconds: float = 30.0,
    ) -> AgentObservation:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return AgentObservation(
                output=None,
                error="OPENAI_API_KEY environment variable is not configured.",
                latency_ms=0.0,
            )

        start_time = time.perf_counter()

        try:
            import openai
            client = openai.OpenAI(api_key=api_key, base_url=self.base_url, timeout=timeout_seconds)

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": task_prompt})

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            message = response.choices[0].message
            output = message.content or ""

            # Extract any tool calls from OpenAI response
            tool_calls = []
            if getattr(message, "tool_calls", None):
                for tc in message.tool_calls:
                    tool_calls.append({
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                        "id": tc.id,
                    })

            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return AgentObservation(
                output=output,
                tool_calls=tool_calls,
                tool_call_count=len(tool_calls),
                retry_count=0,
                latency_ms=round(elapsed_ms, 2),
                token_usage=usage,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return AgentObservation(
                output=None,
                error=f"OpenAI agent error: {str(e)}",
                latency_ms=round(elapsed_ms, 2),
            )
