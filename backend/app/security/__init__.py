import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from .prompt_injection import get_indirect_injection_test
from .data_leakage import get_canary_leakage_test
from .tool_abuse import get_unauthorized_tool_test
from .jailbreaks import get_jailbreak_conflict_test

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "security_payloads.json"


def get_security_tests() -> List[Dict[str, Any]]:
    """Loads all defined security tests."""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                tests = json.load(f)
                if isinstance(tests, list) and len(tests) > 0:
                    return tests
        except Exception:
            pass

    # Built-in fallback definitions
    return [
        get_indirect_injection_test(),
        get_canary_leakage_test(),
        get_unauthorized_tool_test(),
        get_jailbreak_conflict_test(),
    ]


def get_security_test(test_id: str) -> Optional[Dict[str, Any]]:
    """Get a security test by ID."""
    for test in get_security_tests():
        if test.get("id") == test_id:
            return test
    return None


__all__ = [
    "get_security_tests",
    "get_security_test",
    "get_indirect_injection_test",
    "get_canary_leakage_test",
    "get_unauthorized_tool_test",
    "get_jailbreak_conflict_test",
]
