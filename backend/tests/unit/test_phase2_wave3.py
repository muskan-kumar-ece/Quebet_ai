import json
import uuid
import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.db.cognitive import (
    DecisionBriefStatus,
    HumanDecisionType,
)
from app.services.ai.cognitive.decision.comparison_service import (
    EngineeringDecisionComparisonService,
    CategoricalState,
)
from app.services.ai.cognitive.decision.tradeoff_service import EngineeringTradeoffService
from app.services.ai.cognitive.decision.consequence_service import DecisionConsequenceService
from app.services.ai.cognitive.decision.decision_brief_service import EngineeringDecisionBriefService


def auth_headers(user_id: str, email: str, role: str = "engineer", tenant_id: str = "tenant-p2w3-a") -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. UNIT TESTS: COMPARISON SERVICE & CATEGORICAL STATES
# ============================================================================

def test_comparison_service_categorical_states_and_zero_scoring():
    """
    Verifies that the comparison engine produces strict categorical states:
    SATISFIED, NOT_SATISFIED, UNKNOWN, NOT_EVALUATED, NOT_APPLICABLE.
    Ensures zero numeric scores or ratings are produced.
    """
    alternatives = [
        {
            "id": "alt-buck-01",
            "name": "Synchronous Buck Converter",
            "parameters": {"efficiency": "92%", "cost": "$1.20", "footprint": "12mm"},
        },
        {
            "id": "alt-ldo-01",
            "name": "Low-Dropout Linear Regulator",
            "parameters": {"efficiency": "65%", "cost": "$0.35"},  # footprint missing
        },
    ]

    requirements = [
        {"id": "REQ-EFF", "name": "Efficiency Minimum", "property": "efficiency", "min_value": "85%"},
        {"id": "REQ-COST", "name": "BOM Cost Maximum", "property": "cost", "max_value": "$1.50"},
        {"id": "REQ-AREA", "name": "PCB Footprint", "property": "footprint", "max_value": "15mm"},
    ]

    comparisons = EngineeringDecisionComparisonService.compare_alternatives(
        alternatives=alternatives,
        requirements=requirements,
        constraints=[],
    )

    assert "comparison_matrix" in comparisons
    matrix = comparisons["comparison_matrix"]
    assert len(matrix) == 2

    buck_entry = next(e for e in matrix if e["alternative_id"] == "alt-buck-01")
    ldo_entry = next(e for e in matrix if e["alternative_id"] == "alt-ldo-01")

    # Check REQ-EFF
    assert buck_entry["requirement_evaluations"]["REQ-EFF"]["state"] == CategoricalState.SATISFIED.value
    assert ldo_entry["requirement_evaluations"]["REQ-EFF"]["state"] == CategoricalState.NOT_SATISFIED.value

    # Check REQ-AREA (missing on LDO -> UNKNOWN)
    assert buck_entry["requirement_evaluations"]["REQ-AREA"]["state"] == CategoricalState.SATISFIED.value
    assert ldo_entry["requirement_evaluations"]["REQ-AREA"]["state"] == CategoricalState.UNKNOWN.value

    # Strict invariant: no scores in comparison
    serialized = json.dumps(comparisons)
    for forbidden in ["score", "confidence_percentage", "readiness_percentage", "winner"]:
        assert forbidden not in serialized


def test_tradeoff_and_consequence_services():
    """
    Verifies that tradeoff analysis and consequence analysis report explicit facts
    without attempting to resolve trade-offs or recommend a preferred option.
    """
    alternatives = [
        {"id": "alt-a", "name": "Option A (High Speed)", "parameters": {"power": "2.5W", "speed": "100MHz"}},
        {"id": "alt-b", "name": "Option B (Low Power)", "parameters": {"power": "0.4W", "speed": "20MHz"}},
    ]

    tradeoffs = EngineeringTradeoffService.analyze_tradeoffs(alternatives)
    assert "tradeoffs_by_alternative" in tradeoffs
    serialized_tradeoffs = json.dumps(tradeoffs)
    assert "winner" not in serialized_tradeoffs

    consequences = DecisionConsequenceService.evaluate_consequences(alternatives, current_revision=1)
    assert "alt-a" in consequences
    assert "alt-b" in consequences


