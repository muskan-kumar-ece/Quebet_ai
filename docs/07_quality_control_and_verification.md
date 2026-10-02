# QUEBET AI — Quality Control & AI Verification
> Version 1.0 | Output Quality Standards | Verification Architecture

---

## 1. Quality Philosophy

QUEBET AI's outputs influence physical engineering decisions. A wrong resistor value recommendation causes component damage. An underestimated thermal risk leads to product failure in the field. A missed failure mode costs a hardware startup ₹5,00,000 in PCB re-spins.

The quality control architecture treats AI outputs with the same rigor as safety-critical software: every output is verified before delivery, every verification failure is logged and analyzed, and every prompt that generates unreliable outputs is flagged for human review.

**The core standard:** An AI output that cannot be validated to engineering standards is not delivered. A delayed correct answer is better than a prompt wrong one.

---

## 2. Output Quality Standards by Feature Category

### Category A — Safety-Critical (Risk Score, Failure Prediction, Thermal Analysis)

These outputs can directly prevent or cause physical damage. Standards:

| Standard | Requirement |
|---|---|
| JSON schema compliance | 100% — rejected on any schema violation |
| Engineering rule pass rate | 100% — rejected if any recommendation violates physics |
| Confidence floor | 0.80 minimum — below this, human review is recommended |
| Component value validity | All suggested values must be in standard component series |
| Voltage/current recommendations | Must include ≥ 20% safety margin from absolute max ratings |
| Review escalation | Any `severity: critical` finding with confidence < 0.80 → auto-flag |

### Category B — Design Assistance (Project Builder, PCB Auto-Design, Debug Wizard)

These outputs are starting points for engineer review, not final specifications.

| Standard | Requirement |
|---|---|
| JSON schema compliance | 100% |
| Engineering rule pass rate | ≥ 90% (minor rule violations surfaced as warnings, not rejections) |
| Confidence floor | 0.65 minimum |
| BOM validity | All components must exist in electronics-kb or be searchable by identifier |
| Code compilation | Generated Arduino/MicroPython code must pass syntax check |

### Category C — Informational (Datasheet Simplification, Learning Tutor, Debug Guide)

These outputs are explanations and guides. Lower validation strictness but still monitored.

| Standard | Requirement |
|---|---|
| Schema compliance | Required for structured outputs; relaxed for prose |
| Technical accuracy | No contradictions with engineering rule engine |
| Safety claims | No claim that a component is "safe" if it violates derating rules |
| Hallucination risk | Component part numbers must be verified against KB or flagged as "verify before ordering" |

---

## 3. The Four-Stage Validation Pipeline

Every AI output, regardless of category, passes through all four stages. Category determines what happens on failure at each stage.

