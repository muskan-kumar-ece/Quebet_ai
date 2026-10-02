# QUEBET AI — Subscription & Token Economics
> Version 2.0 | OpenRouter-Powered Monetization | Admin-Managed Model Routing

---

## 1. Plan Architecture

### Plan Philosophy

The plan structure is designed around four economic goals:

1. **Free plan drives organic acquisition.** Uses ultra-cheap models (DeepSeek, Gemma free) to demonstrate real value to students at near-zero marginal cost (~$0.03/user/month). Restrictive enough that power users hit the ceiling and upgrade.
2. **Plus plan captures price-sensitive users.** ₹499/month (≈$6 USD) — affordable for students and hobbyists who need better models (Gemini Flash, GPT-4o-mini) and more daily generations than Free allows.
3. **Pro plan is the primary revenue driver.** ₹999/month (≈$12 USD) — premium models (Claude Sonnet 4, GPT-4o), unlimited vision, full exports. Priced for Indian engineers. Volume × accessible price > low volume × high price.
4. **Enterprise plan is the high-margin tier.** Custom contracts, all models, on-premise deployments, private knowledge graphs. These are ARR contracts, not monthly.

### AI Gateway: OpenRouter

All LLM calls route through **OpenRouter** (`api.openrouter.ai`) — a unified gateway to 500+ models from every major provider. This eliminates the need for separate API keys per provider and enables:

- **One API key, all models** — single billing dashboard, single SDK (OpenAI-compatible)
- **User model switching** — users select their preferred model from a plan-gated list
- **Admin-managed routing** — model assignments stored in PostgreSQL, editable from admin panel without code deploys
- **Built-in fallback** — if a model is down, OpenRouter routes to an alternative automatically
- **Future-proof** — when a new model launches on OpenRouter, admin adds it to the routing table in 30 seconds

---

## 2. Plan Definitions

### Free Plan — ₹0/month

**Target user:** College student, hobbyist, first-time user evaluating the platform

| Resource | Limit | Enforcement |
|---|---|---|
| AI generations | 10/day | Redis counter: `rate:free:{user_id}:daily_gen` |
| LLM models | DeepSeek V3 only | `model_router.get_model(plan="free", task)` |
| Model selection | Locked — no user choice | Model selector UI disabled for free tier |
| Fallback model | `deepseek/deepseek-chat-v3-0324` | If primary free model unavailable |
| Vision features | Not available | Plan gate in BFF middleware |
| PCB damage detection | Not available | Plan gate in BFF middleware |
| Circuit simulation | 1/day, 10-component limit | Redis + netlist component count check |
| Risk score | Available (text input only, no PDF export) | Feature flag: `PDF_EXPORT=false` |
| Knowledge graph | Read-only access | Route middleware |
| RAG retrieval | Public KB only (no user project personalization) | `user_id` filter excluded in ChromaDB queries |
| Project history | 5 projects, 30-day retention | PostgreSQL row count gate + scheduled cleanup |
| Export | No PDF reports, no BOM CSV export | Feature flag |
| Concurrent jobs | 1 | Redis semaphore: `jobs:concurrent:{user_id}` |
| Job queue priority | lowest | Celery routing: `queue="low_priority"` |
| API access | No | Blocked at BFF |
| Model badge shown | Yes — "Powered by DeepSeek" in response footer | Encourages upgrades |

**Free Tier Model Routing:**

| Task Type | OpenRouter Model ID | Cost/1M Input | Cost/1M Output |
|---|---|---|---|
| All text tasks | `deepseek/deepseek-chat-v3-0324` | $0.27 | $1.10 |
| Embedding | `openai/text-embedding-3-small` | $0.02 | N/A |
| Vision | ❌ Not available | — | — |

**Estimated AI cost per free user per month:**
- 5 gen/day actual (avg) × 30 days = 150 generations
- Average 1,500 input tokens + 800 output tokens per generation
- Cost: 150 × (1500 × $0.27/1M + 800 × $1.10/1M) = 150 × ($0.000405 + $0.00088) = **$0.19/month**
- With 60% cache hit rate (free users ask common questions): effective cost ~**$0.08/month per free user**

