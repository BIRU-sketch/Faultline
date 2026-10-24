import pytest
import uuid

from app.core.orchestrator import OpenAIOrchestrator, OrchestrationPlan, RunSynthesis
from app.providers.openai import OpenAIConfigurationError, OpenAIProvider
from app.core.runner import TestRunner
from app.db.models import RunModel, TestResultModel
from app.db.session import SessionScoped


class FakeProvider:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, prompt, schema, timeout_seconds=30):
        self.prompts.append(prompt)
        return schema.model_validate(self.response)


def test_plan_only_dispatches_selected_test_ids():
    provider = FakeProvider({"tests": [{"test_id": "sec-a", "objective": "check policy", "expected_behavior": "ignore injection", "observations": ["output"]}]})
    orchestrator = OpenAIOrchestrator(provider=provider, config={"OPENAI_MAX_REQUESTS": 2})
    selected = [{"id": "sec-a", "category": "security", "task_prompt": "controlled input"}]

    plan = orchestrator.plan({"agent_id": "demo"}, selected, max_tests=1)

    assert [test["id"] for test in plan] == ["sec-a"]
    assert plan[0]["orchestration"]["observations"] == ["output"]


def test_openai_structured_output_schemas_forbid_extra_properties():
    schemas = [OrchestrationPlan.model_json_schema(), RunSynthesis.model_json_schema()]
    for schema in schemas:
        assert schema["additionalProperties"] is False
        for definition in schema.get("$defs", {}).values():
            if definition.get("type") == "object":
                assert definition["additionalProperties"] is False


def test_plan_rejects_unknown_test_ids():
    provider = FakeProvider({"tests": [{"test_id": "not-selected", "objective": "x", "expected_behavior": "y", "observations": ["z"]}]})
    orchestrator = OpenAIOrchestrator(provider=provider)

    with pytest.raises(ValueError, match="unknown or unapproved"):
        orchestrator.plan({}, [{"id": "sec-a"}], max_tests=1)


def test_plan_enforces_test_count():
    provider = FakeProvider({"tests": [
        {"test_id": f"sec-{index}", "objective": "x", "expected_behavior": "y", "observations": ["z"]}
        for index in range(2)
    ]})
    orchestrator = OpenAIOrchestrator(provider=provider)

    with pytest.raises(ValueError, match="maximum tests"):
        orchestrator.plan({}, [{"id": "sec-0"}, {"id": "sec-1"}], max_tests=1)


def test_orchestrator_retries_transient_provider_errors_within_budget():
    class TransientError(Exception):
        status_code = 503

    class FlakyProvider:
        attempts = 0

        def generate(self, prompt, schema, timeout_seconds=30):
            self.attempts += 1
            if self.attempts == 1:
                raise TransientError("temporary provider error")
            return schema.model_validate({"tests": [{"test_id": "sec-a", "objective": "check policy", "expected_behavior": "safe", "observations": ["output"]}]})

    orchestrator = OpenAIOrchestrator(
        provider=FlakyProvider(), config={"OPENAI_MAX_REQUESTS": 2, "OPENAI_MAX_RETRIES": 1},
    )
    result = orchestrator.plan({}, [{"id": "sec-a"}], max_tests=1)

    assert len(result) == 1
    assert orchestrator.requests == 2
    assert orchestrator.retries == 1


def test_live_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(OpenAIConfigurationError, match="OPENAI_API_KEY"):
        OpenAIProvider(api_key="")


def test_runner_executes_evidence_based_follow_up_and_persists_synthesis(app, monkeypatch):
    class FakeOrchestrator:
        max_steps = 2
        requests = 0
        retries = 0

        def __init__(self, config):
            self.calls = []

        def plan(self, context, available, max_tests):
            self.calls.append(context.get("stage", "initial"))
            self.requests += 1
            return available[:1]

        def synthesize(self, report_context):
            self.requests += 1
            return {"assessment": f"Observed {len(report_context['observed_results'])} tests.", "findings": [], "remediations": [], "limitations": []}

    fake = FakeOrchestrator({})
    monkeypatch.setattr("app.core.runner.OpenAIOrchestrator", lambda config: fake)
    app.config["OPENAI_API_KEY"] = "fake-key"
    run_id = str(uuid.uuid4())
    session = SessionScoped()
    session.add(RunModel(
        id=run_id, agent_id="vulnerable-demo",
        test_selection={"security": ["sec-indirect-injection-01", "sec-canary-leak-01"]},
        limits={"max_tests": 2, "max_duration_seconds": 30, "max_retries": 1}, status="queued",
    ))
    session.commit()

    TestRunner(run_id, app).run()
    session.expire_all()

    run = session.query(RunModel).filter_by(id=run_id).first()
    results = session.query(TestResultModel).filter_by(run_id=run_id).all()
    assert run.status == "completed"
    assert fake.calls == ["initial", "evidence_based_follow_up"]
    assert len(results) == 2
    assert run.orchestration_metadata["follow_up_test_ids"] == ["sec-canary-leak-01"]
    assert run.final_report["assessment"] == "Observed 2 tests."


