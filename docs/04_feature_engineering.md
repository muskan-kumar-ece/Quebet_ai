# QUEBET AI — Feature Engineering Specification
> Version 1.0 | All 25 Features | Production Engineering Standards

---

## Engineering Standards Applied to All Features

Before individual feature specs, the following standards apply universally:

- Every AI output is validated through the 4-stage pipeline (JSON parse → schema validate → engineering rules → confidence score)
- Every feature has a `performance_target` SLA
- Every feature has defined `failure_modes` with recovery paths
- Features marked `[ASYNC]` return `job_id` immediately and results are polled
- Features marked `[STREAM]` use SSE for token-by-token delivery

---

## Feature 01 — College Project Builder

**Purpose:** Turn a natural language project idea into a complete hardware blueprint in under 90 seconds.

**Performance Target:** P95 response time < 25s (async job), perceived response < 200ms (job_id returned immediately)

**Engineering Workflow:**
1. User submits project idea + target board via `ProjectBuilderForm.tsx`
2. BFF validates plan allows project builder access (free: 5/day, pro: unlimited)
3. FastAPI enqueues Celery job → returns `job_id` in < 200ms
4. Worker: retrieves RAG context (top-5 similar reference circuits from ChromaDB)
5. Worker: renders `project_builder.py` prompt with RAG context + board constraints
6. LLM call via `model_router.py` (OpenRouter: `anthropic/claude-sonnet-4` for Pro, `openai/gpt-4o-mini` for Plus, `deepseek/deepseek-chat-v3-0324` for Free)
7. Response parsed through validation pipeline
8. SchemDraw generates circuit SVG from component list (deterministic, not AI)
9. Result stored in `analysis_results` + `user_projects`
10. JobStatusPoller receives `{ status: "done", result: {...} }`

**Output Schema:**
```json
{
  "project_name": "string",
  "circuit": { "components": [], "connections": [], "svg_url": "string" },
  "bom": [{ "part": "string", "value": "string", "quantity": int, "india_price_inr": float }],
  "code": { "language": "arduino|micropython", "sketch": "string" },
  "pin_map": [{ "component": "string", "pin": "string", "board_pin": "string" }],
  "warnings": [],
  "confidence": float
}
```

**Validation Rules:**
- All components in BOM must exist in `electronics-kb/data/components/`
- Pin assignments must be valid for selected board model
- Code must include `#include` statements for all required libraries
- If RAG context quality < 0.70, add `"grounding": "low"` flag to output

**Failure Handling:**
- LLM JSON parse failure → repair pipeline → retry once → return error with `retry_url`
- SchemDraw rendering failure → return BOM + code without circuit SVG, flag as partial
- No RAG context found → proceed without grounding, add low-confidence flag

**Abuse Prevention:**
- Free tier: 5 generations/day per user (Redis counter)
- Prompt injection detection: scan `idea` text for system prompt override patterns
- Max input length: 2000 characters

**Enterprise Usage:** Manufacturing teams use Project Builder to generate starter BOMs for new product lines, then refine with BOM Optimizer. R&D teams use it for feasibility sketches before committing engineer time.

---

## Feature 02 — AI PCB Auto-Design [ASYNC]

**Purpose:** Generate a schematic from circuit requirements without manual KiCad entry.

**Performance Target:** P95 < 45s (complex schematics with 15+ components)

**Engineering Workflow:**
1. User fills form: voltage rails, current budget, key ICs, form factor constraints
2. LLM generates structured netlist JSON (components + connections)
3. Engineering rule engine validates netlist:
   - Decoupling capacitors present for each IC's VCC pin
   - MOSFET gate resistors within reasonable range (10Ω–1kΩ)
   - Pull-up/pull-down resistors on open-collector outputs
4. SchemDraw Python library converts netlist JSON → SVG schematic (deterministic rendering)
5. PCBCanvas.tsx renders interactive zoom/pan SVG

