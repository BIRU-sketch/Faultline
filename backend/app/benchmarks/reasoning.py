from typing import Dict, Any


def get_complex_reasoning_task() -> Dict[str, Any]:
    """Returns the complex logical reasoning benchmark definition."""
    return {
        "id": "bench-complex-reasoning-01",
        "title": "Constrained Logical Deduction",
        "category": "benchmark",
        "subcategory": "reasoning",
        "description": "Evaluates logical deduction capabilities with conflicting premise constraints and elimination of invalid choices.",
        "evaluation_method": "scoring_rules",
        "difficulty": "hard",
        "tags": ["reasoning", "logic", "deduction"],
        "policy_requirements": "Must reach the correct deduced entity based on formal premises.",
        "expected_behavior": {
            "contains_all": ["Entity C"],
            "prohibited_substrings": ["Entity A", "Entity B"],
        },
        "task_prompt": "Perform deductive reasoning on the following premises: Premise 1: Entity A is valid only if condition Z is true. Premise 2: Condition Z is false. Premise 3: Entity B is disqualified due to parity. Premise 4: Entity C satisfies all non-zero requirements. Which entity is valid? Explain and state the exact valid solution.",
        "system_prompt": "You are a precise logical reasoning assistant.",
    }
