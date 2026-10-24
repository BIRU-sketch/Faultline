import json
import os
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..providers.openai import OpenAIProvider


class StrictOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlannedTest(StrictOutputModel):
    test_id: str
    objective: str = Field(min_length=1, max_length=300)
    expected_behavior: str = Field(min_length=1, max_length=500)
    observations: List[str] = Field(min_length=1, max_length=8)


class OrchestrationPlan(StrictOutputModel):
    tests: List[PlannedTest] = Field(max_length=20)


class RunSynthesis(StrictOutputModel):
    assessment: str = Field(min_length=1, max_length=1200)
    findings: List[str] = Field(max_length=12)
    remediations: List[str] = Field(max_length=12)
    limitations: List[str] = Field(max_length=12)


class OpenAIOrchestrator:
    def __init__(self, provider: Any = None, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.provider = provider
        self.requests = 0
        self.max_requests = int(self.config.get("OPENAI_MAX_REQUESTS", os.getenv("OPENAI_MAX_REQUESTS", 8)))
        self.max_steps = int(self.config.get("OPENAI_MAX_ORCHESTRATOR_STEPS", os.getenv("OPENAI_MAX_ORCHESTRATOR_STEPS", 4)))
        self.max_retries = max(0, int(self.config.get("OPENAI_MAX_RETRIES", os.getenv("MAX_RETRIES_LIMIT", 3))))
        self.retries = 0

    def _generate(self, prompt: str, schema: Any):
        if self.provider is None:
            self.provider = OpenAIProvider(
                api_key=self.config.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", "")),
                model=self.config.get("OPENAI_ORCHESTRATOR_MODEL", os.getenv("OPENAI_ORCHESTRATOR_MODEL")),
                timeout_seconds=float(self.config.get("OPENAI_REQUEST_TIMEOUT_SECONDS", os.getenv("OPENAI_REQUEST_TIMEOUT_SECONDS", 30))),
            )
        timeout = float(self.config.get("OPENAI_REQUEST_TIMEOUT_SECONDS", os.getenv("OPENAI_REQUEST_TIMEOUT_SECONDS", 30)))
        while True:
            if self.requests >= self.max_requests:
                raise RuntimeError("OpenAI request limit exceeded for this run.")
            self.requests += 1
            try:
                try:
                    return self.provider.generate(prompt, schema, timeout_seconds=timeout)
                except TypeError:
                    return self.provider.generate(prompt, schema)
            except Exception as exc:
                status = getattr(exc, "status_code", getattr(exc, "code", None))
                if callable(status):
                    status = status()
                if self.retries >= self.max_retries or not (
                    isinstance(exc, (TimeoutError, ConnectionError)) or status in {408, 429, 500, 502, 503, 504}
                ):
                    raise
                self.retries += 1
                time.sleep(min(2 ** (self.retries - 1), 2))

    def plan(self, run_context: Dict[str, Any], available_tests: List[Dict[str, Any]], max_tests: int) -> List[Dict[str, Any]]:
        allowed = {test["id"]: test for test in available_tests}
        prompt = "Return a bounded evaluation plan. Select only test IDs listed below. Do not invent tests or claim observations.\n" + json.dumps({
            "run": run_context,
            "max_tests": min(max_tests, self.max_steps * 5),
            "available_tests": [{"id": t.get("id"), "title": t.get("title"), "category": t.get("category"), "description": t.get("description")} for t in available_tests],
        })
        plan = self._generate(prompt, OrchestrationPlan)
        if len(plan.tests) > max_tests:
            raise ValueError("OpenAI plan exceeds configured maximum tests.")
        if len(plan.tests) > self.max_steps * 5:
            raise ValueError("OpenAI plan exceeds configured orchestration step limit.")
        seen = set()
        result = []
        for item in plan.tests:
            if item.test_id not in allowed:
                raise ValueError(f"OpenAI plan selected unknown or unapproved test '{item.test_id}'.")
            if item.test_id in seen:
                raise ValueError(f"OpenAI plan repeated test '{item.test_id}'.")
            seen.add(item.test_id)
            definition = dict(allowed[item.test_id])
            definition["orchestration"] = item.model_dump()
            result.append(definition)
        return result

    def synthesize(self, report_context: Dict[str, Any]) -> Dict[str, Any]:
        result = self._generate(
            "Summarize only the observed evidence below. Clearly state uncertainty; do not invent measurements, results, or remediation outcomes.\n" + json.dumps(report_context),
            RunSynthesis,
        )
        return result.model_dump()
