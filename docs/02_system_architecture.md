# QUEBET AI — System Architecture
> Version 1.0 | Senior Architect Review | Production Blueprint

---

## 1. Architecture Philosophy

QUEBET AI is designed around three architectural invariants:

1. **No single point of failure for AI.** Every LLM call has a fallback provider, a cache layer, and a retry strategy. The platform degrades gracefully — never fails completely — when any external AI vendor has an outage.

2. **Sync for perception; async for computation.** User-facing interactions (streaming explanations, form submissions, search) are synchronous and low-latency. Heavy computation (simulation, PCB analysis, embedding generation) is always asynchronous with job-tracking. This prevents LLM timeouts from corrupting the user experience.

3. **Data is a first-class product.** Every interaction enriches the knowledge graph. The architecture treats Neo4j, ChromaDB, and PostgreSQL not as storage backends but as the product's core intelligence accumulator. Schema decisions, indexing strategies, and ingestion pipelines are reviewed with the same rigor as feature code.

---

## 2. High-Level System Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│                                                                               │
│  Browser (Next.js 14)    Mobile PWA    CLI / API Client (future)            │
│  React Server Components + Client Components + Streaming SSE                 │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ HTTPS / WSS
┌───────────────────────────────▼─────────────────────────────────────────────┐
│                         EDGE / CDN LAYER                                     │
│                                                                               │
│  Cloudflare CDN (static assets, PCB images)                                  │
│  Cloudflare R2 (user-uploaded files: PCB photos, datasheets, BOM CSVs)      │
│  DDoS protection + WAF at edge                                                │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────────────┐
│                    BFF / NEXT.JS API GATEWAY LAYER                           │
│                                                                               │
│  /api/proxy/[...path]  — Validates session, injects JWT, rate-limits        │
│  /api/auth/[...]        — NextAuth: Google OAuth + credentials               │
│                                                                               │
│  Responsibilities:                                                            │
│  • Session validation (server-side, NextAuth)                                │
│  • Per-user per-endpoint rate limiting (Redis)                               │
│  • Plan-based feature gating (free/pro/enterprise)                          │
│  • Request sanitization + max body size enforcement                          │
│  • Auth token injection into backend requests                                │
│  • Response compression (gzip >1KB)                                          │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ Internal network (not public)
┌───────────────────────────────▼─────────────────────────────────────────────┐
│                     FASTAPI APPLICATION LAYER                                 │
│                    (Uvicorn ASGI, async Python)                               │
│                                                                               │
│  /api/v1/design/*      /api/v1/analysis/*    /api/v1/troubleshoot/*         │
│  /api/v1/components/*  /api/v1/learn/*       /api/v1/knowledge/*            │
│  /api/v1/projects/*    /api/v1/jobs/*        /api/v1/auth/*                 │
│                                                                               │
│  Dependency injection: get_db(), get_current_user(), get_ai_provider()      │
│  Pydantic request/response validation at every boundary                      │
└───────┬───────────┬────────────┬──────────────┬────────────────────────────┘
        │           │            │              │
        ▼           ▼            ▼              ▼
┌──────────┐  ┌──────────┐  ┌────────┐   ┌──────────────────────────────────┐
│ Services │  │  Repos   │  │  Utils │   │         AI LAYER                  │
│ (Business│  │  (DB I/O)│  │(OpenCV,│   │  provider_factory.py             │
│  Logic)  │  │          │  │ PyMuPDF│   │  claude_provider.py              │
└──────────┘  └──────────┘  │ etc.)  │   │  openai_provider.py              │
                             └────────┘   │  response_cache.py (Redis)       │
                                          └──────────────────────────────────┘
        │
        ▼ (heavy jobs only)
┌───────────────────────────────────────────────────────────────────────────┐
│                        CELERY WORKER LAYER                                 │
│                                                                             │
│  Queue: high_priority   → vision analysis (PCB damage, component ID)      │
│  Queue: default         → simulation, risk scoring, full analysis         │
│  Queue: low_priority    → embedding generation, knowledge graph updates   │
│                                                                             │
│  Broker: Redis (pub/sub)    Result backend: Redis (TTL 24h)               │
└───────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                          │
│                                                                            │
│  PostgreSQL (RDS)    Neo4j (Aura)    ChromaDB    Redis Cluster    R2/S3   │
│  ─ Users             ─ Knowledge     ─ Semantic   ─ Cache          ─ Files │
│  ─ Projects          ─ Graph         ─ Search     ─ Sessions        ─ PDFs │
│  ─ Analysis results  ─ Components    ─ Embeddings ─ Job queue       ─ PCB  │
│  ─ Jobs              ─ Failures                   ─ Rate limits     ─ imgs  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Frontend Architecture

### Stack Rationale

**Next.js 14 App Router** is chosen over alternatives for these specific reasons:

- **React Server Components (RSC)** allow project history pages, component catalogs, and knowledge graph data to be rendered server-side — zero client JavaScript for content that doesn't need interactivity
- **Route Groups** cleanly separate the `(auth)` layout (centered card, no nav) from the `(dashboard)` layout (sidebar + auth guard) without any runtime routing logic
- **API Routes as BFF** means the backend URL is never exposed to the client, and auth token injection happens server-side — zero risk of credential leakage
- **Streaming support** (via `ReadableStream`) handles SSE-based AI response streaming natively

### Component Architecture

```
components/
├── ui/          ← shadcn/ui primitives — never modified directly
├── shared/      ← Domain-agnostic, used in 2+ modules
│                   (RiskScoreMeter, KnowledgeGraphViewer, AIResponseStream,
│                    JobStatusPoller, CircuitDiagramViewer, FileUpload)
└── modules/     ← Feature-specific, one folder per module
                    (design/, analysis/, troubleshoot/, components-intel/,
                     learn/)
```

**Key invariant:** `modules/` components never import from other `modules/` folders. Cross-cutting concerns go to `shared/`. This prevents circular dependencies and makes modules independently removable.

### State Management

| State Type | Tool | Why |
|---|---|---|
| Server state (API data) | TanStack Query | Automatic cache invalidation, background refetch, loading states |
| Global UI state | Zustand | Lightweight, no boilerplate, tree-shake friendly |
| Form state | React Hook Form | Minimal re-renders, built-in validation |
| Auth state | NextAuth session | Server-side validated, no client JWT exposure |

Zustand stores are deliberately thin: `projectStore` (current circuit + results), `aiStore` (provider selection + streaming flag), `sessionStore` (skill level + region). Business logic stays in services; stores only hold view-relevant state.

---

## 4. Backend Architecture

### FastAPI Design Patterns

**Dependency Injection hierarchy:**
```python
# Every protected route uses this chain:
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User: ...

async def get_ai_provider(
    request: Request,
    user: User = Depends(get_current_user)
) -> BaseProvider:
    provider_name = request.headers.get("X-AI-Provider", user.preferred_provider)
    return provider_factory.get(provider_name, user.plan)
```

This means every route that needs AI gets the right provider automatically — free users get routed to cost-optimized models, pro users get premium models — with zero logic duplication across routes.

**Repository pattern enforcement:** Services import repository functions, not SQLAlchemy sessions directly. `project_repo.create(db, data)` — not `db.add(Project(**data))`. This decouples business logic from ORM internals and makes testing trivial (mock the repo, not the DB session).

---

## 5. Async Architecture

### Why Celery Over FastAPI Background Tasks

FastAPI's `BackgroundTasks` are tied to the HTTP worker process. If the worker restarts (deploy, OOM kill, timeout), the background task is lost with no recovery mechanism. Celery workers are independent processes with persistent task queues in Redis — tasks survive worker restarts and can be retried.

### Job Lifecycle

```
POST /analysis/risk-score
    │
    ├── FastAPI validates request (Pydantic) — synchronous, <50ms
    ├── Creates Job record in PostgreSQL: { status: "pending" }
    ├── Enqueues Celery task: risk_score.apply_async(args=[...], queue="default")
    └── Returns: { job_id: "uuid", status: "pending" } — HTTP 202

Frontend:
    JobStatusPoller polls GET /jobs/{job_id} every 2 seconds
        ├── { status: "running", progress: 45 } → show progress bar
        └── { status: "done", result: {...} }  → render result, stop polling

Celery Worker:
    Picks up task from Redis queue
    Executes: services/analysis/risk_scorer.py
    On complete: job_repo.update_status(job_id, "done", result=output)
    On failure: retries up to 3x with exponential backoff (2s, 4s, 8s)
    On final failure: status="failed", result={ error, trace_id }
```

### Queue Priority Design

```
high_priority:  Vision tasks (user holds camera → needs result in <10s)
default:        Risk score, thermal analysis, simulation (15–30s acceptable)
low_priority:   Embedding generation, knowledge graph updates (background, non-blocking)
```

Free plan jobs go into default queue with lower priority weight. Pro plan jobs get priority scheduling within the same queue. Enterprise gets dedicated worker allocation.

---

## 6. Streaming Architecture

AI streaming responses use Server-Sent Events (SSE), not WebSockets. The choice is deliberate:

- SSE is unidirectional (server → client), which matches the use case exactly
- SSE reconnects automatically on connection drop
- SSE works through HTTP proxies and CDNs without special configuration
- WebSockets require stateful connections — expensive at scale

```
FastAPI SSE endpoint:
    async def stream_ai_response(...) -> StreamingResponse:
        async def event_generator():
            async for token in ai_provider.stream(system, user):
                yield f"data: {json.dumps({'token': token})}\n\n"
        return StreamingResponse(event_generator(), media_type="text/event-stream")

Frontend:
    useAIStream.ts:
        const eventSource = new EventSource('/api/proxy/learn/explain')
        eventSource.onmessage = (e) => appendToken(JSON.parse(e.data).token)
```

---

## 7. Caching Architecture

### Three-Tier Cache

```
L1 — Response Cache (Redis, TTL 1h)
     Key: SHA256(model_id + system_prompt + user_prompt)
     Use: Identical LLM requests → skip API call entirely
     Hit rate: ~40% (common questions, same datasheet queries)

L2 — Embedding Cache (Redis, TTL 24h)
     Key: SHA256(text_string)
     Use: Same component description embedded 1000 times → embed once
     Hit rate: ~70% (component names repeat heavily)

L3 — Search Result Cache (Redis, TTL 15min)
     Key: SHA256(collection + embedding + n + filters)
     Use: Same circuit query in active session → reuse ChromaDB results
     Hit rate: ~25% (session-scoped query refinement)
```

**Cache invalidation rules:**
- New KB entry → flush L3 for affected collection
- Prompt template version change → flush L1 for that prompt prefix
- User updates project → flush L2+L3 for user_projects collection

---

## 8. Load Balancing and High Availability

### Stateless Design

Both Next.js BFF and FastAPI are fully stateless. All state lives in Redis (sessions, caches, job queue) or PostgreSQL (persistent data). This means:

- Any BFF instance can handle any request
- Any FastAPI instance can handle any request
- Load balancer can remove/add instances without session loss
- Zero sticky sessions required

### Deployment Topology

```
AWS ALB (or Nginx)
├── Target Group: Next.js BFF (3 replicas minimum, auto-scale to 10)
│   Health check: GET /api/health → 200
└── Target Group: FastAPI (3 replicas minimum, auto-scale to 10)
    Health check: GET /api/v1/health → 200

Redis: ElastiCache cluster (3 nodes, Multi-AZ)
PostgreSQL: RDS Multi-AZ (primary + read replica)
Neo4j: Aura Enterprise or self-hosted with replica
ChromaDB: Single instance (v0.4+) or distributed mode at scale
Celery workers: ECS tasks, auto-scale on queue depth metric
```

### Fault Tolerance Matrix

| Component Failure | Impact | Mitigation |
|---|---|---|
| Primary LLM provider (Anthropic) | AI features degrade | Auto-failover to OpenAI via provider_factory |
| Redis cluster node | Cache miss spike | ElastiCache Multi-AZ auto-failover (<30s) |
| PostgreSQL primary | Write failures | RDS Multi-AZ failover (<60s); reads continue on replica |
| Neo4j | Knowledge graph queries fail | Graceful degradation: skip graph retrieval, use vector only |
| ChromaDB | Semantic search fails | Graceful degradation: skip RAG context, use base prompt |
| Celery worker | Jobs queue up | Auto-scale triggers on queue depth >50 |
| S3/R2 | File upload/retrieval fails | Retry with exponential backoff; surface error to user |

**Principle:** No single external service failure should cause the entire platform to return 500 errors. Every external dependency has a degraded-mode fallback.

---

## 9. CDN and Storage Strategy

### Static Assets
Cloudflare CDN with aggressive caching:
- Static JS/CSS bundles: `Cache-Control: max-age=31536000, immutable` (content-hashed filenames)
- Component SVG icons and images: `Cache-Control: max-age=86400`
- Fonts (self-hosted): `Cache-Control: max-age=31536000` — self-hosted to eliminate Google Fonts latency from India

### User Files (Cloudflare R2 / AWS S3)
- PCB images: uploaded via pre-signed URL from frontend → stored in R2 → served via CDN
- Datasheet PDFs: stored in R2, processed in worker, never cached publicly (potentially proprietary)
- Generated circuit SVGs: stored in R2, served with 24h CDN TTL, regenerated on cache miss
- S3 lifecycle: objects older than 30 days → Glacier (cold storage) → 80% storage cost reduction

---

## 10. Microservice Migration Roadmap

The current architecture is a **modular monolith** — all services run in one FastAPI process, organized into domain folders. This is the correct starting point: easy to develop, deploy, and debug.

**Trigger for microservice extraction:** when a specific domain causes operational issues for other domains (e.g., PCB image processing consuming all CPU, starving simulation requests).

Planned extraction order when scaling requires it:

1. **Vision Service** (first to extract) — GPU-heavy image processing; benefits from isolated scaling
2. **Simulation Service** — CPU-heavy PySpice; benefits from dedicated compute isolation
3. **Knowledge Graph Service** — Neo4j queries; can be read-heavy replica with own connection pool
4. **Notification / Jobs Service** — Celery infrastructure is already logically isolated

**Shared infrastructure that must remain centralized:** Auth validation, Redis, rate limiting. These are cross-cutting; extracting them creates distributed auth complexity with no benefit.

The current file structure is already organized by domain (`services/design/`, `services/analysis/`) — extracting a microservice means moving a folder to its own FastAPI instance and pointing the monolith at it via HTTP. Zero code rewrite required.

---

## 11. Infrastructure as Code

All infrastructure is managed via Terraform (AWS) or Pulumi, with:
- Environment parity: dev / staging / production identical infrastructure, different sizes
- All secrets in AWS Secrets Manager or HashiCorp Vault — never in `.env` files in production
- Database migrations run as pre-deploy jobs (Alembic), not in application startup
- Celery worker count is parameterized — `TF_VAR_worker_count=10` for prod, `=2` for staging

---

*Document Owner: Infrastructure Architecture Team*
*Last Updated: Q1 2025*
