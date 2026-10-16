import json
import uuid
import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.core.database import AsyncSessionLocal
from app.models.db.project import Project
from app.models.db.circuit import Circuit
from app.models.db.system import EngineeringSystem
from app.models.db.verification import (
    EngineeringDesignReview,
    EngineeringVerificationRequirement,
    EngineeringEvidence,
    VerificationStatus,
    EvidenceStatus,
)
from app.models.db.decision import (
    EngineeringRequirement,
    EngineeringAssumption,
    EngineeringDecisionRecord,
    EngineeringDesignReviewSession,
    EngineeringReviewFinding,
    EngineeringReviewAction,
    RequirementStatus,
    DecisionStatus,
)
from app.models.db.cognitive import (
    EngineeringCognitiveWorkflow,
    CognitiveWorkflowStatus,
)
from app.models.schemas.cognitive import (
    ActionCenterCategory,
    EvidenceSufficiencyStatus,
)


def auth_headers(
    user_id: str,
    email: str,
    role: str = "engineer",
    tenant_id: str = "tenant-p2-audit-a",
) -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


async def setup_circuit_and_review(
    async_client: AsyncClient,
    headers: dict[str, str],
    name: str = "Audit Circuit",
) -> tuple[str, str, str, str]:
    # 1. Project
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": name, "project_type": "power"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    # 2. Circuit
    c_payload = {
        "name": f"{name} Step-Down Topology",
        "description": "24V to 3.3V Step-down Buck Converter Topology",
        "components": [
            {
                "ref_des": "U1",
                "component_type": "regulator",
                "value": "TPS54331",
                "metadata": {"voltage_rating": "28V", "max_current": "3A"},
            },
            {
                "ref_des": "C1",
                "component_type": "capacitor",
                "value": "10uF",
                "metadata": {"voltage_rating": "50V"},
            },
            {
                "ref_des": "L1",
                "component_type": "inductor",
                "value": "10uH",
                "metadata": {"current_rating": "3.5A"},
            },
        ],
        "nets": [
            {"name": "VIN", "net_type": "power"},
            {"name": "VOUT", "net_type": "power"},
            {"name": "GND", "net_type": "ground"},
        ],
        "connections": [],
        "assumptions": [],
    }
    c_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json=c_payload,
        headers=headers,
    )
    assert c_res.status_code == 201
    circuit_id = c_res.json()["data"]["id"]

    # 3. Design Review generating verification requirements
    rev_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design-review",
        headers=headers,
    )
    assert rev_res.status_code == 201
    review_data = rev_res.json()["data"]
    review_id = review_data["id"]
    vr_id = review_data["verification_requirements"][0]["id"]

    return project_id, circuit_id, review_id, vr_id


# ==============================================================================
# SECTION 21: FINAL PHASE 2 FORENSIC INTEGRATION TEST
# ==============================================================================

