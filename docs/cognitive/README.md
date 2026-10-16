# Phase 2 Wave 1: Cognitive Engineering Intent & Planning Foundation

## 1. Overview
Phase 2 Wave 1 introduces the **Cognitive Engineering Layer** to QUEBET AI. This cognitive layer bridges the gap between natural language engineering queries from human engineers and the authoritative, deterministic engineering calculation engines established in Phase 1 (Waves 1–9).

### Core Architectural Principle
> **The AI interprets, extracts, plans, routes, proposes, and explains; the deterministic layer calculates, validates, checks constraints, evaluates verification, and produces authoritative engineering results.**

AI is strictly **informational and non-authoritative**. It possesses:
- **Zero Engineering Authority:** AI output never constitutes verification, sign-off, or closure.
- **Zero Autonomous Mutation:** Cognitive execution is read-only (`mutates_state = False`).
- **Zero Autonomous Approval:** All proposals, alternative selections, and review closures require human engineer action.
- **Strict Epistemological Boundaries:** `UNKNOWN != PASS`, `UNKNOWN != SATISFIED`, `UNKNOWN != VERIFIED`.
- **Zero Synthetic Scoring:** Composite scores (`overall_score`, `plan_score`, `intelligence_score`, `best_capability`) are strictly prohibited.

---

## 2. Key Capabilities
1. **Engineering Intent Resolution:** Translates unconstrained natural language prompts into formal `EngineeringIntentPacket` structures containing classified intent types, extracted electrical entities (voltages, currents, temperatures), constraints, requirements, scenarios, and ambiguities.
2. **Context Resolution & Disambiguation:** Deterministically binds intent packets to project, system, and circuit graphs. Ambiguous component references (e.g. "the regulator" when multiple exist) are flagged with `CLARIFICATION_REQUIRED`, pausing autonomous planning until the human engineer specifies the target component.
3. **Task DAG Decomposition:** Transforms intents into Directed Acyclic Graphs (DAGs) of `EngineeringTask`s, with Kahn's algorithm cycle detection and capability dependency validation.
4. **Multi-Dimensional Plan Validation:** Evaluates plans across Structural, Context, Engineering, Security, and Governance dimensions.
5. **Revision Freshness & Stale Plan Rejection:** Enforces revision binding against system and circuit revisions. Concurrent modifications advance revisions, immediately invalidating stale plans with HTTP 409 `COGNITIVE_PLAN_STALE`.
6. **Deterministic Execution:** Runs registered read-only capabilities against Phase 1 engines, recording input and output SHA-256 digests.
7. **Auditable Provenance & Explanation:** Formulates explanations labeled `ORIGIN: AI_GENERATED (INFORMATIONAL ONLY)` with explicit disclaimers and cryptographic provenance traces.
