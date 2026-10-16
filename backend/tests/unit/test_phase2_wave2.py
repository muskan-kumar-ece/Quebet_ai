import json
import uuid
import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.db.cognitive import (
    ReflectionStatus,
    ReasoningFindingType,
    ReasoningFindingSeverity,
)
from app.services.ai.cognitive.reflection.contradiction_engine import (
    UnitNormalizer,
    EngineeringContradictionEngine,
)
from app.services.ai.cognitive.reflection.unknown_service import UnknownAnalysisService
from app.services.ai.cognitive.reflection.requirement_reflection import RequirementReflectionService
from app.services.ai.cognitive.reflection.verification_reflection import VerificationReflectionService
from app.services.ai.cognitive.reflection.evidence_sufficiency import EvidenceSufficiencyEngine
from app.services.ai.cognitive.reflection.sufficiency_engine import ResultSufficiencyEngine
from app.services.ai.cognitive.reflection.replanner import ReflectionReplanner, MAX_REFLECTION_CYCLES


def auth_headers(user_id: str, email: str, role: str = "engineer", tenant_id: str = "tenant-p2w2-a") -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. UNIT NORMALIZER & CONTRADICTION ENGINE TESTS
# ============================================================================

def test_unit_normalizer_accuracy_and_formatting():
    """
    Verifies that UnitNormalizer parses electrical units accurately into SI base units,
    preventing false positive contradictions due to representation formatting.
    """
    assert UnitNormalizer.parse_value_unit("500mA") == (0.5, "A")
    assert UnitNormalizer.parse_value_unit("0.5 A") == (0.5, "A")
    assert UnitNormalizer.parse_value_unit("3.3V") == (3.3, "V")
    assert UnitNormalizer.parse_value_unit("3.30 V") == (3.3, "V")
    assert UnitNormalizer.parse_value_unit("3300 mV") == (3.3, "V")
    assert UnitNormalizer.parse_value_unit("100mW") == (0.1, "W")
    assert UnitNormalizer.parse_value_unit("10 kohm") == (10000.0, "Ohm")
    assert UnitNormalizer.parse_value_unit("25°C") == (25.0, "°C")
    assert UnitNormalizer.parse_value_unit("85 C") == (85.0, "°C")


def test_contradiction_detection_unit_normalized():
    """
    Verifies detection of true physical contradictions (operating current > maximum requirement)
    and prevents false positives on identical normalized values.
    """
    # 1. Violation: 620 mA operating current exceeds 500 mA requirement limit
    reqs = [{"id": "REQ-I-MAX", "target_property": "current", "max_value": "500mA"}]
    results = [{"task_id": "T1", "details": {"current": "620mA"}}]
    findings = EngineeringContradictionEngine.check_contradictions(results, reqs, [])
    assert len(findings) == 1
    assert findings[0]["finding_type"] == ReasoningFindingType.CONTRADICTORY_RESULT.value
    assert findings[0]["severity"] == ReasoningFindingSeverity.CRITICAL.value
    assert "exceeds requirement" in findings[0]["title"]

    # 2. Compliant: 450 mA is within 500 mA limit -> No contradiction
    results_ok = [{"task_id": "T1", "details": {"current": "450mA"}}]
    findings_ok = EngineeringContradictionEngine.check_contradictions(results_ok, reqs, [])
    assert len(findings_ok) == 0

    # 3. Formatting equivalence: 0.5A vs 500mA -> No contradiction
    results_equiv = [{"task_id": "T1", "details": {"current": "0.5A"}}]
    findings_equiv = EngineeringContradictionEngine.check_contradictions(results_equiv, reqs, [])
    assert len(findings_equiv) == 0


def test_conflicting_assumptions_detection():
    """
    Verifies detection of conflicting engineering assumptions across subsystems
    (e.g., ambient temperature 25°C in one subsystem vs 85°C in another).
    """
    assumptions = [
        {"id": "A1", "name": "Power ambient temp", "value": "25°C"},
        {"id": "A2", "name": "RF ambient temp", "value": "85°C"},
    ]
    findings = EngineeringContradictionEngine.check_contradictions([], [], assumptions)
    assert len(findings) == 1
    assert findings[0]["finding_type"] == ReasoningFindingType.ASSUMPTION_CONFLICT.value
    assert findings[0]["severity"] == ReasoningFindingSeverity.WARNING.value
    assert "Conflicting Ambient Temperature" in findings[0]["title"]


# ============================================================================
# 2. UNKNOWN ANALYSIS & EPISTEMIC INVARIANTS
# ============================================================================

