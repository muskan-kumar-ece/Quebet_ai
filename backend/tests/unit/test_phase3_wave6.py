"""
Phase 3 Wave 6 Test Suite: BOM & Supply-Chain Intelligence.

Verifies strict non-negotiable invariants:
- Design Identity vs Procurement Identity
- Voltage/Power/Current rating and tolerance compatibility
- Footprint & Package compatibility (pin count alone != compatible)
- Missing parameter handling (UNKNOWN != SATISFIED)
- Multi-source inventory conflicts (CONFLICTING)
- Zero synthetic scoring (no SUPPLY_SCORE, WINNER, etc.)
- Deterministic diff generation
- Human-gated substitution approval (AI actors rejected with 403)
- Stale revision rejection
- Deterministic canonical snapshot and SHA-256 digest
- Multi-tenant isolation and IDOR protection
"""

import hashlib
import json
import uuid
import pytest
from fastapi import HTTPException

from app.core.dependencies import AuthenticatedUser
from app.models.db.bom import (
    EngineeringBOM,
    EngineeringBOMLine,
    ComponentPartCandidate,
    BOMSubstitutionProposal,
    BOMStatus,
    BOMLineStatus,
    PartLifecycleStatus,
    PartAvailabilityStatus,
    PartCompatibilityStatus,
    ParameterEvaluationStatus,
)
from app.models.db.circuit import Circuit
from app.models.db.component import Component
from app.models.db.project import Project, ProjectStatus, ProjectType
from app.models.db.proposal import ProposalStatus
from app.models.schemas.bom import (
    EngineeringBOMCreate,
    ComponentPartCandidateCreate,
    BOMSubstitutionProposalCreate,
    SupplySourceObservation,
)
from app.services.ai.bom.bom_generator import BOMGenerator
from app.services.ai.bom.compatibility_engine import BOMCompatibilityEngine
from app.services.ai.bom.package_compatibility_engine import BOMPackageCompatibilityEngine
from app.services.ai.bom.requirement_extractor import BOMRequirementExtractor
from app.services.ai.bom.snapshot import BOMSnapshotService
from app.services.ai.bom.substitute_validator import BOMSubstituteValidator
from app.services.ai.bom.supply_intelligence_engine import BOMSupplyIntelligenceEngine
from app.services.bom_service import bom_service


