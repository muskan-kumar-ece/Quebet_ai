# QUEBET AI — Database & RAG Architecture
> Version 1.0 | Data Architecture | Retrieval-Augmented Generation Design

---

## 1. Data Architecture Philosophy

QUEBET AI has four distinct data stores, each chosen for a specific access pattern. Using a single database for all four access patterns would force tradeoffs that degrade performance at scale.

| Store | Access Pattern | Why This Store |
|---|---|---|
| PostgreSQL | Relational, ACID transactions, complex queries | User accounts, projects, analysis results need consistent relations and foreign key integrity |
| Neo4j | Graph traversal: "what's connected to X?" | Component→Circuit→Failure→Fix is a graph; 5-hop traversals that take 10 SQL joins take 1 Cypher line |
| ChromaDB | Approximate nearest neighbor (ANN) search | "Find circuits semantically similar to this description" requires vector similarity, not keyword matching |
| Redis | High-frequency key-value, TTL-based expiry | Cache, rate limiting, job queue, session state — all need microsecond reads and automatic expiry |

---

## 2. PostgreSQL Schema

### Schema Philosophy

- Every table has `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` — UUIDs prevent ID enumeration attacks and allow distributed ID generation
- Every table has `created_at TIMESTAMPTZ DEFAULT NOW()` and `updated_at TIMESTAMPTZ`
- Soft deletes: `deleted_at TIMESTAMPTZ NULL` — rows are never hard-deleted (audit requirements); filtered in ORM base class
- JSON columns (`JSONB`) for flexible structured data (circuit descriptions, analysis details) — avoids schema migrations for evolving AI output formats while preserving queryability via PostgreSQL JSON operators

### Core Schema

