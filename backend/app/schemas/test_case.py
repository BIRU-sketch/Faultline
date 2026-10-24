from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TestCategory(str, Enum):
    SECURITY = "security"
    BENCHMARK = "benchmark"


class EvaluationMethod(str, Enum):
    REGEX = "regex"
    SCORING_RULES = "scoring_rules"
    LLM_JUDGE = "llm_judge"


class TestCaseSchema(BaseModel):
    id: str
    title: str
    category: str
    subcategory: Optional[str] = None
    description: str
    evaluation_method: str
    difficulty: Optional[str] = "medium"
    tags: List[str] = Field(default_factory=list)
    policy_requirements: Optional[str] = None
    expected_behavior: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TestCatalogResponse(BaseModel):
    tests: List[TestCaseSchema]
    total: int
    categories: Dict[str, int]
