from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    status: str = Field(..., description="'passed', 'failed', 'inconclusive', or 'error'")
    summary: str = Field(..., description="Concise human-readable explanation of the finding")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Structured supporting evidence")
    score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Normalized score 0.0 to 1.0")


class BaseEvaluator(ABC):
    """Common interface for all evaluators."""

    @abstractmethod
    def evaluate(
        self,
        test_definition: Dict[str, Any],
        agent_observation: Dict[str, Any],
        expected_behavior: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """
        Evaluate observed agent behavior against expected test criteria.

        :param test_definition: Definition of the test case, policies, and parameters.
        :param agent_observation: Data captured from agent execution (output, tool calls, traces, errors).
        :param expected_behavior: Specific criteria or rules to evaluate against.
        :return: EvaluationResult with status, summary, and structured evidence.
        """
        pass
