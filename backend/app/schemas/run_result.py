from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"


class RunLimitsSchema(BaseModel):
    max_tests: int = Field(default=10, ge=1, le=20)
    max_retries: int = Field(default=1, ge=0, le=3)
    max_duration_seconds: int = Field(default=60, ge=5, le=180)


class TestSelectionSchema(BaseModel):
    security: List[str] = Field(default_factory=list)
    benchmarks: List[str] = Field(default_factory=list)


class RunCreateRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)
    test_selection: TestSelectionSchema
    limits: Optional[RunLimitsSchema] = Field(default_factory=RunLimitsSchema)

    @field_validator("test_selection")
    @classmethod
    def validate_test_selection(cls, v: TestSelectionSchema) -> TestSelectionSchema:
        if not v.security and not v.benchmarks:
            raise ValueError("At least one test (security or benchmark) must be selected.")
        return v


class RunCreateResponse(BaseModel):
    run_id: str
    status: str


class EvidenceSchema(BaseModel):
    observed_output: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    prohibited_actions_detected: Optional[List[str]] = None
    canary_leaked: Optional[bool] = None
    matched_pattern: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class TestResultResponse(BaseModel):
    id: str
    run_id: str
    test_id: str
    test_title: str
    category: str
    status: str
    summary: str
    latency_ms: float
    tool_call_count: int
    retry_count: int
    token_usage: Optional[Dict[str, Any]] = None
    evidence: Dict[str, Any]
    created_at: str


class RunResponse(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_duration_ms: Optional[float] = None
    overall_grade: Optional[float] = None
    component_scores: Optional[Dict[str, Any]] = None
    test_counts: Dict[str, int]
    error_message: Optional[str] = None


class RunListResponse(BaseModel):
    runs: List[RunResponse]
    total: int
    page: int
    limit: int