**Validation Rules (Engineering Rule Engine):**
- Every voltage regulator must have input and output decoupling
- Crystal oscillator circuits must include load capacitors
- Differential pairs must be routed symmetrically (flagged as warning in text, not enforced in schematic)
- Power ground and signal ground should be labeled separately if split ground plane recommended

**Quality Assurance:**
- Generated schematic is fed back to a second LLM call (reviewer prompt) that checks for obvious omissions
- Reviewer response: `{ passed: bool, issues: [], suggestions: [] }`
- If `passed: false` → first LLM call retried with reviewer's issues appended to prompt

**Performance Optimization:**
- Schematics are cached by netlist hash (Redis, TTL 4h)
- SchemDraw rendering runs in Celery worker, not in HTTP thread

---

## Feature 03 — Circuit Simulation with AI Narrative [ASYNC]

**Purpose:** Run a real SPICE simulation and explain results in plain English.

**Performance Target:** Simulation execution < 30s, narrative generation < 10s

**Engineering Workflow:**
1. User submits SPICE netlist (text paste or KiCad export)
2. `circuit_parser.py` validates SPICE syntax → rejects malformed netlists before simulation
3. PySpice runs DC operating point analysis + transient analysis
4. Simulation output: arrays of `{ time[], voltage[], current[] }` per node
5. Arrays sampled to 200 points (downsampling for LLM token efficiency)
6. LLM receives sampled data + component context: generates narrative explanation
7. Recharts renders full-resolution arrays (stored in job result)

**Simulation Validation:**
- If any node voltage exceeds component's absolute max rating (from KB lookup) → flag as warning before running simulation
- Convergence failure → retry with relaxed tolerance → if still fails, inform user of netlist issue
- Results are deterministic (same netlist = same simulation). Results are cached by netlist MD5.

**AI Narrative Quality:**
- Narrative must reference specific node names from the netlist (not generic "the output")
- Must include at least one quantitative value (voltage, frequency, time constant)
- Must include at least one actionable insight ("At 2A load, output ripple increases to 180mV. Increasing C2 to 470µF would reduce this below 50mV.")

**Security:** SPICE netlists are executed in sandboxed Python subprocess with:
- No filesystem access beyond the simulation temp directory
- CPU time limit: 30 seconds (kills hung simulations)
- Memory limit: 256MB

---

## Feature 04 — Hardware Risk Score Engine [ASYNC]

**Purpose:** Quantified design risk assessment, comparable across design iterations.

**Performance Target:** P95 < 20s. Score must be deterministic for identical inputs.

**Scoring Architecture:**
```
Risk Score = Σ(weight × subscore)

Thermal subscore (30%):
  - NumPy calculation: Tj = Ta + (Pd × Rθja) for each component
  - Score: 100 - Σ(thermal_headroom_deficit_per_component)
  - Input: component list with Pd and Rθja values

EMI subscore (20%):
  - Frequency domain checks: switching harmonics vs PCB trace lengths
  - Score: 100 - Σ(emi_risk_factor_per_violation)
  - Input: switching frequencies + layout description

Design Quality subscore (30%):
  - Rule engine: decoupling, floating pins, voltage margins
  - Score: 100 - Σ(rule_violation_weight)
  - Input: circuit schematic description

Component Quality subscore (20%):
  - Cross-reference components against KB: obsolescence risk, failure rate data
  - LLM augmented: identifies known-problematic parts
  - Score: 100 - Σ(component_risk_factor)
```

**Score Determinism:** The three deterministic subscores (thermal, EMI rule checks, design rules) always produce the same output for the same input. Only the Component Quality subscore involves LLM. This means:
- Score changes between runs reflect only non-deterministic component analysis variance
- Score variance between runs should be < 5 points for same input
- If variance > 5 detected: alert engineering team (prompt drift or model change)