---

### Plus Plan — ₹499/month

**Target user:** Engineering student needing better models, hobbyist engineer, budget-conscious professional

| Resource | Limit |
|---|---|
| AI generations | 50/day |
| LLM models | Gemini 2.0 Flash + GPT-4o-mini (user can switch) |
| Model selection | User picks from curated list of 3 models |
| Vision features | 15/day (GPT-4o-mini vision) |
| PCB damage detection | Available |
| Circuit simulation | 5/day, 25-component limit |
| Risk score | Full (including PDF export) |
| Knowledge graph | Read-only access |
| RAG retrieval | Public KB + personal project corpus |
| Project history | 25 projects, 90-day retention |
| Export | PDF reports, BOM CSV |
| Concurrent jobs | 3 |
| Job queue priority | normal |
| API access | No |
| Model badge shown | Yes — shows selected model name |

**Plus Tier Model Routing:**

| Task Type | Default Model | User Can Switch To |
|---|---|---|
| Default (text) | `google/gemini-2.0-flash` | GPT-4o-mini, DeepSeek V3 |
| Risk Score | `google/gemini-2.0-flash` | GPT-4o-mini |
| Project Builder | `openai/gpt-4o-mini` | Gemini Flash |
| Failure Prediction | `google/gemini-2.0-flash` | GPT-4o-mini |
| Datasheet Simplify | `openai/gpt-4o-mini` | Gemini Flash |
| Thermal Analysis | `openai/gpt-4o-mini` | — (cheapest model auto-selected) |
| EMI Analysis | `google/gemini-2.0-flash` | GPT-4o-mini |
| Debug Wizard | `google/gemini-2.0-flash` | GPT-4o-mini |
| Component ID (vision) | `openai/gpt-4o-mini` | — |
| PCB Damage (vision) | `openai/gpt-4o-mini` | — |
| Learning Tutor | `google/gemini-2.0-flash` | GPT-4o-mini, DeepSeek |
| Embedding | `openai/text-embedding-3-small` | — |

**User-Selectable Models (Plus):**
1. `google/gemini-2.0-flash` — Fast, good quality, cost-effective
2. `openai/gpt-4o-mini` — Reliable, excellent for structured JSON output
3. `deepseek/deepseek-chat-v3-0324` — Budget option, strong reasoning

**Estimated cost per Plus user/month:**
- 25 gen/day actual (avg) × 30 = 750 generations
- Model mix: 60% Gemini Flash ($0.75/$3.75 per 1M), 40% GPT-4o-mini ($0.15/$0.60 per 1M)
- Average 1,800 input + 1,000 output tokens
- Gemini: 450 × (1800 × $0.75/1M + 1000 × $3.75/1M) = 450 × $0.00510 = $2.30
- GPT-4o-mini: 300 × (1800 × $0.15/1M + 1000 × $0.60/1M) = 300 × $0.00087 = $0.26
- Vision: ~$0.20/month (15 calls × 5 days)
- Total before caching: **$2.76/month**
- With 45% cache hit: ~**$1.52/month**
- **Gross margin at ₹499 ($6): $6 - $1.52 (AI) - $0.50 (infra) = $3.98 (~66% margin)**

---

### Pro Engineer Plan — ₹999/month

**Target user:** Professional engineer, hardware startup founder, PCB designer

| Resource | Limit |
|---|---|
| AI generations | 200/day |
| LLM models | Claude Sonnet 4 + GPT-4o + Gemini 2.5 Pro (task-routed + user selectable) |
| Model selection | User picks from curated list of 6+ models |
| Vision features | Unlimited (GPT-4o full vision) |
| All analysis features | Full access |
| Circuit simulation | Unlimited, 100-component limit |
| Risk score | Full + version comparison + team sharing |
| Knowledge graph | Read + contribute (add failure cases) |
| RAG retrieval | Public KB + personal project corpus |
| Project history | Unlimited, 12-month retention |
| Export | All formats (PDF, CSV, KiCad-compatible JSON) |
| Concurrent jobs | 5 |
| Job queue priority | high |
| API access | Yes (1,000 requests/day) |
| BOM optimization | Full (live pricing APIs) |
| Indian alternatives | Full (including real-time availability) |
| Model badge shown | Shows selected model name |