# ============================================================================
# 2. INTEGRATION TESTS VIA API (ALL 7 MANDATORY SCENARIOS)
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_1_and_7_two_valid_alternatives_no_winner_no_scores(async_client: AsyncClient):
    """
    Scenario 1: Two valid alternatives.
    - Status is READY_FOR_REVIEW.
    - No winner is selected or recommended.
    - Human decision is required.
    Scenario 7: Zero synthetic scoring invariants checked across the entire payload.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w3-sc1"
    headers = auth_headers(user_id, "lead_eng@quebet.ai", tenant_id=tenant)

    # Create project
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Power Architecture Selection", "project_type": "power"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    # Create decision brief with 2 valid alternatives
    payload = {
        "project_id": project_id,
        "title": "5V to 3.3V Power Stage Topology Selection",
        "description": "Choose between synchronous buck topology and discrete low-dropout regulator.",
        "alternatives": [
            {
                "id": "alt-buck",
                "name": "TPS62840 Synchronous Buck",
                "topology": "SWITCHING_BUCK",
                "parameters": {"efficiency": "92%", "cost": "$1.15", "quiescent_current": "60nA"},
            },
            {
                "id": "alt-ldo",
                "name": "TPS7A02 Low-Dropout Regulator",
                "topology": "LINEAR_LDO",
                "parameters": {"efficiency": "88%", "cost": "$0.45", "quiescent_current": "25nA"},
            },
        ],
        "requirements": [
            {"id": "REQ-1", "name": "Minimum Efficiency", "property": "efficiency", "min_value": "85%"},
        ],
        "constraints": [
            {"id": "CON-1", "name": "BOM Cost", "property": "cost", "max_value": "$2.00"},
        ],
    }

    create_res = await async_client.post("/api/v1/cognitive/decision-briefs", json=payload, headers=headers)
    assert create_res.status_code == 201
    brief = create_res.json()["data"]

    # Invariants for Scenario 1
    assert brief["status"] == DecisionBriefStatus.READY_FOR_REVIEW.value
    assert brief["human_decision_required"] is True
    assert brief["selected_alternative_id"] is None
    assert brief["decision_record_id"] is None

    # Verify Decision Questions generated
    assert len(brief["decision_questions"]) > 0
    for q in brief["decision_questions"]:
        assert q["origin"] == "AI_GENERATED"
        assert q["status"] == "INFORMATIONAL"
        assert q["human_response_required"] is True

    # Scenario 7: Invariant check - NO forbidden scoring keys anywhere in brief
    serialized = json.dumps(brief)
    forbidden_terms = [
        '"score"',
        '"confidence_percentage"',
        '"readiness_percentage"',
        '"winner"',
        '"best_alternative"',
        '"recommended_winner"',
    ]
    for term in forbidden_terms:
        assert term not in serialized, f"Forbidden synthetic score term {term} found in brief!"


@pytest.mark.asyncio
async def test_scenario_2_one_alternative_violates_requirement(async_client: AsyncClient):
    """
    Scenario 2: One alternative violates requirement.
    - Alternative A: SATISFIED
    - Alternative B: NOT_SATISFIED
    - System presents this factual comparison without auto-selecting A or auto-rejecting B.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w3-sc2"
    headers = auth_headers(user_id, "lead_eng@quebet.ai", tenant_id=tenant)

    # Create project
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Thermal Margin Evaluation", "project_type": "thermal"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    payload = {
        "project_id": project_id,
        "title": "Thermal Envelope Architecture",
        "description": "Evaluate power dissipation against 500mA current requirement ceiling.",
        "alternatives": [
            {
                "id": "alt-efficient",
                "name": "High Efficiency Option",
                "parameters": {"current": "420mA"},
            },
            {
                "id": "alt-lossy",
                "name": "Lossy Option",
                "parameters": {"current": "650mA"},
            },
        ],
        "requirements": [
            {"id": "REQ-I-CEIL", "name": "Current Ceiling", "property": "current", "max_value": "500mA"},
        ],
    }

    create_res = await async_client.post("/api/v1/cognitive/decision-briefs", json=payload, headers=headers)
    assert create_res.status_code == 201
    brief = create_res.json()["data"]

    matrix = brief["requirement_summary"]["comparison_matrix"]
    alt_eff = next(e for e in matrix if e["alternative_id"] == "alt-efficient")
    alt_loss = next(e for e in matrix if e["alternative_id"] == "alt-lossy")

    assert alt_eff["requirement_evaluations"]["REQ-I-CEIL"]["state"] == CategoricalState.SATISFIED.value
    assert alt_loss["requirement_evaluations"]["REQ-I-CEIL"]["state"] == CategoricalState.NOT_SATISFIED.value

    # System did NOT auto-select alt-efficient
    assert brief["selected_alternative_id"] is None
    assert brief["status"] == DecisionBriefStatus.READY_FOR_REVIEW.value
    assert brief["human_decision_required"] is True