**Output Schema:**
```json
{
  "score": 78,
  "grade": "B",
  "thermal_score": 85,
  "emi_score": 70,
  "design_score": 80,
  "component_score": 75,
  "risk_factors": [
    {
      "category": "thermal",
      "component": "U1 (LM7805)",
      "description": "Junction temperature at 72°C. Max rated 125°C. Headroom adequate but heatsink recommended above 500mA.",
      "severity": "medium",
      "recommendation": "Add TO-220 heatsink with Rθsa ≤ 10°C/W"
    }
  ],
  "critical_issues": [],
  "confidence": 0.87
}
```

---

## Feature 05 — Failure Prediction Engine

**Purpose:** Static analysis for design rule violations and subtle failure modes.

**Performance Target:** P95 < 8s (no simulation required)

**Two-Stage Analysis:**
1. **Deterministic rule engine** (Python, no LLM): checks voltage margins, current ratings, known forbidden patterns (CMOS floating inputs, capacitors near their voltage rating, etc.)
2. **LLM analysis** (routed via OpenRouter: Claude Sonnet for Pro, Gemini Flash for Plus, DeepSeek for Free): identifies subtle, context-dependent failure modes that rules cannot encode (e.g., "This BJT base resistor will cause saturation at elevated temperature, leading to excessive collector current")

**Rule Engine Coverage:**
- Capacitor voltage rating must be ≥ 2× operating voltage (derating rule)
- MOSFET Vgs must have ≥ 20% margin from absolute max
- Open-collector outputs must have pull-up resistors
- Decoupling capacitor required within 2cm of each IC VCC pin
- No floating CMOS inputs

**LLM Failure Mode Library:** Prompt is engineered with a library of 50+ known failure mode patterns, instructing the model to check each class: latch-up, ESD vulnerability, thermal runaway, oscillator instability, and so on.

**Severity Classification:**
- `critical`: Will definitely fail in normal operation
- `high`: Will likely fail under stress (temperature, voltage variation)
- `medium`: May fail in edge cases; should be addressed before production
- `low`: Best practice violation; does not affect reliability significantly

---

## Feature 06 — Power & Thermal Analyzer

**Purpose:** Physics-based thermal analysis with actionable cooling recommendations.

**Performance Target:** P95 < 5s (NumPy calculation is fast; bottleneck is LLM narrative)

**Thermal Model:**
```python
# For each component:
Tj = Ta + (Pd × Rθja)  # Junction temperature
thermal_headroom = Tj_max - Tj
derating_factor = Tj / Tj_max

# If Rθja not in user input → looked up from electronics-kb component database
# If Pd not in user input → estimated from supply current × VCC
```

**Heatmap Generation:**
- Components plotted on a 2D grid based on user-provided placement coordinates
- Color gradient: green (< 50% of max Tj) → yellow (50–75%) → red (> 75%)
- Components exceeding 85% of max Tj are flagged as `critical_thermal`

**LLM Narrative Quality Requirements:**
- Must include specific heatsink recommendations with thermal resistance values
- Must include airflow velocity recommendations where applicable
- Must suggest component derating percentages for specific temperature reduction

---

## Feature 07 — EMI & Noise Detection

**Performance Target:** P95 < 10s

**Frequency Domain Checks:**
- For each switching element: calculate harmonic frequencies up to 30th harmonic
- Compare against CISPR 22/32 Class B limits (stored in KB)
- Check trace lengths against λ/20 antenna criterion (traces longer than λ/20 at switching frequency radiate)
- Check decoupling capacitor self-resonant frequencies against switching harmonics

**Ground Plane Analysis:**
- Detect split ground plane patterns from user description
- Flag ground loops (return current path longer than signal path)
- Check for common-mode choke requirements on power lines

**Enterprise Use:** Pre-compliance EMI analysis before formal chamber testing. Catching one EMI issue before a $15,000 chamber session justifies the platform cost for an entire year.

---

## Feature 08 — Circuit Troubleshooting Wizard [STREAM]