```sql
CREATE TYPE plan_type AS ENUM ('free', 'plus', 'pro', 'team', 'enterprise');

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT,  -- NULL for OAuth-only users
    name TEXT,
    plan plan_type NOT NULL DEFAULT 'free',  -- ENUM: free, plus, pro, team, enterprise
    tenant_id UUID REFERENCES tenants(id),   -- NULL for individual users
    skill_level TEXT DEFAULT 'beginner',      -- beginner | intermediate | advanced
    preferred_model TEXT DEFAULT NULL,        -- OpenRouter model ID if user customized (Plus/Pro/Enterprise)
    daily_generation_count INTEGER DEFAULT 0,
    daily_count_reset_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL
);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tenant_id ON users(tenant_id);

-- Tenants (Enterprise accounts)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'enterprise',
    max_seats INTEGER,
    neo4j_namespace TEXT UNIQUE,  -- Namespace prefix for tenant's graph nodes
    chroma_collection_prefix TEXT UNIQUE,  -- ChromaDB collection prefix
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Projects
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id UUID REFERENCES tenants(id),
    name TEXT NOT NULL,
    module_type TEXT NOT NULL,  -- design | analysis | troubleshoot | components | learn
    circuit_data JSONB,         -- Full circuit description at creation time
    board_type TEXT,            -- arduino | esp32 | stm32 | custom
    tags TEXT[],
    is_shared BOOLEAN DEFAULT FALSE,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL
);
CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_projects_module_type ON projects(module_type);
CREATE INDEX idx_projects_circuit_data ON projects USING GIN (circuit_data);

-- Analysis Results (versioned per project)
CREATE TABLE analysis_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    analysis_type TEXT NOT NULL,  -- risk_score | failure_prediction | thermal | emi
    version INTEGER NOT NULL,     -- increments on each re-run; enables v1 vs v2 comparison
    score NUMERIC(5,2),           -- For scored analyses (0-100)
    result_data JSONB NOT NULL,   -- Full structured output
    provider TEXT,                -- Which LLM produced this result
    model TEXT,
    confidence NUMERIC(4,3),
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd NUMERIC(10,6),
    validation_passed BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_analysis_results_project_id ON analysis_results(project_id);
CREATE INDEX idx_analysis_results_type_version ON analysis_results(analysis_type, version);

-- Jobs (async task tracking)
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | running | done | failed
    progress INTEGER DEFAULT 0,             -- 0-100
    celery_task_id TEXT UNIQUE,
    result JSONB,
    error_detail TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
CREATE INDEX idx_jobs_user_id_status ON jobs(user_id, status);

-- AI Interaction Audit Log (append-only, partitioned by month)
CREATE TABLE ai_audit_log (
    id BIGSERIAL,
    trace_id UUID NOT NULL,
    user_id UUID NOT NULL,
    feature TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd NUMERIC(10,6),
    latency_ms INTEGER,
    cached BOOLEAN,
    validation_stage_failed TEXT,  -- NULL = all passed
    confidence NUMERIC(4,3),
    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);
-- Create monthly partitions: ai_audit_log_2025_01, etc.
-- Old partitions archived to cold storage after 6 months

-- Admin-Managed AI Model Catalog (OpenRouter)
CREATE TABLE model_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id TEXT NOT NULL UNIQUE,         -- e.g. "anthropic/claude-sonnet-4", "deepseek/deepseek-chat-v3-0324"
    display_name TEXT NOT NULL,             -- e.g. "Claude Sonnet 4"
    provider TEXT NOT NULL,                -- e.g. "anthropic", "openai", "google", "deepseek"
    is_vision_capable BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    cost_per_1k_input NUMERIC(10,6),
    cost_per_1k_output NUMERIC(10,6),
    max_context_tokens INTEGER,
    supports_json_mode BOOLEAN DEFAULT TRUE,
    supports_streaming BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Plan Model Routing & Fallback Priorities
CREATE TABLE plan_model_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan plan_type NOT NULL,
    task_type TEXT NOT NULL,                -- default | risk_score | project_builder | failure_prediction | ...
    model_id TEXT NOT NULL REFERENCES model_configs(model_id),
    priority INTEGER DEFAULT 0,            -- Higher = preferred (fallback ordering)
    is_user_selectable BOOLEAN DEFAULT FALSE, -- Shows in user's model dropdown
    is_default BOOLEAN DEFAULT FALSE,      -- Plan's default model for this task
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_plan_model_task ON plan_model_access(plan, task_type, model_id);

-- Dynamic Plan Rate Limits (Admin-Configurable without code deployment)
CREATE TABLE plan_rate_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan plan_type NOT NULL UNIQUE,
    daily_generations INTEGER NOT NULL,
    daily_vision_calls INTEGER,            -- NULL = unlimited
    max_concurrent_jobs INTEGER NOT NULL,
    bff_requests_per_minute INTEGER NOT NULL,
    api_calls_per_day INTEGER,             -- NULL = no external API access
    max_simulation_components INTEGER,
    max_projects INTEGER,                  -- NULL = unlimited
    project_retention_days INTEGER,        -- NULL = unlimited
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by UUID REFERENCES users(id)
);
```

---

## 3. Neo4j Knowledge Graph

### Node Types

```cypher
// Core entity nodes
(:Component { id: UUID, name: String, category: String, package: String,
              specs: Map, india_available: Boolean, tenant_id: String? })

(:Circuit { id: UUID, name: String, topology: String, application: String,
             description: String, board_type: String, verified: Boolean,
             source: String, created_at: DateTime, tenant_id: String? })

(:Failure { id: UUID, category: String, description: String,
            symptom: String, severity: String, frequency: Integer,
            created_at: DateTime })

(:Fix { id: UUID, description: String, component_change: String?,
        schematic_change: String?, upvotes: Integer, verified: Boolean })

(:Symptom { id: UUID, description: String, normalized_text: String })

(:DatasheetSection { id: UUID, component_id: UUID, section_title: String,
                     content_summary: String })
```

### Relationship Types

