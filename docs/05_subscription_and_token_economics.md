# QUEBET AI — Subscription & Token Economics
> Version 1.0 | Monetization Architecture | Cost Engineering

---

## 1. Plan Architecture

### Plan Philosophy

The plan structure is designed around three economic goals:

1. **Free plan drives organic acquisition.** Generous enough to demonstrate real value to students. Restrictive enough that power users hit the ceiling and upgrade.
2. **Pro plan is the primary revenue driver.** Priced for Indian engineers (₹999/month ≈ $12 USD), not US market rates. Volume × accessible price > low volume × high price.
3. **Enterprise plan is the high-margin tier.** Custom contracts, on-premise deployments, private knowledge graphs. These are ARR contracts, not monthly.

---

## 2. Plan Definitions

### Free Plan

**Target user:** College student, hobbyist, first-time user evaluating the platform

| Resource | Limit | Enforcement |
|---|---|---|
| AI generations | 10/day | Redis counter: `rate:free:{user_id}:daily_gen` |
| LLM model | gpt-4o-mini only | `provider_factory.get(user.plan)` returns mini |
| Vision features | 3 component identifications/day | Redis counter: `rate:free:{user_id}:daily_vision` |
| PCB damage detection | Not available | Plan gate in BFF middleware |
| Circuit simulation | 1 simulation/day, 10-component limit | Redis + netlist component count check |
| Risk score | Available (limited to text input, no PDF export) | Feature flag: `PDF_EXPORT=false` for free |
| Knowledge graph | Read-only access | Route middleware |
| RAG retrieval | Public KB only (no user project personalization) | `user_id` filter excluded in free tier ChromaDB queries |
| Project history | 5 projects, 30-day retention | PostgreSQL row count gate + scheduled cleanup job |
| Export | No PDF reports, no BOM CSV export | Feature flag |
| Concurrent jobs | 1 | Redis semaphore: `jobs:concurrent:{user_id}` |
| Job queue priority | lowest | Celery routing: `queue="low_priority"` |
| API access | No | Blocked at BFF |

**Estimated AI cost per free user per month:**
- 10 generations/day × 30 days = 300 generations
- Average 1,500 input tokens + 800 output tokens per generation (gpt-4o-mini)
- Cost: 300 × (1500 × $0.15/1M + 800 × $0.60/1M) = 300 × ($0.000225 + $0.00048) = **$0.22/month**
- With 40% cache hit rate: effective cost ~**$0.13/month per free user**

---

### Student Plan — ₹299/month

**Target user:** Engineering student who needs more daily generations and basic export

| Resource | Limit |
|---|---|
| AI generations | 50/day |
| LLM model | gpt-4o-mini + gpt-4o (for analysis features only) |
| Vision features | 15/day |
| PCB damage detection | Available |
| Circuit simulation | 5/day, 25-component limit |
| Risk score | Full (including PDF export) |
| Project history | 25 projects, 90-day retention |
| Export | PDF reports, BOM CSV |
| Concurrent jobs | 2 |
| Job queue priority | normal |
| API access | No |

**Estimated cost per Student user/month:** ~$0.70/month
**Gross margin at ₹299:** ₹299 - ₹58 (cost) = ₹241 (~80% margin)

---

### Pro Engineer Plan — ₹999/month

**Target user:** Professional engineer, hardware startup founder, PCB designer

| Resource | Limit |
|---|---|
| AI generations | 200/day |
| LLM model | claude-3-5-sonnet + gpt-4o (task-routed) |
| Vision features | Unlimited |
| All analysis features | Full access |
| Circuit simulation | Unlimited, 100-component limit |
| Risk score | Full + version comparison + team sharing |
| Knowledge graph | Read + contribute (add failure cases) |
| RAG retrieval | Public KB + personal project corpus |
| Project history | Unlimited, 12-month retention |
| Export | All formats (PDF, CSV, KiCad-compatible JSON) |
| Concurrent jobs | 5 |
| Job queue priority | high |
| API access | Yes (1000 requests/day) |
| BOM optimization | Full (live pricing APIs) |
| Indian alternatives | Full (including real-time availability) |

