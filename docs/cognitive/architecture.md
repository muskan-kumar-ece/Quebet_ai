# Cognitive Engineering Architecture

## 1. High-Level Architecture Flow

```text
Human Engineer Prompt
        ↓
EngineeringIntentResolver (Taxonomy Classification & Entity Extraction)
        ↓
EngineeringIntentPacket (Entities, Constraints, Requirements, Ambiguities)
        ↓
EngineeringContextResolver (Authoritative Project/System/Circuit Binding)
        ↓
    [Ambiguity Check] ──(Multiple Matches)──> Prompt Clarification Modal (Engineer Selection)
        ↓
EngineeringTaskDecomposer (DAG Synthesis, Cycle Check, Capability Mapping)
        ↓
EngineeringTaskPlan (Sequential & Parallel Tasks, Base Revision Binding)
        ↓
EngineeringPlanValidator (Structural, Context, Engineering, Security, Governance)
        ↓
EngineeringPlanExecutor (Deterministic Phase 1 Capability Execution, Unknown Propagation)
        ↓
EngineeringCognitiveProvenance (SHA-256 Input/Output Digests, Model Traces)
        ↓
EngineeringExplanationService (Informational-Only Non-Authoritative Explanation)
```

## 2. Component Taxonomy
- **`EngineeringIntentPacket`**: Represents the structured understanding of what the engineer wants to accomplish, parsed from natural language with confidence score and extracted parameters.
- **`EngineeringTaskPlan`**: An ordered collection of tasks linked by dependencies forming a Directed Acyclic Graph (DAG), bound to a specific system/circuit `base_revision`.
- **`EngineeringTask`**: A discrete step requiring specific deterministic capabilities (`circuit_analysis`, `finding_analysis`, `verification_status`, etc.) with declared inputs and outputs.
- **`EngineeringCognitiveExecution`**: Auditable execution log of an `EngineeringTaskPlan`, recording findings, results, unknowns, and required human actions.
- **`EngineeringCognitiveProvenance`**: Cryptographic provenance record storing SHA-256 digests of all inputs and outputs, capability versions, and model identifiers.