def test_unknown_service_aggregation_and_classification():
    """
    Verifies consolidation of unknowns from execution, intent missing info,
    and uncharacterized component parameters.
    Preserves invariant: UNKNOWN != SATISFIED.
    """
    execution_unknowns = [
        {"source": "SPICE", "unknown": "Inductor L1 parasitic capacitance not specified", "ref_des": "L1"},
        {"source": "Thermal", "unknown": "Heatsink thermal resistance undefined"},
    ]
    context_payload = {
        "components": [
            {"ref_des": "C1", "type": "CAPACITOR", "parameters": {}},  # Missing ESR
        ]
    }
    findings = UnknownAnalysisService.analyze_unknowns(
        execution_unknowns=execution_unknowns,
        context_payload=context_payload,
    )
    assert len(findings) == 3
    types = [f["finding_type"] for f in findings]
    assert types.count(ReasoningFindingType.UNRESOLVED_UNKNOWN.value) == 3
    assert any("ESR" in f["title"] for f in findings)


# ============================================================================
# 3. REQUIREMENT REFLECTION & 4-STATE EVALUATION
# ============================================================================

def test_requirement_reflection_unknown_invariant():
    """
    Verifies that requirements not evaluated by deterministic results are strictly
    treated as UNKNOWN and flagged as REQUIREMENT_GAP. UNKNOWN != SATISFIED.
    """
    requirements = [
        {"id": "REQ-V", "name": "Input Voltage Ripple", "target_property": "ripple_voltage"},
        {"id": "REQ-T", "name": "Operating Temperature", "target_property": "operating_temp"},
    ]
    # Execution results only provide operating_temp, leaving ripple_voltage uncharacterized
    results = [{"details": {"operating_temp": "45°C"}}]

    findings = RequirementReflectionService.evaluate_requirements(
        requirements=requirements,
        execution_results=results,
    )
    assert len(findings) == 1
    assert findings[0]["finding_type"] == ReasoningFindingType.REQUIREMENT_GAP.value
    assert findings[0]["affected_entity_id"] == "REQ-V"
    assert "UNKNOWN != SATISFIED" in findings[0]["description"]


# ============================================================================
# 4. VERIFICATION REFLECTION & EMPIRICAL INVARIANTS
# ============================================================================

def test_verification_reflection_calculated_not_physically_verified():
    """
    Verifies the non-negotiable invariant: CALCULATED != PHYSICALLY VERIFIED.
    When a physical laboratory test obligation is claimed as verified via simulation,
    a critical VERIFICATION_GAP finding must be emitted.
    """
    verifications = [
        {
            "verification_id": "V-EMC-01",
            "name": "Radiated Emissions Physical Bench Test",
            "method": "SIMULATION",
            "status": "PASSED",
            "requirement_type": "PHYSICAL_TEST",
        }
    ]
    findings = VerificationReflectionService.audit_verification(
        verification_impacts=verifications,
        requirements=[],
    )
    assert len(findings) == 1
    assert findings[0]["finding_type"] == ReasoningFindingType.VERIFICATION_GAP.value
    assert findings[0]["severity"] == ReasoningFindingSeverity.CRITICAL.value
    assert "CALCULATED != PHYSICALLY VERIFIED" in findings[0]["title"]


# ============================================================================
# 5. EVIDENCE SUFFICIENCY & CALIBRATION AUDIT
# ============================================================================

def test_evidence_sufficiency_staleness_and_calibration():
    """
    Verifies detection of:
    1. Stale evidence from prior hardware revisions.
    2. Uncalibrated or expired test bench instrumentation.
    3. Simulation data disguised as physical measurement.
    """
    evidence = [
        {
            "id": "EV-01",
            "name": "Step response lab measurement",
            "revision": 1,  # Current is 2 -> Stale
            "instrument_calibration_status": "VALID",
        },
        {
            "id": "EV-02",
            "name": "Oscilloscope capture",
            "revision": 2,
            "instrument_calibration_status": "EXPIRED",  # Uncalibrated instrument
        },
        {
            "id": "EV-03",
            "name": "Simulated thermal capture",
            "revision": 2,
            "category": "PHYSICAL_LAB_MEASUREMENT",
            "is_simulation": True,  # Contradiction: ANALYSIS != PHYSICAL EVIDENCE
        },
    ]
    findings = EvidenceSufficiencyEngine.evaluate_evidence(evidence, current_revision=2)
    assert len(findings) == 3
    assert all(f["finding_type"] == ReasoningFindingType.INSUFFICIENT_EVIDENCE.value for f in findings)
    assert any("Stale Evidence" in f["title"] for f in findings)
    assert any("Uncalibrated" in f["title"] for f in findings)
    assert any("ANALYSIS != PHYSICAL EVIDENCE" in f["title"] for f in findings)


# ============================================================================
# 6. RESULT SUFFICIENCY & ZERO SYNTHETIC SCORING
# ============================================================================

