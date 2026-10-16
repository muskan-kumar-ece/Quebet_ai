# Execution Boundaries & Epistemological Guardrails

## 1. Zero Autonomous Authority
1. **AI Never Signs Off:** The AI assistant cannot mark any requirement as `VERIFIED`, cannot approve any architecture proposal, cannot select design alternatives, and cannot close any design review.
2. **Read-Only Mode:** Wave 1 cognitive plans are strictly read-only (`mutates_state = False`). Creating proposals or modifying system revisions requires human-initiated actions via Phase 1 endpoints.

## 2. Strict Epistemological Boundaries
- **`UNKNOWN != PASS`**: If a circuit parameter, thermal margin, or requirement cannot be deterministically computed due to missing evidence or uncharacterized parts, it is explicitly flagged as `UNKNOWN`. Under no circumstances may an `UNKNOWN` state be coerced to `PASS` or `SATISFIED`.
- **Prohibition of Synthetic Scores**: Overall plan scores, system intelligence scores, composite design grades, or automated "best capability" rankings are strictly forbidden. Results are presented transparently without synthetic weighting.
- **Explicit Gaps**: Any missing datasheet specifications or physical test results are listed under `unknowns` and assigned as human engineering verification obligations.