**Estimated cost per Pro user/month:**
- 200 generations/day × 30 = 6,000 generations
- Mix: 60% claude-3-5-sonnet ($3/$15 per 1M i/o), 40% gpt-4o ($5/$15 per 1M i/o)
- Average 2,000 input + 1,500 output tokens
- Claude cost: 3,600 × (2000 × $3/1M + 1500 × $15/1M) = 3,600 × ($0.006 + $0.0225) = **$102.60**
- GPT-4o cost: 2,400 × (2000 × $5/1M + 1500 × $15/1M) = 2,400 × ($0.010 + $0.0225) = **$78.00**
- Total before caching: $180.60/month
- With 40% prompt cache hit rate: ~$108/month
- Embedding costs: ~$3/month
- Vision API calls: ~$5/month
- **Total AI cost per Pro user: ~$116/month = ₹9,700/month**

⚠️ **At ₹999/month, the raw AI cost exceeds the subscription price for heavy users.** This is addressed by:
1. The 200/day limit prevents worst-case scenarios (a user hitting 200 claude-3-5-sonnet calls every day is an outlier)
2. Actual average usage is ~30–40 generations/day for active users
3. Cache hit rates of 40–50% reduce effective costs significantly
4. Response-length optimization: prompts specify `max_tokens` per feature type

**Realistic cost per Pro user (actual usage patterns):**
- 40 generations/day average × 30 = 1,200 generations
- With 45% cache hit rate: ~660 actual LLM calls
- Blended cost: ~$25/month AI costs
- **Gross margin at ₹999 ($12): $12 - $3 (AI) - $1 (infra) = $8 (~67% margin)**

---

### Team Plan — ₹4,999/month (up to 5 users)

| Feature | Specification |
|---|---|
| Everything in Pro | Per-user Pro limits |
| Shared knowledge graph | Team-scoped Neo4j namespace |
| BOM collaboration | Multi-user BOM editing with change tracking |
| Shared project library | Team-accessible project repository |
| Admin dashboard | Usage analytics per team member |
| Priority support | < 4h response time SLA |

**Cost per seat:** ₹4,999 / 5 = ₹1,000/seat — marginal premium over Pro for collaboration features
**Target:** Hardware startups, R&D teams at manufacturing companies

---

### Enterprise Plan — Custom Pricing (₹50,000–₹5,00,000+/month)

| Feature | Specification |
|---|---|
| Everything in Team | Unlimited seats (per contract) |
| Private knowledge graph | Customer-owned Neo4j instance (their data stays private) |
| Private vector DB | Dedicated ChromaDB instance seeded with their circuit corpus |
| Custom model routing | Route specific features to their preferred LLM providers |
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

### Token Budget Allocation by Feature

| Feature | Avg Input Tokens | Avg Output Tokens | Model | Cost per Call |
|---|---|---|---|---|
| Project Builder | 2,500 (RAG context heavy) | 2,000 | claude-3-5-sonnet | $0.037 |
| Risk Score | 2,000 | 1,500 | claude-3-5-sonnet | $0.028 |
| Datasheet Simplifier | 4,000 (from PDF) | 2,000 | gpt-4o | $0.050 |
| Thermal Analysis | 800 | 600 | gpt-4o-mini | $0.0005 |
| Debug Wizard (per turn) | 1,500 | 800 | gpt-4o | $0.020 |
| Component ID (vision) | image + 200 tokens | 400 | gpt-4o vision | $0.008 |
| PCB Damage (vision) | image + 300 tokens | 600 | gpt-4o vision | $0.010 |
| Learning Tutor | 1,200 | 1,500 | claude-3-5-sonnet | $0.026 |

### Monthly Platform Cost at Scale

**Scenario: 1,000 Pro users, 5,000 Free users, 10 Enterprise users**

