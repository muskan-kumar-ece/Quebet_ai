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

---

## 🏗️ Architecture

```
Client (Next.js 14 App Router) 
       │ (Encrypted HTTPS)
       ▼
Next.js BFF API Proxy (/api/proxy/*)
       │ (Internal Network with JWT)
       ▼
FastAPI Application Layer (/api/v1/*)
       │
       ├── Services & Validation Pipeline (DRC, ERC, Thermal)
       ├── OpenRouter AI Gateway (Dynamic Model Router: DeepSeek, Gemini, Claude, GPT)
       ├── PostgreSQL (Relational Data & Model Configs)
       ├── Redis (L1 Response Cache, Rate Limiting, Semaphores)
       ├── Neo4j (Hardware Knowledge Graph)
       └── ChromaDB (Vector Embeddings & Circuit RAG)
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

### 2. Run Backend (FastAPI)
```bash
cd apps/api
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
- API Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`

### 3. Run Frontend (Next.js 14)
```bash
cd apps/web
npm install
npm run dev
```
- Web Application: `http://localhost:3000`

---

## 📦 Monorepo Layout

- `apps/api`: FastAPI backend, AI orchestration layer, and database repositories
- `apps/web`: Next.js 14 App Router, shadcn/ui components, and interactive dashboard shell
- `packages/electronics-kb`: Static knowledge base containing component catalogs and failure modes
- `docs/`: 12 complete industrial-grade architectural specifications

---

## 🛡️ License

Apache-2.0
