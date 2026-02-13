# ArchAdvisor

**AI-powered multi-agent system that designs, debates, validates, and documents production-grade software architectures.**

Give it your system requirements. Get back a complete architecture document — reviewed by a Devil's Advocate, validated against real-world benchmarks, costed across AWS/GCP/Azure, and rendered with Mermaid diagrams.

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![React](https://img.shields.io/badge/React-19-61DAFB)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange)](https://langchain-ai.github.io/langgraph/)

## Demo



https://github.com/user-attachments/assets/1d24c9a5-b0c8-42e7-a1a2-aa690fdb618e



https://github.com/user-attachments/assets/1d24c9a5-b0c8-42e7-a1a2-aa690fdb618e



https://github.com/user-attachments/assets/40bb1560-fdfb-45b4-bed3-7637e18048e5



https://github.com/user-attachments/assets/40bb1560-fdfb-45b4-bed3-7637e18048e5



[https://www.loom.com/share/80d5b0c4a7d643c49eeef72316de99df](https://www.loom.com/share/80d5b0c4a7d643c49eeef72316de99df)
---

## How It Works

```
Requirements --> RAG Context --> Architect --> Validator --+
                                    ^                     |
                                    | revise    PASS/FAIL |
                                    +---------------------+
                                                          | PASS
                                                          v
                              Architect <-- Devil's Advocate
                                  | proceed       (up to 3 rounds)
                                  v
                           Cost Analyzer --> Documentation --> Final Output
```

1. **RAG Retrieval** — Pulls similar past architectures from ChromaDB for context
2. **Architect Agent** (GPT-4o) — Proposes a full system design with components, APIs, data flows, and deployment strategy
3. **Deterministic Validator** — Runs 7 rule-based checks in <50ms (SPOF detection, availability math, capacity benchmarks, consistency validation, contradiction detection, complexity analysis, requirements coverage)
4. **Devil's Advocate Agent** (GPT-4o) — Challenges the design as an SRE + Security Architect, producing scored findings
5. **Debate Loop** — Architect revises based on critical findings, up to 3 rounds
6. **Cost Analyzer Agent** (GPT-4o-mini) — Estimates costs across 3 scale tiers (Startup/Growth/Scale) for AWS, GCP, and Azure
7. **Documentation Agent** (GPT-4o) — Produces a polished architecture document with 11 mandatory sections, Mermaid diagrams, ADRs, and risk register

All steps stream real-time progress to the browser via WebSocket.

### The Agents

| Agent | Model | Role |
|-------|-------|------|
| **Architect** | GPT-4o | Proposes and revises system designs with components, APIs, data flows |
| **Validator** | Deterministic | 7 rule-based checks — SPOF, availability math, capacity, consistency |
| **Devil's Advocate** | GPT-4o | Finds weaknesses, SPOFs, security gaps as an SRE + Security Architect |
| **Cost Analyzer** | GPT-4o-mini | Estimates AWS/GCP/Azure costs at Startup/Growth/Scale tiers |
| **Documentation** | GPT-4o | Produces polished HLD with Mermaid diagrams, ADRs, risk register |

**Key differentiator**: The adversarial debate loop between Architect and Devil's Advocate, gated by deterministic validation, produces better designs than a single-agent approach — mimicking real architecture review boards.

---

## Features

- **Multi-Agent Debate** — Architect vs Devil's Advocate adversarial review loop
- **Deterministic Validation Gate** — 7 validators catch issues before burning LLM tokens on review
- **Composite Availability Math** — Calculates real SLA from component chain (e.g., 99.9% x 99.95% x 99.99%)
- **SPOF Detection** — Flags single-instance databases, caches, gateways, and queues
- **Contradiction Detection** — Catches event-driven without message broker, strong consistency with DynamoDB, etc.
- **Multi-Cloud Cost Estimation** — Side-by-side pricing for AWS, GCP, Azure across 3 scale tiers
- **Real-Time WebSocket Streaming** — Live agent progress, findings, and debate rounds in the browser
- **Mermaid Diagram Rendering** — Architecture, sequence, deployment, and ER diagrams rendered as SVG
- **Markdown Export** — Download the full architecture document as `.md`
- **Rate Limiting** — Per-IP session throttling (configurable)
- **Quick-Start Templates** — 4 pre-built requirement templates (notification system, payment gateway, chat platform, data pipeline)

---

## Quick Start

### Prerequisites

- **Node.js** 20+ (for frontend)
- **Python** 3.11+ (for backend)
- **Docker** (for Redis, or run Redis natively)
- **OpenAI API key** with GPT-4o access

### 1. Clone and configure

```bash
git clone https://github.com/yourusername/archadvisor.git
cd archadvisor
cp .env.example .env
```

Edit `.env` and set your OpenAI API key:

```env
OPENAI_API_KEY=sk-proj-your-key-here
```

### 2. Start with Docker (recommended)

```bash
make docker-up
```

This starts Redis + the backend API on port 8000.

Then start the frontend:

```bash
cd frontend-react
npm install
npm run dev
```

Open **http://localhost:3003**

### 3. Start without Docker

```bash
# Terminal 1 — Redis
docker run -d --name redis -p 6378:6379 redis:7-alpine

# Terminal 2 — Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 3 — Frontend
cd frontend-react
npm install && npm run dev
```

**API docs**: http://localhost:8000/docs

---

## Sample Output

Each run produces:

- **Executive Summary** — 3-5 sentence overview for leadership
- **Architecture Overview** — Style justification and high-level description
- **Component Deep Dive** — Each service with API contracts, data models, scaling strategy
- **Data Flow Diagrams** — Mermaid sequence diagrams for key user flows
- **Infrastructure & Deployment** — Regions, containerization, CI/CD strategy
- **Cost Comparison** — AWS vs GCP vs Azure at Startup/Growth/Scale tiers
- **Security Architecture** — Auth, encryption, secrets, network, compliance
- **Tradeoff Log** — What the Architect and Devil's Advocate debated
- **Reliability & Validation** — Composite availability math, SLA targets, unresolved findings
- **Risk Register** — Severity, likelihood, mitigation, owner for each risk
- **Architecture Decision Records** — ADRs for every major choice

**Cost per run**: ~$0.15-0.25 | **Time**: ~90-120 seconds

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI + Uvicorn |
| Agent Orchestration | LangGraph (cyclic state graph) |
| LLM Provider | OpenAI (GPT-4o, GPT-4o-mini) |
| Vector DB (RAG) | ChromaDB |
| Session Store | Redis |
| Frontend | React 19 + TypeScript + Vite |
| Styling | Tailwind CSS v4 |
| Charts | Recharts |
| Diagrams | Mermaid.js |
| Markdown | react-markdown + remark-gfm |
| Containerization | Docker + Docker Compose |

---

## Project Structure

```
archadvisor/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point, CORS, routers
│   │   ├── config.py                # Pydantic settings (env vars)
│   │   ├── agents/
│   │   │   ├── base.py              # BaseAgent — LLM calls, cost tracking, retries
│   │   │   ├── architect.py         # Designs system architecture
│   │   │   ├── devils_advocate.py   # Reviews and challenges designs
│   │   │   ├── cost_analyzer.py     # Multi-cloud cost estimation
│   │   │   └── documentation.py     # Produces final architecture document
│   │   ├── graph/
│   │   │   ├── state.py             # LangGraph TypedDict state schema
│   │   │   ├── nodes.py             # Graph node functions (agent wrappers)
│   │   │   ├── workflow.py          # Graph definition + compilation
│   │   │   └── validator_node.py    # Validation gate node
│   │   ├── validators/
│   │   │   ├── engine.py            # Validation orchestrator (runs all 7)
│   │   │   ├── models.py            # ErrorCode enum, ValidationReport
│   │   │   ├── reference_data.py    # SLA benchmarks, throughput limits
│   │   │   ├── schema_validator.py
│   │   │   ├── availability_validator.py
│   │   │   ├── capacity_validator.py
│   │   │   ├── consistency_validator.py
│   │   │   ├── contradiction_validator.py
│   │   │   ├── operational_complexity_validator.py
│   │   │   └── missing_requirement_validator.py
│   │   ├── api/
│   │   │   ├── router.py            # API + WebSocket router setup
│   │   │   ├── sessions.py          # Session CRUD + templates
│   │   │   ├── websocket.py         # WebSocket event streaming
│   │   │   └── health.py            # Health check endpoint
│   │   ├── services/
│   │   │   ├── session_manager.py   # Redis-backed session storage
│   │   │   ├── event_bus.py         # In-memory pub/sub for WebSocket
│   │   │   └── rate_limiter.py      # Per-IP rate limiting
│   │   ├── models/
│   │   │   ├── requests.py          # Pydantic request models
│   │   │   ├── responses.py         # Pydantic response models
│   │   │   └── events.py            # WebSocket event models
│   │   └── prompts/                 # Agent system prompts
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend-react/
│   ├── src/
│   │   ├── App.tsx                  # Main app — view state machine
│   │   ├── components/
│   │   │   ├── Sidebar.tsx          # Navigation, settings, recent sessions
│   │   │   ├── InputView.tsx        # Requirements input + templates
│   │   │   ├── ProcessingView.tsx   # Real-time progress with WebSocket
│   │   │   └── ResultsView.tsx      # Document, diagrams, conversation, metrics
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts      # WebSocket hook with reconnection
│   │   ├── services/
│   │   │   └── api.ts               # REST API client
│   │   └── types/
│   │       ├── api.ts               # TypeScript API types
│   │       └── constants.ts         # Agent metadata, severity config
│   ├── vite.config.ts
│   └── package.json
├── docker-compose.yml
├── Makefile
├── .env.example
├── README.md
└── ARCHITECTURE.md
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/sessions` | Create a new architecture session |
| `GET` | `/api/v1/sessions` | List recent sessions |
| `GET` | `/api/v1/sessions/{id}` | Get session status + conversation |
| `GET` | `/api/v1/sessions/{id}/output` | Get final architecture document |
| `POST` | `/api/v1/sessions/{id}/cancel` | Cancel a running session |
| `GET` | `/api/v1/templates` | List requirement templates |
| `GET` | `/api/v1/health` | Health check (Redis status) |
| `WS` | `/ws/sessions/{id}` | WebSocket for real-time events |

### WebSocket Events

| Event Type | Description |
|-----------|-------------|
| `agent_started` | Agent begins processing |
| `agent_thinking` | Agent progress update |
| `agent_completed` | Agent finished (with duration + cost) |
| `finding_discovered` | Issue found (with severity) |
| `debate_round_started` | New debate round begins |
| `debate_round_completed` | Debate round summary |
| `workflow_progress` | Overall pipeline progress |
| `session_complete` | Workflow finished successfully |
| `error` | Error occurred (with recoverable flag) |

---

## Configuration

All configuration via environment variables (loaded from `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *required* | OpenAI API key |
| `REDIS_URL` | `redis://localhost:6378/0` | Redis connection URL |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `false` | Debug mode |
| `LOG_LEVEL` | `info` | Logging level |
| `MAX_DEBATE_ROUNDS` | `3` | Max architect vs DA debate rounds |
| `ARCHITECT_MODEL` | `gpt-4o` | Model for Architect agent |
| `DEVILS_ADVOCATE_MODEL` | `gpt-4o` | Model for Devil's Advocate agent |
| `COST_ANALYZER_MODEL` | `gpt-4o-mini` | Model for Cost Analyzer |
| `DOCUMENTATION_MODEL` | `gpt-4o` | Model for Documentation agent |
| `RATE_LIMIT_MAX_SESSIONS` | `10` | Sessions per IP per hour |
| `RATE_LIMIT_WINDOW_SECONDS` | `3600` | Rate limit window |

---

## Makefile Commands

```bash
make setup        # Create venv, install deps, copy .env
make dev          # Run backend with hot reload
make dev-redis    # Start Redis container
make test         # Run pytest
make lint         # Run Ruff linter
make format       # Format code with Ruff
make docker-up    # Build and start all containers
make docker-down  # Stop all containers
make docker-logs  # Tail backend logs
make clean        # Remove containers, venv, cache
```

---

## Cost Per Run

| Agent | Model | Approx. Cost |
|-------|-------|-------------|
| Architect (initial) | GPT-4o | ~$0.04 |
| Architect (revisions) | GPT-4o | ~$0.03/round |
| Validator | Deterministic | $0.00 |
| Devil's Advocate | GPT-4o | ~$0.03/round |
| Cost Analyzer | GPT-4o-mini | ~$0.01 |
| Documentation | GPT-4o | ~$0.06 |
| **Total** | | **~$0.15-0.25** |

---

## License

MIT