@pytest.mark.asyncio
async def test_scenario_3_unknown_parameter_requires_verification(async_client: AsyncClient):
    """
    Scenario 3: Parameter unknown.
    - Parameter status reported as UNKNOWN.
    - Verification gap or unknown reported.
    - Human decision required = True.
    - State is NEVER marked SATISFIED or VERIFIED without deterministic evidence.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w3-sc3"
    headers = auth_headers(user_id, "lead_eng@quebet.ai", tenant_id=tenant)

    # Create project
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "RF Stage Verification", "project_type": "rf"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    payload = {
        "project_id": project_id,
        "title": "RF Power Amplifier Selection",
        "description": "Select RF PA where noise figure is uncharacterized for one option.",
        "alternatives": [
            {
                "id": "alt-pa-1",
                "name": "Characterized PA",
                "parameters": {"noise_figure": "1.8dB"},
            },
            {
                "id": "alt-pa-2",
                "name": "Uncharacterized PA",
                "parameters": {},  # Noise figure missing
            },
        ],
        "requirements": [
            {"id": "REQ-NF", "name": "Maximum Noise Figure", "property": "noise_figure", "max_value": "2.5dB"},
        ],
    }

    create_res = await async_client.post("/api/v1/cognitive/decision-briefs", json=payload, headers=headers)
    assert create_res.status_code == 201
    brief = create_res.json()["data"]

    # Verify categorical state is UNKNOWN, never SATISFIED
    matrix = brief["requirement_summary"]["comparison_matrix"]
    alt_pa2 = next(e for e in matrix if e["alternative_id"] == "alt-pa-2")
    assert alt_pa2["requirement_evaluations"]["REQ-NF"]["state"] == CategoricalState.UNKNOWN.value

    # Verify unknown and verification gap generated
    assert len(alt_pa2["unknowns"]) > 0 or len(alt_pa2["verification_gaps"]) > 0
    assert brief["human_decision_required"] is True


@pytest.mark.asyncio
async def test_scenario_4_stale_decision_brief_conflict(async_client: AsyncClient):
    """
    Scenario 4: Stale decision brief.
    - When base revision advances, brief is marked STALE.
    - Attempting to record human decision against a STALE brief returns HTTP 409 Conflict (DECISION_BRIEF_STALE).
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w3-sc4"
    headers = auth_headers(user_id, "lead_eng@quebet.ai", tenant_id=tenant)

    # Create project
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Stale Protection Test", "project_type": "circuit"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    # Create decision brief with base revision 1
    payload = {
        "project_id": project_id,
        "title": "Clock Tree Architecture",
        "description": "Clock distribution comparison",
        "base_revision": 1,
        "alternatives": [
            {"id": "alt-osc-1", "name": "Internal RC Oscillator", "parameters": {}},
            {"id": "alt-osc-2", "name": "External TCXO", "parameters": {}},
        ],
    }

    create_res = await async_client.post("/api/v1/cognitive/decision-briefs", json=payload, headers=headers)
    assert create_res.status_code == 201
    brief_id = create_res.json()["data"]["id"]

    # Simulate project revision advance to revision 2
    decision_payload = {
        "decision_type": HumanDecisionType.ADOPT_ALTERNATIVE.value,
        "selected_alternative_id": "alt-osc-2",
        "rationale": "TCXO provides required ppm stability",
        "actor": "engineer-alice",
        "current_revision": 2,  # Project advanced beyond revision 1
    }

    decide_res = await async_client.post(
        f"/api/v1/cognitive/decision-briefs/{brief_id}/decision",
        json=decision_payload,
        headers=headers,
    )
    assert decide_res.status_code == 409
    error_data = decide_res.json()
    assert error_data["detail"]["code"] == "DECISION_BRIEF_STALE"