```
STAGE 1: JSON PARSING
─────────────────────
Input: raw LLM response string
Action: json.loads(response)

Pass → continue to Stage 2
Fail → trigger REPAIR PIPELINE:
  - Identify malformation type (unterminated string, trailing comma, etc.)
  - Construct targeted repair prompt: "Fix this JSON syntax error: {error}. Original: {response}"
  - Call LLM with temperature=0 (no creativity, just repair)
  - Attempt parse again
  - Second fail → AIOutputError(code="JSON_PARSE_FAILED", stage=1, retries=1)
  - Log: prompt_id, user_id, response_excerpt, error_type
  - Return: { error: "generating your response, please retry", retry_available: true }


STAGE 2: SCHEMA VALIDATION
───────────────────────────
Input: parsed JSON dict
Action: OutputModel.model_validate(parsed_json)

Pass → continue to Stage 3
Fail → log field-level validation errors
  - For each missing required field: attempt field extraction from LLM response context
  - If field can be inferred → inject with `"inferred": true` flag
  - If critical fields missing → AIOutputError(code="SCHEMA_INVALID", stage=2)
  - Category A features: hard fail — never deliver incomplete safety-critical output
  - Category B/C features: deliver with missing fields flagged as null + warning banner


STAGE 3: ENGINEERING RULE VALIDATION
──────────────────────────────────────
Input: validated schema object
Action: EngineeringRuleEngine.validate(output, circuit_context)

Rules evaluated (50+ rules, examples):
  R001: No voltage recommendation may exceed component's absolute max rating
  R002: Capacitor voltage rating must be ≥ 2× operating voltage (derating)
  R003: MOSFET Vgs_max - Vgs_recommended ≥ 20% safety margin
  R004: Junction temperature in thermal analysis ≤ 0.85 × Tj_max
  R005: Component values must be within standard E-series (E12/E24/E96)
  R006: Switching regulator output capacitor must meet minimum ESR requirement
  R007: EMI recommendations: trace lengths ≤ λ/20 at cited frequency
  R008: Pull-up resistor value must keep signal rise time within spec
  R009: Power dissipation recommendations cannot exceed thermal derating curves
  R010: PCB trace width must support cited current (IPC-2221 tables)

Pass → continue to Stage 4
Fail:
  - Category A: hard fail → retry LLM with violations appended to prompt
    "Your previous response violated these engineering rules: {violations}. Correct and regenerate."
    → If retry also fails → escalate to human review queue, inform user of delay
  - Category B: soft fail → deliver output with violations highlighted as warnings
    → Log violation rate for prompt monitoring


STAGE 4: CONFIDENCE SCORING
─────────────────────────────
Input: validated + rule-checked output
Action: calculate confidence score from multiple signals

Confidence signals:
  - RAG context quality: avg similarity score of retrieved contexts (higher = more grounded)
  - Provider health: degraded provider → confidence penalty
  - Response length: very short responses for complex queries → confidence penalty
  - Internal consistency: check if recommendations in output contradict each other
  - Historical accuracy: if this prompt template has a high validation failure rate → confidence penalty

Output: confidence ∈ [0.0, 1.0]

Results:
  - confidence ≥ threshold → deliver with no warning
  - threshold - 0.10 ≤ confidence < threshold → deliver with "Review recommended" UI flag
  - confidence < threshold - 0.10 → deliver with "Low confidence — verify with datasheet" warning
  - confidence < 0.40 → do not deliver; prompt user to provide more circuit detail
```

---

## 4. Electronics Engineering Rule Engine

The rule engine is a deterministic Python module — no LLM involved. It enforces physical laws and industry standards.

### Architecture

```python
class EngineeringRuleEngine:
    def __init__(self):
        self.rules: list[Rule] = load_rules_from_kb()
        self.component_db: ComponentDatabase = ComponentDatabase(path="electronics-kb/")

    def validate(self, output: AIOutput, context: CircuitContext) -> ValidationResult:
        violations = []
        warnings = []

        for rule in self.rules:
            if not rule.applies_to(output.feature_type):
                continue
            result = rule.check(output, context, self.component_db)
            if result.status == "violation":
                violations.append(result)
            elif result.status == "warning":
                warnings.append(result)

        return ValidationResult(
            passed=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            rule_coverage=len([r for r in self.rules if r.applies_to(output.feature_type)])
        )

class Rule:
    @abstractmethod
    def applies_to(self, feature_type: str) -> bool: ...
    @abstractmethod
    def check(self, output: AIOutput, context: CircuitContext, db: ComponentDatabase) -> RuleResult: ...
```

### Rule Categories

| Rule Category | Count | Data Source |
|---|---|---|
| Voltage derating rules | 8 | MIL-STD-975, component datasheets |
| Thermal derating rules | 6 | JEDEC standards, Rθja database |
| PCB design rules | 12 | IPC-2221, IPC-7351 |
| EMC rules | 7 | CISPR 22/32 Class B limits |
| Component standard values | 3 | E12/E24/E96/E192 series |
| Safety margins | 6 | Industry best practice |
| Capacitor selection rules | 5 | Application-specific (decoupling, bulk, filter) |
| MOSFET/BJT operating point | 4 | Active region constraints |

---

## 5. Multi-Model Consensus (Critical Features)

For features where a wrong answer has high physical consequence (Risk Score ≥ 80, Failure Prediction with `severity: critical`), a second independent LLM call is made:

```python
async def critical_consensus_check(primary_result: AIOutput, circuit_context: str) -> ConsensusResult:
    """
    When primary_result contains critical-severity findings, verify with a second model.
    If the two models significantly disagree → flag for human review.
    """
    secondary_result = await secondary_provider.complete(
        system=REVIEWER_SYSTEM_PROMPT,
        user=f"Review this risk assessment and indicate if you agree: {primary_result.model_dump_json()}"
    )

    agreement_score = calculate_semantic_agreement(primary_result, secondary_result)

    if agreement_score < 0.70:
        # Models significantly disagree on critical findings
        return ConsensusResult(
            consensus_reached=False,
            primary=primary_result,
            secondary=secondary_result,
            review_required=True,
            message="This design has complex risk factors. Our AI models produced differing assessments. A manual engineering review is recommended."
        )

    # Models agree — deliver with consensus flag
    return ConsensusResult(
        consensus_reached=True,
        final_output=primary_result,  # Use primary; secondary confirmed
        consensus_confidence=agreement_score
    )
```

This adds ~5–8 seconds and ~$0.02 to the cost of critical assessments. Justified for Category A features.

---

## 6. Hallucination Detection

### Component Value Hallucination

The most common form of hallucination in electronics AI: the model cites a component value that does not correspond to a standard part.

Detection: after generation, every resistor/capacitor/inductor value in the output is checked against the E-series lookup table. Values not in the nearest E-series (±5%) are flagged.

```python
def check_component_value_validity(value: float, component_type: str) -> ValueCheck:
    if component_type == "resistor":
        nearest_e96 = find_nearest_e96(value)
        deviation = abs(value - nearest_e96) / nearest_e96
        if deviation > 0.05:
            return ValueCheck(
                valid=False,
                suggested=nearest_e96,
                reason=f"{value}Ω is not a standard E96 value. Nearest: {nearest_e96}Ω"
            )
    # Similar logic for capacitors (E12 series), inductors...
```

### Part Number Hallucination

When an AI output cites a specific part number (e.g., "LM3480-3.3", "TPS62840DLCR"), it is verified:
1. Check `electronics-kb/data/components/` — if found, confirm specs match context
2. If not in KB → mark as "verify before ordering" in the UI — the part number may be fabricated

### Specification Hallucination

When an AI output cites a specification (e.g., "ESP32 draws 240mA peak"), it is cross-referenced against the KB:
- If KB has the value → cite confidence boost
- If KB value contradicts AI output → flag the specific spec for verification
- If not in KB → deliver without confidence boost, add "verify with datasheet" note

---

## 7. Reliability Monitoring and SLAs

### Quality Metrics Tracked (Prometheus)

| Metric | Formula | Target |
|---|---|---|
| `ai_output_validation_pass_rate` | Stage 3 passes / total calls | > 95% |
| `ai_output_hallucination_rate` | Component value failures / total calls | < 3% |
| `ai_output_schema_failure_rate` | Stage 2 failures / total calls | < 1% |
| `consensus_disagreement_rate` | Consensus < 0.70 / critical calls | < 5% |
| `confidence_score_p50` | Median confidence score | > 0.80 |
| `human_review_escalation_rate` | Escalations / total calls | < 2% |

### Prompt Regression Detection

When a model version changes (e.g., claude-3-5-sonnet → next version), or when a prompt template is updated:
- 500 historical prompt/response pairs are re-run against the new version
- Quality metrics compared against baseline
- If any metric degrades by > 10% relative → deployment blocked; engineering team notified

This prevents silent quality degradation from model updates.

---

## 8. Human Review Queue

When AI outputs cannot be validated to standard (consensus disagreement, repeated rule violations, confidence < 0.40 after retry), they enter a human review queue:

- User is notified: "This design has complex factors. A senior engineer will review within 4 hours (Pro) / 24 hours (Free)."
- Internal tool presents the original request, AI attempt, and validation failures to an internal engineer
- Engineer either: approves the AI output, corrects it, or provides a manual response
- Response delivered to user with "Reviewed" badge
- The corrected output is used to fine-tune the prompt (added to few-shot examples)

Human review escalation rates are tracked as a quality metric. A high escalation rate for a specific feature indicates a prompt or model issue requiring engineering attention.

---

*Document Owner: AI Quality Engineering Team*
*Last Updated: Q1 2025*
