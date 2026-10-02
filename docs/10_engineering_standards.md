# 10 — Engineering Standards
## QUEBET AI Electronics Engineer Platform
> Document Version: 1.0.0 | Classification: Internal Engineering Reference | Status: Active

---

## PREAMBLE

This document defines the non-negotiable engineering standards that govern every line of code, every prompt, every API contract, and every AI output produced by the QUEBET AI platform. These are not style preferences — they are operational constraints that exist because this system operates in engineering-critical workflows where incorrect outputs cause hardware failures, PCB re-spins, and real financial loss.

Every engineer contributing to QUEBET AI must treat this document as a constitution, not a checklist. Deviation from these standards requires a documented RFC, senior architecture review, and explicit approval — not a comment in a pull request.

The philosophy underlying these standards: **engineering software for engineers must itself be engineered to engineering-grade standards.** A platform that helps identify design flaws in hardware cannot tolerate design flaws in its own implementation.

---

## SECTION 1 — CODING STANDARDS

### 1.1 Language-Level Constraints

**Python (Backend — FastAPI)**

Python version: 3.11+ required. No 3.9 or 3.10 code shall be merged. The reason: 3.11 delivers 25–60% performance improvements on async I/O workloads — the exact profile of an LLM-heavy backend.

```python
# REQUIRED: All function signatures must include type annotations
# WRONG
def get_risk_score(circuit, user_id):
    pass

# CORRECT
async def get_risk_score(circuit: CircuitInput, user_id: UUID) -> RiskScoreResponse:
    pass
```

Every service function must be `async`. Synchronous functions are permitted only in:
- Pure computation utilities (NumPy thermal calculations, SPICE parsing)
- One-time seeding scripts
- Test helpers

Blocking I/O inside `async` functions is a critical violation. If a library does not support `async` natively (e.g., `PyMuPDF`, `OpenCV`), it must be wrapped using `asyncio.get_event_loop().run_in_executor()` with a dedicated `ThreadPoolExecutor`.

```python
# CORRECT: Blocking library wrapped for async compatibility
async def extract_pdf_text(pdf_path: str) -> str:
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(executor, _sync_extract, pdf_path)
    return result

def _sync_extract(pdf_path: str) -> str:
    # PyMuPDF (fitz) runs here — blocking, isolated from event loop
    import fitz
    doc = fitz.open(pdf_path)
    return "\n".join(page.get_text() for page in doc)
```

**TypeScript (Frontend — Next.js 14)**

TypeScript strict mode is mandatory. `tsconfig.json` must contain:

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitReturns": true
  }
}
```

`any` type is prohibited. The only permitted exception is when interfacing with third-party libraries that ship no type definitions — in which case, a local `.d.ts` declaration file must be created within 48 hours of introduction.

---

### 1.2 Module Boundary Rules

The service layer (`services/`) must never import from the API route layer (`api/v1/routes/`). Information flows in one direction only:

```
routes/ → services/ → repositories/ → database
                    ↘ ai_provider/ 
                    ↘ knowledge_graph/