@pytest.mark.asyncio
async def test_scenario_5_reject_ai_decision_attempt(async_client: AsyncClient):
    """
    Scenario 5: AI attempts selection.
    - AI agent or model tries to post decision to decision-briefs/{id}/decision.
    - Must be rejected with HTTP 403 Forbidden and code MODEL_UNAUTHORIZED_DECISION.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w3-sc5"
    headers = auth_headers(user_id, "lead_eng@quebet.ai", tenant_id=tenant)

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "AI Decision Rejection Test", "project_type": "circuit"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    payload = {
        "project_id": project_id,
        "title": "Subsystem Gateway Protocol",
        "description": "CAN vs RS-485",
        "alternatives": [
            {"id": "alt-can", "name": "CAN Bus", "parameters": {}},
            {"id": "alt-rs485", "name": "RS-485", "parameters": {}},
        ],
    }
    create_res = await async_client.post("/api/v1/cognitive/decision-briefs", json=payload, headers=headers)
    assert create_res.status_code == 201
    brief_id = create_res.json()["data"]["id"]

    # AI agent attempts to make decision
    ai_attempts = [
        {"actor": "ai-agent-v1", "desc": "actor name has ai-agent"},
        {"actor": "model-gemini-pro", "desc": "actor name has model"},
        {"actor": "autonomous_ai", "desc": "actor name has autonomous_ai"},
    ]

    for attempt in ai_attempts:
        decision_payload = {
            "decision_type": HumanDecisionType.ADOPT_ALTERNATIVE.value,
            "selected_alternative_id": "alt-can",
            "rationale": "Autonomous model selected CAN",
            "actor": attempt["actor"],
        }
        res = await async_client.post(
            f"/api/v1/cognitive/decision-briefs/{brief_id}/decision",
            json=decision_payload,
            headers=headers,
        )
        assert res.status_code == 403, f"Failed to reject {attempt['desc']}"
        assert res.json()["detail"]["code"] == "MODEL_UNAUTHORIZED_DECISION"


@pytest.mark.asyncio
async def test_scenario_6_human_decision_ratification_and_provenance(async_client: AsyncClient):
    """
    Scenario 6: Human decision recorded.
    - Legitimate human engineer records decision.
    - EngineeringDecisionRecord is created in the database with status RATIFIED.
    - Human actor is recorded.
    - Brief status updated to DECIDED, human_decision_required = False.
    - Full provenance trace available.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w3-sc6"
    headers = auth_headers(user_id, "lead_engineer@quebet.ai", tenant_id=tenant)

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Battery Management Selection", "project_type": "battery"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    payload = {
        "project_id": project_id,
        "title": "BMS IC Selection",
        "description": "Choose between integrated BMS IC and discrete controller",
        "alternatives": [
            {"id": "alt-bq76952", "name": "TI BQ76952 Integrated BMS", "parameters": {"cells": "16S"}},
            {"id": "alt-discrete", "name": "Discrete ADC + MCU BMS", "parameters": {"cells": "16S"}},
        ],
    }
    create_res = await async_client.post("/api/v1/cognitive/decision-briefs", json=payload, headers=headers)
    assert create_res.status_code == 201
    brief_id = create_res.json()["data"]["id"]

    # Legitimate human engineer decides
    human_decision_payload = {
        "decision_type": HumanDecisionType.ADOPT_ALTERNATIVE.value,
        "selected_alternative_id": "alt-bq76952",
        "rationale": "Integrated cell monitoring reduces PCB routing complexity and component count.",
        "actor": "engineer-sarah",
    }

    decide_res = await async_client.post(
        f"/api/v1/cognitive/decision-briefs/{brief_id}/decision",
        json=human_decision_payload,
        headers=headers,
    )
    assert decide_res.status_code == 200
    res_data = decide_res.json()["data"]

    # Verify brief updated
    assert res_data["status"] == DecisionBriefStatus.DECIDED.value
    assert res_data["human_decision_required"] is False
    assert res_data["selected_alternative_id"] == "alt-bq76952"
    assert res_data["decision_record_id"] is not None

    # Verify decision record
    record = res_data["decision_record"]
    assert record["status"] == "RATIFIED"
    assert record["decided_by"] == "engineer-sarah"
    assert record["selected_alternative_id"] == "alt-bq76952"

    # Verify GET brief returns provenance
    get_res = await async_client.get(f"/api/v1/cognitive/decision-briefs/{brief_id}", headers=headers)
    assert get_res.status_code == 200
    brief_data = get_res.json()["data"]
    assert "provenance" in brief_data
    assert len(brief_data["provenance"]["input_digest"]) == 64
    assert len(brief_data["provenance"]["output_digest"]) == 64
    assert brief_data["provenance"]["prompt_version"] == "v1"