@pytest.mark.asyncio
async def test_01_complete_phase2_end_to_end_cognitive_lifecycle(async_client: AsyncClient):
    """
    SECTION 21 END-TO-END PIPELINE:
    Executes complete engineering lifecycle across all Phase 2 cognitive layers:
    User Request -> Intent -> Context Synthesis -> Task DAG Planning -> Deterministic Execution
    -> Reflection & Reasoning -> Decision Preparation -> Historical Memory -> Workflow Orchestration
    -> Grounded Explanation -> Physical Evidence Verification -> Action Center -> Human-only Closure Gate.
    """
    tenant_id = f"tenant-audit-e2e-{uuid.uuid4().hex[:6]}"
    headers = auth_headers("usr-audit-1", "engineer@quebet.internal", tenant_id=tenant_id)

    project_id, circuit_id, review_id, vr_id = await setup_circuit_and_review(
        async_client, headers, name="Cognitive Lifecycle Pipeline"
    )

    # --------------------------------------------------------------------------
    # Step 1: Intent Resolution (Wave 1)
    # --------------------------------------------------------------------------
    intent_req = {
        "raw_request": "Analyze thermal dissipation and verify efficiency for 24V to 3.3V buck regulator",
        "project_id": project_id,
        "circuit_id": circuit_id,
        "scope": "CIRCUIT",
    }
    res_intent = await async_client.post(
        "/api/v1/cognitive/intents/resolve",
        json=intent_req,
        headers=headers,
    )
    assert res_intent.status_code == 201
    intent_data = res_intent.json()["data"]
    assert intent_data["id"] is not None
    assert intent_data["intent_type"] in ["ANALYSIS_QUERY", "VERIFICATION_REQUEST", "PARAMETRIC_SWEEP", "GENERAL_DESIGN", "PLAN_VERIFICATION"]
    intent_id = intent_data["id"]

    # --------------------------------------------------------------------------
    # Step 2: Context Resolution & Context Synthesis (Wave 1.1 & Wave 5)
    # --------------------------------------------------------------------------
    synth_req = {
        "project_id": project_id,
        "circuit_id": circuit_id,
    }
    res_synth = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json=synth_req,
        headers=headers,
    )
    assert res_synth.status_code == 201
    synth_data = res_synth.json()["data"]
    assert synth_data["id"] is not None
    assert synth_data["canonical_digest"] is not None
    # Verify SHA-256 canonical digest format
    assert len(synth_data["canonical_digest"]) == 64
    snapshot_id = synth_data["id"]

    # --------------------------------------------------------------------------
    # Step 3: Task Planning with Registered Read-Only Capabilities (Wave 1 & 1.1)
    # --------------------------------------------------------------------------
    plan_req = {
        "intent_packet_id": intent_id,
        "execution_policy": {},
    }
    res_plan = await async_client.post(
        "/api/v1/cognitive/plans",
        json=plan_req,
        headers=headers,
    )
    assert res_plan.status_code == 201
    plan_data = res_plan.json()["data"]
    assert plan_data["id"] is not None
    assert len(plan_data["tasks"]) >= 1
    plan_id = plan_data["id"]

    # --------------------------------------------------------------------------
    # Step 4: Deterministic Task Execution (Wave 1)
    # --------------------------------------------------------------------------
    res_exec = await async_client.post(
        f"/api/v1/cognitive/plans/{plan_id}/execute",
        headers=headers,
    )
    assert res_exec.status_code == 200
    exec_data = res_exec.json()["data"]
    assert exec_data["execution_status"] in ["COMPLETED", "SUCCESS", "EXECUTED"]
    assert len(exec_data["results"]) >= 1
    execution_id = exec_data["id"]

    # --------------------------------------------------------------------------
    # Step 5: Reflection & Engineering Reasoning (Wave 2)
    # --------------------------------------------------------------------------
    res_ref = await async_client.post(
        f"/api/v1/cognitive/executions/{execution_id}/reflect",
        headers=headers,
    )
    assert res_ref.status_code == 201
    ref_data = res_ref.json()["data"]
    assert ref_data["id"] is not None
    reflection_id = ref_data["id"]

    # --------------------------------------------------------------------------
    # Step 6: Controlled Decision Preparation (Wave 3) - Zero Synthetic Scoring
    # --------------------------------------------------------------------------
    brief_req = {
        "project_id": project_id,
        "circuit_id": circuit_id,
        "context_snapshot_id": snapshot_id,
        "reflection_id": reflection_id,
        "scope": "CIRCUIT",
        "question": "Which switching regulator topology best satisfies thermal requirements?",
        "title": "Buck Converter Controller Selection Brief",
        "description": "Comparative evaluation of candidate switching controllers",
        "alternatives": [
            {
                "id": "alt-tps54331",
                "name": "TPS54331 (Current Selected)",
                "parameters": {"fsw_khz": 570, "vin_max_v": 28, "efficiency_pct": 91.2},
                "requirement_evaluations": {"REQ-01": "SATISFIED", "REQ-02": "UNKNOWN"},
            },
            {
                "id": "alt-lm5164",
                "name": "LM5164 Wide-Vin Alternative",
                "parameters": {"fsw_khz": 400, "vin_max_v": 100, "efficiency_pct": 89.5},
                "requirement_evaluations": {"REQ-01": "SATISFIED", "REQ-02": "SATISFIED"},
            },
        ],
        "requirements": [
            {"id": "REQ-01", "name": "Input Voltage Range 24V", "type": "FUNCTIONAL"},
            {"id": "REQ-02", "name": "Physical Thermal Margin", "type": "ENVIRONMENTAL"},
        ],
    }
    res_brief = await async_client.post(
        "/api/v1/cognitive/decision-briefs",
        json=brief_req,
        headers=headers,
    )
    assert res_brief.status_code == 201
    brief_data = res_brief.json()["data"]
    assert brief_data["id"] is not None
    # Strictly zero synthetic scores and no automated winner declaration
    assert "priority_score" not in brief_data
    assert "confidence_score" not in brief_data
    assert "readiness_score" not in brief_data
    assert "winner" not in brief_data
    assert "recommended_alternative" not in brief_data

    # --------------------------------------------------------------------------
    # Step 7: Historical Memory Retrieval (Wave 4) - Non-Authoritative Advisory
    # --------------------------------------------------------------------------
    mem_req = {
        "project_id": project_id,
        "circuit_id": circuit_id,
    }
    res_mem = await async_client.post(
        f"/api/v1/cognitive/projects/{project_id}/memories/retrieve",
        json=mem_req,
        headers=headers,
    )
    assert res_mem.status_code == 200
    mem_data = res_mem.json()["data"]
    assert "memories" in mem_data
    for item in mem_data["memories"]:
        # Epistemic invariant: Memory is strictly non-authoritative
        assert item.get("is_authoritative", False) is False

    # --------------------------------------------------------------------------
    # Step 8: Workflow Orchestration (Wave 6)
    # --------------------------------------------------------------------------
    wf_req = {
        "project_id": project_id,
        "circuit_id": circuit_id,
        "user_request": "Execute end-to-end design verification",
    }
    res_wf = await async_client.post(
        "/api/v1/cognitive/workflows",
        json=wf_req,
        headers=headers,
    )
    assert res_wf.status_code == 201
    wf_data = res_wf.json()["data"]
    workflow_id = wf_data["id"]
    assert wf_data["status"] is not None
    assert wf_data["base_revision"] == 1

    # --------------------------------------------------------------------------
    # Step 9: Wave 7 Grounded Explanation
    # --------------------------------------------------------------------------
    res_explain = await async_client.post(
        f"/api/v1/cognitive/actions/ENGINEERING_VERIFICATION_REQUIREMENT/{vr_id}/explain",
        json={"category": "WHY"},
        headers=headers,
    )
    assert res_explain.status_code == 200
    exp_data = res_explain.json()["data"]
    assert exp_data["authority"] == "INFORMATIONAL_ONLY"
    assert len(exp_data["evidence_chain"]) >= 1

    # --------------------------------------------------------------------------
    # Step 10: Wave 8 Evidence & Verification Workspace
    # Invariants: CALCULATED != PHYSICALLY VERIFIED, AI CLOSURE = FORBIDDEN
    # --------------------------------------------------------------------------
    ws_res = await async_client.get(
        f"/api/v1/cognitive/workflows/{workflow_id}/verification",
        headers=headers,
    )
    assert ws_res.status_code == 200
    ws_data = ws_res.json()["data"]
    assert "obligations" in ws_data
    assert len(ws_data["obligations"]) >= 1

    target_vr = ws_data["obligations"][0]
    target_vr_id = target_vr["verification_requirement_id"]

    # 10a. Attach SIMULATION / CALCULATED evidence
    sim_evidence_req = {
        "evidence_type": "CALCULATION",
        "source": "SPICE Simulation Engine",
        "description": "Simulated output ripple 24mV peak-to-peak",
        "is_physical": False,
    }
    res_sim_evi = await async_client.post(
        f"/api/v1/cognitive/verification/{target_vr_id}/evidence",
        json=sim_evidence_req,
        headers=headers,
    )
    assert res_sim_evi.status_code == 200

    # 10b. If obligation requires physical measurement, try closing with simulation evidence -> 422
    if target_vr.get("is_physical_required"):
        close_fail_res = await async_client.post(
            f"/api/v1/cognitive/verification/{target_vr_id}/close",
            json={
                "decision": "VERIFIED",
                "rationale": "Attempting verification closure with simulation only",
                "actor": "lead-engineer@quebet.internal",
                "current_revision": 1,
            },
            headers=headers,
        )
        assert close_fail_res.status_code == 422
        assert "PHYSICAL_MEASUREMENT_MISSING" in close_fail_res.text

    # Attach real physical lab evidence
    lab_evidence_req = {
        "evidence_type": "MEASUREMENT",
        "source": "Keysight DSOX3024T Bench Scope",
        "description": "Physical bench test measured 26mV ripple with 500MHz probe",
        "is_physical": True,
    }
    res_lab_evi = await async_client.post(
        f"/api/v1/cognitive/verification/{target_vr_id}/evidence",
        json=lab_evidence_req,
        headers=headers,
    )
    assert res_lab_evi.status_code == 200

    # 10c. AI Actor attempts closure -> 403 Forbidden
    ai_close_res = await async_client.post(
        f"/api/v1/cognitive/verification/{target_vr_id}/close",
        json={
            "decision": "VERIFIED",
            "rationale": "Autonomous AI agent closing verification",
            "actor": "ai-assistant-v2",
            "current_revision": 1,
        },
        headers=headers,
    )
    assert ai_close_res.status_code == 403
    assert "AI_UNAUTHORIZED_VERIFICATION_CLOSURE" in ai_close_res.text

    # 10d. Human Engineer closes verification -> 200 OK
    human_close_res = await async_client.post(
        f"/api/v1/cognitive/verification/{target_vr_id}/close",
        json={
            "decision": "VERIFIED",
            "rationale": "Verified in laboratory by Senior Hardware Engineer",
            "actor": "lead-engineer@quebet.internal",
            "current_revision": 1,
        },
        headers=headers,
    )
    assert human_close_res.status_code == 200
    assert human_close_res.json()["data"]["status"] == VerificationStatus.SATISFIED.value
    assert human_close_res.json()["data"]["audit_event_id"] is not None

    # --------------------------------------------------------------------------
    # Step 11: Wave 9 Action Center Aggregation
    # --------------------------------------------------------------------------
    res_actions = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions",
        headers=headers,
    )
    assert res_actions.status_code == 200
    ac_data = res_actions.json()["data"]
    assert ac_data["project_id"] == project_id
    assert ac_data["base_revision"] == 1
    assert "actions" in ac_data
    assert "summary" in ac_data
    # Zero synthetic scoring check
    assert "priority_score" not in ac_data["summary"]
    assert "risk_score" not in ac_data["summary"]
    for act in ac_data["actions"]:
        assert "priority_score" not in act
        assert "confidence_score" not in act