**Purpose:** Interactive Socratic debugging that narrows to root cause.

**Session Architecture:**
- Each debug session stored in Redis with 2h TTL: `debug_session:{session_id}`
- Each LLM call includes full conversation history + accumulated context object
- `accumulated_context` tracks: symptom, circuit type, user measurements, eliminated hypotheses

**Termination Conditions:**
- `root_cause_confidence > 0.90` → present final diagnosis
- `turn >= 8` → present best current hypothesis with remaining uncertainty noted
- User types "give me the answer" → present current best hypothesis immediately

**Output at Each Turn:**
```json
{
  "ai_question": "What is the output voltage when there is no load connected?",
  "hypothesis_being_tested": "inadequate output capacitance causing instability under load",
  "eliminated_count": 3,
  "confidence": 0.67,
  "is_final": false
}
```

---

## Feature 09 — Step-by-Step Debug Guide Generator

**Purpose:** Offline-usable, printable debugging procedure.

**Output Requirements:**
- Each step must include: action, expected measurement, instrument required, if-fail branch
- Steps must be ordered by probability of confirming/eliminating hypothesis (most likely first)
- PDF generation uses `reportlab` (not LLM-generated HTML — avoids layout hallucination)
- PDF is stored in R2 with download link valid for 7 days

---

## Feature 10 — Repair Technician Assistant

**Purpose:** Component-level diagnosis from failure symptoms, backed by historical data.

**Graph Query Strategy:**
```cypher
// Find components historically associated with reported symptoms
MATCH (s:Symptom)-[:INDICATES]->(f:Failure)-[:IN_COMPONENT]->(c:Component)
WHERE s.description CONTAINS $symptom_keyword
RETURN c.name, c.category, count(f) as frequency, collect(f.fix) as known_fixes
ORDER BY frequency DESC
LIMIT 5
```

**Confidence Calculation:**
- Based on: frequency in graph + symptom match specificity + component category match
- Results with frequency < 3 (insufficient data) flagged as "limited data"

**Replacement Part Cross-Reference:**
- After identifying likely faulty component → query `indian-market.json` for local replacements
- Return: original part number + 2–3 local equivalents with Robu/Evelta availability

---

## Features 11–16 (Component Intelligence Module)

### Feature 11 — Vision Component Identifier

**Vision Pipeline:**
1. OpenCV preprocessing: resize to 800×600, CLAHE contrast enhancement, denoising
2. Vision LLM (gpt-4o): component identification with `detail: "high"`
3. Result enriched from KB: official datasheet URL, full spec sheet, known alternatives

**Confidence Thresholds:**
- `confidence > 0.85`: Display result with "Identified" badge
- `0.65–0.85`: Display result with "Likely match — verify datasheet" badge
- `< 0.65`: Ask user to retake photo with better lighting/angle

### Feature 12 — PCB Damage Detection [ASYNC]

**OpenCV Preprocessing:**
- CLAHE (Contrast Limited Adaptive Histogram Equalization): makes burn marks visible
- Gaussian blur + edge detection: highlights physical damage
- Normalized image sent to Vision LLM alongside original

**Damage Region Output:**
```json
{
  "damaged_regions": [
    {
      "location": { "x_pct": 0.3, "y_pct": 0.7 },
      "type": "burnt_trace",
      "severity": "high",
      "affected_component": "U3 (estimated)",
      "confidence": 0.82
    }
  ]
}
```

Frontend overlays SVG annotation boxes on original image using percentage coordinates.

### Feature 13 — Datasheet Simplifier

**Chunking Strategy for Long Datasheets:**
- PDFs > 30 pages: process in chunks by section (identified by header text)
- Key sections always prioritized: "Absolute Maximum Ratings", "Electrical Characteristics", "Typical Application", "Pin Descriptions"
- Remaining sections summarized, not simplified in detail

