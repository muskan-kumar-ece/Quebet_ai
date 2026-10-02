# QUEBET AI — DevOps & Deployment
> Version 1.0 | Infrastructure Engineering | CI/CD & Operations

---

## 1. Infrastructure Philosophy

QUEBET AI's deployment architecture is built around two operational principles:

1. **Zero-downtime by default.** Every deployment, every database migration, every configuration change can be applied without user-visible downtime. Hardware engineers work at odd hours; the platform must be available 24/7.

2. **Observable over opaque.** Every system component emits structured metrics, traces, and logs. When something goes wrong at 2am, the on-call engineer has complete context within 3 minutes of receiving an alert — not 30 minutes of log hunting.

---

## 2. Docker Architecture

### Container Definitions

```
services/
├── nextjs_bff          (Node.js 20 Alpine, 256MB limit)
│   CMD: node .next/standalone/server.js
│   Health: GET /api/health → 200
│   Env: NEXTAUTH_SECRET, FASTAPI_URL, REDIS_URL
│
├── fastapi_app         (Python 3.11 slim, 512MB limit)
│   CMD: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
│   Health: GET /api/v1/health → { status: "ok", version: "...", db: "ok" }
│   Env: DATABASE_URL, REDIS_URL, NEO4J_URI, AI_PROVIDER, ANTHROPIC_API_KEY
│
├── celery_worker       (Python 3.11 slim, 1GB limit — LLM responses are large)
│   CMD: celery -A worker.celery_app worker --concurrency=4 --queues=high_priority,default,low_priority
│   Health: celery inspect ping
│   Env: Same as fastapi_app
│
├── celery_beat         (Python 3.11 slim, 128MB limit)
│   CMD: celery -A worker.celery_app beat --schedule=/tmp/celerybeat-schedule
│   Purpose: Scheduled tasks (embedding batch jobs, stale cache cleanup)
│
├── flower              (Internal only — Celery monitoring UI)
│   Port: 5555 (not exposed externally)
│
└── chromadb            (Official ChromaDB image, 2GB limit — embeddings in memory)
    CMD: chroma run --host 0.0.0.0 --port 8001
    Volume: /data/chromadb → persistent volume
```

### docker-compose.yml (Development)

```yaml
version: '3.9'
services:
  nextjs_bff:
    build: ./ai_electronics_web
    ports: ["3000:3000"]
    depends_on: [fastapi_app, redis]
    environment:
      FASTAPI_URL: http://fastapi_app:8000
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      REDIS_URL: redis://redis:6379

  fastapi_app:
    build: ./ai_electronics_backend
    ports: ["8000:8000"]
    depends_on: [postgres, redis, neo4j, chromadb]
    environment:
      DATABASE_URL: postgresql+asyncpg://quebet:${DB_PASS}@postgres:5432/quebet
      REDIS_URL: redis://redis:6379
      NEO4J_URI: bolt://neo4j:7687
      AI_PROVIDER: ${AI_PROVIDER:-claude}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}

  celery_worker:
    build: ./ai_electronics_backend
    command: celery -A worker.celery_app worker --concurrency=4 -Q high_priority,default,low_priority
    depends_on: [fastapi_app, redis]
    environment:  # same as fastapi_app

  postgres:
    image: postgres:15-alpine
    volumes: [postgres_data:/var/lib/postgresql/data]
    environment:
      POSTGRES_DB: quebet
      POSTGRES_PASSWORD: ${DB_PASS}

  redis:
    image: redis:7-alpine
    volumes: [redis_data:/data]
    command: redis-server --appendonly yes  # Persistence enabled

  neo4j:
    image: neo4j:5-community
    volumes: [neo4j_data:/data]
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASS}

  chromadb:
    image: chromadb/chroma:latest
    volumes: [chroma_data:/chroma/chroma]
    ports: ["8001:8001"]

volumes:
  postgres_data: neo4j_data: redis_data: chroma_data:
```

---

## 3. CI/CD Pipeline (GitHub Actions)

### Branch Strategy

```
main          ← Production. Only receives merges from release/* branches.
develop       ← Integration branch. All feature PRs merge here first.
feature/*     ← Individual feature branches
hotfix/*      ← Emergency production fixes. Merges directly to main + develop.
release/vX.Y  ← Release candidates. Branched from develop, merged to main.
```

### Pipeline: Feature PR