**Pro Tier Model Routing:**

| Task Type | Default Model | Optimized For |
|---|---|---|
| Default (text) | `anthropic/claude-sonnet-4` | Best reasoning quality |
| Risk Score | `anthropic/claude-sonnet-4` | Safety-critical accuracy |
| Project Builder | `anthropic/claude-sonnet-4` | Complex JSON generation |
| Failure Prediction | `anthropic/claude-sonnet-4` | Engineering edge cases |
| Datasheet Simplify | `openai/gpt-4o` | Long document processing |
| Thermal Analysis | `openai/gpt-4o-mini` | Simple calc — cheap model sufficient |
| EMI Analysis | `anthropic/claude-sonnet-4` | Complex physics reasoning |
| Debug Wizard | `openai/gpt-4o` | Multi-turn conversation |
| Component ID (vision) | `openai/gpt-4o` | Best vision accuracy |
| PCB Damage (vision) | `openai/gpt-4o` | Best vision accuracy |
| Learning Tutor | `anthropic/claude-sonnet-4` | Best explanation quality |
| Embedding | `openai/text-embedding-3-small` | Industry standard |

**User-Selectable Models (Pro):**
1. `anthropic/claude-sonnet-4` — Best reasoning, highest quality
2. `openai/gpt-4o` — Excellent all-rounder, strong vision
3. `openai/gpt-4o-mini` — Fast and cheap for simple tasks
4. `google/gemini-2.0-flash` — Fast, good for iterative work
5. `google/gemini-2.5-pro` — Strong reasoning, long context
6. `deepseek/deepseek-chat-v3-0324` — Budget option, strong coding

**Estimated cost per Pro user/month:**
- 40 gen/day actual (avg) × 30 = 1,200 generations
- Model mix: 50% Claude Sonnet ($3/$15 per 1M), 30% GPT-4o ($2.50/$10 per 1M), 20% GPT-4o-mini
- Average 2,000 input + 1,500 output tokens
- Claude: 600 × (2000 × $3/1M + 1500 × $15/1M) = 600 × $0.0285 = $17.10
- GPT-4o: 360 × (2000 × $2.50/1M + 1500 × $10/1M) = 360 × $0.020 = $7.20
- GPT-4o-mini: 240 × (2000 × $0.15/1M + 1000 × $0.60/1M) = 240 × $0.0009 = $0.22
- Vision: ~$2/month
- Embedding: ~$0.50/month
- Total before caching: **$27.02/month**
- With 45% cache hit rate: ~**$14.86/month**

⚠️ **At ₹999/month ($12), the raw AI cost exceeds the subscription price for heavy users.** This is addressed by:
1. The 200/day limit prevents worst-case scenarios
2. Actual average usage is ~30–40 generations/day for active Pro users
3. Cache hit rates of 45–50% reduce costs significantly
4. Model downgrade: simple tasks (thermal, tutor common questions) auto-route to GPT-4o-mini
5. Admin can dynamically adjust routing from the admin panel to optimize costs

**Realistic cost per Pro user (actual usage patterns):**
- 30 gen/day average × 30 = 900 generations
- With 50% cache hit rate: ~450 actual LLM calls
- Blended cost with smart routing: ~**$8/month AI costs**
- **Gross margin at ₹999 ($12): $12 - $8 (AI) - $1 (infra) = $3 (~25% margin)**
- **At scale (5,000+ users), cache rates improve to 55%+, margin reaches 40%+**

---

### Team Plan — ₹4,999/month (up to 5 users)

| Feature | Specification |
|---|---|
| Everything in Pro | Per-user Pro limits |
| LLM models | Same as Pro (all 6+ models available per user) |
| Shared knowledge graph | Team-scoped Neo4j namespace |
| BOM collaboration | Multi-user BOM editing with change tracking |
| Shared project library | Team-accessible project repository |
| Admin dashboard | Usage analytics per team member + model usage breakdown |
| Priority support | < 4h response time SLA |
| API access | 5,000 requests/day (team-wide) |