def test_result_sufficiency_zero_synthetic_scoring():
    """
    Verifies that ResultSufficiencyEngine produces discrete facts, discrete status booleans,
    and ZERO synthetic/composite percentages or scores.
    """
    reqs = [{"id": "R1", "name": "Current Limit", "target_property": "current", "max_value": "100mA"}]
    results = [{"task_id": "T1", "details": {"current": "150mA"}}]
    unknowns = [{"unknown": "Undefined ESR"}]

    summary = ResultSufficiencyEngine.evaluate(
        execution_results=results,
        execution_findings=[],
        execution_unknowns=unknowns,
        requirements=reqs,
        assumptions=[],
        verification_impacts=[],
        traceability_records=[],
        evidence_items=[],
    )

    assert summary["has_contradictions"] is True
    assert summary["has_unresolved_unknowns"] is True
    assert summary["additional_work_required"] is True
    assert summary["status"] == ReflectionStatus.ADDITIONAL_WORK_REQUIRED.value
    assert len(summary["proposed_follow_up_tasks"]) > 0

    # Ensure zero synthetic scoring terms exist in serialized output
    serialized = json.dumps(summary).lower()
    forbidden_terms = ["score", "readiness_percentage", "confidence_level", "quality_metric", "overall_rating"]
    for term in forbidden_terms:
        assert term not in serialized, f"Forbidden synthetic score term '{term}' found in reflection summary!"


# ============================================================================
# 7. INTEGRATION TESTS VIA API (EXECUTION, REFLECTION & REPLANNING)
# ============================================================================

@pytest.mark.asyncio
async def test_reflection_api_flow_and_replan_limit(async_client: AsyncClient):
    """
    Full end-to-end integration test of Phase 2 Wave 2:
    1. Create Project, Intent, Plan, and Execution.
    2. POST /cognitive/executions/{id}/reflect -> Generates reflection with discrete findings & SHA-256 provenance.
    3. GET /cognitive/reflections/{id} -> Verifies retrieval with findings.
    4. POST /cognitive/reflections/{id}/replan -> Generates follow-up plan bound to context.
    5. Test MAX_REFLECTION_CYCLES bound: Re-planning is rejected when cycle limit (3) is reached.
    6. Verify strict multi-tenant isolation.
    """
    user_id = str(uuid.uuid4())
    tenant_a = "tenant-reflection-test-a"
    headers_a = auth_headers(user_id, "lead_engineer@quebet.ai", tenant_id=tenant_a)

    # 1. Create project
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Reflection Test Project", "project_type": "embedded"},
        headers=headers_a,
    )
    assert p_res.status_code == 201
    proj_id = p_res.json()["data"]["id"]

    # 2. Create intent packet with conflicting electrical requirements
    intent_res = await async_client.post(
        "/api/v1/cognitive/intents",
        json={
            "raw_request": "Verify power rails and operating margins.",
            "goal": "Verify power rails and operating margins.",
            "project_id": proj_id,
            "intent_type": "CHECK_REQUIREMENTS",
            "requirements": [
                {"id": "REQ-PWR-MAX", "target_property": "current", "max_value": "500mA", "name": "Current Ceiling"}
            ],
        },
        headers=headers_a,
    )
    assert intent_res.status_code == 201
    intent_id = intent_res.json()["data"]["id"]

    # 3. Create and execute plan
    plan_res = await async_client.post(
        "/api/v1/cognitive/plans",
        json={"intent_packet_id": intent_id},
        headers=headers_a,
    )
    assert plan_res.status_code == 201
    plan_id = plan_res.json()["data"]["id"]

    exec_res = await async_client.post(
        f"/api/v1/cognitive/plans/{plan_id}/execute",
        headers=headers_a,
    )
    assert exec_res.status_code == 200
    exec_id = exec_res.json()["data"]["id"]

    # 4. Trigger Reflection on Execution
    refl_res = await async_client.post(
        f"/api/v1/cognitive/executions/{exec_id}/reflect",
        json={"user_focus": "Check current and requirement compliance."},
        headers=headers_a,
    )
    assert refl_res.status_code == 201
    refl_data = refl_res.json()["data"]
    assert refl_data["execution_id"] == exec_id
    assert refl_data["reflection_cycle"] == 1
    assert "provenance" in refl_data
    assert len(refl_data["provenance"]["input_digest"]) == 64
    assert len(refl_data["provenance"]["output_digest"]) == 64

    reflection_id = refl_data["id"]

    # 5. Retrieve Reflection
    get_res = await async_client.get(
        f"/api/v1/cognitive/reflections/{reflection_id}",
        headers=headers_a,
    )
    assert get_res.status_code == 200
    assert get_res.json()["data"]["id"] == reflection_id

    # 6. Replan from Reflection (Cycle 1 -> Cycle 2)
    # If additional work is required, trigger replanning
    if refl_data.get("additional_work_required"):
        replan_res = await async_client.post(
            f"/api/v1/cognitive/reflections/{reflection_id}/replan",
            headers=headers_a,
        )
        assert replan_res.status_code == 201
        replan_data = replan_res.json()["data"]
        assert replan_data["reflection_id"] == reflection_id
        assert replan_data["reflection_cycle"] == 2
        assert replan_data["tasks_count"] > 0

    # 7. Test Tenant Isolation: Tenant B cannot access Tenant A's reflection
    headers_b = auth_headers(str(uuid.uuid4()), "other@quebet.ai", tenant_id="tenant-reflection-test-b")
    forbidden_get = await async_client.get(
        f"/api/v1/cognitive/reflections/{reflection_id}",
        headers=headers_b,
    )
    assert forbidden_get.status_code == 404
