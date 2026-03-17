# AI Electronics Engineer Platform — Complete File Structure
> Deep-reasoned for FastAPI + PostgreSQL + Redis + Neo4j + ChromaDB backend
> Next.js 14 Web App — with switchable Claude / OpenAI AI layer

---

## 🧠 Reasoning Behind Every Decision

| Decision | Why |
|---|---|
| `FastAPI` over Django for backend | AI-heavy workloads need async Python natively; FastAPI is 3x faster than Django for I/O-bound LLM calls; Pydantic schemas match LLM JSON outputs perfectly |
| `LLM Provider Factory` pattern | Never hardcode `anthropic.messages.create()` directly in services — one env var `AI_PROVIDER=claude` or `AI_PROVIDER=openai` switches everything; add Gemini later with zero refactor |
| `services/ai/prompts/` folder per module | Prompts are business logic, not strings — version them, test them, swap them; each module (design, analysis, troubleshoot) has its own prompt folder |
| `Celery + Redis` for AI jobs | LLM calls take 5–30 seconds — never block an HTTP request; return `job_id` instantly, frontend polls `/jobs/{id}` for result |
| `Neo4j` for Knowledge Graph | Components → Circuits → Failures → Fixes is a graph problem, not a table problem; Cypher queries find "what failed with this component before" in 1 line vs 10 SQL joins |
| `ChromaDB` for vector search | "Find circuits similar to this" needs semantic search; store embeddings of every circuit description + failure case for LLM context injection |
| `repositories/` layer between services and DB | Services never write raw SQL — all DB access goes through repo functions; swap PostgreSQL for another DB without touching business logic |
| `(auth)/` and `(dashboard)/` route groups in Next.js | Auth pages (login/register) get a clean centered layout; dashboard pages always get sidebar + auth guard — zero layout duplication |
| `packages/electronics-kb/` static JSON | Indian component catalog, failure modes, reference circuits — static data that ships with the app; works offline, seeds the knowledge graph on first run |
| `BFF (Backend-for-Frontend)` via Next.js API Routes | Frontend never calls FastAPI directly — API keys stay server-side; rate limiting per user happens here before hitting the AI layer |

---

## 📁 BACKEND — FastAPI

