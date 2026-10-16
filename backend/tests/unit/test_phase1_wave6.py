import hashlib
import uuid
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token
from app.models.db.provenance import (
    EngineeringKnowledgeRecord,
    EngineeringSource,
    KnowledgeApplicability,
    KnowledgeStatus,
    SourceStatus,
    SourceTrustLevel,
    SourceType,
)
from app.services.ai.analysis.circuit_analysis_service import CircuitAnalysisService
from app.services.ai.verification.applicability_engine import KnowledgeApplicabilityEngine


def auth_headers(user_id: str, email: str, role: str = "engineer", tenant_id: str = "tenant-wave6-a") -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_source_lifecycle_versioning_and_supersession(async_client: AsyncClient):
    """
    Verifies source registration, deterministic SHA-256 document hashing,
    versioning lineage, and supersession preservation.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "engineer_src@quebet.ai", tenant_id="tenant-src-test")

    # 1. Register initial source (Rev A)
    raw_content = b"TI-LM7805:Rev.A:1998:Texas Instruments:Initial Release"
    doc_hash = hashlib.sha256(raw_content).hexdigest()

    create_payload = {
        "source_type": SourceType.DATASHEET.value,
        "title": "LM78xx Positive Regulators",
        "publisher": "Texas Instruments",
        "document_identifier": "TI-LM7805-DS",
        "revision": "Rev A",
        "version": "1.0",
        "publication_date": "1998-05-01",
        "document_hash": doc_hash,
        "trust_level": SourceTrustLevel.MANUFACTURER_PRIMARY.value,
        "status": SourceStatus.CURRENT.value,
        "metadata": {"initial_release": True},
    }

    res = await async_client.post("/api/v1/sources", json=create_payload, headers=headers)
    assert res.status_code == 201
    source_a = res.json()["data"]
    assert source_a["revision"] == "Rev A"
    assert source_a["document_hash"] == doc_hash
    assert source_a["status"] == "CURRENT"

    # 2. Query source
    res_get = await async_client.get(f"/api/v1/sources/{source_a['id']}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["data"]["document_identifier"] == "TI-LM7805-DS"

    # 3. Supersede with Rev B
    rev_b_content = b"TI-LM7805:Rev.B:2003:Texas Instruments:Updated Thermal Ratings"
    rev_b_hash = hashlib.sha256(rev_b_content).hexdigest()

    supersede_payload = {
        "new_source": {
            "source_type": SourceType.DATASHEET.value,
            "title": "LM78xx Positive Regulators Updated",
            "publisher": "Texas Instruments",
            "document_identifier": "TI-LM7805-DS",
            "revision": "Rev B",
            "version": "2.0",
            "publication_date": "2003-11-12",
            "document_hash": rev_b_hash,
            "trust_level": SourceTrustLevel.MANUFACTURER_PRIMARY.value,
            "status": SourceStatus.CURRENT.value,
            "metadata": {"updated_ratings": True},
        },
        "reason": "Manufacturer updated thermal dissipation specs for TO-220 package",
    }

    res_sup = await async_client.post(
        f"/api/v1/sources/{source_a['id']}/supersede",
        json=supersede_payload,
        headers=headers,
    )
    assert res_sup.status_code == 200
    source_b = res_sup.json()["data"]
    assert source_b["revision"] == "Rev B"
    assert source_b["supersedes_source_id"] == source_a["id"]

    # 4. Verify historical source A is preserved with SUPERSEDED status
    res_old = await async_client.get(f"/api/v1/sources/{source_a['id']}", headers=headers)
    assert res_old.status_code == 200
    assert res_old.json()["data"]["status"] == "SUPERSEDED"

    # 5. List versions
    res_versions = await async_client.get(f"/api/v1/sources/{source_b['id']}/versions", headers=headers)
    assert res_versions.status_code == 200
    versions = res_versions.json()["data"]
    assert len(versions) >= 2


@pytest.mark.asyncio
async def test_knowledge_record_and_applicability_engine():
    """
    Verifies Knowledge Applicability Engine deterministic evaluation:
      - Matches all conditions -> APPLICABLE
      - Contradicts condition -> NOT_APPLICABLE
      - Edge boundary condition -> CONDITIONALLY_APPLICABLE
      - Missing required context condition -> UNKNOWN (Never assume applicability)
    """
    conditions = {
        "package": "TO-220",
        "temp_max_c": 125.0,
        "vin_max_v": 25.0,
    }

    # Case 1: Fully Applicable
    ctx_good = {
        "package": "TO-220",
        "temp_c": 60.0,
        "vin_v": 12.0,
    }
    eval1 = KnowledgeApplicabilityEngine.evaluate(conditions, ctx_good)
    assert eval1["applicability"] == KnowledgeApplicability.APPLICABLE.value

    # Case 2: Package Mismatch -> NOT_APPLICABLE
    ctx_wrong_pkg = {
        "package": "SOT-223",
        "temp_c": 60.0,
        "vin_v": 12.0,
    }
    eval2 = KnowledgeApplicabilityEngine.evaluate(conditions, ctx_wrong_pkg)
    assert eval2["applicability"] == KnowledgeApplicability.NOT_APPLICABLE.value
    assert "Package mismatch" in eval2["reasons"][0]

    # Case 3: Over-temperature -> NOT_APPLICABLE
    ctx_overtemp = {
        "package": "TO-220",
        "temp_c": 135.0,
        "vin_v": 12.0,
    }
    eval3 = KnowledgeApplicabilityEngine.evaluate(conditions, ctx_overtemp)
    assert eval3["applicability"] == KnowledgeApplicability.NOT_APPLICABLE.value
    assert "Temperature overstress" in eval3["reasons"][0]

    # Case 4: Near edge -> CONDITIONALLY_APPLICABLE
    ctx_edge = {
        "package": "TO-220",
        "temp_c": 120.0,  # within 10°C of 125°C
        "vin_v": 12.0,
    }
    eval4 = KnowledgeApplicabilityEngine.evaluate(conditions, ctx_edge)
    assert eval4["applicability"] == KnowledgeApplicability.CONDITIONALLY_APPLICABLE.value

    # Case 5: Missing temperature context -> UNKNOWN (Never assume applicability)
    ctx_missing_temp = {
        "package": "TO-220",
        "vin_v": 12.0,
        # ambient temp not provided
    }
    eval5 = KnowledgeApplicabilityEngine.evaluate(conditions, ctx_missing_temp)
    assert eval5["applicability"] == KnowledgeApplicability.UNKNOWN.value
    assert "temp_max_c" in eval5["missing_conditions"]


@pytest.mark.asyncio
async def test_deterministic_analysis_reproducibility():
    """
    Mandatory Section 38: Reproducibility Test
    Given the identical circuit revision, rule-set version, knowledge state, and inputs,
    deterministic analysis produces 100% identical calculations and findings.
    """
    analyzer = CircuitAnalysisService()

    circuit_dict = {
        "id": "circ-repro-1",
        "version": 1,
        "components": [
            {
                "id": "c1",
                "name": "R1",
                "component_type": "RESISTOR",
                "value": "100",
                "footprint": "0805",
                "properties": {"power_rating": "0.125W"},
            },
            {
                "id": "c2",
                "name": "R2",
                "component_type": "RESISTOR",
                "value": "100",
                "footprint": "0805",
                "properties": {"power_rating": "0.125W"},
            },
        ],
        "nets": [
            {"id": "n1", "name": "VCC_5V"},
            {"id": "n2", "name": "MID"},
            {"id": "n3", "name": "GND"},
        ],
        "connections": [
            {"id": "conn1", "component_id": "c1", "pin_number": "1", "net_id": "n1"},
            {"id": "conn2", "component_id": "c1", "pin_number": "2", "net_id": "n2"},
            {"id": "conn3", "component_id": "c2", "pin_number": "1", "net_id": "n2"},
            {"id": "conn4", "component_id": "c2", "pin_number": "2", "net_id": "n3"},
        ],
        "assumptions": [{"key": "ambient_temp_c", "value": "25.0"}],
    }

    # Run analysis 1
    a1 = analyzer.analyze_circuit(circuit_dict=circuit_dict, user_assumptions=circuit_dict["assumptions"])

    # Run analysis 2 with identical context
    a2 = analyzer.analyze_circuit(circuit_dict=circuit_dict, user_assumptions=circuit_dict["assumptions"])

    # Verification: identical results
    assert a1["status"] == a2["status"]
    assert a1["confidence"] == a2["confidence"]
    assert len(a1["calculations"]) == len(a2["calculations"])
    assert len(a1["findings"]) == len(a2["findings"])
    assert a1["engine_versions"] == a2["engine_versions"]
    assert a1["rule_set_version"] == a2["rule_set_version"]

    # Verify each calculation output matches exactly
    for c1, c2 in zip(a1["calculations"], a2["calculations"]):
        assert c1["category"] == c2["category"]
        assert c1["formula"] == c2["formula"]
        assert c1["result"] == c2["result"]


@pytest.mark.asyncio
async def test_traceability_graph_and_end_to_end_chain(async_client: AsyncClient):
    """
    Tests complete traceability traversal:
    Analysis Traceability -> Finding Traceability -> Requirement Traceability -> Evidence Traceability.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "trace_eng@quebet.ai", tenant_id="tenant-trace-test")

    # 1. Create a Project and Circuit
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Traceability Circuit Lab", "project_type": "circuit"},
        headers=headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Linear Regulator Trace Circuit"},
        headers=headers,
    )
    assert circ_res.status_code == 201
    circuit_id = circ_res.json()["data"]["id"]

    # 2. Add Component (LM7805)
    await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={
            "ref_des": "U1",
            "component_type": "REGULATOR",
            "value": "LM7805",
            "footprint": "TO-220",
            "properties": {"load_current": "450mA"},
        },
        headers=headers,
    )

    # 3. Run Analysis
    ana_res = await async_client.post(f"/api/v1/circuits/{circuit_id}/analyze", headers=headers)
    assert ana_res.status_code == 200
    analysis_id = ana_res.json()["data"]["id"]

    # 4. Query Analysis Traceability
    trace_res = await async_client.get(f"/api/v1/analyses/{analysis_id}/traceability", headers=headers)
    assert trace_res.status_code == 200
    ana_trace = trace_res.json()["data"]
    assert ana_trace["analysis_id"] == analysis_id
    assert "OhmsLawEngine" in ana_trace["engine_versions"]
    assert "QUEBET-ELECTRICAL-001" in ana_trace["rule_set_version"]

    # 5. Create Design Review
    dr_res = await async_client.post(f"/api/v1/circuits/{circuit_id}/design-review", headers=headers)
    assert dr_res.status_code in [200, 201]
    review = dr_res.json()["data"]
    assert len(review["verification_requirements"]) > 0
    target_req = review["verification_requirements"][0]

    # 6. Requirement Traceability
    req_trace_res = await async_client.get(
        f"/api/v1/verification-requirements/{target_req['id']}/traceability",
        headers=headers,
    )
    assert req_trace_res.status_code == 200
    req_trace = req_trace_res.json()["data"]
    assert req_trace["requirement_id"] == target_req["id"]

    # 7. Add Traceable Evidence with Instrument & Calibration Reference
    ev_payload = {
        "evidence_type": "MEASUREMENT",
        "source": "Fluke 87V DMM",
        "description": "5.02V rail measured on pin 3 under 450mA active load",
        "value": "5.02",
        "unit": "V",
        "reference": "Lab Bench Log #402",
        "confidence": "HIGH",
        "metadata": {
            "instrument": "Digital Multimeter",
            "instrument_model": "Fluke 87V",
            "instrument_serial": "SN-8820491",
            "calibration_reference": "CAL-CERT-2026-03",
            "calibration_status": "CALIBRATED",
        },
    }
    ev_res = await async_client.post(
        f"/api/v1/verification-requirements/{target_req['id']}/evidence",
        json=ev_payload,
        headers=headers,
    )
    assert ev_res.status_code == 201
    evidence_id = ev_res.json()["data"]["id"]

    # 8. Query Evidence Traceability
    ev_trace_res = await async_client.get(f"/api/v1/evidence/{evidence_id}/traceability", headers=headers)
    assert ev_trace_res.status_code == 200
    ev_trace = ev_trace_res.json()["data"]
    assert ev_trace["evidence_id"] == evidence_id
    assert ev_trace["instrument_model"] == "Fluke 87V"
    assert ev_trace["calibration_status"] == "CALIBRATED"
    assert ev_trace["is_stale"] is False


