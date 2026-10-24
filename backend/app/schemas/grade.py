from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from .run_result import TestResultResponse


class GradeComponentScore(BaseModel):
    name: str
    score: Optional[float] = Field(None, ge=0.0, le=10.0, description="Component score from 0.0 to 10.0")
    weight: float
    explanation: str
    tests_count: int
    passed_count: int
    failed_count: int
    effective_weight: Optional[float] = None
    contribution: Optional[float] = None
    excluded_count: int = 0


class GradeReportSchema(BaseModel):
    overall_grade: Optional[float] = Field(None, ge=0.0, le=10.0, description="Overall grade on 0-10 scale")
    grade_scale: str = "0-10"
    rubric_version: str = "v1.0"
    is_complete: bool
    summary: str
    calculation: str = ""
    methodology: List[str] = Field(default_factory=list)
    components: Dict[str, GradeComponentScore]
    limitations: List[str] = Field(default_factory=list)


class ReportResponse(BaseModel):
    run_id: str
    agent_id: str
    agent_name: str
    adapter_type: str
    status: str
    timestamps: Dict[str, Optional[str]]
    total_duration_ms: Optional[float] = None
    summary_counts: Dict[str, int]
    grading: GradeReportSchema
    security_results: List[TestResultResponse]
    benchmark_results: List[TestResultResponse]
    recommendations: List[str]
    limitations: List[str]
    progress: Optional[Dict[str, Any]] = None