**Cost per seat:** ₹4,999 / 5 = ₹1,000/seat — marginal premium over Pro for collaboration features
**Target:** Hardware startups, R&D teams at manufacturing companies

---

### Enterprise Plan — Custom Pricing (₹50,000–₹5,00,000+/month)

| Feature | Specification |
|---|---|
| Everything in Team | Unlimited seats (per contract) |
| LLM models | **All models on OpenRouter** — full catalog access |
| Model override | Users can select ANY model on OpenRouter (not just curated list) |
| Custom model routing | Admin configures task→model routing specific to their workflows |
| Private knowledge graph | Customer-owned Neo4j instance (their data stays private) |
| Private vector DB | Dedicated ChromaDB instance seeded with their circuit corpus |
| On-premise deployment | Full Docker/K8s deployment on customer infrastructure |
| SSO / SAML | Integration with customer identity provider (Okta, Azure AD) |
| Audit logs | Complete AI interaction audit trail for compliance |
| SLA | 99.9% uptime with financial penalties |
| Dedicated support | Named account engineer + Slack channel |
| Custom fine-tuning | Option to fine-tune embeddings on customer circuit corpus |

**Enterprise contract economics:**
- ₹50,000/month × 12 = ₹6,00,000 ARR at minimum deal size
- Infrastructure cost per enterprise tenant: ~₹8,000–12,000/month (dedicated DB instances, workers)
- Target gross margin: 75–80%

---

## 3. Token Economics and Cost Analysis

### Token Budget Allocation by Feature (OpenRouter Pricing)

| Feature | Avg Input Tokens | Avg Output Tokens | Free Model | Plus Model | Pro Model | Pro Cost/Call |
|---|---|---|---|---|---|---|
| Project Builder | 2,500 | 2,000 | DeepSeek V3 | GPT-4o-mini | Claude Sonnet 4 | $0.037 |
| Risk Score | 2,000 | 1,500 | DeepSeek V3 | Gemini Flash | Claude Sonnet 4 | $0.028 |
| Datasheet Simplifier | 4,000 | 2,000 | DeepSeek V3 | GPT-4o-mini | GPT-4o | $0.030 |
| Thermal Analysis | 800 | 600 | DeepSeek V3 | GPT-4o-mini | GPT-4o-mini | $0.0005 |
| Debug Wizard (per turn) | 1,500 | 800 | DeepSeek V3 | Gemini Flash | GPT-4o | $0.012 |
| Component ID (vision) | image + 200 | 400 | ❌ | GPT-4o-mini | GPT-4o | $0.008 |
| PCB Damage (vision) | image + 300 | 600 | ❌ | GPT-4o-mini | GPT-4o | $0.010 |
| Learning Tutor | 1,200 | 1,500 | DeepSeek V3 | Gemini Flash | Claude Sonnet 4 | $0.026 |

### Monthly Platform Cost at Scale

**Scenario: 2,000 Pro users, 5,000 Plus users, 20,000 Free users, 10 Enterprise tenants**