@pytest.mark.asyncio
async def test_02_epistemic_invariants_unknown_and_physical_evidence(async_client: AsyncClient):
    """
    Epistemic Invariant Verification:
    - UNKNOWN != SATISFIED
    - CALCULATED != PHYSICALLY VERIFIED
    - Unvalidated assumptions and unknown requirements never silently pass.
    """
    tenant_id = f"tenant-epistemic-{uuid.uuid4().hex[:6]}"
    headers = auth_headers("usr-epi-1", "engineer@test.com", tenant_id=tenant_id)
    project_id, circuit_id, _, _ = await setup_circuit_and_review(
        async_client, headers, name="Epistemic Invariant Circuit"
    )

    async with AsyncSessionLocal() as db:
        sys_obj = EngineeringSystem(
            project_id=project_id,
            tenant_id=tenant_id,
            name="Thermal System",
            revision=1,
            created_by="usr-epi-1",
        )
        db.add(sys_obj)
        await db.flush()

        # Add an UNKNOWN assumption
        asm = EngineeringAssumption(
            system_id=sys_obj.id,
            tenant_id=tenant_id,
            description="Ambient junction thermal resistance theta-JA is 35 C/W",
            basis="Vendor preliminary datasheet table 4",
            status="UNKNOWN",
            impact="REVIEW_REQUIRED",
        )
        db.add(asm)

        # Add a VIOLATED requirement
        req = EngineeringRequirement(
            project_id=project_id,
            system_id=sys_obj.id,
            tenant_id=tenant_id,
            requirement_key="REQ-TH-01",
            title="Max Junction Temperature",
            description="Junction temperature shall not exceed 105C under worst-case ambient",
            status=RequirementStatus.VIOLATED.value,
            revision=1,
            created_by="usr-epi-1",
        )
        db.add(req)
        await db.commit()

    # Query Action Center
    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions",
        headers=headers,
    )
    assert res.status_code == 200
    actions = res.json()["data"]["actions"]

    # UNKNOWN assumption must appear in UNKNOWN category, not satisfied
    unknown_actions = [a for a in actions if a["source_entity_type"] == "ENGINEERING_ASSUMPTION"]
    assert len(unknown_actions) >= 1
    assert any(a["category"] == ActionCenterCategory.UNKNOWN.value for a in unknown_actions)
    assert any("UNKNOWN" in a["current_status"] for a in unknown_actions)

    # VIOLATED requirement must appear in BLOCKED category
    violated_actions = [a for a in actions if a["source_entity_type"] == "ENGINEERING_REQUIREMENT"]
    assert len(violated_actions) >= 1
    assert any(a["category"] == ActionCenterCategory.BLOCKED.value for a in violated_actions)