```

Cross-module service calls are prohibited. The `analysis` service must not import from the `design` service. Shared logic lives in `utils/` or a dedicated `shared/` service — not in sibling modules.

The repositories layer is the single source of truth for database access. No raw SQLAlchemy `session.execute()` calls are permitted in `services/`. Every database operation goes through a repository function with a typed return value.

```python
# WRONG — service directly accessing DB session
async def get_project(project_id: UUID, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    return result.scalar_one()

# CORRECT — service calls repository function
async def get_project_with_history(project_id: UUID, user_id: UUID) -> ProjectWithHistory:
    project = await project_repo.get_by_id(project_id)
    history = await analysis_repo.get_history_by_project(project_id)
    return ProjectWithHistory(project=project, analysis_history=history)
```

---

### 1.3 Error Handling Contract

Every service function must handle its own failure modes. Unhandled exceptions that bubble to the route layer are a code review rejection.

**Exception Hierarchy:**

```python
# core/exceptions.py
class QUEBETError(Exception):
    """Base exception. All platform errors inherit from this."""
    def __init__(self, message: str, error_code: str, status_code: int = 500):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code

class AIProviderError(QUEBETError):
    """LLM API call failed — provider timeout, rate limit, invalid response."""
    pass

class ValidationError(QUEBETError):
    """AI output failed schema validation or engineering rule check."""
    pass

class InsufficientPlanError(QUEBETError):
    """User's subscription plan does not permit this operation."""
    def __init__(self, feature: str, required_plan: str):
        super().__init__(
            message=f"Feature '{feature}' requires {required_plan} plan.",
            error_code="PLAN_RESTRICTION",
            status_code=403
        )

class RateLimitError(QUEBETError):
    """User has exceeded their rate limit for this time window."""
    pass
```

**Error Response Shape (all API errors):**

```json
{
  "error": {
    "code": "AI_PROVIDER_TIMEOUT",
    "message": "The AI provider did not respond within the expected window. Please retry.",
    "retry_after": 5,
    "request_id": "req_8f2a3b4c",
    "timestamp": "2025-03-15T14:22:31Z"
  }
}
```

Client-facing error messages must never expose: stack traces, internal service names, database table names, API keys (even partials), or model-specific error strings from Anthropic/OpenAI.

---

### 1.4 Code Organization — File Size Limits

| File Type | Maximum Lines | Enforcement |
|---|---|---|
| Service file (`services/`) | 300 lines | CI lint check |
| Route file (`routes/`) | 150 lines | CI lint check |
| Repository file | 200 lines | CI lint check |
| React component | 250 lines | CI lint check |
| Prompt template | 100 lines | Manual review |
| Utility function file | 200 lines | CI lint check |

When a file approaches its limit, it is a signal that the abstraction is wrong — not that the limit should be raised. Split the file by responsibility, not by line count arithmetic.

---

## SECTION 2 — API STANDARDS

### 2.1 URL Design

All API endpoints follow RESTful resource naming. URLs are lowercase, hyphenated, and resource-first:

```
POST   /api/v1/design/projects              ← create project
GET    /api/v1/design/projects              ← list user projects
GET    /api/v1/design/projects/{id}         ← get single project
PATCH  /api/v1/design/projects/{id}         ← update project
DELETE /api/v1/design/projects/{id}         ← delete project

POST   /api/v1/analysis/risk-score          ← trigger analysis (returns job_id for async)
GET    /api/v1/jobs/{job_id}                ← poll async job status
GET    /api/v1/jobs/{job_id}/result         ← fetch completed result

POST   /api/v1/components/identify          ← vision identification
POST   /api/v1/components/bom/optimize      ← BOM optimization (nested resource action)
```

**Version Contract:** `/api/v1/` is the current stable contract. No breaking changes are permitted to v1 endpoints once a feature is released to production. New behavior with breaking changes requires `/api/v2/` — v1 must continue to function for a minimum of 6 months after v2 release.

**HTTP Method Semantics:**

| Operation | Method | Idempotent | Body |
|---|---|---|---|
| Create resource | POST | No | Required |
| Read resource | GET | Yes | None |
| Full update | PUT | Yes | Required |
| Partial update | PATCH | No | Required |
| Delete | DELETE | Yes | None |
| Trigger AI job | POST | No | Required |

`GET` requests must never trigger side effects. Specifically: `GET /analysis/risk-score` is prohibited — analysis is triggered via `POST` and results fetched via `GET /jobs/{id}/result`.

---

### 2.2 Request/Response Contracts

Every route must have a typed Pydantic request model and a typed Pydantic response model. Untyped `dict` responses are prohibited.

```python
# CORRECT: Explicit request and response models
@router.post(
    "/risk-score",
    response_model=RiskScoreJobResponse,
    status_code=202,  # 202 Accepted — async job created
    summary="Trigger hardware risk score analysis",
    description="Accepts circuit description and returns job_id for async polling."
)
async def trigger_risk_score(
    request: RiskScoreRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> RiskScoreJobResponse:
    ...
```

**Standard Response Envelope:**

All successful responses are wrapped in a consistent envelope:

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "request_id": "req_8f2a3b4c",
    "timestamp": "2025-03-15T14:22:31Z",
    "version": "1.0.0"
  }
}
```

Async job initiation responses use `202 Accepted`:

```json
{
  "success": true,
  "data": {
    "job_id": "job_9a1b2c3d",
    "status": "queued",
    "estimated_duration_seconds": 15,
    "poll_url": "/api/v1/jobs/job_9a1b2c3d"
  }
}
```

---

### 2.3 Pagination

All list endpoints must support cursor-based pagination. Offset pagination is prohibited at scale because it becomes unusable at large offsets (PostgreSQL must scan all preceding rows).

```python
# CORRECT: Cursor-based pagination
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: Optional[str]  # Base64-encoded: "{created_at}:{id}"
    has_more: bool
    total_count: int

# Usage
GET /api/v1/design/projects?cursor=eyJjcmVhdGVkX2F0IjoiMjAyNS0wMyJ9&limit=20
```

Default page size: 20. Maximum: 100. Requests for `limit > 100` return a `400 Bad Request` with message: "Maximum page size is 100."

---

### 2.4 Rate Limit Response Headers

Every API response must include rate limit metadata in headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1710508800
X-RateLimit-Window: 60
Retry-After: 13   (only present on 429 responses)
```

---

## SECTION 3 — PROMPT ENGINEERING STANDARDS

### 3.1 Prompt Architecture

Prompts are first-class engineering artifacts in QUEBET AI. They are versioned, tested, and reviewed with the same rigor as service code. The following rules are non-negotiable:

**Rule 1: No Inline Prompt Strings**

Prompts must never be defined inside service files as string literals. Every prompt lives in `services/ai/prompts/{module}/{feature}.py` as a class with a `render()` method.

```python
# WRONG — prompt buried in service logic
async def analyze_thermal(components: list[ComponentInput]) -> ThermalResult:
    response = await ai_provider.complete(
        system="Analyze the thermal properties of these components...",  # ← PROHIBITED
        user=str(components)
    )

# CORRECT — prompt is a versioned, testable class
class ThermalAnalysisPrompt:
    VERSION = "thermal_v2.1.0"
    
    def render_system(self, context: ThermalPromptContext) -> str:
        return f"""You are a senior electronics thermal engineer with expertise in power dissipation analysis.

Operating context:
- Ambient temperature: {context.ambient_temp}°C
- Enclosure type: {context.enclosure_type}
- Airflow available: {context.airflow_available}

You will analyze the provided component list and return a structured thermal assessment.
The output MUST be valid JSON conforming to the ThermalResult schema.
Do not include prose outside the JSON structure.
"""

    def render_user(self, components: list[ComponentInput]) -> str:
        component_text = "\n".join(
            f"- {c.name}: Pd={c.power_dissipation}W, Rθja={c.thermal_resistance}°C/W"
            for c in components
        )
        return f"Analyze thermal behavior for these components:\n{component_text}"
```

**Rule 2: JSON Output Enforcement**

Every prompt that feeds a structured pipeline must explicitly instruct the model to return valid JSON and nothing else. The instruction must appear in three places:

1. At the end of the system prompt
2. In the JSON schema specification embedded in the prompt  
3. As a final instruction in the user prompt (for multi-turn flows)

```python
# Mandatory closing instruction in every structured system prompt
STRUCTURED_OUTPUT_FOOTER = """
CRITICAL OUTPUT REQUIREMENTS:
1. Return ONLY valid JSON. No preamble, no explanation, no markdown code fences.
2. Your response must conform exactly to this schema:
{schema}
3. If you cannot determine a value with confidence, use null — never guess.
4. Numeric fields must be numbers, not strings. Do not wrap numbers in quotes.
"""
```

**Rule 3: Temperature Control by Task Type**

| Task Type | Temperature | Reasoning |
|---|---|---|
| Circuit design generation | 0.2 | Low creativity needed — correctness is critical |
| Risk score analysis | 0.1 | Near-deterministic — same input should give same score |
| Failure prediction | 0.1 | Safety-critical — consistency over creativity |
| Debug wizard (Q&A) | 0.3 | Slight variation acceptable in diagnostic questions |
| Datasheet simplification | 0.4 | Some variation in phrasing is acceptable |
| Learning/tutor explanations | 0.5 | Variety in explanations improves learning |
| Voice assistant responses | 0.6 | Conversational variation is desirable |

**Rule 4: Context Budget Management**

Every prompt must be accompanied by a `token_budget` specification:

```python
class PromptBudget:
    SYSTEM_MAX_TOKENS: int       # Maximum system prompt tokens
    USER_MAX_TOKENS: int         # Maximum user prompt tokens
    RAG_CONTEXT_MAX_TOKENS: int  # Maximum injected RAG context tokens
    COMPLETION_MAX_TOKENS: int   # Maximum expected completion tokens
    
    @property
    def total_context_tokens(self) -> int:
        return self.SYSTEM_MAX_TOKENS + self.USER_MAX_TOKENS + self.RAG_CONTEXT_MAX_TOKENS

# Example: Risk Score prompt budget
class RiskScorePromptBudget(PromptBudget):
    SYSTEM_MAX_TOKENS = 800
    USER_MAX_TOKENS = 1200
    RAG_CONTEXT_MAX_TOKENS = 1500
    COMPLETION_MAX_TOKENS = 1000
    # Total: 4500 tokens — well within claude-3-5-sonnet 200K context
```

If RAG context retrieval would cause `total_context_tokens > MODEL_CONTEXT_LIMIT * 0.8`, the RAG context must be truncated using the `truncate_to_fit()` function — never silently dropped.

---

### 3.2 Prompt Versioning

Every prompt has a version string in the format `{feature}_{vMAJOR.MINOR.PATCH}`:

- **MAJOR**: Breaking change — output schema changed, incompatible with previous consumers
- **MINOR**: New capability added — backwards-compatible output, new optional fields
- **PATCH**: Wording improvement — identical schema, improved accuracy or phrasing

Prompt versions are stored in PostgreSQL's `prompt_versions` table and included in every LLM call's log entry. This enables: A/B testing between prompt versions, rollback when a new version regresses, and audit trails for AI outputs (required for enterprise clients).

```sql
CREATE TABLE prompt_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature     VARCHAR(100) NOT NULL,  -- e.g., "risk_score"
    version     VARCHAR(50)  NOT NULL,  -- e.g., "v2.1.0"
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by  VARCHAR(100) NOT NULL,
    change_note TEXT         NOT NULL,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    UNIQUE (feature, version)
);
```

---

### 3.3 Prompt Review Process

A prompt change follows the same review process as a code change, with an additional domain review step:

```
Developer writes prompt change
  ↓
Unit tests pass (prompt renders correctly with all variable combinations)
  ↓
Evaluation suite runs (prompt tested against 20+ canonical test cases, accuracy delta measured)
  ↓
Pull Request opened with:
  - Old vs new prompt diff
  - Evaluation score comparison table
  - Token count change (cost impact)
  - Any schema changes
  ↓
Electronics domain review (a practicing electronics engineer reviews the technical accuracy)
  ↓
Senior engineer approves
  ↓
Merged — deployed as new PATCH/MINOR/MAJOR version
```

No prompt change that degrades accuracy by more than 5% on the evaluation suite may be merged, regardless of other improvements.

---

## SECTION 4 — TESTING STANDARDS

### 4.1 Test Coverage Requirements

| Component Type | Minimum Coverage | Enforcement |
|---|---|---|
| Repository functions | 95% | CI gate |
| Service functions | 85% | CI gate |
| AI provider abstraction | 90% | CI gate |
| Prompt rendering | 100% | CI gate |
| Route handlers | 80% | CI gate |
| Utility functions | 90% | CI gate |
| React components (critical path) | 70% | CI gate |

Coverage below these thresholds blocks merge to `main`. There are no exceptions — "we'll add tests later" is not an engineering culture that produces reliable software.

---

### 4.2 Test Classification

**Unit Tests** (`tests/unit/`): Fast, isolated, no I/O. Run on every commit, must complete in under 60 seconds total.

```python
# Unit test: prompt rendering
def test_risk_score_prompt_renders_with_all_variables():
    prompt = RiskScorePrompt()
    context = RiskScorePromptContext(
        circuit_description="Buck converter with IR3840",
        voltage_rails=["12V", "5V"],
        ambient_temp=40,
        skill_level=SkillLevel.ENGINEER
    )
    system = prompt.render_system(context)
    
    assert "CRITICAL OUTPUT REQUIREMENTS" in system
    assert "12V" in system
    assert "40" in system
    assert len(system) < 4000  # Token budget check

# Unit test: thermal calculation
def test_junction_temperature_calculation():
    result = calculate_junction_temperature(
        power_dissipation=2.5,  # Watts
        thermal_resistance=50,  # °C/W
        ambient_temp=25         # °C
    )
    assert result == 150.0  # Tj = Ta + (Pd × Rθja) = 25 + (2.5 × 50)
    assert result > 125.0   # Must flag as over-temperature (max Tj for most parts = 125°C)
```

**Integration Tests** (`tests/integration/`): Real database, real Redis, mocked AI providers. Run on PR merge to `develop`. Must complete in under 5 minutes.

```python
# Integration test: full risk score flow
@pytest.mark.asyncio
async def test_risk_score_endpoint_returns_job_id(client, authenticated_user):
    response = await client.post(
        "/api/v1/analysis/risk-score",
        json={"circuit_description": "12V to 5V buck converter with IRF540N MOSFET"},
        headers={"Authorization": f"Bearer {authenticated_user.token}"}
    )
    assert response.status_code == 202
    data = response.json()["data"]
    assert "job_id" in data
    assert data["status"] == "queued"
    assert "/api/v1/jobs/" in data["poll_url"]
```

**Evaluation Tests** (`tests/eval/`): Real AI providers, canonical test cases, accuracy measurement. Run nightly on `main`. Results stored in PostgreSQL for trend tracking.

```python
# Evaluation test: risk score accuracy
@pytest.mark.evaluation
async def test_risk_score_catches_overvoltage():
    """A capacitor rated 16V connected to an 18V rail must score >70 (high risk)."""
    result = await risk_scorer.analyze(
        circuit_description="""
        Filter capacitor C1: 100µF, 16V rating, connected to 18V power rail.
        Operating temperature: 55°C. No heatsinking on power section.
        """
    )
    assert result.score > 70, f"Expected risk >70, got {result.score}"
    assert any("overvoltage" in r.lower() for r in result.risk_factors)
    assert any("capacitor" in r.lower() for r in result.risk_factors)
```

---

### 4.3 AI Provider Mocking Strategy

Real LLM API calls must never be made in unit or integration tests. The mock system uses response fixtures:

```python
# tests/fixtures/ai_responses.py
RISK_SCORE_FIXTURES = {
    "overvoltage_capacitor": {
        "score": 78,
        "risk_factors": ["Capacitor C1 exceeds voltage rating by 12.5%", "Operating temperature reduces capacitor lifespan by 40%"],
        "recommendations": ["Replace C1 with 25V rated capacitor", "Add thermal relief to power section"],
        "confidence": 0.91
    },
    "clean_design": {
        "score": 12,
        "risk_factors": [],
        "recommendations": ["Design meets all standard engineering guidelines"],
        "confidence": 0.95
    }
}

# Mock provider returns fixture based on prompt hash
class MockAIProvider(BaseProvider):
    async def complete(self, system: str, user: str, **kwargs) -> str:
        prompt_key = classify_prompt(user)  # Matches against known test inputs
        fixture = RISK_SCORE_FIXTURES.get(prompt_key, RISK_SCORE_FIXTURES["clean_design"])
        return json.dumps(fixture)
```

---

### 4.4 Frontend Testing

React component tests use Vitest + React Testing Library. Playwright handles end-to-end flows.

```typescript
// Unit test: RiskScoreMeter renders correct color zone
test('RiskScoreMeter shows red zone for score above 70', () => {
  render(<RiskScoreMeter score={78} />)
  const dial = screen.getByTestId('risk-dial')
  expect(dial).toHaveAttribute('data-zone', 'critical')
  expect(dial).toHaveStyle({ stroke: 'var(--color-risk-critical)' })
})

// E2E test: Full risk score workflow
test('engineer can submit circuit and see risk score', async ({ page }) => {
  await page.goto('/analysis/risk-score')
  await page.fill('[data-testid="circuit-input"]', '12V buck converter with IRF540N')
  await page.click('[data-testid="analyze-button"]')
  await expect(page.locator('[data-testid="job-status"]')).toHaveText('Analyzing...')
  await expect(page.locator('[data-testid="risk-score-value"]')).toBeVisible({ timeout: 30000 })
})
```

---

## SECTION 5 — DOCUMENTATION STANDARDS

### 5.1 Code Documentation

**Python Docstrings — Google Style:**

Every public service function and repository function requires a docstring. Internal helper functions with self-evident names do not.

```python
async def analyze_thermal_profile(
    components: list[ComponentInput],
    ambient_temp: float,
    enclosure: EnclosureType,
    user_id: UUID
) -> ThermalAnalysisResult:
    """Analyze thermal dissipation for a component set and generate cooling recommendations.

    Performs physics-based junction temperature calculation using Rθja values from
    component specifications, then uses the LLM to interpret results and suggest
    thermal management strategies.

    Args:
        components: List of components with power dissipation and thermal resistance specs.
            Each component must have `power_dissipation_w` and `thermal_resistance_ja` set.
        ambient_temp: Operating ambient temperature in degrees Celsius. Acceptable range: -40 to 85°C.
        enclosure: Enclosure type affecting airflow assumptions (OPEN, VENTED, SEALED).
        user_id: Authenticated user ID for project association and caching.

    Returns:
        ThermalAnalysisResult containing:
            - Per-component junction temperatures
            - Components flagged as exceeding maximum Tj
            - Ordered cooling recommendations
            - Confidence score from AI validation stage

    Raises:
        ValidationError: If component specs are incomplete or physically impossible
            (e.g., negative power dissipation).
        AIProviderError: If LLM call fails after retry exhaustion.

    Example:
        >>> result = await analyze_thermal_profile(
        ...     components=[ComponentInput(name="IRF540N", power_dissipation_w=3.2, thermal_resistance_ja=62.0)],
        ...     ambient_temp=25.0,
        ...     enclosure=EnclosureType.SEALED,
        ...     user_id=current_user.id
        ... )
        >>> result.components[0].junction_temp  # 227.4°C — will be flagged as critical
    """
```

**TypeScript JSDoc:**

```typescript
/**
 * Polls the job status endpoint at 2-second intervals until the job completes or fails.
 * Automatically stops polling after `maxAttempts` and calls `onTimeout` if provided.
 *
 * @param jobId - The job ID returned from an async API call (e.g., risk score, PCB analysis)
 * @param onProgress - Callback invoked on each poll with current progress percentage (0-100)
 * @param onComplete - Callback invoked when job reaches "done" status with the result payload
 * @param onError - Callback invoked when job fails or polling times out
 * @param maxAttempts - Maximum number of poll attempts before timing out (default: 60 = 2 minutes)
 *
 * @example
 * useJobPoller({
 *   jobId: 'job_9a1b2c3d',
 *   onProgress: (pct) => setProgress(pct),
 *   onComplete: (result) => setRiskScore(result.score),
 *   onError: (err) => showErrorToast(err.message)
 * })
 */
export function useJobPoller(options: JobPollerOptions): JobPollerState
```

---

### 5.2 Architecture Decision Records (ADRs)

Every significant architectural decision — database choice, library adoption, provider strategy, schema design — must be documented as an ADR in `docs/adr/`. ADRs are permanent records. They are never deleted, only superseded by newer ADRs.

**ADR Template:**

```markdown
# ADR-{NUMBER}: {Decision Title}

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Superseded by ADR-{N}
**Deciders:** {Names}

## Context
What is the situation that forces a decision? What are the constraints?

## Decision
What is the decision made? State it clearly and specifically.

## Reasoning
Why this option over alternatives? Include quantitative reasoning where possible.

## Alternatives Considered
What else was evaluated? Why was each rejected?

## Consequences
**Positive:** What does this enable?
**Negative:** What does this cost or constrain?
**Risks:** What could go wrong?

## Review Date
When should this decision be re-evaluated?
```

**Example ADR — ChromaDB over Pinecone:**

```markdown
# ADR-004: Use ChromaDB for Vector Store, Not Pinecone

**Date:** 2025-03-01
**Status:** Accepted

## Context
QUEBET AI requires semantic similarity search over ~100K circuit descriptions and
failure cases. Two candidate vector databases were evaluated: ChromaDB (open-source,
self-hosted) and Pinecone (managed cloud service).

## Decision
Use ChromaDB, self-hosted on the application server cluster.

## Reasoning
1. Cost: Pinecone starter is $70/month minimum. At our scale (Phase 1), ChromaDB
   costs nothing beyond the compute we already pay for.
2. Data sovereignty: Electronics KB content and user circuit data stay on our servers.
   Enterprise clients will not accept their proprietary circuit data leaving their
   infrastructure perimeter.
3. Operational control: We can tune ChromaDB collection settings, run background
   reindexing, and control backup schedules without vendor dependency.
4. Performance: At <1M vectors, ChromaDB with HNSW index meets our <100ms retrieval
   target. Pinecone would only be relevant beyond 10M vectors.

## Consequences
Positive: Zero incremental cost, full data control, easier on-premise packaging.
Negative: We own the operational burden of running ChromaDB.
Risk: At very large scale (>10M vectors), we may need to migrate to a managed solution.
Review Date: 2026-01-01 — reassess if corpus exceeds 5M vectors.
```

---

## SECTION 6 — AI SAFETY STANDARDS

### 6.1 Output Containment Rules

AI-generated outputs in QUEBET AI must never be rendered to users without passing through at least one validation stage. The minimum validation pipeline for each output category:

| Output Category | Minimum Validation | Blocking Condition |
|---|---|---|
| Risk score (numeric) | Schema validation + range check | Score outside 0–100 |
| Component specifications | Schema + units validation | Missing critical fields |
| Circuit code (Arduino/C) | Syntax check + dangerous function scan | `system()`, memory corruption patterns |
| BOM data | Schema + price sanity check | Negative prices, impossible quantities |
| Thermal calculations | Physics constraint check | Tj below absolute zero, negative Rθja |
| Debugging steps | Step count check + action verb scan | Steps with no measurable test point |
| Repair recommendations | Component name lookup | Recommending non-existent components |

**Dangerous Output Patterns — Auto-Reject:**

```python
DANGEROUS_OUTPUT_PATTERNS = [
    # Circuit safety
    r"connect.*live.*mains",          # Suggesting live mains connections without isolation
    r"bypass.*protection.*circuit",   # Removing protection circuits
    r"exceed.*absolute.*maximum",     # Intentional overvoltage suggestions
    
    # Code safety
    r"system\s*\(",                   # Shell injection in generated code
    r"exec\s*\(",                     # Code execution
    r"eval\s*\(",                     # Dynamic evaluation
    
    # Physical safety
    r"lithium.*short.*circuit",       # Dangerous battery handling
    r"capacitor.*discharge.*direct",  # Dangerous capacitor discharge method
]

def scan_for_dangerous_patterns(output: str) -> list[str]:
    violations = []
    for pattern in DANGEROUS_OUTPUT_PATTERNS:
        if re.search(pattern, output, re.IGNORECASE):
            violations.append(f"Dangerous pattern detected: {pattern}")
    return violations
```

---

### 6.2 Confidence Score Thresholds

Every AI output must carry a confidence score. What happens at each confidence level:

| Confidence Range | Action | User-Facing Behavior |
|---|---|---|
| 0.90 – 1.00 | Accept, deliver | Normal result display |
| 0.75 – 0.89 | Accept with caveat | Yellow warning banner: "Review recommended" |
| 0.60 – 0.74 | Soft retry (different temperature) | Loading state → retry once |
| 0.40 – 0.59 | Hard retry (different model) | Loading state → retry with fallback model |
| 0.00 – 0.39 | Reject, surface error | "Analysis inconclusive. Please provide more detail." |

Confidence scores are computed as a weighted combination of:
- Schema validation pass rate (binary → 1.0 or 0.0)
- Engineering rule check pass rate (count of rules passed / total rules checked)
- Model's self-reported confidence (where extractable from output)
- Cross-validation agreement (when multi-model verification is active)

---

### 6.3 Prompt Injection Defense

All user-provided text that is injected into prompts must pass through a sanitization pipeline before injection:

```python
# utils/prompt_sanitizer.py
INJECTION_PATTERNS = [
    r"ignore (previous|above|all) instructions",
    r"you are now",
    r"new system prompt",
    r"forget (everything|all|your)",
    r"act as (if you are|a different|an unrestricted)",
    r"<\|system\|>",           # Token injection attempt
    r"\[INST\]",               # Llama-style injection
    r"```system",              # Markdown-wrapped system injection
]

def sanitize_user_input(text: str, max_length: int = 4000) -> SanitizedInput:
    """
    Sanitize user-provided text before prompt injection.
    Returns SanitizedInput with cleaned text and any detected violation types.
    """
    violations = []
    
    # Length enforcement
    if len(text) > max_length:
        text = text[:max_length]
        violations.append("INPUT_TRUNCATED")
    
    # Injection pattern detection
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            violations.append(f"INJECTION_ATTEMPT:{pattern}")
            # Log the attempt for security monitoring
            security_logger.warning(f"Prompt injection attempt detected", extra={
                "pattern": pattern, "input_preview": text[:100]
            })
            # Remove the injection attempt
            text = re.sub(pattern, "[FILTERED]", text, flags=re.IGNORECASE)
    
    return SanitizedInput(text=text, violations=violations, was_modified=bool(violations))
```

All detected injection attempts are logged to the security event stream and aggregated for abuse pattern analysis. Users with more than 3 injection attempts in 24 hours have their account flagged for review.

---

## SECTION 7 — JSON SCHEMA STANDARDS

### 7.1 Schema Versioning

All Pydantic models used in AI output validation are versioned. Schema versions are embedded in the model class and stored with every AI response in the database. This enables:
- Debugging what schema was in use when a validation failure occurred
- Rolling back schema validation for a specific prompt version
- Analytics on which schema fields are most frequently missing from AI outputs

```python
class RiskScoreResponse(BaseModel):
    """
    Schema version: risk_score_response_v2.1.0
    Breaking changes from v2.0.0: 
      - `factors` renamed to `risk_factors`
      - `score` is now an integer, not float
    """
    model_config = ConfigDict(
        json_schema_extra={
            "schema_version": "risk_score_response_v2.1.0",
            "prompt_compatibility": ["risk_score_v2.x.x"]
        }
    )
    
    score: int = Field(..., ge=0, le=100, description="Risk score from 0 (safest) to 100 (critical)")
    risk_factors: list[RiskFactor] = Field(..., description="Individual risk findings")
    recommendations: list[str] = Field(..., min_length=1, description="Ordered improvement actions")
    confidence: float = Field(..., ge=0.0, le=1.0, description="AI confidence in this assessment")
    validation_status: ValidationStatus = Field(..., description="Result of deterministic validation checks")
```

---

### 7.2 Nullable vs Required Fields

The rule: a field is **required** if its absence makes the output unusable. A field is **nullable** if the AI may legitimately not have the information.

```python
class ComponentIdentifyResponse(BaseModel):
    # Required — if these are missing, the identification failed
    component_name: str           = Field(..., description="Primary component identifier")
    package_type: str             = Field(..., description="Physical package (DIP-8, SOT-23, QFP-48, etc.)")
    
    # Nullable — not all components have all of these
    manufacturer: Optional[str]   = Field(None, description="Component manufacturer")
    part_number: Optional[str]    = Field(None, description="Manufacturer part number")
    datasheet_url: Optional[str]  = Field(None, description="Direct datasheet link")
    
    # Required with minimum content
    key_specifications: dict[str, str] = Field(
        ..., 
        min_length=2,  # At minimum: voltage rating + current rating
        description="Critical specifications as key-value pairs"
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
```

---

## SECTION 8 — LOGGING CONVENTIONS

### 8.1 Structured Logging

Every log entry in QUEBET AI is structured JSON. No freeform log strings. The reason: structured logs are queryable, alertable, and parseable by observability tooling without regex. Freeform strings require regex to extract information — which is fragile and slow.

```python
# core/logging.py
import structlog

logger = structlog.get_logger()

# CORRECT: Structured log with typed fields
logger.info(
    "ai_call_completed",
    feature="risk_score",
    provider="claude",
    model="claude-3-5-sonnet-20241022",
    prompt_version="risk_score_v2.1.0",
    prompt_tokens=1240,
    completion_tokens=387,
    total_tokens=1627,
    latency_ms=2340,
    cost_usd=0.0048,
    cached=False,
    confidence=0.91,
    validation_passed=True,
    user_id=str(user_id),
    job_id=str(job_id),
    request_id=str(request_id)
)

# WRONG: Freeform string
logger.info(f"Claude call done: 1627 tokens in 2340ms for risk_score")
```

**Required Fields on Every Log Entry:**

| Field | Type | Description |
|---|---|---|
| `timestamp` | ISO 8601 | Auto-injected by log processor |
| `level` | enum | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `event` | string | Snake_case event name (e.g., `ai_call_completed`) |
| `request_id` | UUID | Traces a single HTTP request end-to-end |
| `user_id` | UUID | Authenticated user (null for system events) |
| `service` | string | `api`, `worker`, `knowledge_graph`, etc. |

---

### 8.2 Log Levels — Precise Definitions

| Level | When to Use | Examples |
|---|---|---|
| DEBUG | Internal state useful only during development | RAG context content, prompt rendering internals |
| INFO | Normal operational events | API call completed, job queued, cache hit |
| WARNING | Abnormal but recoverable | AI confidence below threshold, cache miss rate spiking, retry needed |
| ERROR | Failed operation, user-impacting | LLM validation failed after retries, database write failed |
| CRITICAL | System-threatening condition | AI cost runaway detected, database connection pool exhausted |

`DEBUG` logs are disabled in production by default. They are enabled per-user via feature flag for debugging specific customer issues — never globally in production.

---

### 8.3 Sensitive Data — Log Exclusion List

The following must never appear in any log entry, regardless of level:

- API keys (Anthropic, OpenAI, AWS)
- JWT tokens (even partial)
- User passwords or password hashes
- Full prompt content containing user's proprietary circuit descriptions
- Component supplier pricing data covered by API agreements
- User email addresses in non-auth service logs

The structured logging system enforces this via a `SensitiveDataFilter` that scans log entries for patterns matching these categories and replaces them with `[REDACTED]` before writing to the log sink.

---

## SECTION 9 — NAMING CONVENTIONS

### 9.1 Python Naming

| Construct | Convention | Example |
|---|---|---|
| Files | `snake_case` | `risk_scorer.py`, `pcb_analyzer.py` |
| Classes | `PascalCase` | `RiskScoreAnalyzer`, `ClaudeProvider` |
| Functions/methods | `snake_case` | `analyze_thermal_profile()` |
| Constants | `SCREAMING_SNAKE_CASE` | `MAX_RETRY_ATTEMPTS = 3` |
| Pydantic models (request) | `{Resource}Request` | `RiskScoreRequest` |
| Pydantic models (response) | `{Resource}Response` | `RiskScoreResponse` |
| SQLAlchemy models | `{Entity}` | `Project`, `AnalysisResult` |
| Repository functions | `{verb}_{noun}` | `get_by_id()`, `save_result()` |
| Celery tasks | `{verb}_{noun}_task` | `run_simulation_task()` |

### 9.2 TypeScript Naming

| Construct | Convention | Example |
|---|---|---|
| Files | `PascalCase` for components, `camelCase` for hooks/utils | `RiskScoreMeter.tsx`, `useJobPoller.ts` |
| React components | `PascalCase` | `RiskScoreMeter`, `JobStatusPoller` |
| Hooks | `use{Name}` | `useAIStream`, `useJobPoller` |
| Types/Interfaces | `PascalCase` | `RiskScoreResult`, `CircuitInput` |
| Zustand stores | `use{Domain}Store` | `useProjectStore`, `useAIStore` |
| Constants | `SCREAMING_SNAKE_CASE` | `MAX_POLL_ATTEMPTS` |
| API functions | `{verb}{Resource}` | `fetchRiskScore()`, `createProject()` |

### 9.3 Database Naming

PostgreSQL tables and columns follow `snake_case`. All table names are plural nouns.

```sql
-- CORRECT
CREATE TABLE analysis_results (
    id                  UUID        PRIMARY KEY,
    project_id          UUID        NOT NULL REFERENCES projects(id),
    result_type         VARCHAR(50) NOT NULL,
    risk_score          INTEGER,
    confidence_score    DECIMAL(4,3),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- WRONG: singular table name, camelCase columns
CREATE TABLE analysisResult (
    resultType VARCHAR(50),
    riskScore INTEGER
);
```

Neo4j nodes use `PascalCase` labels. Relationships use `SCREAMING_SNAKE_CASE`:

```cypher
// CORRECT
(:Component)-[:APPEARS_IN]->(:Circuit)-[:HAS_FAILURE]->(:FailureMode)-[:FIXED_BY]->(:Fix)

// WRONG
(:component)-[:appearsIn]->(:circuit)
```

---

## SECTION 10 — MODULARIZATION RULES

### 10.1 Feature Cohesion Test

Before creating a new module or adding to an existing one, apply the cohesion test: "If this module were deleted, would the remaining system still function for all other use cases?" If yes — it is correctly bounded. If no — the module is doing too much.

Modules that fail this test must be split until each module passes.

### 10.2 Dependency Direction

Dependencies flow inward. Outer layers may depend on inner layers. Inner layers must never depend on outer layers.

```
Routes (outermost)
  ↓ depends on
Services
  ↓ depends on
Repositories | AI Provider | Knowledge Graph
  ↓ depends on
Core (database, redis, config) — innermost, depends on nothing
```

Any PR introducing an import that violates this direction is rejected at code review.

### 10.3 Shared Code — The Rule of Three

A function or class becomes a shared utility only after it is used in three separate modules. Until it is needed in the third place, it lives in the module that first needed it. Premature generalization is a form of waste.

```python
# WRONG: Immediately moving to utils/ after first use
# utils/circuit_helpers.py
def format_component_name(name: str) -> str:
    return name.strip().upper()

# CORRECT: Let it live in its first home until genuinely shared
# services/components/identifier.py
def _format_component_name(name: str) -> str:  # ← private, local
    return name.strip().upper()
```

---

## SECTION 11 — FEATURE RELEASE WORKFLOW

### 11.1 Branch Strategy

```
main          ← Production. Protected. Direct push prohibited.
develop       ← Integration branch. All features merge here first.
feature/*     ← Feature branches. Branched from develop.
fix/*         ← Bug fix branches.
hotfix/*      ← Critical production fixes. Branched from main, merged to both main + develop.
release/*     ← Release staging. Created from develop, merged to main + tagged.
```

Branch names follow: `{type}/{ticket-id}-{short-description}`

Examples:
- `feature/Q-142-thermal-heatmap-component`
- `fix/Q-087-risk-score-null-pointer`
- `hotfix/Q-201-jwt-expiry-calculation`

### 11.2 Definition of Done

A feature is complete — ready for merge to `develop` — only when all of the following are true:

- All code changes are reviewed and approved by at least 2 engineers
- Test coverage meets or exceeds section 4.1 thresholds
- New prompt changes have passed evaluation suite with documented accuracy scores
- API changes are reflected in updated OpenAPI spec
- ADR written if an architectural decision was made
- Electronics domain review completed if feature involves engineering analysis
- Feature is behind a feature flag in production (not enabled by default)
- Monitoring dashboard updated with new metrics if feature introduces new observable behavior

### 11.3 Feature Flags

Every new feature ships behind a feature flag. No exceptions. Feature flags are managed in PostgreSQL:

```sql
CREATE TABLE feature_flags (
    flag_name       VARCHAR(100)    PRIMARY KEY,
    enabled_globally BOOLEAN        NOT NULL DEFAULT FALSE,
    enabled_plans   VARCHAR[]       DEFAULT '{}',  -- e.g., '{"pro", "enterprise"}'
    enabled_users   UUID[]          DEFAULT '{}',  -- Specific user beta test list
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,                   -- Auto-disable date
    description     TEXT            NOT NULL
);
```

Feature flags are evaluated at the BFF layer. A disabled flag returns a `feature_coming_soon` response — the backend service is never called.

---

## SECTION 12 — CODE REVIEW STANDARDS

### 12.1 What Reviewers Must Check

**Correctness:**
- Does the logic match the specification?
- Are all edge cases handled (null inputs, empty lists, boundary values)?
- Are error paths properly handled and tested?

**Safety:**
- Is user-provided text sanitized before prompt injection?
- Are there any secrets or sensitive data in logs?
- Does new code respect the module boundary rules?

**Performance:**
- Are there N+1 query patterns in loops?
- Is heavy computation happening in the async event loop without executor wrapping?
- Are Redis cache keys correctly scoped (not over-caching, not under-caching)?

**AI Reliability:**
- Does new prompt code include schema validation on the response?
- Is the temperature appropriate for the task type?
- Is there a retry mechanism for low-confidence outputs?

**Naming and Documentation:**
- Do function names describe what they do, not how?
- Are complex algorithms documented with their reasoning, not just their mechanics?
- Are new public APIs documented with docstrings?

### 12.2 Review Response Time SLA

| PR Type | First Review SLA | Resolution SLA |
|---|---|---|
| Hotfix (production incident) | 1 hour | 4 hours |
| Bug fix | 4 hours | 24 hours |
| Feature (small, < 200 lines changed) | 24 hours | 48 hours |
| Feature (large, > 200 lines changed) | 48 hours | 5 business days |
| Architecture change | 72 hours | 10 business days |

Reviews that exceed these SLAs are escalated to the engineering lead.

---

## APPENDIX — QUICK REFERENCE

### A. Prohibited Patterns (Auto-Reject in Code Review)

| Pattern | Reason |
|---|---|
| Inline prompt strings in service code | Unpromptable, untestable, unversionable |
| `any` type in TypeScript | Defeats type safety, hides bugs |
| Synchronous I/O in async functions | Blocks event loop, kills throughput |
| Raw SQL in service layer | Bypasses repository abstraction |
| `console.log` in committed React code | Use structured logger |
| `print()` in committed Python code | Use structlog |
| Hardcoded API keys in any file | Security incident risk |
| Missing Pydantic model on route response | Uncontracted API surface |

### B. Standard Retry Configuration

```python
# All LLM calls use this retry policy
RETRY_POLICY = {
    "max_attempts": 3,
    "backoff_strategy": "exponential",
    "base_delay_seconds": 2,
    "max_delay_seconds": 16,
    "retryable_errors": [
        "RateLimitError",
        "ServiceUnavailableError",
        "TimeoutError"
    ],
    "non_retryable_errors": [
        "InvalidAPIKeyError",
        "MalformedRequestError",
        "ContentPolicyViolation"
    ]
}
```

### C. Electronics Domain Validation Checklist

Every AI output involving circuit design must pass these domain-specific checks before delivery:

- [ ] No component recommended above its absolute maximum rating
- [ ] No floating signal pins on digital ICs (must be pulled high or low)
- [ ] No power supply output without decoupling capacitors specified
- [ ] Resistor values within standard E-series (E12, E24, E96)
- [ ] No wire gauges recommended that would exceed their current capacity
- [ ] No capacitor voltage rating below supply voltage (minimum 1.25× derating)
- [ ] Arduino/microcontroller GPIO current limits respected (max 40mA per pin for ATmega)
- [ ] No advice to bypass fuses or protection circuits

---

*Document Owner: Platform Engineering*
*Review Cycle: Quarterly*
*Next Review: 2025-06-01*
*Change Requests: Submit via RFC process defined in this document*
