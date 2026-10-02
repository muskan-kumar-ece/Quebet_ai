# QUEBET AI

> **The AI-Native Engineering Operating System for Electronics**  
> *"GitHub Copilot for Hardware Engineering"*

---

## ⚡ Overview

QUEBET AI collapses the gap between hardware engineering intent and validated, manufacturable design. It powers:
- Real-time AI-assisted schematic and circuit generation
- Deterministic and physics-grounded verification (Thermal, EMI, Rule Engine)
- Signature **Hardware Risk Score** (0–100 animated dial)
- Automated static analysis and component-level fault diagnosis
- Component intelligence with Indian supply chain awareness (Robu, Evelta, SP Road)
- Hardware Knowledge Graph connecting components, topologies, failures, and verified fixes
- Operational **Admin Portal** for real-time model catalog and tier routing management

---

## 🏛️ 3-Pillar Monorepo Architecture

```
quebet-ai/
│
├── frontend/             ← 🌟 Next.js 14 Client App (Port 3000)
│   ├── (marketing)       ← Landing page & product showcase
│   ├── (auth)            ← Google OAuth & email login/register
│   ├── (dashboard)       ← 6 Hardware Copilot Modules, Risk Score & Project Library
│   └── api/proxy         ← Next.js BFF proxy to backend
│
├── admin/                ← 🛡️ Next.js 14 Dedicated Admin Portal (Port 3001)
│   ├── (overview)        ← Executive KPI metrics (Token spend, active users, latency)
│   ├── models/           ← OpenRouter Model Catalog (Add, toggle, view pricing)
│   ├── routing/          ← Plan × Task Routing Matrix (Free / Plus / Pro / Enterprise)
│   └── rate-limits/      ← Live Rate Limit Controls per plan tier
│
├── backend/              ← ⚙️ FastAPI Python Backend (Port 8000)
│   ├── core/             ← Database (SQLAlchemy 2.0), Redis, Neo4j, Security & Config
│   ├── models/           ← ORM DB entities & Pydantic DTOs
│   ├── services/ai/      ← OpenRouter Gateway, Dynamic Model Router & Prompts
│   ├── repositories/     ← Data access layer
│   ├── migrations/       ← Async Alembic database migrations
│   └── api/v1/routes/    ← REST endpoints (health, models, admin, etc.)
│
└── packages/
    └── electronics-kb/   ← 📚 Static Hardware Knowledge Base
        └── data/         ← Resistors, capacitors, ICs, Indian market & failure modes
```

---

## 🚀 Quickstart

### Prerequisites
- Node.js 18+ (Node 22 recommended)
- Python 3.11+
- Git

### 1. Clone & Configure Environment
```bash
git clone https://github.com/muskan-kumar-ece/Quebet_ai.git
cd Quebet_ai
cp .env.example .env
```

### 2. Run All Services Locally

```bash
# Terminal 1 — Backend (FastAPI, Port 8000)
npm run dev:backend
# API Docs: http://localhost:8000/api/v1/docs
# Health: http://localhost:8000/api/v1/health

# Terminal 2 — Frontend User App (Next.js 14, Port 3000)
npm run dev:frontend
# App: http://localhost:3000

# Terminal 3 — Admin Portal (Next.js 14, Port 3001)
npm run dev:admin
# Admin Console: http://localhost:3001
```

---

## 🧪 Testing & Verification

```bash
# Run backend tests
npm run test:backend

# Build frontend
npm run build:frontend

# Build admin portal
npm run build:admin
```

---

## 🛡️ License

Apache-2.0