```
ai_electronics_backend/
│
├── app/
│   │
│   ├── main.py                              ← FastAPI app: CORS, routers, lifespan events
│   │
│   ├── core/                                ← Infrastructure — never touches business logic
│   │   ├── __init__.py
│   │   ├── config.py                        ← Pydantic Settings: reads all env vars (API keys, DB URLs)
│   │   ├── security.py                      ← JWT create/verify, password hashing (passlib)
│   │   ├── database.py                      ← SQLAlchemy async engine + session factory (PostgreSQL)
│   │   ├── redis_client.py                  ← aioredis async client — cache + job queue
│   │   ├── neo4j_client.py                  ← Neo4j async driver — knowledge graph connection
│   │   ├── vector_store.py                  ← ChromaDB client — embeddings for semantic circuit search
│   │   └── dependencies.py                  ← FastAPI Depends() helpers: get_db, get_current_user, get_ai_provider
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── router.py                    ← Mounts all route modules under /api/v1/
│   │       └── routes/
│   │           ├── auth.py                  ← POST /auth/register, /auth/login, /auth/refresh
│   │           ├── design.py                ← POST /design/project-builder, /design/pcb, /design/simulate
│   │           ├── analysis.py              ← POST /analysis/failure, /analysis/thermal, /analysis/emi, /analysis/risk-score
│   │           ├── troubleshoot.py          ← POST /troubleshoot/diagnose, /troubleshoot/debug-guide, /troubleshoot/repair
│   │           ├── components.py            ← POST /components/identify, /components/pcb-analyze, /components/datasheet
│   │           │                              POST /components/alternatives, /components/availability, /components/bom
│   │           ├── learn.py                 ← POST /learn/explain, /learn/quiz, /learn/voice
│   │           ├── knowledge.py             ← GET /knowledge/graph, POST /knowledge/query
│   │           ├── projects.py              ← CRUD /projects — save/load user project history
│   │           └── jobs.py                  ← GET /jobs/{id} — poll async job status + result
│   │
│   ├── services/
│   │   │
│   │   ├── ai/                              ← ⭐ LLM ABSTRACTION LAYER — the most important folder
│   │   │   ├── __init__.py
│   │   │   ├── base_provider.py             ← ABC: complete(system, user) → str, stream(), analyze_image()
│   │   │   ├── claude_provider.py           ← Anthropic SDK: claude-3-5-sonnet + vision support
│   │   │   ├── openai_provider.py           ← OpenAI SDK: gpt-4o + vision support
│   │   │   ├── provider_factory.py          ← get_ai_provider() reads AI_PROVIDER env var → returns correct class
│   │   │   ├── response_cache.py            ← Redis cache decorator: same prompt hash → skip LLM call, return cached
│   │   │   └── prompts/                     ← All prompts are versioned files, not inline strings
│   │   │       ├── base.py                  ← PromptTemplate base class: render(variables) → str
│   │   │       ├── design/
│   │   │       │   ├── project_builder.py   ← System: "You are a hardware engineer. Given idea, return circuit+BOM+code in JSON"
│   │   │       │   ├── pcb_design.py        ← Schematic generation prompt with component constraints
│   │   │       │   └── simulation.py        ← Circuit behaviour prediction prompt
│   │   │       ├── analysis/
│   │   │       │   ├── failure_prediction.py ← "Analyze this circuit description for design flaws. Return JSON: {risks: [], severity: str}"
│   │   │       │   ├── power_thermal.py     ← Thermal dissipation analysis with component ratings
│   │   │       │   ├── emi_noise.py         ← EMI source identification + grounding suggestions
│   │   │       │   └── risk_score.py        ← "Score this hardware design 0-100. Return JSON: {score: int, factors: []}"
│   │   │       ├── troubleshoot/
│   │   │       │   ├── circuit_debug.py     ← Symptom → root cause diagnosis chain-of-thought prompt
│   │   │       │   ├── debug_guide.py       ← Generate numbered step-by-step debugging plan
│   │   │       │   └── repair.py            ← Repair assistant: "Component X likely failed because..."
│   │   │       ├── components/
│   │   │       │   ├── identify.py          ← Vision prompt: "Identify this component from image. Return: name, specs, datasheet link"
│   │   │       │   ├── pcb_analyze.py       ← Vision prompt: "Find damaged/burnt components in this PCB image"
│   │   │       │   ├── datasheet.py         ← "Simplify this datasheet for a student. Use plain language."
│   │   │       │   ├── alternatives.py      ← "Suggest 3 Indian market alternatives to {component}. Include Robu/Evelta availability."
│   │   │       │   └── bom_optimize.py      ← "Optimize this BOM for cost. Suggest substitutions without compromising specs."
│   │   │       └── learn/
│   │   │           └── tutor.py             ← Adaptive tutor prompt: explains concepts at beginner/intermediate/advanced level
│   │   │
│   │   ├── design/
│   │   │   ├── project_builder.py           ← Calls AI provider → parses JSON → returns circuit+BOM+code structure
│   │   │   ├── pcb_designer.py              ← AI schematic generation + SchemDraw rendering
│   │   │   └── circuit_simulator.py         ← PySpice-based simulation + AI narrative explanation
│   │   │
│   │   ├── analysis/
│   │   │   ├── failure_predictor.py         ← Rule-based checks (voltage limits, current ratings) + LLM for edge cases
│   │   │   ├── power_thermal.py             ← NumPy thermal calculations → LLM adds cooling suggestions
│   │   │   ├── emi_analyzer.py              ← Frequency domain checks → LLM identifies noise sources
│   │   │   └── risk_scorer.py               ← Weighted scoring: thermal(30%) + EMI(20%) + design(30%) + component(20%)
│   │   │
│   │   ├── troubleshoot/
│   │   │   ├── circuit_debugger.py          ← LLM-guided fault diagnosis: symptom → hypothesis → test → fix
│   │   │   ├── debug_guide.py               ← Generates printable step-by-step debugging plan
│   │   │   └── repair_assistant.py          ← Identifies likely faulty components from failure symptoms
│   │   │
│   │   ├── components/
│   │   │   ├── identifier.py                ← Vision LLM (GPT-4o / Claude vision) → component name + specs
│   │   │   ├── pcb_analyzer.py              ← OpenCV preprocessing → Vision LLM damage detection
│   │   │   ├── datasheet_parser.py          ← PyMuPDF text extraction → LLM simplification
│   │   │   ├── alternative_finder.py        ← Query indian-market.json + LLM cross-reference
│   │   │   ├── availability_checker.py      ← Robu.in / Evelta / Mouser API calls + LLM summary
│   │   │   └── bom_optimizer.py             ← Cost optimizer: check alternatives, rank by price+availability
│   │   │
│   │   ├── learn/
│   │   │   ├── learning_engine.py           ← Adaptive curriculum: user history → next concept → LLM explanation
│   │   │   └── voice_processor.py           ← Whisper API: audio → text → learning_engine → text response
│   │   │
│   │   └── knowledge_graph/
│   │       ├── graph_builder.py             ← Writes nodes/edges to Neo4j: Component→Circuit→Failure→Fix
│   │       ├── graph_queries.py             ← Cypher queries: find_similar_failures(), get_component_history()
│   │       ├── embeddings.py                ← Generate embeddings (OpenAI/Claude) → store in ChromaDB
│   │       └── ingestion/
│   │           ├── component_ingester.py    ← Seeds Neo4j from electronics-kb/data/components/*.json
│   │           └── failure_ingester.py      ← Seeds Neo4j from electronics-kb/data/failure-modes/*.json
│   │
│   ├── models/
│   │   ├── db/                              ← SQLAlchemy ORM table definitions
│   │   │   ├── base.py                      ← Base class with id, created_at, updated_at
│   │   │   ├── user.py                      ← User: email, hashed_password, plan (free/pro), created_at
│   │   │   ├── project.py                   ← Project: user_id(FK), name, type (design/analysis/etc), circuit_data(JSON)
│   │   │   ├── analysis_result.py           ← AnalysisResult: project_id(FK), type, score, details(JSON)
│   │   │   ├── component.py                 ← Component: name, category, specs(JSON), india_available(bool)
│   │   │   └── job.py                       ← Job: user_id(FK), type, status (pending/running/done/failed), result(JSON)
│   │   └── schemas/                         ← Pydantic request/response shapes
│   │       ├── user.py                      ← RegisterRequest, LoginRequest, UserResponse, TokenResponse
│   │       ├── project.py                   ← ProjectCreate, ProjectResponse, ProjectList
│   │       ├── circuit.py                   ← CircuitInput, SimulationResult, PCBDesignOutput
│   │       ├── component.py                 ← ComponentInput, ComponentIdentifyResponse, BOMItem, BOMResponse
│   │       └── analysis.py                  ← RiskScoreResponse, ThermalResult, FailurePrediction, EMIResult
│   │
│   ├── repositories/                        ← All DB reads/writes happen here — services never write raw SQL
│   │   ├── user_repo.py                     ← get_by_email(), create_user(), update_plan()
│   │   ├── project_repo.py                  ← create(), get_by_user(), get_by_id(), delete()
│   │   ├── analysis_repo.py                 ← save_result(), get_history_by_project()
│   │   └── job_repo.py                      ← create_job(), update_status(), get_result()
│   │
│   └── utils/
│       ├── image_processor.py               ← OpenCV: resize, denoise, contrast-enhance PCB images before Vision LLM
│       ├── pdf_extractor.py                 ← PyMuPDF: extract text + tables from datasheets
│       ├── circuit_parser.py                ← Parse SPICE netlists and KiCad JSON formats
│       ├── cache.py                         ← @cached(ttl=3600) decorator using Redis
│       └── file_storage.py                  ← Cloudflare R2 / AWS S3: upload PCB images, return CDN URL
│
├── worker/                                  ← Celery background workers (separate process)
│   ├── __init__.py
│   ├── celery_app.py                        ← Celery config: Redis as broker + result backend
│   └── tasks/
│       ├── ai_tasks.py                      ← @celery.task: run_pcb_analysis(), run_simulation() — heavy AI jobs
│       ├── image_tasks.py                   ← @celery.task: process_pcb_image() — OpenCV pipeline before Vision LLM
│       └── knowledge_tasks.py               ← @celery.task: update_knowledge_graph(), generate_embeddings()
│
├── migrations/                              ← Alembic PostgreSQL migrations
│   ├── versions/
│   │   └── 001_initial_tables.py
│   └── env.py
│
├── tests/
│   ├── unit/
│   │   ├── test_ai_providers.py             ← Mock Claude + OpenAI → assert same output format
│   │   ├── test_risk_scorer.py              ← Assert score = 0 for short circuit, 95 for clean design
│   │   ├── test_bom_optimizer.py            ← Assert cheaper alternative is ranked first
│   │   └── test_prompt_templates.py         ← Assert prompts render with correct variables
│   └── integration/
│       ├── test_design_api.py               ← POST /design/project-builder → assert 201 + valid JSON
│       └── test_analysis_api.py             ← POST /analysis/risk-score → assert score field in response
│
├── .env.example                             ← AI_PROVIDER=claude, ANTHROPIC_API_KEY=, OPENAI_API_KEY=,
│                                              DATABASE_URL=postgresql+asyncpg://..., REDIS_URL=redis://...,
│                                              NEO4J_URI=bolt://..., NEO4J_USER=, NEO4J_PASSWORD=,
│                                              S3_BUCKET=, AWS_ACCESS_KEY=, AWS_SECRET_KEY=
├── requirements.txt                         ← fastapi, sqlalchemy[asyncio], asyncpg, aioredis, celery,
│                                              anthropic, openai, langchain, pymupdf, opencv-python,
│                                              pyspice, neo4j, chromadb, passlib, python-jose, alembic
├── requirements-dev.txt                     ← pytest, httpx, factory-boy, faker, pytest-asyncio
├── Dockerfile
└── docker-compose.yml                       ← Runs: api + worker + postgres + redis + neo4j together locally
```