```
Pro users (1,000):
  Avg 40 gen/day × 1,000 users × 30 days = 1,200,000 calls
  With 45% cache hit: 660,000 actual LLM calls
  Avg $0.020/call blended: $13,200/month AI cost
  Revenue: 1,000 × ₹999 = ₹9,99,000 ($12,000)
  Margin after AI: ~$0/month at this scale (unit economics tighten at low volume)

Free users (5,000):
  Avg 5 gen/day × 5,000 × 30 = 750,000 calls
  With 40% cache: 450,000 actual calls
  gpt-4o-mini at $0.00060/call: $270/month AI cost
  Revenue: $0
  → Free tier is a CAC investment, not a revenue source

Enterprise (10):
  Avg $2,000/month AI cost per tenant
  Revenue: avg ₹1,50,000/month per tenant × 10 = ₹15,00,000 ($18,000)
  AI cost: $20,000
  Infra cost: $5,000
  Margin: ~$0 at 10 tenants (enterprise is loss-leading until 25+ tenants)

Break-even analysis:
  Target: 5,000 Pro + 50 Enterprise users
  Revenue: $60,000 + $90,000 = $150,000/month
  Total AI cost: ~$45,000/month
  Infra: ~$15,000/month
  Gross margin: ~60%
  Operating expenses (team, etc.) bring net margin to positive at ~7,000 Pro users
```

---

## 4. Cost Optimization Strategies

### Redis Prompt Caching Impact

The same datasheet simplification (e.g., "simplify LM317 datasheet for student") is requested by hundreds of users. Without caching:
- 500 requests × $0.050 = $25

With Redis L1 cache (TTL 1h):
- 1 LLM call + 499 cache hits = $0.050 + negligible Redis cost

**Rule:** Any prompt that includes only public data (not user-specific context) is a caching candidate. Features where caching applies:
- Datasheet simplification (high cache rate — same popular components)
- Component identification for standard packages (555 timer, LM317, etc.)
- Learning tutor for common concepts ("explain Kirchhoff's laws")

Features where caching does NOT apply:
- Risk score (user-specific circuit)
- Debug wizard (session-specific)
- PCB damage detection (unique image)

### Model Downgrade Path

For Pro users who have not used any premium-model-specific features in a session:
- If only using learning tutor + datasheet simplifier → serve with gpt-4o instead of claude-3-5-sonnet
- Cost difference: $0.020/call (claude-sonnet) vs $0.010/call (gpt-4o) — 50% savings on these features

### Batching Embeddings

New circuit embeddings do not need to be generated immediately. They are batched:
- Celery low_priority worker runs embedding job every 15 minutes
- Batch of 50 circuits → 1 API call with 50 inputs (OpenAI batch endpoint)
- Cost: same as 50 individual calls but 10x fewer API round trips

### Free Tier gpt-4o-mini Lock

gpt-4o-mini at $0.15/$0.60 per 1M tokens is approximately 20× cheaper than claude-3-5-sonnet. All free tier users are hard-routed to gpt-4o-mini via `provider_factory.get(plan="free")`. The model selection UI in Settings is disabled for free users.

---

## 5. Fair Usage and Abuse Prevention

### Rate Limiting Stack

```
Layer 1 — BFF rate limit (Redis, per minute):
  Free: 10 req/min per endpoint
  Pro: 60 req/min per endpoint
  Enterprise: 300 req/min per endpoint

Layer 2 — Daily generation counter (Redis, resets at midnight IST):
  Per plan limits as defined above

Layer 3 — Concurrent job limiter (Redis semaphore):
  Prevents one user from queuing 50 jobs simultaneously

Layer 4 — Unusual usage detection (async analysis):
  If user generates >80% of daily limit in <1 hour → flag for review
  If user submits identical prompts >10 times → suspected automation abuse → throttle
```

### API Plan Abuse Prevention

Pro API access (1,000 calls/day) is intended for integrations, not for building competing products on top of QUEBET AI's AI layer. Terms of Service restrictions:
- API outputs may not be used to train competing models
- API access is per-user, not per-application (no reselling)
- Anomalous patterns (identical prompts at machine speed) trigger account review

---

*Document Owner: Product & Finance Team*
*Last Updated: Q1 2025*
