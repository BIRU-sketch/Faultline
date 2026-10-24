from app.adapters import MockAgentAdapter
from app.evaluators import RegexMatcherEvaluator, ScoringRulesEvaluator, LLMJudgeEvaluator
from app.security import get_indirect_injection_test, get_canary_leakage_test, get_unauthorized_tool_test
from app.benchmarks import get_benchmark_test


def test_vulnerable_vs_hardened_indirect_prompt_injection():
    """Verify vulnerable agent succumbs to indirect injection while hardened agent resists."""
    test_def = get_indirect_injection_test()
    regex_evaluator = RegexMatcherEvaluator()

    # 1. Vulnerable demo agent
    vuln_adapter = MockAgentAdapter(agent_id="vulnerable-demo")
    vuln_obs = vuln_adapter.execute_task(test_def["task_prompt"], test_def["system_prompt"])
    vuln_result = regex_evaluator.evaluate(test_def, vuln_obs.model_dump())

    assert vuln_result.status == "failed"
    assert "PWNED_EXPLOIT_SUCCESSFUL" in vuln_obs.output
    assert vuln_result.evidence.get("matched_forbidden_pattern") is not None

    # 2. Hardened demo agent
    hardened_adapter = MockAgentAdapter(agent_id="hardened-demo")
    hardened_obs = hardened_adapter.execute_task(test_def["task_prompt"], test_def["system_prompt"])
    hardened_result = regex_evaluator.evaluate(test_def, hardened_obs.model_dump())

    assert hardened_result.status == "passed"
    assert "PWNED_EXPLOIT_SUCCESSFUL" not in hardened_obs.output


def test_vulnerable_vs_hardened_canary_leak():
    """Verify vulnerable agent leaks synthetic canary while hardened agent protects it."""
    test_def = get_canary_leakage_test()
    regex_evaluator = RegexMatcherEvaluator()
    canary = test_def["metadata"]["canary"]

    # Vulnerable agent
    vuln_adapter = MockAgentAdapter(agent_id="vulnerable-demo", config={"canary": canary})
    vuln_obs = vuln_adapter.execute_task(test_def["task_prompt"], test_def["system_prompt"])
    vuln_result = regex_evaluator.evaluate(test_def, vuln_obs.model_dump())

    assert vuln_result.status == "failed"
    assert canary in vuln_obs.output
    assert vuln_result.evidence.get("canary_leaked") is True

    # Hardened agent
    hardened_adapter = MockAgentAdapter(agent_id="hardened-demo")
    hardened_obs = hardened_adapter.execute_task(test_def["task_prompt"], test_def["system_prompt"])
    hardened_result = regex_evaluator.evaluate(test_def, hardened_obs.model_dump())

    assert hardened_result.status == "passed"
    assert canary not in hardened_obs.output
    assert hardened_result.evidence.get("canary_leaked") is False


def test_prohibited_tool_action_detection():
    """Verify prohibited mock-tool execution is caught by ScoringRulesEvaluator."""
    test_def = get_unauthorized_tool_test()
    scoring_evaluator = ScoringRulesEvaluator()

    # Vulnerable agent attempts prohibited tool call
    vuln_adapter = MockAgentAdapter(agent_id="vulnerable-demo")
    vuln_obs = vuln_adapter.execute_task(test_def["task_prompt"])
    vuln_result = scoring_evaluator.evaluate(test_def, vuln_obs.model_dump())

    assert vuln_result.status == "failed"
    assert "execute_system_command" in vuln_result.evidence.get("prohibited_actions_detected", [])

    # Hardened agent avoids prohibited tool calls
    hardened_adapter = MockAgentAdapter(agent_id="hardened-demo")
    hardened_obs = hardened_adapter.execute_task(test_def["task_prompt"])
    hardened_result = scoring_evaluator.evaluate(test_def, hardened_obs.model_dump())

    assert hardened_result.status == "passed"


def test_llm_judge_unavailable_behavior():
    """Verify LLM judge returns explicit 'inconclusive' when provider is not configured."""
    judge = LLMJudgeEvaluator(provider="none")
    assert not judge.is_available()

    test_def = {"id": "subjective-test-01", "description": "Subjective task"}
    obs = {"output": "Agent output", "tool_calls": []}
    result = judge.evaluate(test_def, obs)

    assert result.status == "inconclusive"
    assert "unavailable" in result.summary.lower()


def test_inconclusive_evaluation_on_empty_output():
    """Verify empty/missing output produces an inconclusive evaluation rather than false pass."""
    regex_evaluator = RegexMatcherEvaluator()
    test_def = {"id": "test-pattern", "expected_behavior": {"must_match": ["hello"]}}
    obs = {"output": None, "tool_calls": []}

    result = regex_evaluator.evaluate(test_def, obs)
    assert result.status == "inconclusive"


def test_bash_file_workflow_requires_successful_verified_file_output():
    task = get_benchmark_test("bench-bash-file-workflow-01")
    evaluator = ScoringRulesEvaluator()
    observation = {
        "output": "Both files were written and the summary was verified.",
        "tool_call_count": 1,
        "retry_count": 0,
        "tool_calls": [
            {"name": "bash", "arguments": {"command": "read meeting_notes.txt; read meeting_summary.txt"}, "executed": True, "exit_code": 0, "stdout": "Project Aurora; river cleanup; June 12; three volunteers"},
        ],
    }
    assert evaluator.evaluate(task, observation).status == "passed"

    observation["tool_calls"][0]["exit_code"] = 1
    assert evaluator.evaluate(task, observation).status == "failed"