---

## 📁 FRONTEND — Next.js 14

```
ai_electronics_web/
│
├── public/
│   ├── fonts/                               ← Self-hosted fonts (faster for India — no Google Fonts latency)
│   ├── icons/                               ← SVG icons: one per module (circuit, chip, wrench, book, graph)
│   └── logo.svg
│
├── src/
│   │
│   ├── app/                                 ← Next.js App Router
│   │   ├── globals.css                      ← Tailwind base + CSS variables (colors per module)
│   │   ├── layout.tsx                       ← Root layout: fonts, QueryProvider, AuthProvider, ThemeProvider
│   │   ├── not-found.tsx                    ← Custom 404 page
│   │   │
│   │   ├── (auth)/                          ← Route group: no sidebar, clean centered layout
│   │   │   ├── layout.tsx                   ← Auth layout — just centered card, no nav
│   │   │   ├── login/
│   │   │   │   └── page.tsx                 ← Email + Google OAuth login form
│   │   │   ├── register/
│   │   │   │   └── page.tsx                 ← Registration: name, email, password, role (student/engineer)
│   │   │   └── forgot-password/
│   │   │       └── page.tsx
│   │   │
│   │   ├── (dashboard)/                     ← Route group: sidebar + topbar always present
│   │   │   ├── layout.tsx                   ← Dashboard shell: Sidebar + Header + auth guard
│   │   │   ├── page.tsx                     ← Home: recent projects, usage stats, quick-start buttons
│   │   │   │
│   │   │   ├── design/                      ← MODULE 1: Design & Build Intelligence
│   │   │   │   ├── layout.tsx               ← Module layout with green accent
│   │   │   │   ├── page.tsx                 ← Module landing: 3 tool cards
│   │   │   │   ├── project-builder/
│   │   │   │   │   ├── page.tsx             ← Idea input form → generates circuit+code+BOM (College Project Builder)
│   │   │   │   │   └── [id]/
│   │   │   │   │       └── page.tsx         ← View generated project: circuit diagram + code + downloadable BOM
│   │   │   │   ├── pcb-design/
│   │   │   │   │   └── page.tsx             ← PCB Auto-Design: describe requirements → AI generates schematic
│   │   │   │   └── simulation/
│   │   │   │       └── page.tsx             ← Circuit Simulation: netlist input → voltage/current graphs
│   │   │   │
│   │   │   ├── analysis/                    ← MODULE 2: Analysis & Failure Prediction
│   │   │   │   ├── layout.tsx               ← Module layout with blue accent
│   │   │   │   ├── page.tsx                 ← Module landing: 4 tool cards
│   │   │   │   ├── failure/
│   │   │   │   │   └── page.tsx             ← Failure Prediction: describe circuit → get risk list
│   │   │   │   ├── thermal/
│   │   │   │   │   └── page.tsx             ← Power & Thermal Analyzer: component list → heatmap + cooling tips
│   │   │   │   ├── emi/
│   │   │   │   │   └── page.tsx             ← EMI & Noise Detector: layout description → noise sources + fixes
│   │   │   │   └── risk-score/
│   │   │   │       └── page.tsx             ← ⭐ Hardware Risk Score: full circuit input → animated 0-100 dial + report
│   │   │   │
│   │   │   ├── troubleshoot/                ← MODULE 3: Troubleshooting & Repair
│   │   │   │   ├── layout.tsx               ← Module layout with amber accent
│   │   │   │   ├── page.tsx                 ← Module landing: 3 tool cards
│   │   │   │   ├── circuit/
│   │   │   │   │   └── page.tsx             ← Circuit Troubleshooter: describe symptom → AI diagnosis wizard
│   │   │   │   ├── debug-guide/
│   │   │   │   │   └── page.tsx             ← Debug Guide Generator: problem description → printable step-by-step plan
│   │   │   │   └── repair/
│   │   │   │       └── page.tsx             ← Repair Technician Assistant: device fault → faulty component suggestions
│   │   │   │
│   │   │   ├── components/                  ← MODULE 4: Component Intelligence
│   │   │   │   ├── layout.tsx               ← Module layout with purple accent
│   │   │   │   ├── page.tsx                 ← Module landing: 6 tool cards
│   │   │   │   ├── identify/
│   │   │   │   │   └── page.tsx             ← Smart Component ID: camera capture → Vision AI → specs + datasheet
│   │   │   │   ├── pcb-analyzer/
│   │   │   │   │   └── page.tsx             ← PCB Image Analyzer: upload PCB photo → AI marks damaged parts
│   │   │   │   ├── datasheet/
│   │   │   │   │   └── page.tsx             ← Datasheet Simplifier: upload PDF or paste text → plain English summary
│   │   │   │   ├── alternatives/
│   │   │   │   │   └── page.tsx             ← 🇮🇳 Indian Alternative Finder: enter part name → local substitutes
│   │   │   │   ├── availability/
│   │   │   │   │   └── page.tsx             ← Availability Checker: BOM list → which parts available where + price
│   │   │   │   └── bom/
│   │   │   │       └── page.tsx             ← BOM Optimization Engine: upload BOM → AI reduces cost, suggests swaps
│   │   │   │
│   │   │   ├── learn/                       ← MODULE 5: Learning & Interaction
│   │   │   │   ├── layout.tsx               ← Module layout with orange accent
│   │   │   │   ├── page.tsx                 ← Module landing: 2 tool cards + learning streak
│   │   │   │   ├── concepts/
│   │   │   │   │   └── page.tsx             ← Electronics Learning AI: ask any concept → AI teaches with examples
│   │   │   │   └── voice/
│   │   │   │       └── page.tsx             ← Voice Assistant: Web Speech API → Whisper → AI response → TTS
│   │   │   │
│   │   │   ├── knowledge-graph/             ← MODULE 6: Advanced Intelligence
│   │   │   │   └── page.tsx                 ← ⭐ Hardware Knowledge Graph: D3.js graph of component→circuit→failure→fix
│   │   │   │
│   │   │   ├── projects/
│   │   │   │   ├── page.tsx                 ← All saved projects — searchable, filterable by module type
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx             ← Single project view: circuit data + analysis history
│   │   │   │
│   │   │   └── settings/
│   │   │       └── page.tsx                 ← Account settings + AI provider choice (Claude / OpenAI) + API key input
│   │   │
│   │   └── api/                             ← BFF: Next.js API routes (frontend never calls FastAPI directly)
│   │       ├── auth/
│   │       │   └── [...nextauth]/
│   │       │       └── route.ts             ← NextAuth handler: Google OAuth + credentials
│   │       └── proxy/
│   │           └── [...path]/
│   │               └── route.ts             ← Injects auth token + forwards to FastAPI: hides backend URL
│   │
│   ├── components/
│   │   │
│   │   ├── ui/                              ← shadcn/ui base components (auto-generated, don't edit)
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── input.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── progress.tsx
│   │   │   ├── toast.tsx
│   │   │   ├── tabs.tsx
│   │   │   └── select.tsx
│   │   │
│   │   ├── shared/                          ← Cross-module reusable components (used in 2+ modules)
│   │   │   ├── Header.tsx                   ← Top bar: logo, user menu, LLM provider indicator
│   │   │   ├── Sidebar.tsx                  ← Left nav: 6 module links with icons + active state
│   │   │   ├── AIResponseStream.tsx         ← Renders streaming text from SSE — used in every AI tool
│   │   │   ├── FileUpload.tsx               ← Drag-drop zone for PCB images, PDFs, netlists
│   │   │   ├── RiskScoreMeter.tsx           ← ⭐ Animated circular dial 0–100 with color zones (green/amber/red)
│   │   │   ├── KnowledgeGraphViewer.tsx     ← D3.js force-directed graph: nodes = components, edges = relationships
│   │   │   ├── CircuitDiagramViewer.tsx     ← SVG renderer for AI-generated schematic data
│   │   │   ├── JobStatusPoller.tsx          ← Polls /jobs/{id} every 2s → shows progress bar → displays result
│   │   │   └── ErrorBoundary.tsx            ← Catches render errors, shows friendly message
│   │   │
│   │   ├── modules/                         ← Feature-specific components (only used in their module)
│   │   │   │
│   │   │   ├── design/
│   │   │   │   ├── ProjectBuilderForm.tsx   ← Multi-step form: idea → constraints → target board → generate
│   │   │   │   ├── ProjectOutput.tsx        ← Tabbed output: Circuit SVG | Code (syntax highlighted) | BOM table
│   │   │   │   ├── PCBCanvas.tsx            ← Interactive schematic viewer with zoom/pan
│   │   │   │   └── SimulationGraph.tsx      ← Recharts line graph for voltage/current over time
│   │   │   │
│   │   │   ├── analysis/
│   │   │   │   ├── FailureList.tsx          ← Risk factors as expandable cards with severity badges
│   │   │   │   ├── ThermalHeatmap.tsx       ← Color gradient overlay on component positions (hot = red)
│   │   │   │   ├── EMIChart.tsx             ← Recharts frequency domain bar chart with noise markers
│   │   │   │   └── RiskReport.tsx           ← Full risk report: score + all factors + downloadable PDF
│   │   │   │
│   │   │   ├── troubleshoot/
│   │   │   │   ├── DebugWizard.tsx          ← Step-by-step Q&A: AI asks questions → narrows fault → gives fix
│   │   │   │   ├── FaultTree.tsx            ← Visual tree diagram of possible failure causes
│   │   │   │   └── RepairChecklist.tsx      ← Printable repair guide with checkboxes
│   │   │   │
│   │   │   ├── components-intel/
│   │   │   │   ├── ComponentScanner.tsx     ← Webcam/camera capture using browser MediaStream API
│   │   │   │   ├── ComponentCard.tsx        ← Specs display: name, package, ratings, datasheet link
│   │   │   │   ├── BOMTable.tsx             ← Editable spreadsheet-style BOM with inline cost editing
│   │   │   │   ├── AlternativesList.tsx     ← Side-by-side comparison: original vs Indian alternatives
│   │   │   │   └── SupplierLinks.tsx        ← Direct links to Robu / Evelta / Mouser with live price
│   │   │   │
│   │   │   └── learn/
│   │   │       ├── ConceptExplainer.tsx     ← AI explanation with interactive circuit diagrams
│   │   │       ├── QuizCard.tsx             ← MCQ practice problems with AI-generated explanations
│   │   │       └── VoiceInterface.tsx       ← Push-to-talk button + waveform animation + transcript
│   │   │
│   │   └── providers/                       ← React context providers
│   │       ├── AuthProvider.tsx             ← NextAuth SessionProvider wrapper
│   │       ├── QueryProvider.tsx            ← TanStack Query client (caches API responses)
│   │       └── ThemeProvider.tsx            ← next-themes: light/dark mode
│   │
│   ├── hooks/
│   │   ├── useAIStream.ts                   ← Consumes SSE endpoint → streams AI text token by token
│   │   ├── useFileUpload.ts                 ← Gets S3 pre-signed URL from backend → uploads directly
│   │   ├── useVoice.ts                      ← Web Speech API: start/stop recording + transcript state
│   │   ├── useJobPoller.ts                  ← Polls /jobs/{id} every 2s until status = done → returns result
│   │   └── useRiskScore.ts                  ← Fetches risk score + animates dial from 0 to final value
│   │
│   ├── lib/
│   │   ├── api.ts                           ← Axios instance: base URL = /api/proxy → injects auth header
│   │   ├── auth.ts                          ← NextAuth config: Google provider + credentials provider
│   │   ├── utils.ts                         ← cn() for Tailwind merging, formatters, date helpers
│   │   └── constants.ts                     ← API paths, module colors, feature flags
│   │
│   ├── stores/                              ← Zustand global state (lightweight, no Redux needed)
│   │   ├── projectStore.ts                  ← Current project: circuit data, analysis results, history
│   │   ├── aiStore.ts                       ← Selected LLM provider (claude/openai) + streaming state
│   │   └── sessionStore.ts                  ← User preferences: skill level (beginner/advanced), region
│   │
│   └── types/
│       ├── circuit.ts                       ← Circuit, Component, NetList, SimulationResult types
│       ├── analysis.ts                      ← RiskScore, ThermalResult, EMIResult, FailurePrediction types
│       ├── component.ts                     ← ComponentSpec, BOMItem, Alternative, Supplier types
│       └── api.ts                           ← ApiResponse<T>, JobStatus, StreamEvent types
│
├── .env.local                               ← NEXT_PUBLIC_API_URL=http://localhost:8000,
│                                              NEXTAUTH_SECRET=, GOOGLE_CLIENT_ID=, GOOGLE_CLIENT_SECRET=
├── package.json                             ← next, react, tailwindcss, shadcn-ui, zustand,
│                                              @tanstack/react-query, axios, recharts, d3,
│                                              next-auth, lucide-react, framer-motion
├── next.config.js
├── tailwind.config.ts
└── tsconfig.json
```

