# QUEBET AI — AI Orchestration Layer
> Version 1.0 | AI Engineering Standards | Model Routing & Verification

---

## 1. Orchestration Philosophy

The AI orchestration layer is the most critical and most fragile part of the platform. It sits between user intent and validated engineering output. Its job is not merely to call an LLM — it is to ensure that what reaches the user is correct, grounded, appropriately confident, and safe to act on in a physical engineering context.

Three principles govern every design decision in this layer:

1. **Model independence.** The platform must never require a specific LLM to function. Any provider can be swapped, degraded, or replaced without touching business logic.

2. **Validated output or no output.** A response that fails schema validation, contradicts engineering rules, or scores below confidence threshold is not delivered — it is retried, repaired, or escalated. Silence is better than wrong.

3. **Cost is a first-class concern.** Every routing decision has an associated cost. Simple queries are never sent to expensive frontier models. The routing engine optimizes for quality-per-dollar, not raw quality.

---

## 2. Provider Abstraction Layer

### BaseProvider Contract

```python
class BaseProvider(ABC):
    """
    Every LLM integration implements this interface.
    Services call BaseProvider methods — never SDK methods directly.
    This means swapping Claude for Gemini requires zero changes in services/.
    """

    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: str = "json"  # json | text
    ) -> ProviderResponse:
        """
        Returns: ProviderResponse(
            content=str,
            model=str,
            input_tokens=int,
            output_tokens=int,
            latency_ms=int,
            cost_usd=float,
            cached=bool
        )
        """

    @abstractmethod
    async def stream(
        self,
        system: str,
        user: str
    ) -> AsyncGenerator[str, None]:
        """Yields tokens for SSE streaming. No JSON enforcement (text output)."""

    @abstractmethod
    async def analyze_image(
        self,
        image_url: str,
        prompt: str,
        detail: str = "high"  # low | high
    ) -> ProviderResponse:
        """Vision analysis. Only providers supporting vision implement non-stub version."""

    @abstractmethod
    async def embed(
        self,
        text: str,
        model: str = "text-embedding-3-small"
    ) -> list[float]:
        """Returns 1536-dim vector. Used for ChromaDB indexing and search."""
```

### Implemented Providers

**Primary: OpenRouter Gateway (all deployments)**

| Provider | Class | Models Available | Notes |
|---|---|---|---|
| `OpenRouterProvider` | Primary | All 500+ models on OpenRouter | Single API key, OpenAI-compatible SDK. Handles Claude, GPT, Gemini, DeepSeek, etc. via `api.openrouter.ai` |

**OpenRouter Implementation:**
```python
class OpenRouterProvider(BaseProvider):
    """
    Unified LLM provider via OpenRouter.
    Uses the OpenAI-compatible SDK — same interface, any model.
    The `model` parameter is dynamic — resolved by model_router.py
    based on user plan, task type, and admin configuration.
    """
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            default_headers={
                "HTTP-Referer": "https://quebet.ai",
                "X-Title": "QUEBET AI",
            },
        )

    async def complete(self, system, user, model, temperature=0.1, max_tokens=4096, response_format="json"):
        response = await self.client.chat.completions.create(
            model=model,  # Dynamic: "anthropic/claude-sonnet-4", "openai/gpt-4o", etc.
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return ProviderResponse(
            content=response.choices[0].message.content,
            model=response.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            latency_ms=...,
            cost_usd=...,  # Calculated from model_configs table pricing
            cached=False,
        )
```

**Optional: Direct Providers (enterprise on-premise only)**

For enterprise customers deploying on their own infrastructure without internet access to OpenRouter, direct provider implementations are retained:

| Provider | Class | Use Case |
|---|---|---|
| `ClaudeProvider` | Optional | Enterprise on-premise with direct Anthropic API key |
| `OpenAIProvider` | Optional | Enterprise on-premise with direct OpenAI API key |

These are NOT used in the standard cloud deployment. The `provider_factory.py` checks `settings.AI_GATEWAY` — if `"openrouter"` (default), it returns `OpenRouterProvider`. If `"direct"`, it returns the specific provider class.

### BaseProvider Contract Update

The `BaseProvider` interface adds a `model` parameter to all methods, allowing the caller to specify which OpenRouter model to use:

```python
class BaseProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        model: str,              # NEW: OpenRouter model ID, e.g. "anthropic/claude-sonnet-4"
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: str = "json"
    ) -> ProviderResponse: ...

    @abstractmethod
    async def stream(
        self,
        system: str,
        user: str,
        model: str,              # NEW: model ID
    ) -> AsyncGenerator[str, None]: ...

    @abstractmethod
    async def analyze_image(
        self,
        image_url: str,
        prompt: str,
        model: str,              # NEW: must be vision-capable model
        detail: str = "high"
    ) -> ProviderResponse: ...

    @abstractmethod
    async def embed(
        self,
        text: str,
        model: str = "openai/text-embedding-3-small"
    ) -> list[float]: ...
```

---

## 3. Dynamic Model Routing (OpenRouter & Admin Managed)

### Database-Backed Routing Architecture

Model routing is decoupled from application code. OpenRouter model IDs and their mappings to subscription plans and task types are stored in PostgreSQL (`model_configs` and `plan_model_access` tables) and cached in Redis with a 5-minute TTL. System administrators can alter model selection, adjust fallbacks, or enable new models via the Admin Panel (`/admin/models`) without redeploying backend services.

```
INCOMING REQUEST
       │
       ▼
[1] User Context & Plan Resolution
  ├── Free        → Restricted to budget models (DeepSeek V3 / Gemma free)
  ├── Plus (₹499) → Mid-tier models (Gemini 2.0 Flash, GPT-4o-mini)
  ├── Pro (₹999)  → Flagship models (Claude Sonnet 4, GPT-4o, Gemini 2.5 Pro)
  └── Enterprise  → Any OpenRouter model + custom tenant routing

       │
       ▼
[2] User Model Override Check
  ├── If user selected a model in UI (e.g. Header Model Selector / Settings):
  │     Verify model is allowed for user's plan via plan_model_access
  │     If valid → use user's preferred model
  └── If not selected or not allowed → proceed to automated routing

       │
       ▼
[3] Task Type & Capability Filter (Redis Cache `model_route:{plan}:{task_type}`)
  ├── VISION          → Require is_vision_capable=True (e.g., GPT-4o, GPT-4o-mini)
  ├── LONG_CONTEXT    → Check max_context_tokens >= required context length
  ├── STRUCTURED_JSON → Require supports_json_mode=True
  ├── STREAMING       → Require supports_streaming=True
  └── EMBEDDING       → Fixed routing (openai/text-embedding-3-small)

       │
       ▼
[4] Model Health & Circuit Breaker Check
  ├── Check OpenRouter model error rate in Redis sliding window (5 min)
  ├── If current candidate has >5% failure rate → automatically fall back to priority - 1
  └── If all remote providers fail → serve stale L1 cached response if present

       │
       ▼
[5] Execution & Cost Logging
  ├── Check Redis L1 prompt cache (SHA256 hash of model + system + user prompt)
  ├── Call OpenRouter (`https://openrouter.ai/api/v1/chat/completions`)
  └── Record immutable entry in ai_audit_log (model, tokens, cost, latency)
```

### Default Model Routing Table (OpenRouter Catalog)

| Task Type | Free Tier | Plus Tier (₹499/mo) | Pro Tier (₹999/mo) | Enterprise | Rationale |
|---|---|---|---|---|---|
| **Project Builder** | `deepseek/deepseek-chat-v3-0324` | `openai/gpt-4o-mini` | `anthropic/claude-sonnet-4` | Custom / Any | Complex JSON netlist & code generation |
| **Risk Score Engine** | `deepseek/deepseek-chat-v3-0324` | `google/gemini-2.0-flash` | `anthropic/claude-sonnet-4` | Custom / Any | Safety-critical design validation |
| **Datasheet Simplifier** | `deepseek/deepseek-chat-v3-0324` | `openai/gpt-4o-mini` | `openai/gpt-4o` | Custom / Any | Long technical PDF context processing |
| **Thermal / EMI Analysis** | `deepseek/deepseek-chat-v3-0324` | `openai/gpt-4o-mini` | `anthropic/claude-sonnet-4` | Custom / Any | Physical rules combined with LLM narrative |
| **Debug Wizard (Chat)** | `deepseek/deepseek-chat-v3-0324` | `google/gemini-2.0-flash` | `openai/gpt-4o` | Custom / Any | Multi-turn conversational fault diagnosis |
| **Component ID (Vision)** | ❌ Blocked | `openai/gpt-4o-mini` | `openai/gpt-4o` | Custom / Any | Vision OCR and package identification |
| **PCB Damage (Vision)** | ❌ Blocked | `openai/gpt-4o-mini` | `openai/gpt-4o` | Custom / Any | Vision bounding-box inspection |
| **Learning Tutor** | `deepseek/deepseek-chat-v3-0324` | `google/gemini-2.0-flash` | `anthropic/claude-sonnet-4` | Custom / Any | Pedagogical explanations and quizzes |
| **Embeddings** | `openai/text-embedding-3-small` | `openai/text-embedding-3-small` | `openai/text-embedding-3-small` | Dedicated / Same | Vector search for public and user RAG |

---

## 4. Failover & Resilience System

### Circuit Breaker Pattern (Per-Model Tracking)

Rather than tracking an entire provider outage, the circuit breaker tracks errors on a per-model basis via Redis sliding windows. If a specific upstream model experiences degradation or rate limiting, traffic falls back dynamically to the next prioritized model for that plan.

```python
class ModelCircuitBreaker:
    """
    Tracks error rates per OpenRouter model ID.
    Opens circuit (bypasses model to fallback) when error rate exceeds threshold.
    """
    def __init__(self, model_id: str, redis_client):
        self.model_id = model_id
        self.redis = redis_client
        self.window_seconds = 300  # 5-minute sliding window
        self.threshold = 0.05      # 5% error rate opens circuit
        self.cooldown = 60         # 60s cooldown before half-open probe

    async def record_call(self, success: bool):
        key = f"circuit:{self.model_id}:window"
        now = time.time()
        await self.redis.zadd(key, {f"{now}:{1 if success else 0}": now})
        await self.redis.zremrangebyscore(key, 0, now - self.window_seconds)

    async def is_healthy(self) -> bool:
        key = f"circuit:{self.model_id}:window"
        now = time.time()
        calls = await self.redis.zrangebyscore(key, now - self.window_seconds, now)
        if len(calls) < 10:  # Need minimum sample size
            return True
        failures = sum(1 for c in calls if c.decode().endswith(":0"))
        return (failures / len(calls)) < self.threshold