```yaml
# .github/workflows/pr.yml
name: PR Validation

on: pull_request

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres: { image: postgres:15-alpine }
      redis: { image: redis:7-alpine }

    steps:
      - uses: actions/checkout@v4

      - name: Python setup
        uses: actions/setup-python@v4
        with: { python-version: '3.11' }

      - name: Install backend deps
        run: pip install -r requirements-dev.txt

      - name: Run unit tests
        run: pytest tests/unit/ -v --tb=short --cov=app --cov-report=xml

      - name: Run integration tests (subset — fast)
        run: pytest tests/integration/ -v -m "not slow"

      - name: Coverage check
        run: |
          coverage report --fail-under=80
          # Enforce minimum 80% test coverage on all changed files

      - name: Node.js setup
        uses: actions/setup-node@v4
        with: { node-version: '20' }

      - name: Frontend build + type check
        run: |
          cd ai_electronics_web
          npm ci
          npm run type-check
          npm run build

      - name: Prompt regression test
        run: python scripts/test_prompts.py --sample-size 20
        # Run 20 historical prompt/response pairs through updated prompts
        # Fails if quality drops >10%
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY_TEST }}
```

### Pipeline: Merge to Main (Deploy to Production)

```yaml
# .github/workflows/deploy_prod.yml
name: Production Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval

    steps:
      - uses: actions/checkout@v4

      - name: Build Docker images
        run: |
          docker build -t quebet/backend:${{ github.sha }} ./ai_electronics_backend
          docker build -t quebet/frontend:${{ github.sha }} ./ai_electronics_web

      - name: Push to ECR
        run: |
          aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_URL
          docker push quebet/backend:${{ github.sha }}
          docker push quebet/frontend:${{ github.sha }}

      - name: Run DB migrations (pre-deploy)
        run: |
          # Run migrations against production DB before deploying new code
          # Migrations must be backward-compatible (old code + new schema must work)
          docker run quebet/backend:${{ github.sha }} alembic upgrade head

      - name: Deploy to ECS (Blue-Green)
        run: |
          aws ecs update-service \
            --cluster quebet-prod \
            --service quebet-backend \
            --task-definition quebet-backend:$NEW_TASK_DEF_REVISION \
            --deployment-configuration "maximumPercent=200,minimumHealthyPercent=100"
          # ECS rolls new containers alongside old ones, waits for health checks,
          # then drains and terminates old containers. Zero downtime.

      - name: Smoke tests (post-deploy)
        run: python scripts/smoke_tests.py --env production
        # Verifies: auth works, AI endpoint returns 200, job queue processes

      - name: Notify Slack
        if: always()
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: "Production deploy ${{ github.sha }}: ${{ job.status }}"
```

---

## 4. Kubernetes Architecture (Scale Mode)

When ECS limits are reached (~50 Celery workers), the platform migrates to Kubernetes:

```yaml
# k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quebet-fastapi
spec:
  replicas: 3
  selector:
    matchLabels: { app: quebet-fastapi }
  template:
    spec:
      containers:
        - name: fastapi
          image: quebet/backend:latest
          resources:
            requests: { cpu: "500m", memory: "512Mi" }
            limits: { cpu: "2000m", memory: "1Gi" }
          livenessProbe:
            httpGet: { path: /api/v1/health, port: 8000 }
            periodSeconds: 10
          readinessProbe:
            httpGet: { path: /api/v1/ready, port: 8000 }
            initialDelaySeconds: 5

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: quebet-fastapi-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: quebet-fastapi
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: External
      external:
        metric:
          name: celery_queue_depth  # Custom metric from Prometheus
        target:
          type: AverageValue
          averageValue: 50  # Scale workers when queue > 50 tasks
```

---

## 5. Observability Stack

### Three Pillars

**Logs (Loki + Grafana):**
- All application logs in structured JSON format
- Log levels: `DEBUG` (dev only), `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- Every log line includes: `trace_id`, `user_id`, `service`, `version`
- Log shipping: Promtail agent → Loki → Grafana

**Metrics (Prometheus + Grafana):**
```python
# Custom metrics registered at startup

# LLM call metrics
llm_call_duration_seconds = Histogram(
    'llm_call_duration_seconds',
    'LLM API call latency',
    ['provider', 'model', 'feature', 'cached']
)
llm_call_cost_usd = Counter(
    'llm_call_cost_usd_total',
    'Cumulative LLM API cost in USD',
    ['provider', 'model', 'feature']
)
llm_validation_result = Counter(
    'llm_validation_result_total',
    'AI output validation outcomes',
    ['feature', 'stage', 'result']  # result: pass|fail|repair|escalate
)

# Queue metrics
celery_queue_depth = Gauge(
    'celery_queue_depth',
    'Number of tasks in Celery queue',
    ['queue_name']
)
job_completion_duration = Histogram(
    'job_completion_duration_seconds',
    'End-to-end job completion time',
    ['job_type', 'status']
)

# Business metrics
active_users_gauge = Gauge('active_users_1h', 'Users active in last hour', ['plan'])
daily_generations_counter = Counter('daily_generations_total', 'AI generations', ['feature', 'plan'])
```

**Traces (OpenTelemetry → Jaeger/Tempo):**
```python
# Every request gets a trace that follows it through BFF → FastAPI → Celery worker
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor

