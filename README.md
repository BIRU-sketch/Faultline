# Faultline

**Faultline** is an agent security and benchmark testing framework designed to evaluate AI agents against security vulnerabilities (such as prompt injections, jailbreaks, data leakage, and tool abuse), challenge them with complex reasoning and tool-use tasks, measure execution latency, and grade them on a scale of 0 to 10.

---

## Architecture Overview

The system is cleanly separated into two standalone parts:
1. **`backend/`**: Python FastAPI evaluation engine, test suites, timing profiler, scoring system, and database models.
2. **`frontend/`**: Modern web dashboard (TypeScript / React / Vite) providing real-time test execution monitoring, vulnerability matrices, latency charts, and detailed 10-point scorecard reports.

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