```

### Dynamic Fallback Chain

When a request executes, `model_router.py` evaluates the plan's prioritized fallback chain from `plan_model_access`:

```
[Pro User - Risk Score Request]
Primary Target: anthropic/claude-sonnet-4 (Priority 100)
    │ (Circuit Open / HTTP 5xx / Rate Limited)
    ▼
Secondary: openai/gpt-4o (Priority 80)
    │ (Fails)
    ▼
Tertiary: google/gemini-2.5-pro (Priority 60)
    │ (Fails)
    ▼
Emergency Fallback: openai/gpt-4o-mini (Priority 20)
    │ (Fails)
    ▼
Cached Response: Redis L1 Cache (served even if expired, with stale-warning header)
    │ (Cache Miss)
    ▼
Structured API Error: {
    "success": False,
    "error": {
        "code": "AI_SERVICE_DEGRADED",
        "message": "AI inference engine temporarily unavailable. Please retry in 30 seconds."
    }
}
```

The fallback sequence occurs server-side within the request timeout (or async Celery job retry) without leaking internal provider routing state to end users.

---

## 5. Prompt Engineering Standards

### Prompt Template Architecture

Every prompt is a Python class with:
- `version`: semantic version string (`"2.1.0"`)
- `render(**kwargs) -> dict`: returns `{system: str, user: str}`
- `output_schema: dict`: the Pydantic schema the response must match
- `temperature: float`: task-specific temperature (deterministic: 0.0–0.1, creative: 0.3–0.5)

```python
class RiskScorePrompt(PromptTemplate):
    version = "2.3.0"
    temperature = 0.1  # Low: scoring must be consistent

    def render(self, circuit_description: str, rag_context: str, user_plan: str) -> dict:
        return {
            "system": f"""You are a senior hardware validation engineer with 20 years of PCB design experience.
Your task is to analyze a circuit design and return a validated JSON risk assessment.

CONTEXT FROM KNOWLEDGE BASE:
{rag_context}

RESPONSE REQUIREMENTS:
- Return ONLY valid JSON. No preamble, no markdown code fences.
- All scores must be integers 0-100.
- Every factor in risk_factors must include specific component references where applicable.
- recommendations must include actionable specifics (component values, placement distances, etc.)
""",
            "user": f"Analyze this circuit design and return a risk score:\n\n{circuit_description}"
        }

    output_schema = RiskScoreOutput  # Pydantic model
```

### JSON Enforcement Strategy

Every prompt that requires structured output:
1. Instructs the model to return ONLY JSON (no markdown fences, no preamble)
2. Provides the schema inline in the system prompt
3. Sets `temperature ≤ 0.1` (low temperature = higher JSON compliance)
4. Uses Claude's `response_format={"type": "json_object"}` or OpenAI's JSON mode when available

If the response fails JSON parsing, the **repair pipeline** activates (see Section 7).

---

## 6. RAG Retrieval Flow

### Query-Time Retrieval Pipeline

```
USER QUERY TEXT
       │
       ▼