**Skill Level Adaptation:**
- Student: analogies, avoid jargon, explain every term
- Engineer: retain technical terms, add context, highlight non-obvious specs
- Technician: focus on replacement specs and footprint compatibility

### Feature 14 — Indian Market Alternative Finder

**Two-Stage Lookup:**
1. `indian-market.json` static lookup (< 10ms, works offline): exact part match → return stored alternatives
2. If not found: LLM cross-reference with prompt grounded in component category knowledge

**Compatibility Scoring:**
- `pin_compatible`: same pinout (drop-in replacement)
- `spec_compatible`: equivalent electrical specs, may require minor circuit changes
- `functional_equivalent`: same function, different interface (requires schematic change)

### Feature 15 — BOM Optimization Engine

**Optimization Algorithm:**
1. For each BOM line item: find alternatives (static KB + LLM)
2. Score each alternative: `score = cost_saving_pct × availability_score × compatibility_score`
3. Rank substitutions by score; auto-accept above threshold `score > 0.80`
4. Present below-threshold substitutions for user review

**Total BOM Cost Calculation:**
- Base cost: sum of current component prices from Robu/Evelta API
- Optimized cost: sum after substitutions
- Savings report: percentage + absolute INR amount

### Feature 16 — Real-Time Availability Checker

**API Integration:**
- Robu.in API + Evelta API: parallel requests with 5s timeout per call
- Mouser India API: for components not available locally
- Fallback: if all APIs fail → return KB static price estimates with "prices may vary" disclaimer

**Procurement Summary Logic:**
- Lead time > 2 weeks → flag as "critical path component"
- Available from multiple suppliers → recommend lowest-cost option
- Not available anywhere → trigger Alternative Finder automatically

---

## Features 17–18 (Learning Module)

### Feature 17 — Electronics Learning AI (Adaptive Tutor) [STREAM]

**Skill Level Inference:**
- Explicit: user sets level in profile (beginner/intermediate/advanced)
- Implicit: inferred from question complexity over session history
- Mixed: if user asks about "bootstrap gate drive" but "basic Ohm's Law" → treat as intermediate

**Response Quality Requirements:**
- Must include at least one concrete example with real component values
- Must include a circuit diagram reference or ASCII schematic where applicable
- Must end with a "check your understanding" question at the appropriate level
- Analogies must be domain-appropriate (not generic "like water in pipes")

### Feature 18 — Voice Assistant

**Audio Pipeline:**
- Browser: Web Speech API captures audio as `audio/webm` blob
- Backend: Whisper API (`whisper-1`) for transcription
- Transcription sent to Learning Engine (same as text path)
- Response text → browser `speechSynthesis.speak()` (no server TTS needed for MVP)

**Lab Mode UX:**
- Single large push-to-talk button optimized for one-handed operation
- Waveform visualization confirms audio capture
- Transcript displayed alongside audio playback

---

## Features 19 (Knowledge Graph), 20 (Provider Switching), 21–23 (Infrastructure), 24 (Project History), 25 (Semantic Search)

These infrastructure and platform features are detailed in `02_system_architecture.md` (system), `03_ai_orchestration.md` (AI layer), and `09_database_and_rag_design.md` (data layer). Key engineering notes:

**Feature 20 — Provider Switching:** Zero-code switching is enforced by the `BaseProvider` ABC. Any service that calls `provider.complete()` instead of `anthropic.messages.create()` directly is automatically switchable. Code reviews must reject direct SDK calls in service code.

**Feature 21 — Async Job Queue:** Celery task IDs are deterministic (based on task args hash) for idempotent tasks. Submitting the same simulation twice returns the same `job_id` if the first is still running — preventing duplicate LLM calls.

**Feature 25 — Semantic Search:** ChromaDB queries include a `user_id` filter to blend global reference circuit results with the user's own past projects — personalized RAG.

---

*Document Owner: Feature Engineering Team*
*Last Updated: Q1 2025*
