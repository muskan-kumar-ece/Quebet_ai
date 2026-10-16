# Cognitive Layer Security & Tenant Isolation

## 1. Multi-Tenant Isolation
All cognitive endpoints enforce tenant isolation via JWT tokens validated through `require_authenticated_user`:
- `EngineeringIntentPacket.tenant_id`
- `EngineeringTaskPlan.tenant_id`
- `EngineeringCognitiveContextSnapshot.tenant_id`
- `EngineeringCognitiveExecution.tenant_id`
- `EngineeringCognitiveProvenance.tenant_id`

Cross-tenant access attempts return HTTP 404 (or HTTP 403 `TENANT_ISOLATION_VIOLATION`), preventing IDOR enumeration or cross-tenant context leakage.

## 2. Prompt Injection Defense
User prompts are sanitized and treated strictly as data payloads in intent resolution:
- The system prompt defines immutable structural schemas and taxonomy constraints.
- Free-form user text cannot override registered capabilities, execute unauthorized operations, or bypass human gates.
- All tasks in generated plans are matched against server-authoritative `CapabilityRegistry` declarations.

## 3. Capability Escalation Defense
Even if an LLM outputs an unauthorized or human-gated capability name:
- `CapabilityExecutionPolicy` rejects the capability server-side.
- The task is marked `FAILED` or `BLOCKED` with a typed policy violation.
- The plan enters `PARTIAL` or `FAILED` status and halts execution.
