# Capability Registry

## 1. Registry Invariants
Every capability executed by the Cognitive Engineering Layer must be pre-registered in the `CapabilityRegistry`.
Dynamic or undeclared tool execution is strictly prohibited.

All Phase 2 Wave 1 capabilities enforce:
- `mutates_state = False` (Strictly Read-Only)
- `deterministic = True` (Auditable and Reproducible)

## 2. Registered Capabilities

| Capability ID | Description | Backing Engine | Deterministic | Mutates State |
|:---|:---|:---|:---:|:---:|
| `circuit_analysis` | Solves DC operating point, component stresses, and net voltages | CircuitAnalysisEngine v3.1.0 | Yes | No |
| `system_analysis` | Analyzes subsystem interfaces, power domains, and operating modes | SystemArchitectureEngine v2.0.0 | Yes | No |
| `finding_analysis` | Classifies electrical, thermal, and design rule findings | FindingAnalysisEngine v2.0.0 | Yes | No |
| `failure_analysis` | Computes failure propagation and containment barrier health | FailurePropagationEngine v1.0.0 | Yes | No |
| `requirement_coverage`| Evaluates requirement satisfaction, unknown states, and gaps | RequirementCoverageEngine v1.0.0 | Yes | No |
| `constraint_evaluation`| Evaluates hard and soft system constraints | ConstraintEngine v1.0.0 | Yes | No |
| `verification_status` | Audits verification obligations and missing physical evidence | VerificationEngine v1.5.0 | Yes | No |
| `traceability` | Generates end-to-end evidence graph from sources to decisions | TraceabilityEngine v1.0.0 | Yes | No |
| `decision_comparison` | Synthesizes multidimensional alternative tradeoff comparison | DecisionComparisonEngine v1.0.0 | Yes | No |
| `design_review_readiness`| Evaluates gating readiness and blockers for design reviews | DesignReviewReadinessEngine v1.0.0| Yes | No |
| `knowledge_lookup` | Retrieves verified engineering records from Knowledge Base | KnowledgeBase v1.0.0 | Yes | No |