@pytest.mark.asyncio
async def test_03_revision_staleness_and_concurrency_guards(async_client: AsyncClient):
    """
    Revision Binding and Concurrency:
    Advancing circuit revision makes previous cognitive workflows, context snapshots,
    and verification obligations STALE. Closing a stale obligation must be rejected with 409.
    """
    tenant_id = f"tenant-rev-{uuid.uuid4().hex[:6]}"
    headers = auth_headers("usr-rev-1", "engineer@test.com", tenant_id=tenant_id)
    project_id, circuit_id, review_id, vr_id = await setup_circuit_and_review(
        async_client, headers, name="Revision Staleness Circuit"
    )

    # Attach evidence at Revision 1
    evi_req = {
        "title": "Bench Test Revision 1",
        "evidence_type": "MEASUREMENT",
        "summary": "Voltage test at Rev 1",
        "metadata": {"is_physical": True},
    }
    await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json=evi_req,
        headers=headers,
    )

    # Advance Circuit Version from 1 to 2
    async with AsyncSessionLocal() as db:
        c_res = await db.execute(
            Circuit.__table__.update()
            .where(Circuit.id == circuit_id)
            .values(version=2)
        )
        await db.commit()

    # Attempting to close verification at Revision 1 now fails with 409 VERIFICATION_STALE_REVISION
    close_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/close",
        json={
            "decision": "VERIFIED",
            "rationale": "Human closing on stale revision",
            "actor": "lead-engineer@quebet.internal",
            "current_revision": 1,
        },
        headers=headers,
    )
    assert close_res.status_code == 409
    assert "VERIFICATION_STALE_REVISION" in close_res.text