```cypher
// Component → Circuit relationships
(:Component)-[:APPEARS_IN { role: String, position: String? }]->(:Circuit)
(:Component)-[:REPLACES { compatibility: String, notes: String }]->(:Component)
(:Component)-[:COMPATIBLE_WITH]->(:Component)

// Failure relationships
(:Circuit)-[:HAS_FAILURE { frequency: Integer, confirmed: Boolean }]->(:Failure)
(:Component)-[:CAUSES_FAILURE { mechanism: String }]->(:Failure)
(:Failure)-[:MANIFESTS_AS]->(:Symptom)
(:Failure)-[:FIXED_BY { effectiveness: Float, upvotes: Integer }]->(:Fix)
(:Fix)-[:USES_COMPONENT { reason: String }]->(:Component)

// Knowledge building relationships
(:Symptom)-[:INDICATES { confidence: Float }]->(:Failure)
(:DatasheetSection)-[:DESCRIBES]->(:Component)
```

### Key Cypher Queries

```cypher
// Feature 10 — Repair Technician: Find likely faulty components from symptom
MATCH (s:Symptom)
WHERE toLower(s.normalized_text) CONTAINS toLower($symptom_keyword)
MATCH (s)-[:INDICATES]->(f:Failure)-[:IN_COMPONENT|CAUSES_FAILURE]-(c:Component)
RETURN c.name, c.category, count(f) as failure_frequency,
       collect(DISTINCT f.description)[0..3] as failure_types,
       collect(DISTINCT f.fix)[0..2] as common_fixes
ORDER BY failure_frequency DESC
LIMIT 5

// Feature 19 — Knowledge Graph Viewer: Component ecosystem
MATCH path = (c:Component {name: $component_name})
             -[:APPEARS_IN|CAUSES_FAILURE|REPLACES*1..2]-
             (related)
RETURN path LIMIT 50

// Feature 25 — Context enrichment: Circuit history for RAG
MATCH (c:Circuit)-[:HAS_FAILURE]->(f:Failure)-[:FIXED_BY]->(fix:Fix)
WHERE c.topology = $topology
RETURN c.name, f.description, f.severity, fix.description
ORDER BY f.frequency DESC
LIMIT 10

// Knowledge graph growth: Add new failure case from user report
MERGE (s:Symptom {normalized_text: $symptom})
MERGE (f:Failure {id: $failure_id, description: $description, symptom: $symptom})
MERGE (c:Component {name: $component_name})
MERGE (s)-[:INDICATES {confidence: $confidence}]->(f)
MERGE (f)-[:CAUSES_FAILURE {mechanism: $mechanism}]-(c)
SET f.frequency = f.frequency + 1
```

### Tenant Isolation in Neo4j

Enterprise tenants' nodes are prefixed with tenant namespace:
```cypher
// Enterprise query: only see own tenant's nodes + global public nodes
MATCH (c:Component)
WHERE c.tenant_id = $tenant_id OR c.tenant_id IS NULL
// Global nodes have tenant_id = null; tenant nodes have tenant_id = "tenant-uuid"
```

---

## 4. ChromaDB Vector Store

### Collection Architecture

```python
# Four collections with distinct purposes
COLLECTIONS = {
    "electronics_kb": {
        "description": "Static reference circuits, failure cases, components from electronics-kb",
        "size": "~50K vectors at launch, stable",
        "embedding_model": "text-embedding-3-small",
        "metadata_schema": {
            "source_id": str,          # electronics-kb JSON entry ID
            "domain": str,             # "circuit" | "failure" | "component" | "datasheet"
            "component_type": str,     # Category for filtering
            "circuit_topology": str,   # "buck_converter" | "h_bridge" etc.
            "severity": str,           # For failure cases
            "india_available": bool,   # For component alternatives filter
            "verified": bool,          # Human-verified entries
            "created_at": str          # ISO timestamp
        }
    },
    "datasheets": {
        "description": "Chunked text from user-uploaded and system-indexed datasheets",
        "size": "Grows with uploads; ~100K at scale",
        "chunking": "section-aware 512 tokens, 50-token overlap",
        "metadata_schema": {
            "component_name": str,
            "component_id": str,
            "section_title": str,       # "Electrical Characteristics", "Pin Descriptions", etc.
            "page_number": int,
            "datasheet_source": str,    # manufacturer_official | user_upload
            "user_id": str,             # For user-uploaded datasheets
            "tenant_id": str
        }
    },
    "user_projects": {
        "description": "Embeddings of saved user circuit descriptions — personalized RAG",
        "size": "Grows with projects; ~1M at 100K active users",
        "embedding_unit": "full circuit description (no chunking — preserve relational context)",
        "metadata_schema": {
            "project_id": str,
            "user_id": str,
            "tenant_id": str,
            "module_type": str,
            "board_type": str,
            "created_at": str
        },
        "access_pattern": "always filtered by user_id — no cross-user retrieval"
    },
    "failure_cases": {
        "description": "User-reported failures — grows with platform usage",
        "size": "Grows with usage; key long-term data asset",
        "dual_embedding": "Symptom text and root cause text embedded separately, linked by failure_id",
        "metadata_schema": {
            "failure_id": str,
            "embedding_type": str,      # "symptom" | "root_cause"
            "component_name": str,
            "severity": str,
            "upvotes": int,
            "verified": bool,
            "tenant_id": str
        }
    }
}
```

