import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from .tasks import get_constraint_following_task
from .reasoning import get_complex_reasoning_task
from .tool_use import get_bash_file_workflow_task, get_multi_step_tool_task

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "difficult_tasks.json"


def get_benchmark_tests() -> List[Dict[str, Any]]:
    """Loads all defined benchmark tests."""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                tasks = json.load(f)
                if isinstance(tasks, list) and len(tasks) > 0:
                    return tasks
        except Exception:
            pass

    return [
        get_bash_file_workflow_task(),
        get_multi_step_tool_task(),
        get_complex_reasoning_task(),
        get_constraint_following_task(),
    ]


def get_benchmark_test(test_id: str) -> Optional[Dict[str, Any]]:
    """Get a benchmark test by ID."""
    for test in get_benchmark_tests():
        if test.get("id") == test_id:
            return test
    return None


__all__ = [
    "get_benchmark_tests",
    "get_benchmark_test",
    "get_multi_step_tool_task",
    "get_bash_file_workflow_task",
    "get_complex_reasoning_task",
    "get_constraint_following_task",
]