[1] Entity Extraction (fast NLP)
    Extract: component names, circuit topology keywords, failure symptoms
    Example: "ESP32 WiFi overheating" → entities: ["ESP32", "WiFi", "thermal", "overheating"]

       │
       ▼
[2] PARALLEL RETRIEVAL (ChromaDB + Neo4j simultaneously)

    ChromaDB Vector Search:
    ├── query_embedding = embed_with_cache(user_query)
    ├── results = chroma.query(query_embedding, n=7)
    └── Filter: relevance_score > 0.70

    Neo4j Graph Traversal:
    ├── For each extracted entity:
    │   MATCH (e:Component|Symptom {name: entity})
    │         -[:APPEARS_IN|INDICATES]->
    │         (c:Circuit|Failure)
    │         -[:HAS_FAILURE|FIXED_BY]->
    │         (f:Failure|Fix)
    │   RETURN f, c ORDER BY f.frequency DESC LIMIT 5
    └── Returns: structured failure/fix objects with frequencies

       │
       ▼
[3] RESULT FUSION AND RANKING
    Merge vector results + graph results
    Deduplication: remove duplicates by source_id
    Re-rank by: (vector_score × 0.6) + (graph_frequency_weight × 0.4)
    Keep top 5 results

       │
       ▼
[4] CONTEXT ASSEMBLY WITH TOKEN BUDGET
    token_budget = 2000  # Reserved for RAG context in prompt
    context_blocks = []
    for result in ranked_results:
        if token_count(context_blocks + result) < token_budget:
            context_blocks.append(format_for_llm(result))
        else:
            break  # Budget exhausted — better to truncate than overflow

       │
       ▼
[5] INJECT INTO PROMPT
    system_prompt = base_prompt + "\n\nRELEVANT CONTEXT:\n" + "\n---\n".join(context_blocks)
```

### Context Quality Filtering

Not all retrieved context is injected. A result is excluded if:
- Relevance score < 0.70 (low semantic similarity)
- `created_at` > 2 years old AND `user_upvotes` < 3 (stale, unvalidated)
- Domain mismatch (e.g., RF circuit context injected into DC power query)
- Content contradicts engineering rules in the rule engine (flagged as bad data)

---

## 7. Output Verification Pipeline

### Multi-Stage Validation

Every AI response passes through this pipeline before reaching the service layer:

```
RAW LLM RESPONSE (string)
       │
       ▼
STAGE 1: JSON PARSING
  json.loads(response)
  ├── Success → proceed
  └── Failure → REPAIR PIPELINE:
                  repair_prompt = "Fix this malformed JSON: {response}"
                  repaired = llm.complete(repair_prompt, temperature=0)
                  json.loads(repaired)
                  └── Failure again → raise AIOutputError(stage="json_parse")

       │
       ▼
STAGE 2: SCHEMA VALIDATION (Pydantic)
  ResponseModel.model_validate(parsed_json)
  ├── Success → proceed
  └── Failure → log field errors → attempt field-level repair
                └── Failure → raise AIOutputError(stage="schema_validate")

       │
       ▼
STAGE 3: ENGINEERING RULE VALIDATION
  engineering_rule_engine.validate(response, context)
  Rules checked:
  ├── Voltage recommendations: never exceed component absolute max rating
  ├── Current recommendations: respect wire gauge and trace width limits
  ├── Temperature recommendations: junction temp must be < 85% of max rated
  ├── Component values: resistor values must be within E24/E96 series
  ├── Confidence floor: if score < 0.6 on any critical field → flag for review
  └── Contradiction check: response must not contradict physics (e.g., efficiency > 100%)
  ├── All rules pass → proceed
  └── Rule violations → log violations → retry with violation context added to prompt
                         └── Failure after retry → raise AIOutputError(stage="engineering_rules")

       │
       ▼
STAGE 4: CONFIDENCE SCORING
  confidence = calculate_confidence(response, rag_context_quality, provider_health)
  if confidence < CONFIDENCE_THRESHOLD[feature]:
      response.confidence_flag = "low"
      response.review_recommended = True
  # Low confidence responses are delivered but flagged in the UI

       │
       ▼
