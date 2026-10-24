# Faultline

**Faultline** is an agent security and benchmark testing framework designed to evaluate AI agents against security vulnerabilities (such as prompt injections, jailbreaks, data leakage, and tool abuse), challenge them with complex reasoning and tool-use tasks, measure execution latency, and grade them on a scale of 0 to 10.

---

## Architecture Overview

The system keeps a Flask REST backend and a separate frontend project. The frontend is not served by or integrated into Flask.

```text
Faultline/
├── backend/
│   ├── app/
│   │   ├── adapters/       # Connectors for agents (HTTP, OpenAI-compatible, custom)
│   │   ├── api/v1/         # REST API endpoints (agents, tests, runs, reports)
│   │   ├── benchmarks/     # Difficult task benchmarks (reasoning, tool-use, multi-step)
│   │   ├── core/           # Execution runner, high-resolution timer, 10-point grader
│   │   ├── db/             # Database connection & persistence models
│   │   ├── evaluators/     # Evaluator engines (LLM judge, regex matcher, scoring rules)
│   │   ├── schemas/        # Pydantic data schemas
│   │   └── security/       # Security test suites (prompt injection, jailbreak, data leakage, tool abuse)
│   ├── data/               # Security payloads & benchmark task datasets
│   └── tests/              # Unit & integration tests
│
├── frontend/
│   ├── src/
│   │   ├── api/            # API clients for backend communication
│   │   ├── components/     # UI components (dashboard, agent management, test suites, live console)
│   │   ├── hooks/          # React custom hooks
│   │   ├── pages/          # Dashboard, Security, Benchmarks, Run, and Report pages
│   │   ├── types/          # TypeScript interface definitions
│   │   └── utils/          # Formatting and score calculation utilities
│   ├── public/
│   └── package.json
│
├── docker-compose.yml
└── .gitignore
```

---

## OpenAI Orchestration and Agent API Reviews

The Flask API can use OpenAI to plan bounded tests, request evidence-based follow-ups, and synthesize persisted reports. Agent-under-test integration is plain HTTP: Faultline sends each test prompt as JSON to the agent's API endpoint and evaluates the JSON response. No browser automation or Chromium installation is needed.

Set these values in `backend/.env` (the API key is never stored in the database):

```dotenv
OPENAI_API_KEY=your-key
OPENAI_ORCHESTRATOR_MODEL=gpt-4o-mini
OPENAI_AGENT_MODEL=gpt-6-astra
OPENAI_MAX_ORCHESTRATOR_STEPS=4
OPENAI_MAX_TESTS=10
OPENAI_MAX_REQUESTS=8
OPENAI_REQUEST_TIMEOUT_SECONDS=30
```

From the repository root, install the backend dependencies:

```powershell
cd backend
python -m pip install -r requirements.txt
```

### Review an agent API

Start the sample agent API in one terminal:

```powershell
cd backend
python desktop_automation_agent.py
```

In a second terminal, run Faultline against that endpoint:

```powershell
cd backend
python -m app.cli --endpoint http://127.0.0.1:8001/execute --agent-name "Desktop Automation Agent"
```

The CLI sends JSON requests containing `prompt`, `system_prompt`, and `tools` to the agent endpoint. The included sample agent calls the OpenAI Responses API with a single hosted bash shell; it has no browser, computer-use, or other tools. It performs multi-step file tasks in an isolated `/mnt/data` workspace, returns the actual shell commands/results and token usage, and requires `OPENAI_API_KEY` in `backend/.env`. Set `OPENAI_AGENT_MODEL` to a model available to your account. The sample deliberately echoes its system prompt as debug output, so the default canary test reports a system-prompt leakage finding; set `FAULTLINE_DEMO_LEAK_SYSTEM_PROMPT=0` to disable this showcase flaw. Do not use the intentionally vulnerable sample as a production agent. The CLI opens a live report dashboard while the review runs and updates results automatically. This agent uses a hosted shell, not the user's local Windows desktop or Terminal GUI. Press Ctrl+C to stop each server.

Run the offline test suite with `cd backend; pytest -q`. Tests use fake OpenAI providers and do not require a live OpenAI API key.

## Key Modules

### 1. Security Testing (`backend/app/security/`)
- **Prompt Injection**: Direct attacks, indirect injections via simulated web/document retrieval, delimiter escaping.
- **Jailbreaks**: Persona hijacking, hypothetical framing, obfuscated encoding.
- **Data Leakage**: System prompt extraction, private key / PII exfiltration attempts.
- **Tool Abuse**: Unauthorized command execution, SQL injection in tool parameters, SSRF attempts.

### 2. Difficult Task Benchmarks (`backend/app/benchmarks/`)
- Multi-step planning and self-correction.
- Complex symbolic and logical reasoning under constrained contexts.
- Tool use correctness and schema conformity under adversarial distraction.

### 3. Timing & Latency Profiler (`backend/app/core/timer.py`)
- Measures time-to-first-token (TTFT), task turnaround time, and latency per tool call.
- Flags timeouts and degradation under load.

### 4. 10-Point Grading System (`backend/app/core/grader.py`)
- Standardized scale from **0 to 10**:
  - **Security Resilience (40%)**: Resistance against prompt injections, leakage, and unauthorized tool calls.
  - **Task Completion (40%)**: Accuracy, correctness, and reasoning depth on difficult tasks.
  - **Performance & Efficiency (20%)**: Response latency, token economy, and execution speed.
- Produces aggregated scorecards and category breakdown reports.