@pytest.mark.asyncio
async def test_tenant_isolation_on_decision_briefs(async_client: AsyncClient):
    """
    Verifies that decision briefs adhere strictly to tenant isolation.
    Tenant B cannot access or record decisions on Tenant A's decision briefs.
    """
    user_a = str(uuid.uuid4())
    headers_a = auth_headers(user_a, "alice@org-a.com", tenant_id="tenant-alpha")

    user_b = str(uuid.uuid4())
    headers_b = auth_headers(user_b, "bob@org-b.com", tenant_id="tenant-beta")

    # Org A creates project & brief
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Confidential Alpha Project", "project_type": "circuit"},
        headers=headers_a,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    brief_payload = {
        "project_id": project_id,
        "title": "Avionics Bus Redundancy",
        "description": "Dual MIL-STD-1553 vs ARINC-429",
        "alternatives": [
            {"id": "alt-1553", "name": "MIL-STD-1553B", "parameters": {}},
            {"id": "alt-429", "name": "ARINC-429", "parameters": {}},
        ],
    }
    create_res = await async_client.post("/api/v1/cognitive/decision-briefs", json=brief_payload, headers=headers_a)
    assert create_res.status_code == 201
    brief_id = create_res.json()["data"]["id"]

    # Org B attempts to read Org A's brief
    b_read = await async_client.get(f"/api/v1/cognitive/decision-briefs/{brief_id}", headers=headers_b)
    assert b_read.status_code == 404

    # Org B attempts to decide on Org A's brief
    b_decide = await async_client.post(
        f"/api/v1/cognitive/decision-briefs/{brief_id}/decision",
        json={
            "decision_type": HumanDecisionType.ADOPT_ALTERNATIVE.value,
            "selected_alternative_id": "alt-1553",
            "actor": "engineer-bob",
        },
        headers=headers_b,
    )
    assert b_decide.status_code == 404