### Embedding Strategies by Domain

```python
# circuits/ — full description embedding (preserve component relationships)
def embed_circuit(circuit: dict) -> str:
    return (
        f"Circuit: {circuit['name']}. "
        f"Topology: {circuit['topology']}. "
        f"Purpose: {circuit['description']}. "
        f"Key components: {', '.join(c['name'] for c in circuit['components'])}. "
        f"Board: {circuit.get('board_type', 'generic')}. "
        f"Application: {circuit.get('application', 'general')}."
    )

# datasheets/ — section-aware chunking
def chunk_datasheet(text: str, component_name: str) -> list[Chunk]:
    sections = split_by_section_headers(text)
    # Headers detected: "Absolute Maximum Ratings", "Electrical Characteristics",
    #                    "Pin Configuration", "Typical Application Circuit", etc.
    chunks = []
    for section in sections:
        # Prepend component name to each chunk for better retrieval
        prefixed_text = f"Component: {component_name}. Section: {section.title}.\n{section.text}"
        if count_tokens(prefixed_text) <= 512:
            chunks.append(Chunk(text=prefixed_text, metadata={"section_title": section.title}))
        else:
            for window in sliding_window(prefixed_text, size=512, overlap=50):
                chunks.append(Chunk(text=window, metadata={"section_title": section.title}))
    return chunks

# failure_cases/ — dual embedding strategy
def embed_failure_case(failure: dict) -> tuple[Embedding, Embedding]:
    symptom_text = f"Symptom: {failure['symptom']}. Circuit: {failure['circuit_type']}."
    cause_text = f"Root cause: {failure['root_cause']}. Component: {failure['component']}. Fix: {failure['fix']}."
    return embed(symptom_text), embed(cause_text)
    # Symptom embedding: for queries like "output voltage drops under load"
    # Cause embedding: for queries like "inadequate output capacitor ESR"
    # Both stored with same failure_id for cross-reference
```

### Retrieval Optimization

```python
async def retrieve_relevant_context(
    query: str,
    collection: str,
    user_id: str,
    tenant_id: Optional[str] = None,
    k: int = 7,
    min_score: float = 0.70
) -> list[RetrievalResult]:
    """
    Optimized retrieval with three-level cache.
    """
    # L3 cache check (15-minute TTL)
    cache_key = f"search:{sha256(collection + query + user_id)}"
    if cached := await redis.get(cache_key):
        return deserialize(cached)

    # L2 cache: check embedding cache
    embed_key = f"embed:{sha256(query)}"
    if cached_embedding := await redis.get(embed_key):
        query_embedding = deserialize(cached_embedding)
    else:
        query_embedding = await embedding_provider.embed(query)
        await redis.setex(embed_key, 86400, serialize(query_embedding))  # 24h TTL

    # Build metadata filter for tenant isolation
    where_filter = build_tenant_filter(user_id, tenant_id, collection)

    # ChromaDB query
    results = chroma_client.get_collection(collection).query(
        query_embeddings=[query_embedding],
        n_results=k,
        where=where_filter,
        include=["documents", "metadatas", "distances"]
    )

    # Filter by minimum similarity threshold
    filtered = [
        RetrievalResult(
            document=doc,
            metadata=meta,
            score=1 - dist  # cosine distance → similarity
        )
        for doc, meta, dist in zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )
        if (1 - dist) >= min_score
    ]

    # Cache result
    await redis.setex(cache_key, 900, serialize(filtered))  # 15-minute TTL
    return filtered
```

