from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class AdapterType(str, Enum):
    MOCK = "mock"
    HTTP = "http"
    OPENAI = "openai"


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name of the agent")
    adapter_type: AdapterType = Field(..., description="Adapter type (mock, http, openai)")
    config: Dict[str, Any] = Field(default_factory=dict, description="Non-secret agent configuration")
    description: Optional[str] = Field(None, max_length=500)

    @field_validator("config")
    @classmethod
    def sanitize_config(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        forbidden_keys = {"api_key", "secret", "password", "token", "private_key"}
        for k in v.keys():
            if any(forbidden in k.lower() for forbidden in forbidden_keys):
                raise ValueError(
                    f"Direct storage of secrets ({k}) is not allowed in agent config. "
                    "Provide credentials via environment variables."
                )
        return v


class AgentResponse(BaseModel):
    id: str
    name: str
    adapter_type: str
    config: Dict[str, Any]
    description: Optional[str] = None
    enabled: bool
    created_at: str
    updated_at: str


class AgentListResponse(BaseModel):
    agents: List[AgentResponse]
    total: int