```
Free users (20,000):
  Avg 5 gen/day × 20,000 × 30 = 3,000,000 calls
  With 60% cache: 1,200,000 actual DeepSeek calls
  DeepSeek at ~$0.0008/call: $960/month AI cost
  Revenue: $0
  → Free tier is a CAC investment (~$0.05/user/month)

Plus users (5,000):
  Avg 25 gen/day × 5,000 × 30 = 3,750,000 calls
  With 45% cache: 2,062,500 actual calls
  Blended at ~$0.002/call: $4,125/month AI cost
  Revenue: 5,000 × ₹499 = ₹24,95,000 ($30,000)
  Margin after AI: ~$25,875 (~86% margin)

Pro users (2,000):
  Avg 40 gen/day × 2,000 × 30 = 2,400,000 calls
  With 50% cache: 1,200,000 actual calls
  Blended at ~$0.012/call: $14,400/month AI cost
  Revenue: 2,000 × ₹999 = ₹19,98,000 ($24,000)
  Margin after AI: ~$9,600 (~40% margin)

Enterprise (10):
  Avg $2,000/month AI cost per tenant
  Revenue: avg ₹1,50,000/month per tenant × 10 = ₹15,00,000 ($18,000)
  AI cost: $20,000
  Infra cost: $5,000
  Margin: ~$0 at 10 tenants (enterprise is loss-leading until 25+ tenants)

Total at this scale:
  Revenue: $0 + $30,000 + $24,000 + $18,000 = $72,000/month
  AI cost: $960 + $4,125 + $14,400 + $20,000 = $39,485/month
  Infra: ~$8,000/month
  Gross margin: ~34% ($24,515/month)
  
Break-even to healthy margin:
  Target: 5,000 Pro + 10,000 Plus + 50 Enterprise
  Revenue: $60,000 + $60,000 + $90,000 = $210,000/month
  Total AI cost: ~$85,000/month (cache rates improve at scale)
  Infra: ~$15,000/month
  Gross margin: ~52%
```

---

## 4. Cost Optimization Strategies

### Redis Prompt Caching Impact

The same datasheet simplification (e.g., "simplify LM317 datasheet for student") is requested by hundreds of users. Without caching:
- 500 requests × $0.030 = $15

With Redis L1 cache (TTL 1h):
- 1 LLM call + 499 cache hits = $0.030 + negligible Redis cost

**Rule:** Any prompt that includes only public data (not user-specific context) is a caching candidate. Features where caching applies:
- Datasheet simplification (high cache rate — same popular components)
- Component identification for standard packages (555 timer, LM317, etc.)
- Learning tutor for common concepts ("explain Kirchhoff's laws")

Features where caching does NOT apply:
- Risk score (user-specific circuit)
- Debug wizard (session-specific)
- PCB damage detection (unique image)

### Smart Model Downgrade (Automatic)

