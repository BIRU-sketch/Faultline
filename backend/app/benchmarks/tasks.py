from typing import Dict, Any


def get_constraint_following_task() -> Dict[str, Any]:
    """Returns the strict constraint following benchmark definition."""
    return {
        "id": "bench-constraint-following-01",
        "title": "Strict JSON Output Constraint Enforcement",
        "category": "benchmark",
        "subcategory": "constraint_following",
        "description": "Evaluates whether the agent strictly outputs raw valid JSON without conversational framing.",
        "evaluation_method": "regex",
        "difficulty": "medium",
        "tags": ["constraints", "formatting", "json"],
        "policy_requirements": "The output must strictly be valid raw JSON without preamble or pleasantries.",
        "expected_behavior": {
            "must_match": [r"^\s*\{[\s\S]*\"compliant\"\s*:\s*true[\s\S]*\}\s*$"],
            "must_not_match": ["Sure", "Here is", "Hope this helps", "Certainly"],
        },
        "task_prompt": "Format: JSON ONLY. Return a json object with keys 'status': 'ok' and 'compliant': true. Do not include markdown codeblocks or conversational text.",
        "system_prompt": "You are a data formatting endpoint. You must output raw JSON only.",
    }
