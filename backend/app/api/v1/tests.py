from flask import Blueprint, request, jsonify
from ...security import get_security_tests, get_security_test
from ...benchmarks import get_benchmark_tests, get_benchmark_test
from ...schemas.test_case import TestCaseSchema

tests_bp = Blueprint("tests", __name__)


@tests_bp.route("", methods=["GET"])
def list_tests():
    """List all available test cases with optional category filter."""
    category_filter = request.args.get("category", "").lower().strip()

    all_tests = []
    sec_tests = get_security_tests()
    bench_tests = get_benchmark_tests()

    if category_filter == "security":
        raw_list = sec_tests
    elif category_filter in ("benchmark", "benchmarks"):
        raw_list = bench_tests
    else:
        raw_list = sec_tests + bench_tests

    for t in raw_list:
        all_tests.append(
            TestCaseSchema(
                id=t.get("id"),
                title=t.get("title", t.get("id")),
                category=t.get("category", "security"),
                subcategory=t.get("subcategory"),
                description=t.get("description", ""),
                evaluation_method=t.get("evaluation_method", "scoring_rules"),
                difficulty=t.get("difficulty", "medium"),
                tags=t.get("tags", []),
                policy_requirements=t.get("policy_requirements"),
                expected_behavior=str(t.get("expected_behavior")),
                metadata=t.get("metadata", {}),
            ).model_dump()
        )

    categories_count = {
        "security": len(sec_tests),
        "benchmark": len(bench_tests),
    }

    return jsonify({
        "tests": all_tests,
        "total": len(all_tests),
        "categories": categories_count,
    }), 200


@tests_bp.route("/<test_id>", methods=["GET"])
def get_test(test_id: str):
    """Retrieve details of a single test definition."""
    t = get_security_test(test_id) or get_benchmark_test(test_id)
    if not t:
        return jsonify({"error": f"Test '{test_id}' not found in catalog."}), 404

    schema = TestCaseSchema(
        id=t.get("id"),
        title=t.get("title", t.get("id")),
        category=t.get("category", "security"),
        subcategory=t.get("subcategory"),
        description=t.get("description", ""),
        evaluation_method=t.get("evaluation_method", "scoring_rules"),
        difficulty=t.get("difficulty", "medium"),
        tags=t.get("tags", []),
        policy_requirements=t.get("policy_requirements"),
        expected_behavior=str(t.get("expected_behavior")),
        metadata=t.get("metadata", {}),
    )
    return jsonify(schema.model_dump()), 200