---

## 📁 SHARED PACKAGES (Optional — if you want monorepo later)

```
packages/
│
├── electronics-kb/                          ← Static knowledge base — ships with app, works offline
│   └── data/
│       ├── components/
│       │   ├── resistors.json               ← Common resistor values, tolerances, packages
│       │   ├── capacitors.json              ← Ceramic, electrolytic specs
│       │   ├── ics.json                     ← Popular ICs: 555, 741, ESP32, ATmega328, etc.
│       │   └── indian-market.json           ← 🇮🇳 Indian-available parts: Robu, Evelta, SP Road catalog
│       ├── circuits/
│       │   ├── reference-designs.json       ← Verified reference circuits (power supply, amplifier, etc.)
│       │   └── common-topologies.json       ← H-bridge, buck converter, I2C pullup, etc.
│       └── failure-modes/
│           ├── thermal.json                 ← Overheating failure patterns + solutions
│           ├── emi.json                     ← EMI failure patterns + grounding solutions
│           └── component-failures.json      ← Common failure modes per component type
│
└── types/                                   ← Shared TypeScript types (if monorepo)
    └── src/
        ├── domain.ts                        ← Circuit, Component, RiskScore — identical to frontend types
        └── api.ts                           ← Request/response shapes match backend Pydantic schemas
```

