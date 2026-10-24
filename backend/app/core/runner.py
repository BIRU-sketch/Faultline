import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from ..db.session import SessionScoped
from ..db.models import RunModel, TestResultModel, AgentModel
from ..adapters import get_adapter, BaseAgentAdapter
from ..security import get_security_test, get_security_tests
from ..benchmarks import get_benchmark_test, get_benchmark_tests
from ..evaluators import RegexMatcherEvaluator, ScoringRulesEvaluator, LLMJudgeEvaluator
from .timer import LatencyTimer
from .grader import TenPointGrader
from .orchestrator import OpenAIOrchestrator

# Active cancellation registry
_cancellation_flags: Dict[str, threading.Event] = {}
_lock = threading.Lock()


def request_run_cancellation(run_id: str) -> bool:
    """Request cancellation of an active run."""
    with _lock:
        event = _cancellation_flags.get(run_id)
        if event:
            event.set()
            return True
        return False


def _update_run_progress(session, run_record, **updates) -> None:
    metadata = dict(run_record.orchestration_metadata or {})
    progress = dict(metadata.get("progress") or {})
    progress.update(updates)
    metadata["progress"] = progress
    run_record.orchestration_metadata = metadata
    session.commit()


class TestRunner:
    """
    Central test execution engine.
    Executes tests sequentially, enforces limits, evaluates findings,
    and updates run state and results in the database.
    """
    __test__ = False

    def __init__(self, run_id: str, app=None):
        self.run_id = run_id
        self.app = app
        self.grader = TenPointGrader()
        self.regex_evaluator = RegexMatcherEvaluator()
        self.scoring_evaluator = ScoringRulesEvaluator()
        self.llm_evaluator = LLMJudgeEvaluator()

    def start_async(self):
        """Spawns execution in a background thread."""
        with _lock:
            _cancellation_flags[self.run_id] = threading.Event()

        thread = threading.Thread(
            target=self._run_with_app_context,
            name=f"Faultline-Runner-{self.run_id}",
            daemon=True,
        )
        thread.start()
        return thread

    def _run_with_app_context(self):
        """Runs the test workflow inside Flask application context."""
        if self.app:
            with self.app.app_context():
                self.run()
        else:
            self.run()

    def run(self):
        """Execute the test suite sequentially."""
        session = SessionScoped()
        run_timer = LatencyTimer().start()

        try:
            run_record: Optional[RunModel] = session.query(RunModel).filter_by(id=self.run_id).first()
            if not run_record:
                return

            agent_record: Optional[AgentModel] = (
                session.query(AgentModel).filter_by(id=run_record.agent_id).first()
            )
            if not agent_record:
                run_record.status = "failed"
                run_record.error_message = f"Agent '{run_record.agent_id}' not found in registry."
                session.commit()
                return

            # Update status to running
            run_record.status = "running"
            run_record.started_at = datetime.now(timezone.utc)
            session.commit()

            # Enforce limits
            limits = run_record.limits or {}
            configured_test_limit = int(self.app.config.get("OPENAI_MAX_TESTS", 10)) if self.app else 10
            max_tests = min(int(limits.get("max_tests", 10)), 20, configured_test_limit)
            max_duration_seconds = min(int(limits.get("max_duration_seconds", 60)), 180)
            max_retries = min(int(limits.get("max_retries", 1)), 3)

            # Resolve selected tests
            test_selection = run_record.test_selection or {}
            security_ids = test_selection.get("security", [])
            benchmark_ids = test_selection.get("benchmarks", [])

            tests_to_run: List[Dict[str, Any]] = []

            # Add security tests
            for tid in security_ids:
                t = get_security_test(tid)
                if t:
                    tests_to_run.append(t)
            # Add benchmark tests
            for tid in benchmark_ids:
                t = get_benchmark_test(tid)
                if t:
                    tests_to_run.append(t)

            # Truncate to maximum permitted tests limit
            tests_to_run = tests_to_run[:max_tests]
            orchestrator_candidates = list(tests_to_run)

            orchestrator = None
            openai_key = self.app.config.get("OPENAI_API_KEY", "") if self.app else ""
            _update_run_progress(
                session,
                run_record,
                state="planning" if openai_key else "running",
                completed_tests=0,
                total_tests=len(tests_to_run),
                current_test=None,
                test_order=[{"id": test["id"], "title": test.get("title", test["id"]), "category": test.get("category", "security")} for test in tests_to_run],
            )
            if openai_key:
                orchestrator_config = {**self.app.config, "OPENAI_MAX_RETRIES": max_retries}
                orchestrator = OpenAIOrchestrator(config=orchestrator_config)
                try:
                    tests_to_run = orchestrator.plan(
                        {"agent_id": agent_record.id, "capabilities": (agent_record.config or {}).get("actions", []),
                         "policy": (agent_record.config or {}).get("policy", "Use only the declared adapter capabilities and run limits."),
                         "target_adapter": agent_record.adapter_type,
                         "selected_categories": list(test_selection.keys()), "limits": limits},
                        tests_to_run, max_tests,
                    )
                    run_record.orchestration_metadata = {
                        **(run_record.orchestration_metadata or {}),
                        "planned_test_ids": [t["id"] for t in tests_to_run],
                        "test_plan": [t.get("orchestration", {"test_id": t["id"], "objective": "Required desktop baseline"}) for t in tests_to_run],
                        "orchestrator_steps": 1,
                        "provider_requests": orchestrator.requests,
                    }
                    _update_run_progress(
                        session,
                        run_record,
                        state="running",
                        total_tests=len(tests_to_run),
                        test_order=[{"id": test["id"], "title": test.get("title", test["id"]), "category": test.get("category", "security")} for test in tests_to_run],
                    )
                except Exception as exc:
                    run_record.status = "failed"
                    run_record.error_message = f"OpenAI orchestration failed: {exc}"
                    run_record.completed_at = datetime.now(timezone.utc)
                    _update_run_progress(session, run_record, state="failed", current_test=None, error=str(exc))
                    return

            # Instantiate agent adapter
            adapter: BaseAgentAdapter = get_adapter(
                adapter_type=agent_record.adapter_type,
                agent_id=agent_record.id,
                config={**(agent_record.config or {}), "max_retries": max_retries},
            )

            executed_results: List[Dict[str, Any]] = []
            cancel_event = _cancellation_flags.get(self.run_id)
            duration_exceeded = False

            planned_round_end = len(tests_to_run)
            orchestration_steps = 1 if orchestrator else 0
            for test_index, test_def in enumerate(tests_to_run):
                # Check for cancellation request
                if cancel_event and cancel_event.is_set():
                    run_record.status = "cancelled"
                    run_record.error_message = "Run was cancelled by user request."
                    _update_run_progress(session, run_record, state="cancelled", current_test=None)
                    break

                # Check duration limit
                if (run_timer.elapsed_seconds() or 0.0) >= max_duration_seconds:
                    duration_exceeded = True
                    run_record.status = "failed"
                    run_record.error_message = (
                        f"Run exceeded configured maximum duration of {max_duration_seconds} seconds."
                    )
                    _update_run_progress(session, run_record, state="failed", current_test=None, error=run_record.error_message)
                    break

                # Execute test on agent
                _update_run_progress(
                    session,
                    run_record,
                    state="running",
                    completed_tests=len(executed_results),
                    total_tests=len(tests_to_run),
                    current_test={"id": test_def.get("id"), "title": test_def.get("title", test_def.get("id")), "category": test_def.get("category", "security"), "started_at": datetime.now(timezone.utc).isoformat()},
                )
                test_timer = LatencyTimer().start()
                test_started_at = datetime.now(timezone.utc)
                observation = adapter.execute_task(
                    task_prompt=test_def.get("task_prompt", test_def.get("description", "")),
                    system_prompt=test_def.get("system_prompt"),
                    timeout_seconds=min(30.0, float(max_duration_seconds)),
                )
                test_latency = test_timer.stop()
                test_completed_at = datetime.now(timezone.utc)

                # Select and run evaluator
                eval_method = test_def.get("evaluation_method", "scoring_rules")
                obs_dict = observation.model_dump()

                if eval_method == "regex":
                    eval_result = self.regex_evaluator.evaluate(test_def, obs_dict)
                elif eval_method == "llm_judge":
                    eval_result = self.llm_evaluator.evaluate(test_def, obs_dict)
                else:
                    eval_result = self.scoring_evaluator.evaluate(test_def, obs_dict)

                if observation.retry_count > max_retries:
                    from ..evaluators.base import EvaluationResult
                    eval_result = EvaluationResult(
                        status="failed",
                        summary=f"Retry limit exceeded: adapter reported {observation.retry_count} retries (maximum permitted: {max_retries}).",
                        evidence={"retry_count": observation.retry_count, "max_allowed": max_retries},
                        score=0.0,
                    )

                persisted_evidence = {
                    **(eval_result.evidence or {}),
                    "input": test_def.get("task_prompt", test_def.get("description", "")),
                    "output": observation.output,
                    "final_state": (observation.raw_response or {}).get("final_state"),
                    "target_response": observation.output,
                    "tool_calls": observation.tool_calls,
                    "actions_executed": [action for action in observation.tool_calls if action.get("executed")],
                    "adapter_observation": observation.raw_response,
                    "error": observation.error,
                    "started_at": test_started_at.isoformat(),
                    "completed_at": test_completed_at.isoformat(),
                    "test_id": test_def.get("id"),
                }

                # Persist TestResultModel immediately
                test_result = TestResultModel(
                    id=str(uuid.uuid4()),
                    run_id=self.run_id,
                    test_id=test_def.get("id"),
                    test_title=test_def.get("title", test_def.get("id")),
                    category=test_def.get("category", "security"),
                    status=eval_result.status,
                    summary=eval_result.summary,
                    latency_ms=test_latency,
                    tool_call_count=observation.tool_call_count,
                    retry_count=observation.retry_count,
                    token_usage=observation.token_usage,
                    evidence=persisted_evidence,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(test_result)
                session.commit()

                executed_results.append({
                    "test_id": test_result.test_id,
                    "test_title": test_result.test_title,
                    "category": test_result.category,
                    "status": test_result.status,
                    "latency_ms": test_result.latency_ms,
                    "tool_call_count": test_result.tool_call_count,
                    "retry_count": test_result.retry_count,
                    "token_usage": test_result.token_usage,
                    "evidence": test_result.evidence,
                })
                _update_run_progress(
                    session,
                    run_record,
                    state="running",
                    completed_tests=len(executed_results),
                    total_tests=len(tests_to_run),
                    current_test=None,
                    latest_result={"test_id": test_result.test_id, "test_title": test_result.test_title, "status": test_result.status, "summary": test_result.summary},
                )

                if (orchestrator and test_index == planned_round_end - 1
                        and orchestration_steps < orchestrator.max_steps
                        and (run_timer.elapsed_seconds() or 0.0) < max_duration_seconds
                        and any(result["status"] == "failed" for result in executed_results)):
                    completed_ids = {result["test_id"] for result in executed_results}
                    follow_up_pool = [test for test in orchestrator_candidates if test["id"] not in completed_ids]
                    remaining = max_tests - len(executed_results)
                    if follow_up_pool and remaining > 0:
                        follow_ups = orchestrator.plan(
                            {"agent_id": agent_record.id, "stage": "evidence_based_follow_up",
                             "observed_results": executed_results, "remaining_test_budget": remaining,
                             "policy": "Select only a relevant, unexecuted test from the original selection."},
                            follow_up_pool, remaining,
                        )
                        tests_to_run.extend(follow_ups)
                        orchestration_steps += 1
                        planned_round_end = len(tests_to_run)
                        run_record.orchestration_metadata = {
                            **(run_record.orchestration_metadata or {}),
                            "follow_up_test_ids": [test["id"] for test in follow_ups],
                            "follow_up_plan": [test.get("orchestration", {}) for test in follow_ups],
                            "orchestrator_steps": orchestration_steps,
                            "provider_requests": orchestrator.requests,
                        }
                        _update_run_progress(
                            session,
                            run_record,
                            total_tests=len(tests_to_run),
                            test_order=[{"id": test["id"], "title": test.get("title", test["id"]), "category": test.get("category", "security")} for test in tests_to_run],
                        )

            # Calculate grade and finalize run if not cancelled
            total_duration_ms = run_timer.stop()
            run_record.total_duration_ms = total_duration_ms
            run_record.completed_at = datetime.now(timezone.utc)
            _update_run_progress(
                session,
                run_record,
                state="finalizing" if run_record.status == "running" else run_record.status,
                completed_tests=len(executed_results),
                total_tests=len(tests_to_run),
                current_test=None,
            )

            if run_record.status != "cancelled":
                grade_report = self.grader.grade(executed_results)
                run_record.overall_grade = grade_report.overall_grade
                run_record.component_scores = {
                    k: v.model_dump() for k, v in grade_report.components.items()
                }
                if not duration_exceeded:
                    run_record.status = "completed"

                report_context = {
                    "run_id": self.run_id,
                    "observed_results": executed_results,
                    "grade": {"overall_grade": grade_report.overall_grade,
                              "components": {k: v.model_dump() for k, v in grade_report.components.items()},
                              "limitations": grade_report.limitations},
                    "duration_ms": total_duration_ms,
                    "metrics": {
                        "tool_calls": sum(result.get("tool_call_count", 0) for result in executed_results),
                        "retries": sum(result.get("retry_count", 0) for result in executed_results),
                        "token_usage_available": any(result.get("evidence", {}).get("token_usage") for result in executed_results),
                        "cost_available": False,
                    },
                    "unavailable_measurements": ["estimated cost"] + (
                        [] if any(result.get("evidence", {}).get("token_usage") for result in executed_results)
                        else ["token usage"]
                    ),
                "openai_retries": orchestrator.retries if orchestrator else 0,
                }
                if orchestrator and not duration_exceeded:
                    try:
                        run_record.final_report = orchestrator.synthesize(report_context)
                        run_record.orchestration_metadata = {
                            **(run_record.orchestration_metadata or {}),
                            "provider_requests": orchestrator.requests,
                            "provider_retries": orchestrator.retries,
                            "synthesis_generated": True,
                        }
                    except Exception as exc:
                        run_record.final_report = {"assessment": "OpenAI synthesis unavailable.", "error": str(exc), "evidence": report_context}
                elif orchestrator:
                    run_record.final_report = {
                        "assessment": "Evaluation stopped at the configured wall-clock limit; this report contains partial observations.",
                        "findings": [], "remediations": [],
                        "limitations": grade_report.limitations + ["OpenAI synthesis was skipped after the duration limit."],
                        "evidence": report_context,
                    }
                else:
                    run_record.final_report = {
                        "assessment": "Deterministic evaluation report; OpenAI synthesis was not configured.",
                        "evidence": report_context,
                        "findings": [], "remediations": [], "limitations": grade_report.limitations,
                    }

            _update_run_progress(
                session,
                run_record,
                state=run_record.status,
                completed_tests=len(executed_results),
                total_tests=len(tests_to_run),
                current_test=None,
            )

        except Exception as e:
            session.rollback()
            try:
                run_record = session.query(RunModel).filter_by(id=self.run_id).first()
                if run_record:
                    run_record.status = "failed"
                    run_record.error_message = f"Execution engine failure: {str(e)}"
                    run_record.completed_at = datetime.now(timezone.utc)
                    _update_run_progress(session, run_record, state="failed", current_test=None, error=str(e))
            except Exception:
                pass

        finally:
            with _lock:
                _cancellation_flags.pop(self.run_id, None)
            session.close()
