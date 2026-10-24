import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Boolean,
    Float,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
    Text,
    Index,
)
from sqlalchemy.orm import relationship
from .session import Base


def utcnow():
    return datetime.now(timezone.utc)


class AgentModel(Base):
    __tablename__ = "agents"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), nullable=False, index=True)
    adapter_type = Column(String(32), nullable=False)
    config = Column(JSON, nullable=False, default=dict)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    runs = relationship("RunModel", back_populates="agent", cascade="all, delete-orphan")


class RunModel(Base):
    __tablename__ = "runs"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(64), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    test_selection = Column(JSON, nullable=False)
    limits = Column(JSON, nullable=False)
    status = Column(String(32), default="queued", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    total_duration_ms = Column(Float, nullable=True)
    overall_grade = Column(Float, nullable=True)
    component_scores = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    orchestration_metadata = Column(JSON, nullable=True)
    final_report = Column(JSON, nullable=True)

    agent = relationship("AgentModel", back_populates="runs")
    results = relationship(
        "TestResultModel",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="TestResultModel.created_at",
    )


class TestResultModel(Base):
    __test__ = False
    __tablename__ = "test_results"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(64), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    test_id = Column(String(64), nullable=False, index=True)
    test_title = Column(String(256), nullable=False)
    category = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False)  # passed, failed, inconclusive, error
    summary = Column(Text, nullable=False)
    latency_ms = Column(Float, nullable=False, default=0.0)
    tool_call_count = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    token_usage = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    run = relationship("RunModel", back_populates="results")


Index("idx_run_status_created", RunModel.status, RunModel.created_at)
Index("idx_results_run_category", TestResultModel.run_id, TestResultModel.category)