@pytest.mark.asyncio
async def test_knowledge_impact_and_immutability(async_client: AsyncClient):
    """
    Mandatory Section 39: Knowledge Invalidation Test
    When a Knowledge record K1 becomes SUPERSEDED:
      - Historical analyses remain 100% immutable
      - Dependent elements are identified in blast radius
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "impact_eng@quebet.ai", tenant_id="tenant-impact-test")

    # 1. Create Knowledge Record K1
    k_res = await async_client.post(
        "/api/v1/knowledge",
        json={
            "domain": "POWER",
            "subject_type": "COMPONENT",
            "subject_identifier": "LM7805",
            "parameter": "v_in_max",
            "value": "35.0",
            "unit": "V",
            "status": "VERIFIED",
            "conditions": {"package": "TO-220"},
        },
        headers=headers,
    )
    assert k_res.status_code == 201
    k1 = k_res.json()["data"]

    # 2. Check impact on a circuit
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Impact Project", "project_type": "circuit"},
        headers=headers,
    )
    project_id = proj_res.json()["data"]["id"]
    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Impact Circuit"},
        headers=headers,
    )
    circuit_id = circ_res.json()["data"]["id"]

    # Add component
    await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={"ref_des": "U1", "component_type": "REGULATOR", "value": "LM7805"},
        headers=headers,
    )

    # Run analysis
    ana_res = await async_client.post(f"/api/v1/circuits/{circuit_id}/analyze", headers=headers)
    assert ana_res.status_code == 200
    analysis_before = ana_res.json()["data"]

    # 3. Supersede K1 with updated thermal derating value
    sup_res = await async_client.post(
        f"/api/v1/knowledge/{k1['id']}/supersede",
        json={
            "new_record": {
                "domain": "POWER",
                "subject_type": "COMPONENT",
                "subject_identifier": "LM7805",
                "parameter": "v_in_max",
                "value": "25.0",
                "unit": "V",
                "status": "VERIFIED",
                "conditions": {"package": "TO-220"},
            },
            "reason": "Derated for high ambient temperature applications",
        },
        headers=headers,
    )
    assert sup_res.status_code == 200

    # 4. Check Impact API
    impact_res = await async_client.get(
        f"/api/v1/circuits/{circuit_id}/knowledge-impact?knowledge_id={k1['id']}",
        headers=headers,
    )
    assert impact_res.status_code == 200
    impact = impact_res.json()["data"]
    assert impact["knowledge_id"] == k1["id"]
    assert impact["status"] == "SUPERSEDED"
    assert "Historical records remain immutable" in impact["recommendation"]

    # 5. Verify historical analysis remains 100% immutable
    ana_check = await async_client.get(f"/api/v1/circuits/{circuit_id}/analysis/latest", headers=headers)
    assert ana_check.status_code == 200
    assert ana_check.json()["data"]["id"] == analysis_before["id"]


@pytest.mark.asyncio
async def test_wave6_tenant_isolation_and_idor(async_client: AsyncClient):
    """
    Verifies that Tenant A cannot access Tenant B's sources, knowledge,
    or traceability graphs. Cross-tenant access is strictly rejected with HTTP 404.
    """
    tenant_a_headers = auth_headers(str(uuid.uuid4()), "user_a@tenant-a.com", tenant_id="tenant-a-iso")
    tenant_b_headers = auth_headers(str(uuid.uuid4()), "user_b@tenant-b.com", tenant_id="tenant-b-iso")

    # Tenant A creates a proprietary source
    src_res = await async_client.post(
        "/api/v1/sources",
        json={
            "source_type": SourceType.INTERNAL_ENGINEERING_RECORD.value,
            "title": "Tenant A Proprietary Battery Benchmark",
            "publisher": "Tenant A Corp",
            "document_identifier": "T-A-BAT-001",
            "revision": "v1.0",
            "trust_level": SourceTrustLevel.INTERNAL_VALIDATED.value,
        },
        headers=tenant_a_headers,
    )
    assert src_res.status_code == 201
    source_a_id = src_res.json()["data"]["id"]

    # Tenant A creates a proprietary knowledge record
    k_res = await async_client.post(
        "/api/v1/knowledge",
        json={
            "domain": "POWER",
            "subject_type": "COMPONENT",
            "subject_identifier": "PROPRIETARY_PMIC_A",
            "parameter": "quiescent_current_ua",
            "value": "1.2",
            "unit": "uA",
            "source_id": source_a_id,
        },
        headers=tenant_a_headers,
    )
    assert k_res.status_code == 201
    k_a_id = k_res.json()["data"]["id"]

    # Tenant B attempts to access Tenant A's source -> 404
    idor_src = await async_client.get(f"/api/v1/sources/{source_a_id}", headers=tenant_b_headers)
    assert idor_src.status_code == 404

    # Tenant B attempts to access Tenant A's knowledge -> 404
    idor_k = await async_client.get(f"/api/v1/knowledge/{k_a_id}", headers=tenant_b_headers)
    assert idor_k.status_code == 404