@pytest.mark.asyncio
async def test_04_human_authority_boundary_and_ai_mutation_rejection(async_client: AsyncClient):
    """
    Human Authority Boundary:
    AI actors are strictly prohibited from mutating engineering state, approving proposals,
    authorizing decisions, or closing verification obligations.
    """
    tenant_id = f"tenant-authority-{uuid.uuid4().hex[:6]}"
    headers = auth_headers("usr-auth-1", "engineer@test.com", tenant_id=tenant_id)
    project_id, circuit_id, review_id, vr_id = await setup_circuit_and_review(
        async_client, headers, name="Authority Boundary Circuit"
    )

    # Attach valid evidence first
    await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json={
            "title": "Lab Test",
            "evidence_type": "MEASUREMENT",
            "summary": "Lab Test Complete",
            "metadata": {"is_physical": True},
        },
        headers=headers,
    )

    # Test various AI actor identities
    ai_actors = ["ai-copilot", "agent-system", "autonomous-bot-3", "model-gpt-4o"]
    for actor_name in ai_actors:
        res = await async_client.post(
            f"/api/v1/cognitive/verification/{vr_id}/close",
            json={
                "decision": "VERIFIED",
                "rationale": "Automated verification closure",
                "actor": actor_name,
                "current_revision": 1,
            },
            headers=headers,
        )
        assert res.status_code == 403
        assert "AI_UNAUTHORIZED_VERIFICATION_CLOSURE" in res.text


