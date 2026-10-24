import os
from typing import Any, Optional, Type

from pydantic import BaseModel


class OpenAIConfigurationError(RuntimeError):
    pass


class OpenAIProvider:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 client: Any = None, timeout_seconds: float = 30.0):
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        if not self.api_key and client is None:
            raise OpenAIConfigurationError("OPENAI_API_KEY is required for OpenAI-powered runs.")
        self.model = model or os.getenv("OPENAI_ORCHESTRATOR_MODEL", "gpt-4o-mini")
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise OpenAIConfigurationError("Install openai to use OpenAI-powered runs.") from exc
            client = OpenAI(api_key=self.api_key, timeout=timeout_seconds)
        self.client = client

    def generate(self, prompt: str, schema: Type[BaseModel], timeout_seconds: float = 30.0) -> BaseModel:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            text={"format": {
                "type": "json_schema",
                "name": schema.__name__.lower(),
                "strict": True,
                "schema": schema.model_json_schema(),
            }},
            timeout=timeout_seconds,
        )
        output = getattr(response, "output_text", None)
        if not output:
            raise ValueError("OpenAI returned no structured output.")
        return schema.model_validate_json(output)
