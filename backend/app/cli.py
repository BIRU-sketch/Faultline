import argparse
import os
import re
import threading
import webbrowser

from . import create_app
from .core.runner import TestRunner
from .db.models import AgentModel, RunModel
from .db.session import SessionScoped


DEFAULT_SECURITY_TESTS = [
    "sec-indirect-injection-01",
    "sec-instruction-conflict-01",
    "sec-canary-leak-01",
]
DEFAULT_BENCHMARKS = ["bench-bash-file-workflow-01"]


def main() -> None:
    parser = argparse.ArgumentParser(prog="faultline", description="Review an agent API and open the resulting report.")
    parser.add_argument("--endpoint", default=os.getenv("FAULTLINE_AGENT_ENDPOINT", "http://127.0.0.1:8001/execute"),
                        help="Agent HTTP endpoint that accepts a JSON evaluation request.")
    parser.add_argument("--agent-name", default="Desktop Automation Agent")
    parser.add_argument("--security", nargs="*", default=DEFAULT_SECURITY_TESTS, help="Security test IDs to run.")
    parser.add_argument("--benchmarks", nargs="*", default=DEFAULT_BENCHMARKS, help="Benchmark task IDs to run.")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")))
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser after the review.")
    args = parser.parse_args()

    if not args.security and not args.benchmarks:
        parser.error("Select at least one security test or benchmark.")
    from .security import get_security_test
    unknown_tests = [test_id for test_id in args.security if not get_security_test(test_id)]
    if unknown_tests:
        parser.error(f"Unknown security test IDs: {', '.join(unknown_tests)}")
    from .benchmarks import get_benchmark_test
    unknown_benchmarks = [test_id for test_id in args.benchmarks if not get_benchmark_test(test_id)]
    if unknown_benchmarks:
        parser.error(f"Unknown benchmark IDs: {', '.join(unknown_benchmarks)}")

    app = create_app(os.getenv("FLASK_ENV", "development"))
    slug = re.sub(r"[^a-z0-9-]+", "-", args.agent_name.lower()).strip("-") or "http-agent"
    agent_id = f"local-{slug}"[:64]
    with app.app_context():
        session = SessionScoped()
        agent = session.query(AgentModel).filter_by(id=agent_id).first()
        if agent is None:
            agent = AgentModel(id=agent_id, name=args.agent_name, adapter_type="http",
                               config={"endpoint_url": args.endpoint, "allow_local": True},
                               description="Agent API endpoint reviewed by the Faultline CLI.", enabled=True)
            session.add(agent)
        else:
            agent.name = args.agent_name
            agent.adapter_type = "http"
            agent.config = {"endpoint_url": args.endpoint, "allow_local": True}
            agent.enabled = True
        run = RunModel(agent_id=agent_id, test_selection={"security": args.security, "benchmarks": args.benchmarks},
                       limits={"max_tests": len(args.security) + len(args.benchmarks), "max_duration_seconds": 180, "max_retries": 1},
                       status="queued")
        session.add(run)
        session.commit()
        run_id = run.id

    print(f"Queued {len(args.security) + len(args.benchmarks)} tasks for {args.endpoint}...")
    TestRunner(run_id, app).start_async()

    url = f"http://{args.host}:{args.port}/?run_id={run_id}"
    print(f"Starting live Faultline report at {url} (Ctrl+C to stop).")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open_new_tab(url)).start()
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
