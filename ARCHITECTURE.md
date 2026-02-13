# ArchAdvisor — System Architecture

This document explains how ArchAdvisor itself is designed: the agent orchestration, validation engine, real-time communication, and data flow.

---

## Table of Contents

- [System Overview](#system-overview)
- [Workflow Pipeline](#workflow-pipeline)
- [Agent Design](#agent-design)
- [Deterministic Validation Engine](#deterministic-validation-engine)
- [LangGraph State Machine](#langgraph-state-machine)
- [Real-Time Communication](#real-time-communication)
- [Session & Storage Layer](#session--storage-layer)
- [Frontend Architecture](#frontend-architecture)
- [Key Design Decisions](#key-design-decisions)

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│  InputView → ProcessingView (WebSocket) → ResultsView           │
└────────────┬──────────────────────┬─────────────────────────────┘
             │ REST API             │ WebSocket
             ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────┐  │
│  │ Sessions │  │  WebSocket   │  │  Health    │  │   Rate    │  │
│  │   API    │  │  Endpoint    │  │  Check     │  │  Limiter  │  │
│  └────┬─────┘  └──────┬───────┘  └───────────┘  └───────────┘  │
│       │               │                                         │
│       ▼               ▼                                         │
│  ┌──────────────────────────┐                                   │
│  │       Event Bus          │ (in-memory pub/sub)               │
│  └────────────┬─────────────┘                                   │
│               │                                                 │
│       ┌───────▼─────────┐                                       │
│       │  LangGraph       │                                      │
│       │  Workflow Engine  │                                      │
│       └───────┬─────────┘                                       │
│               │                                                 │
│    ┌──────────┼──────────────────────────┐                      │
│    ▼          ▼          ▼               ▼                      │
│ ┌────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐                 │
│ │Architect│ │Devil's │ │  Cost   │ │  Docs    │                 │
│ │ Agent   │ │Advocate│ │Analyzer │ │  Agent   │                 │
│ └────┬───┘ └────┬───┘ └────┬────┘ └────┬─────┘                 │
│      └──────────┴──────────┴────────────┘                       │
│               │                                                 │
│               ▼                                                 │
│       ┌───────────────┐     ┌─────────────┐                    │
│       │  Validation   │     │  ChromaDB   │                    │
│       │  Engine (7)   │     │  (RAG)      │                    │
│       └───────────────┘     └─────────────┘                    │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
                          ┌──────────────┐
                          │    Redis     │
                          │  (Sessions)  │
                          └──────────────┘
```

**Three main layers:**

1. **Frontend** — React SPA with WebSocket for real-time updates
2. **API + Orchestration** — FastAPI serving REST + WebSocket, LangGraph managing the agent pipeline
3. **Storage** — Redis for sessions (24h TTL), ChromaDB for architecture embeddings (RAG)

---

## Workflow Pipeline

The core pipeline is a LangGraph `StateGraph` with conditional edges that form two loops:

### Graph Definition

```
retrieve_context
      │
      ▼
architect_design
      │
      ▼
  validator ─────────────────┐
      │                      │
      ├─ PASS ──────────┐    │
      │                  │    │
      ├─ FAIL ──► architect_revise_validation
      │                  │         │
      └─ MAX_LOOPS ─────┤         │
                         │    (loops back to validator,
                         │     max 2 iterations)
                         ▼
              devils_advocate_review
                         │
                         ├─ revise ──► architect_revise ─┐
                         │                                │
                         │         (loops back, max 3     │
                         │          debate rounds)  ◄─────┘
                         │
                         ├─ proceed
                         ▼
                   cost_analysis
                         │
                         ▼
                    generate_docs
                         │
                         ▼
                        END
```

### Step-by-Step

| Step | Node | Agent | What Happens |
|------|------|-------|-------------|
| 1 | `retrieve_context` | RAG | Query ChromaDB for similar past architectures |
| 2 | `architect_design` | Architect (GPT-4o) | Generate full architecture JSON from requirements + context |
| 3 | `validator` | Deterministic | Run 7 validators in <50ms, score 0-100, pass/fail |
| 3a | `architect_revise_validation` | Architect (GPT-4o) | Fix validation errors, loop back to validator (max 2x) |
| 4 | `devils_advocate_review` | Devil's Advocate (GPT-4o) | Challenge design, produce severity-scored findings |
| 4a | `architect_revise` | Architect (GPT-4o) | Address critical findings, loop back to DA (max 3x) |
| 5 | `cost_analysis` | Cost Analyzer (GPT-4o-mini) | Estimate costs for 3 tiers across AWS/GCP/Azure |
| 6 | `generate_docs` | Documentation (GPT-4o) | Produce 11-section architecture document with diagrams |

### Routing Logic

**After Validator:**
- `validation_passed == True` → proceed to Devil's Advocate
- `validation_passed == False && validation_round < 2` → revise and re-validate
- `validation_passed == False && validation_round >= 2` → force proceed (avoid infinite loop)

**After Devil's Advocate:**
- `proceed_recommendation == "proceed"` → cost analysis
- `proceed_recommendation == "revise_*" && debate_round < max_rounds` → architect revises
- `debate_round >= max_rounds` → force proceed to cost analysis

---

## Agent Design

All agents extend `BaseAgent`, which handles:

- **LLM initialization** — Lazy `ChatOpenAI` creation with configurable model, temperature, max tokens
- **Retry logic** — 3 attempts with exponential backoff (2s base, 30s max) via `tenacity`
- **Cost tracking** — Token-level cost estimation using per-model pricing tables
- **Event emission** — Every agent emits `agent_started`, `agent_thinking`, `agent_completed` events
- **JSON parsing** — Response extraction with fallback regex for malformed JSON

### Agent Specifications

| Agent | Model | Temp | Max Tokens | Persona |
|-------|-------|------|-----------|---------|
| Architect | `gpt-4o` | 0.5 | 8,192 | Principal Software Architect, 15+ years |
| Devil's Advocate | `gpt-4o` | 0.3 | 4,096 | Senior SRE + Security Architect |
| Cost Analyzer | `gpt-4o-mini` | 0.2 | 8,192 | Cloud Infrastructure Cost Specialist |
| Documentation | `gpt-4o` | 0.4 | 16,000 | Senior Technical Writer |

### Architect Output Schema

The Architect produces a structured JSON design containing:

```
{
  overview, architecture_style,
  components: [{ name, type, responsibility, tech_stack, api_endpoints, data_stores, scaling_strategy }],
  data_flow_diagram (mermaid), component_diagram (mermaid),
  tech_decisions: [{ decision, reasoning, alternatives_considered }],
  non_functional: { latency_targets, throughput, availability_target, data_consistency, disaster_recovery },
  deployment: { strategy, regions, containerization }
}
```

Component types: `service`, `database`, `cache`, `queue`, `gateway`, `cdn`, `storage`

### Devil's Advocate Output Schema

```
{
  severity_summary: { critical, high, medium, low },
  findings: [{ id, severity, category, component, issue, impact, recommendation }],
  missing_considerations, strengths, overall_assessment,
  proceed_recommendation: "proceed" | "revise_critical" | "revise_recommended"
}
```

Finding categories: `single_point_of_failure`, `security`, `scalability`, `data_consistency`, `operational_complexity`, `cost_inefficiency`, `missing_requirement`, `over_engineering`

### Cost Analyzer Output Schema

```
{
  scale_tiers: [
    { tier_name: "Startup|Growth|Scale",
      aws: { total_monthly_usd, breakdown: [{ category, service, specs, monthly_usd }] },
      gcp: { ... }, azure: { ... }
    }
  ],
  cost_optimization_tips: [{ tip, estimated_savings_percent, tradeoff }],
  cheapest_path: { provider, reasoning, estimated_monthly_range },
  scaling_cost_projection: { 10x_traffic, 100x_traffic, cost_scaling_pattern }
}
```

### Documentation Output Schema

The Documentation agent produces structured JSON with:
- `title`, `executive_summary`
- `sections[]` — 11 mandatory sections (see below)
- `diagrams[]` — Mermaid diagrams (component, sequence, deployment, ER)
- `decision_log[]` — Architecture Decision Records (ADRs)

**11 Mandatory Sections:**

1. Executive Summary
2. Architecture Overview
3. Component Deep Dive
4. Data Flow
5. Infrastructure & Deployment
6. Cost Analysis (with comparison tables)
7. Security Architecture
8. Tradeoff Log (debate findings + responses)
9. Reliability & Validation (score, availability math)
10. Risk Register (table with 5+ risks)
11. Architecture Decision Records (3+ ADRs)

---

## Deterministic Validation Engine

The validation engine runs **before** the Devil's Advocate to catch structural issues cheaply (<50ms, no LLM calls). This saves ~$0.03+ per caught issue that would otherwise require a full DA review + Architect revision cycle.

### Validator Chain

```
Design JSON
    │
    ▼
┌─────────────────────────────────┐
│  1. Schema Validator            │  Required fields, types, enums
│  2. Availability Validator      │  SPOF detection, composite SLA math
│  3. Capacity Validator          │  Throughput vs benchmarks, auto-scaling
│  4. Consistency Validator       │  CAP theorem, cross-region latency
│  5. Contradiction Validator     │  Event-driven without broker, etc.
│  6. Operational Complexity      │  Over-engineering for scale
│  7. Missing Requirement         │  Requirements coverage check
└─────────────────────────────────┘
    │
    ▼
ValidationReport { score: 0-100, passed: bool, errors: [...] }
```

### Scoring

| Severity | Point Deduction |
|----------|----------------|
| Critical | -30 per error |
| High | -15 per error |
| Medium | -5 per error |
| Low | -2 per error |

**Pass threshold**: No critical errors AND score >= 60

### Validator Details

#### Schema Validator
- Required keys: `overview`, `architecture_style`, `components`, `non_functional`, `tech_decisions`, `deployment`
- Valid styles: `microservices`, `event-driven`, `monolith`, `serverless`, `hybrid`, `modular_monolith`
- Validates availability target format (90%-99.9999%)
- Validates consistency model (`strong`, `eventual`, `causal`)

#### Availability Validator
- **SPOF Detection**: Flags databases, caches, gateways, queues without redundancy keywords (`cluster`, `replica`, `multi-az`, `failover`, `hot-standby`, `sentinel`, etc.)
- **Composite Availability**: Multiplies component SLAs in serial chain. Example: if 3 components have 99.9%, composite = 99.9%^3 = 99.7%
- **High SLA Check**: >= 99.99% requires multi-AZ/multi-region deployment
- **Replication Check**: >= 99.9% SLA requires explicit replication strategy for databases

Reference data maps known services to baseline availability:
- DynamoDB: 99.99%, RDS: 99.9%, Redis: 99.5%, Kafka: 99.95%, etc.

#### Capacity Validator
- Compares declared throughput against per-technology benchmarks
- Flags high throughput (>=10K RPS) without auto-scaling keywords
- Flags high throughput databases (>=20K RPS) without sharding strategy
- Detects write-heavy hotspot risk (>=5K RPS writes)
- Requires non-empty `scaling_strategy` on every service/gateway

Benchmark examples: Node.js single-thread: 10K RPS, PostgreSQL: 5K RPS, Redis: 100K RPS

#### Consistency Validator
- `eventual` consistency must be justified in tech_decisions
- `strong` + multi-region = HIGH severity (50-200ms cross-region latency per write)
- `strong` + eventually-consistent DB (DynamoDB, Cassandra, MongoDB) = CRITICAL contradiction

#### Contradiction Validator
- Event-driven architecture without message broker (Kafka, RabbitMQ, SQS, etc.)
- Serverless + Kubernetes (incompatible operational models)
- Low latency target (<=100ms) + 6+ synchronous service hops
- Multi-region in NFRs but single region in deployment config
- Microservices style with only 1-2 components (it's a monolith)
- Monolith style with 10+ services (it's microservices)
- Claims stateless but uses local file/memory state

#### Operational Complexity Validator
- 15+ components = too many services (suggest consolidation)
- 8+ microservices at <5K RPS = over-engineered for scale (suggest modular monolith)
- Kafka at <10K RPS = overkill (suggest Redis Streams or SQS)
- Multi-region for MVP/startup at <5K RPS = premature
- 3+ enterprise services (Aurora, MSK, DynamoDB) for startup scale

#### Missing Requirement Validator
- Maps requirement keywords to expected components
- Example: user mentions "auth" → architecture must include auth component
- Severity varies: auth/encryption = critical, monitoring/DR = high, analytics/caching = medium

---

## LangGraph State Machine

### State Schema (`ArchAdvisorState`)

```
ArchAdvisorState (TypedDict)
├── Input
│   ├── requirements: str
│   ├── preferences: dict { cloud_provider, max_debate_rounds, detail_level }
│   └── session_id: str
├── RAG
│   └── similar_architectures: list[str]
├── Agent Outputs
│   ├── current_design: str (JSON)       ← updated after each revision
│   ├── review_findings: str (JSON)
│   ├── cost_analysis: str (JSON)
│   ├── final_document: str (JSON)
│   ├── rendered_markdown: str
│   └── mermaid_diagrams: list[dict]
├── Validation
│   ├── validation_report: str (JSON)
│   ├── validation_passed: bool
│   ├── validation_score: float
│   └── validation_round: int            ← increments on each validation loop
├── Control Flow
│   ├── debate_round: int                ← increments on each DA review
│   ├── max_debate_rounds: int
│   └── status: Literal[initializing, retrieving_context, designing, ...]
├── Conversation
│   └── messages: list[AgentMessage]     ← append-only log of all agent runs
├── Errors
│   └── errors: list[str]
└── Metadata
    ├── started_at: str (ISO)
    ├── completed_at: str (ISO)
    └── total_cost_usd: float            ← accumulated across all LLM calls
```

### How State Flows Through Nodes

Each node receives the full state dict and returns a partial update dict. LangGraph merges the update into the state automatically.

Example: `validator_node` returns:
```python
{
    "validation_report": report.model_dump_json(),
    "validation_passed": report.passed,
    "validation_score": report.score,
    "messages": state["messages"] + [new_message],
    "status": "reviewing" if report.passed else "revising",
}
```

The graph is compiled once at module level and reused across all sessions.

---

## Real-Time Communication

### Architecture

```
Browser                    FastAPI                    LangGraph Node
   │                          │                            │
   │── WS Connect ──────────►│                            │
   │◄── event_history ───────│                            │
   │                          │                            │
   │                          │   cb = event_bus.create_callback(session_id)
   │                          │                            │
   │                          │◄── AgentStartedEvent ─────│
   │◄── agent_started ───────│                            │
   │                          │◄── FindingDiscoveredEvent ─│
   │◄── finding_discovered ──│                            │
   │                          │◄── AgentCompletedEvent ───│
   │◄── agent_completed ─────│                            │
   │                          │                            │
   │── { type: "ping" } ────►│                            │
   │◄── { type: "pong" } ───│                            │
```

### Event Bus

The `EventBus` is an in-memory pub/sub singleton:

- **Subscription model**: Multiple listeners per session (multiple browser tabs)
- **History**: Keeps last 100 events per session for reconnecting clients
- **Callback factory**: `event_bus.create_callback(session_id)` returns an async function that nodes call to emit events
- **Dead listener cleanup**: If a listener throws (e.g., client disconnected), it's automatically removed

### Why Event Bus Instead of Passing Callbacks?

LangGraph's `graph.ainvoke(state)` only forwards the state dict to nodes — it does **not** pass extra parameters. So we can't pass an `event_callback` function through the graph. Instead, each node creates its own callback via the module-level `event_bus` singleton:

```python
async def architect_design_node(state: ArchAdvisorState) -> dict:
    cb = event_bus.create_callback(state["session_id"])
    await cb(AgentStartedEvent(...).model_dump())
    # ... run agent ...
    await cb(AgentCompletedEvent(...).model_dump())
```

### WebSocket Protocol

**Server → Client**: JSON events (agent_started, finding_discovered, session_complete, etc.)

**Client → Server**: JSON commands
- `{ "type": "cancel" }` — Request cancellation
- `{ "type": "force_proceed" }` — Skip remaining debate rounds
- `{ "type": "ping" }` — Keep-alive

**On Connect**: Server sends full event history so late joiners/reconnecting clients get the complete picture.

### Frontend WebSocket Hook

The `useWebSocket` hook provides:
- Automatic connection to `/ws/sessions/{sessionId}`
- Reconnection with exponential backoff (1s, 2s, 4s... up to 5 retries)
- Connection status (`connected: boolean`)
- Event accumulator (`events: WebSocketEvent[]`)
- Callback for specific event types (`onEvent`)

---

## Session & Storage Layer

### Redis Session Manager

```
Key: archadvisor:session:{session_id}
Value: JSON-serialized workflow state
TTL: 24 hours (86400 seconds)
```

Operations:
- `create()` — Store initial state, add to recent sessions list (capped at 100)
- `get()` / `update()` — Read/partial-update session state
- `add_message()` — Append agent message to conversation history
- `store_output()` — Store final rendered output (document, diagrams, metadata)
- `list_recent()` — Return last N session IDs

### Why Redis?

- Sessions are ephemeral (24h TTL) — no need for a SQL database
- Fast reads for polling fallback (frontend polls every 3s)
- Built-in TTL expiration handles cleanup
- Docker Compose includes Redis with volume persistence

### ChromaDB (RAG)

- Stores past architecture embeddings for retrieval
- Queried during `retrieve_context` node to find similar designs
- File-based persistence at `./data/chroma`
- Currently partially implemented (TODO in codebase)

---

## Frontend Architecture

### View State Machine

```
        ┌──────────┐
        │  input   │ ← User writes requirements
        └────┬─────┘
             │ POST /sessions (202)
             ▼
        ┌──────────┐
        │processing│ ← WebSocket events + polling
        └────┬─────┘
             │ session_complete event
             ├──────────────────┐
             ▼                  ▼
        ┌──────────┐      ┌──────────┐
        │ results  │      │  error   │ ← on error/cancel
        └──────────┘      └──────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| `App.tsx` | View state machine, session ID management, preferences |
| `Sidebar` | Navigation, backend health indicator, settings panel, recent sessions |
| `InputView` | Requirements textarea, template cards, validation, session creation |
| `ProcessingView` | Agent pipeline visualization, live event feed, WebSocket connection indicator |
| `ResultsView` | 4-tab output view (Document, Diagrams, Conversation, Metrics) |

### ProcessingView — Two-Column Layout

```
┌────────────────────────────┬─────────────────────────────┐
│  Agent Pipeline             │  Live Activity Feed          │
│                             │                              │
│  ✅ RAG Retrieval   1.2s    │  🏗️ Architect started        │
│  ✅ Architect       8.3s    │  💭 Analyzing requirements    │
│  ✅ Validator       0.05s   │  ✅ Architect completed 8.3s  │
│  🟢 Devil's Adv.   ...     │  ⚖️ Validator: 85/100 PASS   │
│  ⬜ Cost Analyzer           │  😈 DA: Found 3 issues       │
│  ⬜ Documentation           │  🔴 CRITICAL: Database SPOF  │
│                             │  🟡 MEDIUM: No auth strategy  │
│                             │  ...                          │
└────────────────────────────┴─────────────────────────────┘
```

### ResultsView — Four Tabs

1. **Document** — Rendered markdown with `react-markdown` + `remark-gfm`, Mermaid diagrams rendered as SVG via `mermaid.render()`, download as `.md`
2. **Diagrams** — Grid of all Mermaid diagrams with copy-to-clipboard
3. **Conversation** — Chronological agent messages grouped by debate round
4. **Metrics** — Summary cards, per-agent breakdown table, cost pie chart, duration bar chart (Recharts)

---

## Key Design Decisions

### 1. Adversarial Multi-Agent over Single-Agent

**Decision**: Use separate Architect and Devil's Advocate agents in a debate loop.

**Why**: A single agent asked to "design and critique" tends to be overly favorable to its own design. Separate agents with distinct personas (optimistic architect vs skeptical SRE) produce more thorough reviews. The debate loop forces the architect to defend or revise decisions.

**Trade-off**: 2-3x more LLM calls (~$0.09 extra per debate round), but significantly better output quality.

### 2. Deterministic Validation Gate Before LLM Review

**Decision**: Run 7 rule-based validators before the Devil's Advocate.

**Why**: Many issues (missing fields, SPOFs, known contradictions) can be caught deterministically in <50ms for $0.00. This prevents wasting ~$0.06 (DA review + Architect revision) on issues that a rule engine can catch instantly. The DA can then focus on higher-level architectural concerns.

**Trade-off**: Maintaining reference data (SLA benchmarks, throughput limits) requires updates as cloud services evolve.

### 3. LangGraph for Orchestration

**Decision**: Use LangGraph's `StateGraph` with conditional edges instead of a simple sequential pipeline.

**Why**: The workflow has two conditional loops (validation and debate) that need state-based routing. LangGraph provides:
- Typed state schema with automatic merging
- Conditional edges with routing functions
- Built-in support for cyclic graphs
- Deterministic execution (same state → same path)

**Trade-off**: LangGraph's `ainvoke` doesn't forward extra parameters to nodes, so we needed the event bus pattern for real-time event emission.

### 4. Event Bus Singleton over Callback Threading

**Decision**: Use a module-level `EventBus` singleton instead of passing event callbacks through the graph.

**Why**: LangGraph nodes only receive the state dict — there's no mechanism to pass extra parameters like `event_callback`. The event bus pattern decouples event emission from graph execution. Nodes use `event_bus.create_callback(state["session_id"])` to get a session-scoped emitter.

**Trade-off**: Module-level singleton is harder to test in isolation, but avoids complex dependency injection through the graph.

### 5. Redis over SQL Database

**Decision**: Use Redis as the sole data store (no PostgreSQL/SQLite).

**Why**: All session data is ephemeral (24h TTL). There are no relational queries, no schema migrations, no joins. Redis provides:
- Sub-millisecond reads for polling
- Built-in TTL for automatic cleanup
- JSON serialization for complex state
- List operations for recent sessions

**Trade-off**: No durable storage — if Redis restarts without persistence, active sessions are lost. Acceptable for a design tool where users can re-run.

### 6. WebSocket + Polling Dual Strategy

**Decision**: WebSocket for real-time events with HTTP polling as fallback.

**Why**: WebSocket provides instant event delivery for the processing view. But WebSocket connections can drop (proxies, network changes), so the frontend also polls `GET /sessions/{id}` every 3 seconds. The polling detects completion even if the WebSocket reconnection fails.

**Trade-off**: Slightly more backend load from polling, but guarantees the user never gets stuck on a "processing" screen.

### 7. Structured JSON Agent Outputs

**Decision**: All agents output structured JSON, not free-form text.

**Why**: Downstream consumers (validators, other agents, frontend) need to programmatically access specific fields. JSON schemas enforced in system prompts ensure consistent structure. The Documentation agent converts everything to Markdown as the final step.

**Trade-off**: JSON formatting instructions consume prompt tokens and occasionally produce malformed JSON. The `BaseAgent` includes regex-based fallback parsing for robustness.