FastAPIInstrumentor.instrument_app(app)
CeleryInstrumentor().instrument()

# Custom span for LLM calls
tracer = trace.get_tracer("quebet.ai.llm")
with tracer.start_as_current_span("llm.complete") as span:
    span.set_attribute("llm.provider", provider_name)
    span.set_attribute("llm.model", model_name)
    span.set_attribute("llm.feature", feature_name)
    response = await provider.complete(system, user)
    span.set_attribute("llm.input_tokens", response.input_tokens)
    span.set_attribute("llm.output_tokens", response.output_tokens)
    span.set_attribute("llm.cached", response.cached)
```

---

## 6. Alerting Rules

```yaml
# prometheus-alerts.yml

groups:
  - name: quebet_critical
    rules:
      - alert: LLMErrorRateHigh
        expr: rate(llm_validation_result_total{result="fail"}[5m]) / rate(llm_validation_result_total[5m]) > 0.05
        for: 2m
        annotations:
          summary: "LLM error rate exceeded 5% — prompt or provider issue"
          runbook: "https://internal.quebet.ai/runbooks/llm-errors"
        labels: { severity: critical }

      - alert: APICostRunaway
        expr: increase(llm_call_cost_usd_total[1h]) > 50
        annotations:
          summary: "AI API cost exceeded $50 in 1 hour — possible runaway loop"
        labels: { severity: critical }

      - alert: CeleryQueueBacklog
        expr: celery_queue_depth{queue_name="high_priority"} > 100
        for: 5m
        annotations:
          summary: "High-priority queue backlog — user-facing vision tasks delayed"
        labels: { severity: warning }

      - alert: DatabaseConnectionPoolExhausted
        expr: pg_pool_available_connections < 5
        for: 1m
        labels: { severity: critical }

      - alert: RedisMemoryHigh
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.85
        annotations:
          summary: "Redis memory above 85% — cache evictions may increase LLM costs"
        labels: { severity: warning }
```

---

## 7. Database Operations

### PostgreSQL Migrations (Zero-Downtime)

All migrations follow the expand-contract pattern:
1. **Expand:** Add new column (nullable, no default) — old code ignores it, new code uses it
2. **Deploy new code:** Uses new column
3. **Contract:** Remove old column (in a separate, later migration)

Never: add NOT NULL constraint to existing column in one migration (breaks running old instances during deployment).

### Backup Strategy

| Database | Backup Method | Frequency | Retention | RTO | RPO |
|---|---|---|---|---|---|
| PostgreSQL | RDS automated snapshots | Daily + continuous WAL | 30 days | 1 hour | 5 minutes |
| Redis | AOF persistence + periodic RDB snapshots | Every 15 minutes | 7 days | 15 minutes | 15 minutes |
| Neo4j | Aura managed backups | Daily | 14 days | 4 hours | 24 hours |
| ChromaDB | Volume snapshots (EBS) | Daily | 14 days | 2 hours | 24 hours |
| R2/S3 | Versioning enabled | Continuous | 90 days | 30 minutes | near-zero |

### Disaster Recovery

Recovery Time Objective (RTO): 2 hours for full service restoration
Recovery Point Objective (RPO): 5 minutes (PostgreSQL WAL replication)

DR runbook:
1. Activate standby RDS instance (Multi-AZ automatic failover or manual promotion)
2. Point application at new PostgreSQL endpoint (via environment variable or Route53 update)
3. Restore Redis from most recent RDB snapshot
4. Neo4j: restore from Aura backup or WAL replay
5. ChromaDB: restore from EBS snapshot
6. Smoke test suite confirms functionality
7. Notify users of any data loss window

---

## 8. Blue-Green and Canary Deployments

### Blue-Green (Standard)

Maintained by AWS ECS deployment configuration:
- `maximumPercent=200`: new tasks start before old ones stop
- `minimumHealthyPercent=100`: old tasks stay until new ones are healthy
- Health checks pass → old tasks drained over 30 seconds (existing requests complete)
- Result: zero downtime, instant rollback by reverting task definition

### Canary (High-Risk Releases)

For releases with significant prompt changes or new model versions:
1. Deploy new version to 10% of traffic (Route53 weighted routing)
2. Monitor quality metrics for 30 minutes:
   - validation pass rate
   - confidence score distribution
   - error rate
   - user satisfaction signal (thumbs up/down on AI responses)
3. If metrics match or exceed baseline → promote to 100%
4. If any metric degrades → rollback 10% slice immediately (no user impact)

---

*Document Owner: Platform Infrastructure Team*
*Last Updated: Q1 2025*
