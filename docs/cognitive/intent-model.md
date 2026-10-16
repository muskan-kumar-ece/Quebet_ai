# Intent Model & Taxonomy

## 1. Controlled Intent Taxonomy
The Intent Resolver maps all natural language requests into an explicit, finite taxonomy of 18 intent types:

| Intent Type | Purpose | Primary Target |
|:---|:---|:---|
| `ANALYZE_CIRCUIT` | Compute electrical operating point, voltages, currents | Circuit graph |
| `ANALYZE_SYSTEM` | Analyze subsystem topologies and power domains | System architecture |
| `INVESTIGATE_FINDING` | Deep-dive into active electrical/thermal findings | Finding records |
| `INVESTIGATE_FAILURE` | Evaluate failure modes and cross-subsystem propagation | Subsystems / Interfaces |
| `PLAN_VERIFICATION` | Map test points and verification requirements | Verification baseline |
| `EXPLORE_DESIGN_ALTERNATIVES` | Synthesize circuit-level alternative proposals | Circuit components |
| `EXPLORE_SYSTEM_ALTERNATIVES` | Synthesize subsystem-level architectural options | Subsystems / Power domains |
| `COMPARE_ALTERNATIVES` | Multidimensional tradeoff evaluation | Decision records |
| `CHECK_REQUIREMENTS` | Evaluate requirement satisfaction and coverage | Requirement records |
| `CHECK_CONSTRAINTS` | Evaluate hard and soft engineering constraints | Constraints |
| `TRACE_ENGINEERING_FACT` | Audit source provenance and fact lineage | Evidence graph |
| `EXPLAIN_ENGINEERING_RESULT` | Formulate informational interpretation of findings | Execution snapshot |
| `REVIEW_DESIGN` | Evaluate gating readiness for CDR / PDR | Design review session |
| `UNKNOWN` | Unrecognized query requiring user clarification | None |

## 2. Entity Extraction
Regex and semantic parsers extract:
- **Voltages:** (e.g. `12V`, `3.3V`, `500mV`)
- **Currents:** (e.g. `2A`, `150mA`, `25uA`)
- **Temperatures:** (e.g. `85C`, `125°C`, `-40C`)
- **Component Designators:** (e.g. `U1`, `R12`, `C4`, `Q2`, `D1`)
- **Requirements & Constraints:** Max limits, min thresholds, ranges.