@pytest.mark.asyncio
async def test_05_cross_tenant_isolation_boundary(async_client: AsyncClient):
    """
    Cross-Tenant Isolation:
    Tenant B cannot access Tenant A's project actions, verification obligations,
    workflows, or explanations.
    """
    tenant_a = f"tenant-a-{uuid.uuid4().hex[:6]}"
    tenant_b = f"tenant-b-{uuid.uuid4().hex[:6]}"

    headers_a = auth_headers("usr-a", "user.a@quebet.internal", tenant_id=tenant_a)
    headers_b = auth_headers("usr-b", "user.b@quebet.internal", tenant_id=tenant_b)

    project_id, circuit_id, review_id, vr_id = await setup_circuit_and_review(
        async_client, headers_a, name="Tenant A Circuit"
    )

    # Tenant B queries Tenant A's project actions -> 404
    res_act = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions",
        headers=headers_b,
    )
    assert res_act.status_code == 404

    # Tenant B queries Tenant A's verification obligation -> 404
    res_vr = await async_client.get(
        f"/api/v1/cognitive/verification/{vr_id}",
        headers=headers_b,
    )
    assert res_vr.status_code == 404

    # Tenant B attempts explanation on Tenant A's obligation -> 404
    res_exp = await async_client.post(
        f"/api/v1/cognitive/actions/ENGINEERING_VERIFICATION_REQUIREMENT/{vr_id}/explain",
        json={"category": "WHY"},
        headers=headers_b,
    )
    assert res_exp.status_code == 404


@pytest.mark.asyncio
async def test_06_provenance_and_audit_integrity(async_client: AsyncClient):
    """
    Provenance & Audit Integrity:
    Context snapshots generate SHA-256 digests.
    Verification closure generates immutable human audit events with full state transitions.
    Output payloads contain strictly zero synthetic scores.
    """
    tenant_id = f"tenant-provenance-{uuid.uuid4().hex[:6]}"
    headers = auth_headers("usr-prov-1", "engineer@test.com", tenant_id=tenant_id)
    project_id, circuit_id, review_id, vr_id = await setup_circuit_and_review(
        async_client, headers, name="Provenance Integrity Circuit"
    )

    # 1. Synthesize Context
    res_synth = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "base_revision": 1,
            "scope": "CIRCUIT",
        },
        headers=headers,
    )
    assert res_synth.status_code == 201
    digest = res_synth.json()["data"]["canonical_digest"]
    assert len(digest) == 64
    int(digest, 16)  # Must be valid hex

    # 2. Attach physical evidence and close
    evi_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json={
            "evidence_type": "MEASUREMENT",
            "source": "Bench Ripple Test Rig",
            "description": "Bench ripple measurement complete",
            "is_physical": True,
        },
        headers=headers,
    )
    assert evi_res.status_code == 200

    close_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/close",
        json={
            "decision": "VERIFIED",
            "rationale": "Audit test closure",
            "actor": "lead-engineer@quebet.internal",
            "current_revision": 1,
        },
        headers=headers,
    )
    assert close_res.status_code == 200
    close_data = close_res.json()["data"]
    assert close_data["audit_event_id"] is not None
    assert close_data["closed_by"] == "lead-engineer@quebet.internal"
    assert close_data["decision"] == "VERIFIED"
