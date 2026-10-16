# Cognitive Reflection & Engineering Reasoning Architecture

## 1. Overview
The **Cognitive Reflection Layer** in QUEBET AI audits completed deterministic engineering execution results, requirements, constraints, assumptions, and physical verification obligations. It acts as an advisory, evidence-oriented reasoning engine designed to catch contradictions, uncharacterized parameters, and verification gaps prior to presenting conclusions to engineers.

---

## 2. Core Architectural Invariants

| Invariant | Meaning | Enforcement Mechanism |
|---|---|---|
| `AI ENGINEERING AUTHORITY = NONE` | AI recommendations are strictly advisory | Flagged as `ORIGIN: AI_GENERATED (INFORMATIONAL ONLY)` |
| `AI DECISION AUTHORITY = NONE` | Engineering decisions require explicit human authorization | No automatic plan approval or decision recording |
| `AUTONOMOUS MUTATION = DISABLED` | Reflection cannot alter circuit topologies or system configurations | Follow-up plans are restricted to read-only capabilities |
| `AUTONOMOUS APPROVAL = DISABLED` | Requirements and design reviews cannot be closed by AI | Reviews remain in open or gating state until engineer signs off |
| `AUTONOMOUS VERIFICATION = DISABLED` | Simulated results cannot close physical verification tasks | `VerificationReflectionService` flags simulation claims on physical tests |
| `UNKNOWN != SATISFIED` | Uncharacterized or unmeasured requirements are never marked pass | `RequirementReflectionService` 4-state evaluation |
| `CALCULATED != PHYSICALLY VERIFIED` | Mathematical calculation does not substitute for hardware lab testing | Critical `VERIFICATION_GAP` finding emitted on violation |
| `ANALYSIS != PHYSICAL EVIDENCE` | Simulation/SPICE data cannot be presented as physical empirical evidence | `EvidenceSufficiencyEngine` audits evidence categories |
| `ZERO SYNTHETIC SCORING` | No synthetic confidence percentages or composite readiness metrics | Discrete booleans, finding counts, and verified engineering tolerances only |

---

## 3. Reflection Engine Modules

### 3.1 EngineeringContradictionEngine
- **Purpose**: Detects physical parameter violations and mutually conflicting assumptions.
- **Unit Normalizer**: Converts units into canonical SI base units (e.g. 500 mA → 0.5 A, 3300 mV → 3.3 V), avoiding false positives from numerical formatting.
- **Operating Checks**: Compares calculated operating current, voltage, and power against absolute maximum ratings and requirement ceilings.

### 3.2 UnknownAnalysisService
- **Purpose**: Consolidates, deduplicates, and classifies explicit engineering unknowns.
- **Sources**: Execution unknowns, missing datasheet parameters (e.g. capacitor ESR, thermal resistance), unverified pinouts.
- **Rule**: Never assumes default values without explicit engineering justification.

### 3.3 RequirementReflectionService
- **Purpose**: Evaluates requirement satisfaction under a 4-state model:
  1. `SATISFIED`: Deterministically verified within limits.
  2. `NOT_SATISFIED`: Deterministically shown to violate specification.
  3. `UNKNOWN`: Uncharacterized by available execution results.
  4. `NOT_EVALUATED`: No execution task mapped to requirement.
- **Rule**: Preserves `UNKNOWN != SATISFIED`.

### 3.4 VerificationReflectionService
- **Purpose**: Audits verification obligations and preserves empirical invariants.
- **Rule**: Enforces `CALCULATED != PHYSICALLY VERIFIED`. Flags simulation-only data for hardware requirements.

### 3.5 EvidenceSufficiencyEngine
- **Purpose**: Audits currency, calibration, and validity of empirical evidence.
- **Staleness Check**: Flags evidence collected on previous hardware revisions.
- **Calibration Check**: Rejects test data captured with expired or uncalibrated instrumentation.

### 3.6 ResultSufficiencyEngine
- **Purpose**: Synthesizes discrete findings across all engines.
- **Outputs**: Discrete booleans (`has_contradictions`, `has_unresolved_unknowns`, `has_evidence_gaps`, `has_requirement_gaps`, `has_verification_gaps`, `additional_work_required`).

---

## 4. Bounded Re-Planning & Prevention of Infinite Loops

To eliminate the danger of autonomous runaway reflection cycles:
1. **Hard Upper Bound**: `MAX_REFLECTION_CYCLES = 3`.
2. **Cycle Escalation**:
   - `Cycle 1`: Initial execution reflection.
   - `Cycle 2`: First targeted re-planning (e.g., retrieving missing datasheet parameters or executing derating analysis).
   - `Cycle 3`: Final re-evaluation. If contradictions or unknowns persist, status shifts to `BLOCKED`.
3. **Human Escalation**: Further autonomous replanning is strictly rejected with `MAX_REFLECTION_CYCLES_REACHED`. Unresolved gaps are formatted into explicit human engineer obligations.

---

## 5. Cryptographic Provenance & Auditability

Every reflection record computes two canonical SHA-256 integrity digests:
- **`input_digest`**: Canonical JSON hash over `(execution_id, plan_id, context_snapshot_id, base_revision, cycle_number, user_focus, results_count)`.
- **`output_digest`**: Canonical JSON hash over `(status, booleans, finding_count, findings_summary)`.
- **Tracked Engines**: Engine versions recorded in `engineering_reflection_provenance`.
