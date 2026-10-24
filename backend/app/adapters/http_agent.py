import time
import ipaddress
import urllib.parse
from typing import Dict, Any, Optional, List
import requests
from .base_agent import BaseAgentAdapter, AgentObservation


class HttpAgentAdapter(BaseAgentAdapter):
    """
    HTTP adapter for sending tasks to external REST-based agent endpoints.
    Includes SSRF protection to block private, loopback, or metadata addresses
    unless explicitly allowed by configuration.
    """

    def __init__(self, agent_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_id, config)
        self.endpoint_url = self.config.get("endpoint_url")
        self.headers = self.config.get("headers", {})
        self.allow_local = bool(self.config.get("allow_local", False))

    def _validate_url(self, url: str) -> None:
        """Validate URL to protect against SSRF."""
        if not url:
            raise ValueError("Endpoint URL is required for HTTP agent adapter.")

        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

        hostname = parsed.hostname or ""
        if not hostname:
            raise ValueError("Invalid URL: missing hostname.")

        # Check for IP address restrictions if not allowing local/private
        if not self.allow_local:
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    raise ValueError(f"Outbound request to private/internal IP {hostname} is blocked for security.")
            except ValueError as e:
                # Hostname is a domain name, not a raw IP
                if hostname.lower() in ("localhost", "127.0.0.1", "::1", "metadata.google.internal"):
                    raise ValueError(f"Outbound request to internal hostname '{hostname}' is blocked.")

    def execute_task(
        self,
        task_prompt: str,
        system_prompt: Optional[str] = None,
        mock_tools: Optional[List[Dict[str, Any]]] = None,
        timeout_seconds: float = 30.0,
    ) -> AgentObservation:
        start_time = time.perf_counter()

        try:
            self._validate_url(self.endpoint_url)

            payload = {
                "prompt": task_prompt,
                "system_prompt": system_prompt,
                "tools": ["bash"],
            }

            response = requests.post(
                self.endpoint_url,
                json=payload,
                headers=self.headers,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # Normalize output
            output = data.get("output") or data.get("response") or data.get("message")
            tool_calls = data.get("tool_calls", [])
            token_usage = data.get("token_usage") or data.get("usage")

            return AgentObservation(
                output=str(output) if output is not None else None,
                tool_calls=tool_calls,
                tool_call_count=len(tool_calls),
                retry_count=int(data.get("retry_count", 0)),
                latency_ms=round(elapsed_ms, 2),
                token_usage=token_usage,
                error=None,
                raw_response=data,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return AgentObservation(
                output=None,
                tool_calls=[],
                tool_call_count=0,
                retry_count=0,
                latency_ms=round(elapsed_ms, 2),
                error=f"HTTP Agent request failed: {str(e)}",
            )