class TestPhase3Wave6BOM:
    """Test suite covering the 30 requirements of Phase 3 Wave 6."""

    def _create_sample_circuit(self, tenant_id: str = "tenant-1") -> Circuit:
        proj_id = str(uuid.uuid4())
        c = Circuit(
            id=str(uuid.uuid4()),
            project_id=proj_id,
            tenant_id=tenant_id,
            name="Power Supply Schematic",
            version=1,
            created_by="user-eng",
        )
        r1 = Component(
            id=str(uuid.uuid4()),
            circuit_id=c.id,
            ref_des="R1",
            component_type="Resistor",
            value=10.0,
            unit="kOhm",
            tolerance="1%",
            rating="0.25W",
            package="0805",
            part_number="RC0805FR-0710KL",
            manufacturer="Yageo",
        )
        c1 = Component(
            id=str(uuid.uuid4()),
            circuit_id=c.id,
            ref_des="C1",
            component_type="Capacitor",
            value=100.0,
            unit="uF",
            tolerance="10%",
            rating="25V",
            package="1206",
            part_number=None,
            manufacturer=None,
        )
        c.components = [r1, c1]
        return c

    # 1. BOM Generation from Circuit
    def test_01_bom_generation_from_circuit(self):
        circuit = self._create_sample_circuit()
        bom = BOMGenerator.generate_from_circuit(circuit=circuit, revision=1)

        assert bom.circuit_id == circuit.id
        assert bom.version == 1
        assert len(bom.lines) == 2
        ref_desses = [l.reference_designator for l in bom.lines]
        assert "C1" in ref_desses
        assert "R1" in ref_desses
        assert bom.status == BOMStatus.DRAFT.value

    # 2. Design Identity vs Procurement Identity
    def test_02_design_identity_vs_procurement_identity(self):
        circuit = self._create_sample_circuit()
        bom = BOMGenerator.generate_from_circuit(circuit=circuit)
        r1_line = next(l for l in bom.lines if l.reference_designator == "R1")

        # Design Identity
        assert r1_line.reference_designator == "R1"
        assert r1_line.component_type == "Resistor"
        assert r1_line.design_package == "0805"
        assert r1_line.engineering_requirements["tolerance"] == 1.0

        # Procurement Identity (Candidates)
        assert len(r1_line.candidates) == 1
        cand = r1_line.candidates[0]
        assert cand.mpn == "RC0805FR-0710KL"
        assert cand.manufacturer == "Yageo"

    # 3. MPN Provenance and Auditability
    def test_03_mpn_provenance_and_auditability(self):
        cand = ComponentPartCandidate(
            id="cand-1",
            bom_line_id="line-1",
            mpn="GRM21BR71E105KA99L",
            manufacturer="Murata",
            lifecycle_status=PartLifecycleStatus.ACTIVE.value,
            availability_status=PartAvailabilityStatus.IN_STOCK.value,
            compatibility_status=PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value,
            parameters={"voltage_rating": 25.0, "tolerance": 10.0},
            supply_sources=[{
                "supplier": "Mouser",
                "stock": 4500,
                "currency": "USD",
                "unit_price": 0.08,
                "observed_at": "2026-10-01T12:00:00Z",
            }],
        )
        assert cand.mpn == "GRM21BR71E105KA99L"
        assert cand.manufacturer == "Murata"
        assert len(cand.supply_sources) == 1
        assert cand.supply_sources[0]["observed_at"] == "2026-10-01T12:00:00Z"

    # 4. Requirement Extraction (Nominal and Ratings)
    def test_04_requirement_extraction_nominal_and_ratings(self):
        comp_dict = {
            "ref_des": "R1",
            "type": "Resistor",
            "value": 4.7,
            "unit": "k",
            "tolerance": "5%",
            "rating": "0.125W",
            "package": "0603",
        }
        specs = BOMRequirementExtractor.extract_requirements(comp_dict)
        assert specs["nominal_value"] == 4700.0
        assert specs["tolerance"] == 5.0
        assert specs["power_rating"] == 0.125
        assert specs["voltage_rating"] is None
        assert specs["package"] == "0603"

    # 5. Voltage Rating Derating Boundary
    def test_05_voltage_rating_derating_boundary(self):
        req = {"nominal_value": 100.0, "voltage_rating": 25.0}
        cand_higher = {"nominal_value": 100.0, "voltage_rating": 50.0}
        eval_higher = BOMCompatibilityEngine.evaluate_candidate(req, cand_higher)
        assert eval_higher.parameter_evaluations["voltage_rating"].status == ParameterEvaluationStatus.SATISFIED.value

        cand_lower = {"nominal_value": 100.0, "voltage_rating": 16.0}
        eval_lower = BOMCompatibilityEngine.evaluate_candidate(req, cand_lower)
        assert eval_lower.parameter_evaluations["voltage_rating"].status == ParameterEvaluationStatus.CONFLICT.value
        assert eval_lower.overall_status == PartCompatibilityStatus.NOT_COMPATIBLE

    # 6. Power Rating Boundary
    def test_06_power_rating_boundary(self):
        req = {"nominal_value": 1000.0, "power_rating": 0.25}
        cand_higher = {"nominal_value": 1000.0, "power_rating": 0.5}
        eval_higher = BOMCompatibilityEngine.evaluate_candidate(req, cand_higher)
        assert eval_higher.parameter_evaluations["power_rating"].status == ParameterEvaluationStatus.SATISFIED.value

        cand_lower = {"nominal_value": 1000.0, "power_rating": 0.125}
        eval_lower = BOMCompatibilityEngine.evaluate_candidate(req, cand_lower)
        assert eval_lower.parameter_evaluations["power_rating"].status == ParameterEvaluationStatus.CONFLICT.value
        assert eval_lower.overall_status == PartCompatibilityStatus.NOT_COMPATIBLE

    # 7. Current Rating Boundary
    def test_07_current_rating_boundary(self):
        req = {"nominal_value": 10.0, "current_rating": 2.0}
        cand_higher = {"nominal_value": 10.0, "current_rating": 3.0}
        eval_higher = BOMCompatibilityEngine.evaluate_candidate(req, cand_higher)
        assert eval_higher.parameter_evaluations["current_rating"].status == ParameterEvaluationStatus.SATISFIED.value

        cand_lower = {"nominal_value": 10.0, "current_rating": 1.5}
        eval_lower = BOMCompatibilityEngine.evaluate_candidate(req, cand_lower)
        assert eval_lower.parameter_evaluations["current_rating"].status == ParameterEvaluationStatus.CONFLICT.value
        assert eval_lower.overall_status == PartCompatibilityStatus.NOT_COMPATIBLE

    # 8. Tolerance Tightening vs Loosening
    def test_08_tolerance_tightening_vs_loosening(self):
        req = {"nominal_value": 10000.0, "tolerance": 5.0}
        cand_tighter = {"nominal_value": 10000.0, "tolerance": 1.0}
        eval_tighter = BOMCompatibilityEngine.evaluate_candidate(req, cand_tighter)
        assert eval_tighter.parameter_evaluations["tolerance"].status == ParameterEvaluationStatus.SATISFIED.value

        cand_looser = {"nominal_value": 10000.0, "tolerance": 10.0}
        eval_looser = BOMCompatibilityEngine.evaluate_candidate(req, cand_looser)
        assert eval_looser.parameter_evaluations["tolerance"].status == ParameterEvaluationStatus.CONFLICT.value
        assert eval_looser.overall_status == PartCompatibilityStatus.NOT_COMPATIBLE

    # 9. Package Footprint Compatibility
    def test_09_package_footprint_compatibility(self):
        assert BOMPackageCompatibilityEngine.are_packages_compatible("0805", "R_0805_2012METRIC") is True
        assert BOMPackageCompatibilityEngine.are_packages_compatible("SOIC-8", "SOIC-8_3.9x4.9mm") is True
        assert BOMPackageCompatibilityEngine.are_packages_compatible("0805", "0402") is False
        assert BOMPackageCompatibilityEngine.are_packages_compatible("SOIC-8", "TSSOP-8") is False

    # 10. Pin Count Alone Does NOT Prove Compatibility
    def test_10_pin_count_alone_does_not_prove_compatibility(self):
        is_compat = BOMPackageCompatibilityEngine.are_packages_compatible(
            pkg_req="SOIC-8",
            pkg_cand="DFN-8",
            pins_req=8,
            pins_cand=8,
        )
        assert is_compat is False

    # 11. Temperature Range Compatibility
    def test_11_temperature_range_compatibility(self):
        req = {"nominal_value": 10.0, "temp_min_c": -40.0, "temp_max_c": 85.0}
        cand_wide = {"nominal_value": 10.0, "temp_min_c": -55.0, "temp_max_c": 125.0}
        eval_wide = BOMCompatibilityEngine.evaluate_candidate(req, cand_wide)
        assert eval_wide.parameter_evaluations["temperature_range"].status == ParameterEvaluationStatus.SATISFIED.value

        cand_narrow = {"nominal_value": 10.0, "temp_min_c": 0.0, "temp_max_c": 70.0}
        eval_narrow = BOMCompatibilityEngine.evaluate_candidate(req, cand_narrow)
        assert eval_narrow.parameter_evaluations["temperature_range"].status == ParameterEvaluationStatus.CONFLICT.value

    # 12. Missing Engineering Parameters Remain UNKNOWN
    def test_12_missing_engineering_parameters_remain_unknown(self):
        req = {"nominal_value": 10.0, "voltage_rating": 50.0}
        cand_missing_v = {"nominal_value": 10.0}
        eval_res = BOMCompatibilityEngine.evaluate_candidate(req, cand_missing_v)
        assert eval_res.parameter_evaluations["voltage_rating"].status == ParameterEvaluationStatus.UNKNOWN.value

    # 13. UNKNOWN != SATISFIED Invariant
    def test_13_unknown_does_not_equal_satisfied(self):
        req = {"nominal_value": 10.0, "voltage_rating": 50.0}
        cand_missing_v = {"nominal_value": 10.0}
        eval_res = BOMCompatibilityEngine.evaluate_candidate(req, cand_missing_v)
        assert eval_res.overall_status != PartCompatibilityStatus.ENGINEERING_COMPATIBLE
        assert eval_res.overall_status == PartCompatibilityStatus.PARTIALLY_EVALUATED

    # 14. Part Lifecycle Normalization
    def test_14_part_lifecycle_normalization(self):
        assert BOMSupplyIntelligenceEngine.normalize_lifecycle("Active") == PartLifecycleStatus.ACTIVE
        assert BOMSupplyIntelligenceEngine.normalize_lifecycle("Not Recommended for New Designs") == PartLifecycleStatus.NRND
        assert BOMSupplyIntelligenceEngine.normalize_lifecycle("EOL") == PartLifecycleStatus.EOL
        assert BOMSupplyIntelligenceEngine.normalize_lifecycle("Obsolete") == PartLifecycleStatus.OBSOLETE
        assert BOMSupplyIntelligenceEngine.normalize_lifecycle("UnknownString") == PartLifecycleStatus.UNKNOWN

    # 15. Temporal Stock Observations
    def test_15_temporal_stock_observations(self):
        obs = SupplySourceObservation(
            supplier="Digi-Key",
            supplier_pn="TEST-MPN",
            stock=1200,
            unit_price=0.45,
            currency="USD",
            observed_at="2026-10-08T10:00:00Z",
        )
        assert obs.supplier == "Digi-Key"
        assert obs.stock == 1200
        assert obs.observed_at == "2026-10-08T10:00:00Z"

    # 16. Multi-Source Stock Conflict
    def test_16_multi_source_stock_conflict(self):
        sources = [
            {"supplier": "DigiKey", "stock_quantity": 500, "unit_price": 0.5},
            {"supplier": "Mouser", "stock_quantity": 0, "unit_price": 0.52},
        ]
        res = BOMSupplyIntelligenceEngine.evaluate_supply_sources(sources)
        assert res["has_conflict"] is True
        assert res["availability_status"] == PartAvailabilityStatus.CONFLICTING.value

    # 17. Single/Consistent In-Stock
    def test_17_single_source_in_stock(self):
        sources = [
            {"supplier": "DigiKey", "stock_quantity": 500, "unit_price": 0.5},
            {"supplier": "Mouser", "stock_quantity": 1200, "unit_price": 0.48},
        ]
        res = BOMSupplyIntelligenceEngine.evaluate_supply_sources(sources)
        assert res["has_conflict"] is False
        assert res["availability_status"] == PartAvailabilityStatus.IN_STOCK.value

    # 18. No Stock Across All Sources
    def test_18_no_stock_across_sources(self):
        sources = [
            {"supplier": "DigiKey", "stock_quantity": 0, "unit_price": 0.5},
            {"supplier": "Mouser", "stock_quantity": 0, "unit_price": 0.52},
        ]
        res = BOMSupplyIntelligenceEngine.evaluate_supply_sources(sources)
        assert res["has_conflict"] is False
        assert res["availability_status"] == PartAvailabilityStatus.OUT_OF_STOCK.value

    # 19. Price Break Structure Preservation
    def test_19_price_break_structure_preservation(self):
        price_sources = [
            {"supplier": "Element14", "unit_price": 1.20, "qty_break": 1, "currency": "USD"},
            {"supplier": "Element14", "unit_price": 0.95, "qty_break": 10, "currency": "USD"},
            {"supplier": "Element14", "unit_price": 0.70, "qty_break": 100, "currency": "USD"},
        ]
        summary = BOMSupplyIntelligenceEngine.summarize_pricing_structure(price_sources)
        assert len(summary) == 3
        assert summary[2]["qty_break"] == 100
        assert summary[2]["unit_price"] == 0.70

    # 20. Zero Synthetic Scoring Invariant
    def test_20_zero_synthetic_scoring_invariant(self):
        req = {"nominal_value": 100.0}
        cand = {"nominal_value": 100.0}
        compat = BOMCompatibilityEngine.evaluate_candidate(req, cand)
        compat_dict = compat.model_dump()

        for forbidden in ["supply_score", "part_score", "winner", "rank", "score"]:
            assert forbidden not in compat_dict
            for eval_item in compat_dict.get("parameter_evaluations", {}).values():
                assert forbidden not in eval_item

    # 21. Substitution Proposal Creation & Deterministic Diff
    def test_21_substitution_proposal_creation(self):
        bom = EngineeringBOM(id="b1", project_id="p1", circuit_id="c1", circuit_version=1, version=1, status=BOMStatus.DRAFT.value, created_by="u1", name="BOM")
        line = EngineeringBOMLine(
            id="l1",
            bom_id="b1",
            reference_designator="R1",
            quantity=1,
            component_type="Resistor",
            design_value="10k",
            design_package="0805",
            engineering_requirements={"nominal_value": 10000.0, "power_rating": 0.125},
            manufacturer_part_number="OLD-MPN-1",
            manufacturer="OldMfr",
        )
        candidate = ComponentPartCandidate(
            id="c1",
            bom_line_id="l1",
            mpn="NEW-MPN-2",
            manufacturer="NewMfr",
            lifecycle_status=PartLifecycleStatus.ACTIVE.value,
            availability_status=PartAvailabilityStatus.IN_STOCK.value,
            compatibility_status=PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value,
            parameters={"nominal_value": 10000.0, "power_rating": 0.25},
            supply_sources=[{"supplier": "Mouser", "unit_price": 0.05, "stock": 5000}],
        )

        proposal = BOMSubstituteValidator.create_proposal(
            bom=bom,
            line=line,
            candidate=candidate,
            proposed_by="engineer-1",
            justification="Old part lead time too long",
        )

        assert proposal.target_line_id == "l1"
        assert proposal.candidate_id == "c1"
        assert proposal.base_bom_revision == 1
        assert "power_rating" in proposal.differences
        assert proposal.differences["power_rating"]["required"] == ">=0.125W"
        assert proposal.differences["power_rating"]["candidate"] == "0.25W"

    # 22. Stale BOM Revision Rejection
    def test_22_stale_bom_revision_rejection(self):
        bom = EngineeringBOM(id="b1", project_id="p1", circuit_id="c1", circuit_version=1, version=2, status=BOMStatus.DRAFT.value, created_by="u1", name="BOM")
        line = EngineeringBOMLine(id="l1", bom_id="b1", reference_designator="R1", design_value="10k", component_type="Resistor")
        cand = ComponentPartCandidate(id="c1", bom_line_id="l1", mpn="NEW", manufacturer="MFR")
        proposal = BOMSubstitutionProposal(
            id="p1",
            bom_id="b1",
            bom_line_id="l1",
            candidate_id="c1",
            proposed_mpn="NEW",
            proposed_manufacturer="MFR",
            rationale="Substitute",
            base_bom_revision=1,
            circuit_version=1,
            diff_preview={},
            created_by="u1",
            status=ProposalStatus.PROPOSED.value,
        )
        user = AuthenticatedUser(id="user-1", email="eng@corp.com", role="engineer", tenant_id="t1")

        with pytest.raises(HTTPException) as exc:
            BOMSubstituteValidator.validate_and_apply_approval(
                proposal=proposal, line=line, bom=bom, candidate=cand, user=user
            )
        assert exc.value.status_code == 409
        assert "STALE_BOM_REVISION" in str(exc.value.detail)

    # 23. Human Approval Boundary Success
    def test_23_human_approval_boundary_success(self):
        bom = EngineeringBOM(id="b1", project_id="p1", circuit_id="c1", circuit_version=1, version=1, status=BOMStatus.DRAFT.value, created_by="u1", name="BOM")
        line = EngineeringBOMLine(id="l1", bom_id="b1", reference_designator="R1", design_value="10k", component_type="Resistor", manufacturer_part_number="OLD", status=BOMLineStatus.SOURCED.value)
        cand = ComponentPartCandidate(
            id="c1", bom_line_id="l1", mpn="NEW", manufacturer="NewCo",
            compatibility_status=PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value
        )
        proposal = BOMSubstitutionProposal(
            id="p1",
            bom_id="b1",
            bom_line_id="l1",
            candidate_id="c1",
            proposed_mpn="NEW",
            proposed_manufacturer="NewCo",
            rationale="Sub",
            base_bom_revision=1,
            circuit_version=1,
            diff_preview={},
            created_by="u1",
            status=ProposalStatus.PROPOSED.value,
        )
        user = AuthenticatedUser(id="user-eng", email="eng@corp.com", role="engineer", tenant_id="t1")

        BOMSubstituteValidator.validate_and_apply_approval(
            proposal=proposal, line=line, bom=bom, candidate=cand, user=user
        )

        assert proposal.status == ProposalStatus.APPROVED.value
        assert proposal.approved_by == "user-eng"
        assert proposal.applied_at is not None
        assert line.manufacturer_part_number == "NEW"
        assert line.manufacturer == "NewCo"
        assert bom.version == 2

    # 24. AI Actor Rejection (AI_UNAUTHORIZED_SUBSTITUTION 403)
    def test_24_ai_substitution_rejection_forbidden(self):
        bom = EngineeringBOM(id="b1", project_id="p1", circuit_id="c1", circuit_version=1, version=1, status=BOMStatus.DRAFT.value, created_by="u1", name="BOM")
        line = EngineeringBOMLine(id="l1", bom_id="b1", reference_designator="R1", design_value="10k", component_type="Resistor")
        cand = ComponentPartCandidate(id="c1", bom_line_id="l1", mpn="NEW", manufacturer="MFR")
        proposal = BOMSubstitutionProposal(
            id="p1", bom_id="b1", bom_line_id="l1", candidate_id="c1",
            proposed_mpn="NEW", proposed_manufacturer="MFR", rationale="Sub",
            base_bom_revision=1, circuit_version=1, diff_preview={}, created_by="ai-bot",
            status=ProposalStatus.PROPOSED.value
        )

        ai_user = AuthenticatedUser(id="ai-agent-01", email="ai@bot.com", role="ai", tenant_id="t1")

        with pytest.raises(HTTPException) as exc:
            BOMSubstituteValidator.validate_and_apply_approval(
                proposal=proposal, line=line, bom=bom, candidate=cand, user=ai_user
            )
        assert exc.value.status_code == 403
        assert "AI_UNAUTHORIZED_SUBSTITUTION" in str(exc.value.detail)

    # 25. Autonomous Purchase Disabled Invariant
    def test_25_autonomous_purchase_disabled(self):
        for method_name in dir(bom_service):
            assert "purchase" not in method_name.lower()
            assert "buy" not in method_name.lower()
            assert "order" not in method_name.lower()
            assert "checkout" not in method_name.lower()

    # 26. BOM Canonical Snapshot Determinism
    def test_26_bom_canonical_snapshot_determinism(self):
        bom = EngineeringBOM(id="b1", project_id="p1", circuit_id="c1", circuit_version=1, version=1, status=BOMStatus.DRAFT.value, created_by="u1", name="BOM")
        l1 = EngineeringBOMLine(id="l1", bom_id="b1", reference_designator="R1", quantity=1, component_type="Resistor", design_value="10k")
        l2 = EngineeringBOMLine(id="l2", bom_id="b1", reference_designator="C1", quantity=1, component_type="Capacitor", design_value="100uF")

        bom.lines = [l1, l2]
        digest_1 = BOMSnapshotService.compute_bom_digest(bom)

        bom.lines = [l2, l1]
        digest_2 = BOMSnapshotService.compute_bom_digest(bom)

        assert digest_1 == digest_2
        assert len(digest_1) == 64

    # 27. BOM Snapshot Mutation Changes Digest
    def test_27_bom_snapshot_mutation_changes_digest(self):
        bom = EngineeringBOM(id="b1", project_id="p1", circuit_id="c1", circuit_version=1, version=1, status=BOMStatus.DRAFT.value, created_by="u1", name="BOM")
        l1 = EngineeringBOMLine(id="l1", bom_id="b1", reference_designator="R1", quantity=1, component_type="Resistor", design_value="10k")
        bom.lines = [l1]
        orig_digest = BOMSnapshotService.compute_bom_digest(bom)

        l1.design_value = "20k"
        mutated_digest = BOMSnapshotService.compute_bom_digest(bom)

        assert orig_digest != mutated_digest

    # 28. Multi-Tenant Isolation (BOM)
    @pytest.mark.asyncio
    async def test_28_multi_tenant_isolation_bom(self, async_client):
        from app.core.database import AsyncSessionLocal
        from app.core.security import create_access_token

        tenant_a = "tenant-bom-a"
        tenant_b = "tenant-bom-b"
        user_a = "user-bom-a"
        user_b = "user-bom-b"
        token_b = create_access_token(user_b, claims={"role": "engineer", "plan": "pro", "tenant_id": tenant_b})
        headers_b = {"Authorization": f"Bearer {token_b}"}

        async with AsyncSessionLocal() as db:
            p_a = Project(id=str(uuid.uuid4()), tenant_id=tenant_a, name="PA", owner_id=user_a, project_type=ProjectType.CIRCUIT.value, status=ProjectStatus.ACTIVE.value)
            c_a = Circuit(id=str(uuid.uuid4()), project_id=p_a.id, tenant_id=tenant_a, name="CA", created_by=user_a)
            bom_a = EngineeringBOM(id=str(uuid.uuid4()), project_id=p_a.id, circuit_id=c_a.id, circuit_version=1, tenant_id=tenant_a, version=1, status=BOMStatus.DRAFT.value, created_by=user_a, name="BOM_A")
            db.add_all([p_a, c_a, bom_a])
            await db.commit()
            bom_a_id = bom_a.id

        res = await async_client.get(f"/api/v1/boms/{bom_a_id}", headers=headers_b)
        assert res.status_code == 404

    # 29. Multi-Tenant Isolation (Substitution Proposal)
    @pytest.mark.asyncio
    async def test_29_multi_tenant_isolation_substitution(self, async_client):
        from app.core.database import AsyncSessionLocal
        from app.core.security import create_access_token

        tenant_a = "tenant-sub-a"
        tenant_b = "tenant-sub-b"
        user_a = "user-sub-a"
        user_b = "user-sub-b"
        token_b = create_access_token(user_b, claims={"role": "engineer", "plan": "pro", "tenant_id": tenant_b})
        headers_b = {"Authorization": f"Bearer {token_b}"}

        async with AsyncSessionLocal() as db:
            p_a = Project(id=str(uuid.uuid4()), tenant_id=tenant_a, name="PA_Sub", owner_id=user_a, project_type=ProjectType.CIRCUIT.value, status=ProjectStatus.ACTIVE.value)
            c_a = Circuit(id=str(uuid.uuid4()), project_id=p_a.id, tenant_id=tenant_a, name="CA_Sub", created_by=user_a)
            bom_a = EngineeringBOM(id=str(uuid.uuid4()), project_id=p_a.id, circuit_id=c_a.id, circuit_version=1, tenant_id=tenant_a, version=1, status=BOMStatus.DRAFT.value, created_by=user_a, name="BOM_A")
            l_a = EngineeringBOMLine(id=str(uuid.uuid4()), bom_id=bom_a.id, reference_designator="R1", design_value="10k", component_type="Resistor", manufacturer_part_number="OLD")
            cand_a = ComponentPartCandidate(id=str(uuid.uuid4()), bom_line_id=l_a.id, mpn="NEW", manufacturer="NewMfr")
            prop_a = BOMSubstitutionProposal(
                id=str(uuid.uuid4()),
                bom_id=bom_a.id,
                bom_line_id=l_a.id,
                candidate_id=cand_a.id,
                proposed_mpn="NEW",
                proposed_manufacturer="NewMfr",
                rationale="Cost",
                tenant_id=tenant_a,
                base_bom_revision=1,
                circuit_version=1,
                diff_preview={},
                created_by=user_a,
                status=ProposalStatus.PROPOSED.value,
            )
            db.add_all([p_a, c_a, bom_a, l_a, cand_a, prop_a])
            await db.commit()
            prop_a_id = prop_a.id

        res = await async_client.post(f"/api/v1/boms/substitutions/{prop_a_id}/approve", headers=headers_b)
        assert res.status_code == 403

    # 30. BOM Evaluation Orchestration
    @pytest.mark.asyncio
    async def test_30_bom_evaluation_orchestration(self):
        from app.core.database import AsyncSessionLocal

        tenant = "tenant-eval-test"
        user = AuthenticatedUser(id="user-eval", email="eval@test.com", role="engineer", tenant_id=tenant)

        async with AsyncSessionLocal() as db:
            p = Project(id=str(uuid.uuid4()), tenant_id=tenant, name="P_Eval", owner_id=user.id, project_type=ProjectType.CIRCUIT.value, status=ProjectStatus.ACTIVE.value)
            c = Circuit(id=str(uuid.uuid4()), project_id=p.id, tenant_id=tenant, name="C_Eval", created_by=user.id)
            bom = EngineeringBOM(id=str(uuid.uuid4()), project_id=p.id, circuit_id=c.id, circuit_version=1, tenant_id=tenant, version=1, status=BOMStatus.DRAFT.value, created_by=user.id, name="BOM_Eval")
            line = EngineeringBOMLine(
                id=str(uuid.uuid4()),
                bom_id=bom.id,
                reference_designator="C1",
                quantity=1,
                component_type="Capacitor",
                design_value="100uF",
                design_package="1206",
                engineering_requirements={"nominal_value": 0.0001, "voltage_rating": 25.0},
                status=BOMLineStatus.UNMATCHED.value,
            )
            cand1 = ComponentPartCandidate(
                id=str(uuid.uuid4()),
                bom_line_id=line.id,
                mpn="C1206C104K5RACAUTO",
                manufacturer="KEMET",
                parameters={"nominal_value": 0.0001, "voltage_rating": 50.0, "package": "1206"},
                supply_sources=[{"supplier": "Mouser", "stock": 2500, "unit_price": 0.12}],
                is_primary=True,
            )
            line.candidates = [cand1]
            bom.lines = [line]

            db.add_all([p, c, bom, line, cand1])
            await db.commit()

            evaluated_bom = await bom_service.evaluate_bom(db=db, bom_id=bom.id, current_user=user)
            assert evaluated_bom.lines[0].status == BOMLineStatus.SOURCED.value
            assert evaluated_bom.lines[0].candidates[0].compatibility_status == PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value
            assert evaluated_bom.lines[0].candidates[0].availability_status == PartAvailabilityStatus.IN_STOCK.value

    # 31. Adversarial Case A: Required Voltage = 24V, Candidate Voltage = NULL -> UNKNOWN, Never SATISFIED
    def test_31_adversarial_unknown_voltage_never_satisfied(self):
        req = {"voltage_rating": 24.0}
        cand = {"nominal_value": 10.0}  # No voltage
        res = BOMCompatibilityEngine.evaluate_candidate(req, cand)
        assert res.parameter_evaluations["voltage_rating"].status == ParameterEvaluationStatus.UNKNOWN.value
        assert res.overall_status != PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value
        assert res.overall_status in (PartCompatibilityStatus.UNKNOWN, PartCompatibilityStatus.PARTIALLY_EVALUATED)

    # 32. Adversarial Case B: Required Power = 1W, Candidate Power = NULL -> UNKNOWN, Never SATISFIED
    def test_32_adversarial_unknown_power_never_satisfied(self):
        req = {"power_rating": 1.0}
        cand = {"nominal_value": 100.0}  # No power
        res = BOMCompatibilityEngine.evaluate_candidate(req, cand)
        assert res.parameter_evaluations["power_rating"].status == ParameterEvaluationStatus.UNKNOWN.value
        assert res.overall_status != PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value
        assert res.overall_status in (PartCompatibilityStatus.UNKNOWN, PartCompatibilityStatus.PARTIALLY_EVALUATED)

    # 33. Adversarial Case C: Required Current = 2A, Candidate Current = NULL -> UNKNOWN, Never SATISFIED
    def test_33_adversarial_unknown_current_never_satisfied(self):
        req = {"current_rating": 2.0}
        cand = {"nominal_value": 1.0}  # No current
        res = BOMCompatibilityEngine.evaluate_candidate(req, cand)
        assert res.parameter_evaluations["current_rating"].status == ParameterEvaluationStatus.UNKNOWN.value
        assert res.overall_status != PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value
        assert res.overall_status in (PartCompatibilityStatus.UNKNOWN, PartCompatibilityStatus.PARTIALLY_EVALUATED)

    # 34. Adversarial Case D: One mandatory param satisfied, another missing -> overall != SATISFIED
    def test_34_adversarial_partial_mandatory_satisfaction_not_satisfied(self):
        req = {"nominal_value": 1000.0, "voltage_rating": 50.0, "power_rating": 0.5}
        cand = {"nominal_value": 1000.0, "voltage_rating": 100.0}  # Power rating is missing
        res = BOMCompatibilityEngine.evaluate_candidate(req, cand)
        assert res.parameter_evaluations["nominal_value"].status == ParameterEvaluationStatus.SATISFIED.value
        assert res.parameter_evaluations["voltage_rating"].status == ParameterEvaluationStatus.SATISFIED.value
        assert res.parameter_evaluations["power_rating"].status == ParameterEvaluationStatus.UNKNOWN.value
        # MUST NOT be declared ENGINEERING_COMPATIBLE
        assert res.overall_status != PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value
        assert res.overall_status == PartCompatibilityStatus.PARTIALLY_EVALUATED.value

    # 35. Package Adversarial Matrix
    def test_35_package_adversarial_matrix(self):
        P = BOMPackageCompatibilityEngine
        # Disallowed mismatches
        assert P.are_packages_compatible("0402", "0603") is False
        assert P.are_packages_compatible("0603", "0805") is False
        assert P.are_packages_compatible("0805", "1206") is False
        assert P.are_packages_compatible("SOIC-8", "TSSOP-8") is False
        assert P.are_packages_compatible("SOT-23", "SOT-23-6") is False
        # Allowed standard footprint family aliases
        assert P.are_packages_compatible("TO-220", "TO-220AB") is True
        assert P.are_packages_compatible("0805", "R_0805_2012METRIC") is True
        assert P.are_packages_compatible("SOIC-8", "SOIC-8_3.9X4.9MM") is True

    # 36. Supply-Chain Isolation Audit: Stock cannot upgrade UNKNOWN to SATISFIED
    def test_36_supply_chain_isolation_stock_does_not_upgrade_unknown(self):
        req = {"nominal_value": 10.0, "voltage_rating": 50.0}

        # Candidate A: compatibility is UNKNOWN (missing voltage), stock is huge (10000)
        cand_a_specs = {"nominal_value": 10.0}
        eval_a = BOMCompatibilityEngine.evaluate_candidate(req, cand_a_specs)
        sources_a = [{"supplier": "MegaDistributor", "stock": 10000, "unit_price": 0.01}]
        supply_a = BOMSupplyIntelligenceEngine.evaluate_supply_sources(sources_a)

        assert eval_a.overall_status == PartCompatibilityStatus.PARTIALLY_EVALUATED.value
        assert supply_a["availability_status"] == PartAvailabilityStatus.IN_STOCK.value
        # Invariant: Availability does NOT alter compatibility
        assert eval_a.overall_status != PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value

        # Candidate B: compatibility is SATISFIED (100V >= 50V), stock is ZERO (0)
        cand_b_specs = {"nominal_value": 10.0, "voltage_rating": 100.0}
        eval_b = BOMCompatibilityEngine.evaluate_candidate(req, cand_b_specs)
        sources_b = [{"supplier": "Mouser", "stock": 0, "unit_price": 0.05}]
        supply_b = BOMSupplyIntelligenceEngine.evaluate_supply_sources(sources_b)

        assert eval_b.overall_status == PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value
        assert supply_b["availability_status"] == PartAvailabilityStatus.OUT_OF_STOCK.value
        # Invariant: Zero stock does NOT invalidate technical compatibility
        assert eval_b.overall_status == PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value

    # 37. Authorization Forensics: AI Service Principals and non-human actors blocked (403)
    def test_37_authorization_ai_service_principal_rejection(self):
        bom = EngineeringBOM(id="b1", project_id="p1", circuit_id="c1", circuit_version=1, version=1, status=BOMStatus.DRAFT.value, created_by="u1", name="BOM")
        line = EngineeringBOMLine(id="l1", bom_id="b1", reference_designator="R1", design_value="10k", component_type="Resistor")
        cand = ComponentPartCandidate(id="c1", bom_line_id="l1", mpn="NEW", manufacturer="MFR")
        proposal = BOMSubstitutionProposal(
            id="p1", bom_id="b1", bom_line_id="l1", candidate_id="c1",
            proposed_mpn="NEW", proposed_manufacturer="MFR", rationale="Auto-sub",
            base_bom_revision=1, circuit_version=1, diff_preview={}, created_by="ai",
            status=ProposalStatus.PROPOSED.value
        )

        for ai_role, ai_id in [
            ("ai", "ai-agent-01"),
            ("service:ai", "svc-ai-evaluator"),
            ("model", "gpt-4-copilot"),
            ("ai_agent", "claude-subagent"),
        ]:
            user = AuthenticatedUser(id=ai_id, email=f"{ai_id}@ai.corp", role=ai_role, tenant_id="t1")
            with pytest.raises(HTTPException) as exc:
                BOMSubstituteValidator.validate_and_apply_approval(
                    proposal=proposal, line=line, bom=bom, candidate=cand, user=user
                )
            assert exc.value.status_code == 403
            assert "AI_UNAUTHORIZED_SUBSTITUTION" in str(exc.value.detail)

    # 38. Atomic Mutation and Rollback on Failure
    @pytest.mark.asyncio
    async def test_38_atomic_mutation_and_rollback_on_failure(self):
        from app.core.database import AsyncSessionLocal

        tenant = "tenant-rollback"
        user_ai = AuthenticatedUser(id="ai-agent-99", email="bot@test.com", role="ai", tenant_id=tenant)

        async with AsyncSessionLocal() as db:
            p = Project(id=str(uuid.uuid4()), tenant_id=tenant, name="P_Rollback", owner_id="u1", project_type=ProjectType.CIRCUIT.value, status=ProjectStatus.ACTIVE.value)
            c = Circuit(id=str(uuid.uuid4()), project_id=p.id, tenant_id=tenant, name="C_Rollback", created_by="u1")
            bom = EngineeringBOM(id=str(uuid.uuid4()), project_id=p.id, circuit_id=c.id, circuit_version=1, tenant_id=tenant, version=1, status=BOMStatus.DRAFT.value, created_by="u1", name="BOM_Rollback")
            line = EngineeringBOMLine(id=str(uuid.uuid4()), bom_id=bom.id, reference_designator="R1", design_value="10k", component_type="Resistor", manufacturer_part_number="ORIGINAL_MPN")
            cand = ComponentPartCandidate(id=str(uuid.uuid4()), bom_line_id=line.id, mpn="SUBSTITUTE_MPN", manufacturer="MFR")
            proposal = BOMSubstitutionProposal(
                id=str(uuid.uuid4()), bom_id=bom.id, bom_line_id=line.id, candidate_id=cand.id,
                proposed_mpn="SUBSTITUTE_MPN", proposed_manufacturer="MFR", rationale="Test",
                base_bom_revision=1, circuit_version=1, tenant_id=tenant, diff_preview={}, created_by="u1",
                status=ProposalStatus.PROPOSED.value
            )
            db.add_all([p, c, bom, line, cand, proposal])
            await db.commit()
            prop_id = proposal.id
            line_id = line.id

            # AI attempts to approve -> raises 403
            with pytest.raises(HTTPException):
                await bom_service.approve_substitution_proposal(db, prop_id, user_ai)

            # Verify line remains completely un-mutated in DB
            refreshed_line = await db.get(EngineeringBOMLine, line_id)
            assert refreshed_line.manufacturer_part_number == "ORIGINAL_MPN"

    # 39. Source Precedence: Authoritative Component Data > AI Context
    def test_39_source_precedence_authoritative_over_ai_context(self):
        # Authoritative component has 50V rating and 10k value
        c = Component(
            id="c1",
            circuit_id="circ1",
            ref_des="R1",
            component_type="Resistor",
            value=10.0,
            unit="kOhm",
            rating="50V 0.5W",
            tolerance="1%",
        )
        # Requirement extractor uses the authoritative component fields
        reqs = BOMRequirementExtractor.extract_requirements(c)
        assert reqs["nominal_value"] == 10000.0
        assert reqs["min_voltage_rating_v"] == 50.0
        assert reqs["min_power_rating_w"] == 0.5
        assert reqs["max_tolerance_percent"] == 1.0

    # 40. Stale Revision Atomic TOCTOU Protection
    def test_40_stale_revision_atomic_protection(self):
        bom = EngineeringBOM(id="b1", project_id="p1", circuit_id="c1", circuit_version=1, version=3, status=BOMStatus.DRAFT.value, created_by="u1", name="BOM")
        line = EngineeringBOMLine(id="l1", bom_id="b1", reference_designator="R1", design_value="10k", component_type="Resistor")
        cand = ComponentPartCandidate(id="c1", bom_line_id="l1", mpn="NEW", manufacturer="MFR")
        # Proposal created against revision 2, but BOM is at revision 3
        proposal = BOMSubstitutionProposal(
            id="p1", bom_id="b1", bom_line_id="l1", candidate_id="c1",
            proposed_mpn="NEW", proposed_manufacturer="MFR", rationale="Test",
            base_bom_revision=2, circuit_version=1, diff_preview={}, created_by="u1",
            status=ProposalStatus.PROPOSED.value
        )
        user = AuthenticatedUser(id="eng-1", email="eng@corp.com", role="engineer", tenant_id="t1")

        with pytest.raises(HTTPException) as exc:
            BOMSubstituteValidator.validate_and_apply_approval(
                proposal=proposal, line=line, bom=bom, candidate=cand, user=user
            )
        assert exc.value.status_code == 409
        assert "STALE_BOM_REVISION" in str(exc.value.detail)
        assert proposal.status == ProposalStatus.STALE.value
        assert bom.version == 3  # Not bumped

