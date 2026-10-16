# Capability Execution Policy & Governance

## 1. Centralized Capability Registry
All capabilities are declared server-side in `CapabilityRegistry` with explicit governance metadata:

- `capability_id`: Canonical unique identifier.
- `name` & `description`: Human-readable engineering specification.
- `human_gate_required`: Whether the capability requires explicit human initiation/authorization.
- `cognitive_execution_allowed`: Whether the cognitive orchestrator may invoke this capability.
- `mutates_state`: Whether the capability performs state mutations.
- `required_permissions`: Fine-grained permission strings (e.g. `circuit:read`, `system:read`).
- `status`: Lifecycle state (`ACTIVE`, `DEPRECATED`, `DISABLED`).

## 2. Server-Authoritative Execution Policy (`CapabilityExecutionPolicy`)
Before any task executes, the engine runs strict evaluation:
1. **Registry Declaration**: Capability must exist in the server registry.
2. **Tenant Isolation**: `tenant_id == plan_tenant_id`. Foreign tenant plans cannot be invoked.
3. **Cognitive Execution Allowed**: Must have `cognitive_execution_allowed == True`.
4. **Human Gate Prohibition**: Autonomous cognitive invocation of human-gated capabilities (`human_gate_required == True`) is strictly blocked (HTTP 403 `COGNITIVE_CAPABILITY_NOT_ALLOWED`).
5. **State Mutation Prohibition**: Any capability where `mutates_state == True` is rejected.
6. **Active Status**: Must have `status == "ACTIVE"`.
7. **Actor Permissions**: Verified against required permissions when provided.

## 3. Human-Gated Capabilities (Prohibited from Autonomous Cognitive Execution)
- `proposal_validation`: System and circuit proposal validation.
- `proposal_application`: Applying approved modifications to schematics or architecture.
- `decision_authorization`: Recording binding engineering decisions.
- `verification_closure`: Closing verification obligations or waiving requirements.
- `review_closure`: Formally completing and archiving formal design reviews.