---

## 🔗 How Everything Connects

```
Browser (Next.js)
  └── Component upload / Text input / Voice
          │
          ▼
  Next.js BFF (/api/proxy/*)              ← Injects JWT, hides FastAPI URL
          │
          ▼
  FastAPI Router (/api/v1/*)
          │
     ┌────┴──────────────────────────────────┐
     │                                       │
     ▼                                       ▼
 Sync (fast <2s)                     Async (slow 5-30s)
 - Datasheet simplify                - PCB image analysis
 - Component identify                - Full circuit simulation
 - Risk score text input             - Knowledge graph update
     │                                       │
     ▼                                       ▼
 services/ai/                         worker/tasks/
 provider_factory.py                  celery_app.py
     │                                       │
     ├── AI_PROVIDER=claude                  └── Returns job_id immediately
     │   └── claude_provider.py                  Frontend polls /jobs/{id}
     │                                            until status = done
     └── AI_PROVIDER=openai
         └── openai_provider.py
                   │
         ┌─────────┴──────────────────────┐
         │                                │
         ▼                                ▼
   Text completion                  Vision analysis
   (design, analysis,               (PCB images,
   troubleshoot, learn)             component photos)
         │
         ▼
   response_cache.py               ← Same prompt hash? Skip LLM → return Redis cache
         │
         ▼
   PostgreSQL                      ← Save result to analysis_results table
   Neo4j                           ← Add failure pattern to knowledge graph
   ChromaDB                        ← Store embedding for future semantic search
```

---

## 📋 Build Order (What to Code First)

```
Week 1  →  Backend: core/ setup + users/ auth (JWT) — foundation everything needs
Week 2  →  Backend: ai/ provider factory + 3 prompts — test Claude AND OpenAI switching works
Week 3  →  Backend: analysis/risk_scorer.py + /analysis/risk-score route — ⭐ signature feature first
Week 4  →  Frontend: Next.js setup + auth + dashboard layout + risk score page
Week 5  →  Backend: troubleshoot/ services + routes (fastest to build, high user value)
Week 6  →  Frontend: troubleshoot module UI + AI streaming component
Week 7  →  Backend: components/ identifier + datasheet + 🇮🇳 alternative finder
Week 8  →  Frontend: components module + FileUpload + ComponentScanner (camera)
Week 9  →  Backend: design/project_builder + worker/ Celery setup for async jobs
Week 10 →  Frontend: design module + JobStatusPoller for async results
Week 11 →  Backend: knowledge_graph/ Neo4j ingestion + graph queries
Week 12 →  Frontend: KnowledgeGraphViewer D3.js + learn module voice assistant
```