---

## 5. Knowledge Ingestion Pipelines

### Startup Seeding (One-Time)

```python
# worker/tasks/knowledge_tasks.py

@celery.task(queue="low_priority")
async def seed_electronics_kb():
    """
    Runs on first deployment. Ingests all static electronics-kb JSON files
    into both Neo4j and ChromaDB.
    """
    for domain in ["components", "circuits", "failure-modes"]:
        files = list(Path(f"packages/electronics-kb/data/{domain}").glob("*.json"))
        for file in files:
            data = json.loads(file.read_text())
            for entry in data:
                # Parallel: Neo4j write + ChromaDB embed
                await asyncio.gather(
                    graph_builder.add_to_graph(entry, domain),
                    embed_and_store(entry, domain)
                )
    logger.info("Electronics KB seeded successfully", extra={"count": total_count})
```

### Continuous Ingestion (User-Driven)

```python
@celery.task(queue="low_priority")
async def ingest_user_project(project_id: str):
    """
    Called whenever a user saves a circuit design.
    Embeds the circuit description for personalized RAG.
    """
    project = await project_repo.get_by_id(project_id)
    circuit_text = embed_circuit(project.circuit_data)
    await chroma_client.get_collection("user_projects").add(
        documents=[circuit_text],
        metadatas=[{ "project_id": project_id, "user_id": project.user_id, ... }],
        ids=[project_id]
    )

@celery.task(queue="low_priority")
async def ingest_failure_report(failure_data: dict):
    """
    Called when a user reports a confirmed hardware failure.
    Adds to Neo4j graph + ChromaDB failure_cases collection.
    """
    # Write to Neo4j
    await graph_builder.add_failure_case(failure_data)
    # Embed both symptom and cause separately
    symptom_embedding, cause_embedding = embed_failure_case(failure_data)
    failure_id = failure_data["id"]
    await chroma_client.get_collection("failure_cases").add(
        documents=[failure_data["symptom"], failure_data["root_cause"]],
        embeddings=[symptom_embedding, cause_embedding],
        metadatas=[
            {"failure_id": failure_id, "embedding_type": "symptom", ...},
            {"failure_id": failure_id, "embedding_type": "root_cause", ...}
        ],
        ids=[f"{failure_id}-symptom", f"{failure_id}-cause"]
    )
```

---

## 6. Deduplication and Quality Control

### Deduplication at Ingestion

Before adding any entry to ChromaDB or Neo4j, a similarity check prevents duplicate content from polluting the corpus:

```python
async def is_duplicate(text: str, collection: str, threshold: float = 0.95) -> bool:
    """
    Returns True if an entry with >95% similarity already exists in the collection.
    Used to prevent duplicate reference circuits from polluting RAG context.
    """
    embedding = await embed_with_cache(text)
    results = chroma_client.get_collection(collection).query(
        query_embeddings=[embedding],
        n_results=1
    )
    if results['distances'][0] and (1 - results['distances'][0][0]) > threshold:
        return True
    return False
```

### Knowledge Graph Quality

- All entries from `electronics-kb` are marked `verified: True` (curated by team)
- User-contributed failure cases start as `verified: False`
- After 3 upvotes from other engineers → promoted to `verified: True`
- Unverified entries included in retrieval but weighted lower (similarity × 0.7 for unverified)

---

*Document Owner: Data Architecture Team*
*Last Updated: Q1 2025*