VALIDATED RESPONSE → service layer → user
```

### Confidence Threshold by Feature

| Feature | Confidence Threshold | On Low Confidence |
|---|---|---|
| Risk Score | 0.75 | Show score but add "Review recommended" banner |
| Failure Prediction (severity: critical) | 0.85 | Escalate to human review queue |
| Component Identification | 0.70 | Show result but prompt user to verify datasheet |
| PCB Damage Detection | 0.80 | Show annotations with confidence per region |
| Circuit Simulation narrative | 0.65 | Delivered; simulation numbers are deterministic |
| Debug Wizard suggestions | 0.70 | Delivered; user is asking for guidance, not specification |

---

## 8. AI Memory Architecture

### Session Memory (Short-Term)

The Debug Wizard and Learning Tutor maintain conversation state within a session. State is stored in Redis with a 2-hour TTL and referenced by `session_id`:

```python
session_memory = {
    "session_id": "uuid",
    "feature": "debug_wizard",
    "turns": [
        {"role": "user", "content": "output voltage drops under load"},
        {"role": "assistant", "content": "...", "hypotheses": [...]},
        {"role": "user", "content": "yes, it drops to 2.8V at 500mA"},
        # ...
    ],
    "accumulated_context": {
        "symptom": "voltage drop under load",
        "eliminated_hypotheses": ["insufficient input voltage", "wrong feedback resistor"],
        "current_hypothesis": "inadequate output capacitance"
    }
}
```

Each subsequent LLM call includes the full `turns` history plus `accumulated_context`. The accumulated context is a structured summary that prevents the LLM from revisiting eliminated hypotheses.

### Project Memory (Long-Term)

User projects stored in PostgreSQL include `circuit_data` as JSON — the full circuit description at time of save. When a user says "continue with last week's motor driver," the system:
1. Fetches the project by name/date from `projects` table
2. Reconstructs the circuit description from `circuit_data`
3. Injects it as context into the new LLM call
4. Continues the design conversation with full historical context

This is not true "memory" — it is structured context injection. The distinction matters: the LLM does not retain state; the application retrieves and injects it explicitly.

---

## 9. Agentic Workflows

### Current: Single-Turn Validated Chains

Most features follow a linear chain:
`Input → RAG retrieval → Prompt construction → LLM call → Validation → Output`

### Near-Term: Multi-Step Orchestration

The Debug Wizard already approximates an agentic loop: each user answer triggers a new LLM call that narrows the hypothesis space. The next evolution is formalizing this pattern:

```python
class DebugAgent:
    """
    Runs a structured diagnostic loop until root_cause_confidence > 0.90
    or max_turns = 8 is reached.
    """
    async def run(self, initial_symptom: str) -> DiagnosisResult:
        state = AgentState(symptom=initial_symptom, turn=0)
        while state.root_cause_confidence < 0.90 and state.turn < 8:
            next_action = await self._plan_next_step(state)
            if next_action.type == "ask_user":
                yield UserQuestion(next_action.question)
                user_response = await self._await_user_input()
                state.add_evidence(user_response)
            elif next_action.type == "run_rule_check":
                result = await rule_engine.check(state.circuit_context, next_action.rule)
                state.add_evidence(result)
            elif next_action.type == "conclude":
                return DiagnosisResult(
                    root_cause=next_action.conclusion,
                    confidence=state.root_cause_confidence,
                    fix=next_action.fix,
                    test_points=next_action.test_points
                )
            state.turn += 1
```

The critical engineering constraint on agentic workflows: **every tool call within the agent must be validated before affecting state**. An agent that autonomously generates a wrong circuit and then builds analysis on top of it compounds errors. Each step is independently validated.

---

## 10. Hallucination Prevention

### Primary Defenses

1. **RAG grounding:** Every design generation is anchored to verified reference circuits. The LLM is not inventing from scratch — it is adapting known-good designs.

2. **Low temperature:** All structured outputs use temperature ≤ 0.1. Higher temperature means more creative, less reliable.

3. **Engineering rule engine:** Post-generation validation catches physically impossible outputs (efficiency > 100%, voltage recommendations exceeding component ratings).

4. **Component value series enforcement:** Resistor and capacitor values are validated against E24/E96/E192 series. An LLM that hallucinates "27.3Ω" is corrected to the nearest E96 value.

5. **Datasheet-backed specifications:** When the user uploads a component's datasheet, absolute max ratings are extracted and stored. Any AI recommendation for that component is validated against its actual datasheet values — not the LLM's training data.

### Detection Metrics

- `hallucination_rate`: % of outputs that fail engineering rule validation per prompt template
- Alert threshold: >5% hallucination rate for any prompt → automatic prompt review triggered
- Per-prompt hallucination tracking enables regression detection when model versions change

---

*Document Owner: AI Engineering Team*
*Last Updated: Q1 2025*