For Pro users, the system automatically routes simple tasks to cheaper models:
- Thermal analysis → always `gpt-4o-mini` (simple calculation, doesn't need Claude)
- Common datasheet queries (cache miss but standard part) → `gpt-4o-mini` instead of `gpt-4o`
- Repeated learning tutor questions in same session → downgrade to Gemini Flash after 3rd turn

Admin can configure these downgrade rules from the admin panel.

### Batching Embeddings

New circuit embeddings do not need to be generated immediately. They are batched:
- Celery `low_priority` worker runs embedding job every 15 minutes
- Batch of 50 circuits → 1 API call with 50 inputs
- Cost: same as 50 individual calls but 10x fewer API round trips

### Free Tier DeepSeek Lock

DeepSeek V3 at $0.27/$1.10 per 1M tokens is approximately 10× cheaper than Claude Sonnet and 3× cheaper than GPT-4o-mini. All free tier users are hard-routed to DeepSeek via `model_router.get_model(plan="free")`. The model selection UI in Settings is disabled for free users. A "Powered by DeepSeek" badge in the response footer subtly encourages upgrades.

### OpenRouter-Specific Optimizations

1. **Provider routing within OpenRouter:** OpenRouter lets you specify preferred providers for the same model. For DeepSeek, routing via DeepInfra or Together is often cheaper than the default provider.
2. **Prompt caching at provider level:** Anthropic and OpenAI support prompt caching natively. OpenRouter passes these savings through. System prompts that are reused across calls get cached at the provider level.
3. **Model fallback via OpenRouter:** If Claude is down, OpenRouter automatically falls back. Our circuit breaker tracks per-model error rates and proactively switches before OpenRouter's own fallback kicks in.

---

## 5. Fair Usage and Rate Limiting

### 4-Layer Rate Limiting Stack

```
Layer 1 — BFF rate limit (Redis, per minute):
  Free:       10 req/min per endpoint
  Plus:       30 req/min per endpoint
  Pro:        60 req/min per endpoint
  Team:       60 req/min per user per endpoint
  Enterprise: 300 req/min per endpoint
  Admin override: rate limits configurable from admin panel per plan

Layer 2 — Daily generation counter (Redis, resets at midnight IST):
  Free:       10 generations/day
  Plus:       50 generations/day
  Pro:        200 generations/day
  Team:       200/day per user
  Enterprise: Unlimited (tracked for billing)
  Key: rate:{plan}:{user_id}:daily_gen

Layer 3 — Concurrent job limiter (Redis semaphore):
  Free:       1 concurrent job
  Plus:       3 concurrent jobs
  Pro:        5 concurrent jobs
  Team:       5 per user
  Enterprise: Custom (default 10)
  Key: jobs:concurrent:{user_id}
  Prevents one user from queuing 50 jobs simultaneously

Layer 4 — Unusual usage detection (async analysis):
  If user generates >80% of daily limit in <1 hour → flag for review
  If user submits identical prompts >10 times → suspected automation abuse → throttle
  If user switches models >20 times in 1 hour → flag for review
  All flags visible in admin panel for manual review
```

### Vision Feature Limits

| Plan | Vision Calls/Day | Enforcement |
|---|---|---|
| Free | 0 (blocked) | BFF middleware returns 403 |
| Plus | 15 | Redis counter: `rate:plus:{user_id}:daily_vision` |
| Pro | Unlimited | No counter |
| Enterprise | Unlimited | No counter |

### API Access Limits (Pro+)

Pro API access (1,000 calls/day) is intended for integrations, not for building competing products on top of QUEBET AI's AI layer. Terms of Service restrictions:
- API outputs may not be used to train competing models
- API access is per-user, not per-application (no reselling)
- Anomalous patterns (identical prompts at machine speed) trigger account review
- Team plan: 5,000 calls/day shared across team
- Enterprise: Custom limits per contract

---

## 6. Admin-Managed Model Configuration

### Architecture

Model routing is **NOT hardcoded** in source code. It is stored in PostgreSQL and cached in Redis, managed via an admin panel at `/admin/models`. This means:

- Adding a new model (e.g., when Claude Opus 4 launches) requires zero code deployment
- Moving all Pro users from one model to another is a 30-second admin action
- A/B testing different models per plan is possible without engineering involvement
- Cost spikes can be addressed immediately by routing to cheaper models

### Database Schema

```sql
-- Admin-managed model configurations
CREATE TABLE model_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id TEXT NOT NULL UNIQUE,         -- OpenRouter model ID, e.g. "anthropic/claude-sonnet-4"
    display_name TEXT NOT NULL,             -- Human-readable, e.g. "Claude Sonnet 4"
    provider TEXT NOT NULL,                -- Provider name, e.g. "anthropic", "openai", "google"
    is_vision_capable BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,        -- Admin can disable without removing
    cost_per_1k_input NUMERIC(10,6),       -- For cost tracking and display
    cost_per_1k_output NUMERIC(10,6),
    max_context_tokens INTEGER,
    supports_json_mode BOOLEAN DEFAULT TRUE,
    supports_streaming BOOLEAN DEFAULT TRUE,
    notes TEXT,                            -- Admin notes (e.g. "Good for electronics reasoning")
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Which plans can access which models + routing priority
CREATE TABLE plan_model_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan TEXT NOT NULL,                     -- free | plus | pro | team | enterprise
    task_type TEXT NOT NULL,                -- default | risk_score | project_builder | failure_prediction |
                                           -- datasheet | thermal | emi | debug_wizard |
                                           -- component_id | pcb_damage | tutor | embedding
    model_id TEXT NOT NULL REFERENCES model_configs(model_id),
    priority INTEGER DEFAULT 0,            -- Higher = preferred (fallback ordering)
    is_user_selectable BOOLEAN DEFAULT FALSE, -- Shows in user's model dropdown
    is_default BOOLEAN DEFAULT FALSE,      -- Default selection when user hasn't chosen
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_plan_model_task ON plan_model_access(plan, task_type, model_id);

-- Plan rate limit overrides (admin can change limits without deploy)
CREATE TABLE plan_rate_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan TEXT NOT NULL UNIQUE,
    daily_generations INTEGER NOT NULL,
    daily_vision_calls INTEGER,            -- NULL = unlimited
    max_concurrent_jobs INTEGER NOT NULL,
    bff_requests_per_minute INTEGER NOT NULL,
    api_calls_per_day INTEGER,             -- NULL = no API access
    max_simulation_components INTEGER,
    max_projects INTEGER,                  -- NULL = unlimited
    project_retention_days INTEGER,        -- NULL = unlimited
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by UUID REFERENCES users(id)
);
```

### Admin Panel Features (`/admin/models`)

1. **Model Catalog Management**
   - View all registered OpenRouter models with pricing, capabilities, and status
   - Add new models by entering the OpenRouter model ID (auto-fetches metadata)
   - Toggle models active/inactive globally
   - View real-time usage stats per model (calls, tokens, cost)

2. **Plan Routing Editor**
   - Visual grid editor: rows = task types, columns = plans
   - Each cell shows the assigned model with priority ordering
   - Drag-and-drop to reorder fallback priority
   - Toggle "user selectable" per model per plan
   - Bulk actions: "Copy Pro routing to Team" or "Move all plans from model X to model Y"

3. **Rate Limit Editor**
   - Edit rate limits per plan from the admin panel
   - Changes take effect within 5 minutes (Redis cache TTL)
   - Audit log tracks who changed what and when

4. **Cost Dashboard**
   - Real-time AI cost per plan tier
   - Cost per model breakdown
   - Projected monthly cost at current usage rate
   - Alerts when cost exceeds configurable thresholds

### Cache Strategy

```python
# Model routing resolution with Redis caching
async def get_model(plan: str, task_type: str, user_preferred: str | None = None) -> str:
    """
    Resolve the model to use for this request.
    Priority: user_preferred (if allowed by plan) > plan default > fallback
    """
    # If user has selected a model, verify it's allowed for their plan
    if user_preferred:
        allowed = await get_user_selectable_models(plan)
        if user_preferred in allowed:
            return user_preferred
    
    # Check Redis cache for plan routing
    cache_key = f"model_route:{plan}:{task_type}"
    cached = await redis.get(cache_key)
    if cached:
        return cached
    
    # Query DB: highest priority active model for this plan+task
    result = await db.execute(
        select(PlanModelAccess.model_id)
        .join(ModelConfig, PlanModelAccess.model_id == ModelConfig.model_id)
        .where(PlanModelAccess.plan == plan)
        .where(PlanModelAccess.task_type == task_type)
        .where(PlanModelAccess.is_default == True)
        .where(ModelConfig.is_active == True)
        .order_by(PlanModelAccess.priority.desc())
        .limit(1)
    )
    model_id = result.scalar_one_or_none() or "deepseek/deepseek-chat-v3-0324"
    
    await redis.set(cache_key, model_id, ex=300)  # 5-minute cache
    return model_id

async def invalidate_routing_cache():
    """Called by admin panel when routing changes are saved."""
    keys = await redis.keys("model_route:*")
    if keys:
        await redis.delete(*keys)
```

---

## 7. Model Upgrade Path (Growth Loop)

The subscription tiers are designed to create a natural upgrade funnel:

```
Free (DeepSeek) → User sees "Powered by DeepSeek" badge
  ↓ "Responses are good but I want faster/better"
Plus (Gemini/GPT-4o-mini) → User sees model selector with 3 options
  ↓ "I want Claude quality for my risk analysis"
Pro (Claude/GPT-4o) → User has 6+ model options, full features
  ↓ "My team needs this"
Team → Shared projects, team analytics
  ↓ "Our company needs private deployment"
Enterprise → Custom everything
```

**Key conversion triggers:**
- Free → Plus: hitting 10 gen/day limit, wanting vision features, wanting PDF export
- Plus → Pro: wanting Claude Sonnet quality, hitting 50 gen/day limit, needing API access
- Pro → Team: multiple engineers on same project, need shared knowledge graph
- Team → Enterprise: compliance requirements, private data, on-premise

---

*Document Owner: Product & Finance Team*
*Last Updated: October 2026*
*AI Gateway: OpenRouter (api.openrouter.ai)*
