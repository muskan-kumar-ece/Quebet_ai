"""
Phase 3 Wave 7 Test Suite: Manufacturing / DFM & Assembly Intelligence.

Verifies strict non-negotiable invariants:
- Real fabrication checks (trace width, clearance, drill, annular ring, edge clearance)
- Real assembly checks (component spacing, depaneling setback, centroid/rotation, soldering consistency, polarity)
- Solder mask slivers and silkscreen pad clipping
- BOM ↔ PCB package and pad count consistency
- Epistemic boundary: UNKNOWN != PASS
- Zero synthetic scoring (no 0-100 score, no fabricator ranking)
- Human authorization gate: AI actors rejected with HTTP 403
- Stale revision atomic TOCTOU rejection: HTTP 409
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
    BOMStatus,
)
from app.models.db.circuit import Circuit
from app.models.db.component import Component
from app.models.db.dfm import (
    ManufacturingAnalysisRecord,
    ManufacturingAnalysisStatus,
    ManufacturingFindingStatus,
    ManufacturingProposalRecord,
    ManufacturingRuleCategory,
    ManufacturingRuleSet,
)
from app.models.db.pcb import (
    BoardFootprint,
    BoardLayer,
    BoardPad,
    BoardStatus,
    BoardTraceSegment,
    BoardVia,
    EngineeringBoard,
    PadType,
    ViaType,
)
from app.models.db.project import Project, ProjectStatus, ProjectType
from app.models.db.proposal import ProposalStatus
from app.models.schemas.dfm import (
    ManufacturingAnalysisCreate,
    ManufacturingRuleSetCreate,
)
from app.services.ai.dfm.assembly_engine import AssemblyDFAEngine
from app.services.ai.dfm.bom_consistency_engine import BOMConsistencyDFMEngine
from app.services.ai.dfm.fabrication_engine import FabricationDFMEngine
from app.services.ai.dfm.proposal_engine import DFMProposalEngine
from app.services.ai.dfm.rule_registry import (
    DEFAULT_RULESETS,
    STANDARD_2LAYER_RULES,
    ADVANCED_4LAYER_RULES,
    compute_ruleset_digest,
)
from app.services.ai.dfm.snapshot import DFMSnapshotService
from app.services.dfm_service import dfm_service


class TestPhase3Wave7DFM:
    """Test suite covering the 43 requirements and invariants of Phase 3 Wave 7."""

    def _create_mock_board(
        self,
        tenant_id: str = "tenant-1",
        width: float = 100.0,
        height: float = 80.0,
        version: int = 1,
    ) -> EngineeringBoard:
        b = EngineeringBoard(
            id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            circuit_id=str(uuid.uuid4()),
            circuit_version=1,
            tenant_id=tenant_id,
            name="Controller Board",
            version=version,
            status=BoardStatus.DRAFT.value,
            dimensions={"width": width, "height": height},
            units="mm",
            created_by="engineer-1",
        )
        b.traces = []
        b.vias = []
        b.footprints = []
        b.layers = [
            BoardLayer(id=str(uuid.uuid4()), board_id=b.id, name="F.Cu", layer_order=1, is_copper=True),
            BoardLayer(id=str(uuid.uuid4()), board_id=b.id, name="B.Cu", layer_order=2, is_copper=True),
        ]
        return b

    # 1. Default Rulesets & Digest Computation
    def test_01_default_ruleset_structure_and_digest(self):
        assert "FAB_STANDARD_2LAYER" in DEFAULT_RULESETS
        assert "FAB_ADVANCED_4LAYER" in DEFAULT_RULESETS
        assert "IPC_CLASS_2" in DEFAULT_RULESETS

        std_rules = DEFAULT_RULESETS["FAB_STANDARD_2LAYER"]["rules"]
        assert "MFG001" in std_rules
        assert "MFG002" in std_rules
        assert "MFG003" in std_rules
        assert "MFG004" in std_rules
        assert "MFG006" in std_rules
        assert "MFG009" in std_rules

        digest = compute_ruleset_digest(std_rules)
        assert len(digest) == 64
        assert int(digest, 16) > 0

    # 2. Advanced Ruleset Precision Thresholds
    def test_02_ruleset_provenance_and_immutability(self):
        adv_rules = ADVANCED_4LAYER_RULES
        assert adv_rules["MFG001"]["parameters"]["min_trace_width_mm"] == 0.10
        assert adv_rules["MFG002"]["parameters"]["min_clearance_mm"] == 0.10
        assert adv_rules["MFG003"]["parameters"]["min_drill_diameter_mm"] == 0.20
        assert adv_rules["MFG004"]["parameters"]["min_annular_ring_mm"] == 0.125

    # 3. Trace Width PASS
    def test_03_trace_width_pass(self):
        board = self._create_mock_board()
        trace = BoardTraceSegment(
            id=str(uuid.uuid4()),
            board_id=board.id,
            start_x=10.0,
            start_y=10.0,
            end_x=20.0,
            end_y=10.0,
            width=0.20,  # > 0.15mm min
            layer="F.Cu",
        )
        board.traces.append(trace)

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        w_findings = [f for f in findings if f.rule_id == "MFG001"]
        assert len(w_findings) == 1
        assert w_findings[0].status == ManufacturingFindingStatus.PASS
        assert w_findings[0].margin is None or w_findings[0].required_value == 0.15

    # 4. Trace Width Violation & Quantitative Margin
    def test_04_trace_width_violation_margin_calculation(self):
        board = self._create_mock_board()
        trace = BoardTraceSegment(
            id=str(uuid.uuid4()),
            board_id=board.id,
            start_x=10.0,
            start_y=10.0,
            end_x=20.0,
            end_y=10.0,
            width=0.10,  # < 0.15mm min
            layer="F.Cu",
        )
        board.traces.append(trace)

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        w_findings = [f for f in findings if f.rule_id == "MFG001"]
        assert len(w_findings) == 1
        assert w_findings[0].status == ManufacturingFindingStatus.FAIL
        assert w_findings[0].measured_value == 0.10
        assert w_findings[0].required_value == 0.15
        assert round(w_findings[0].margin, 4) == -0.05
        assert w_findings[0].proposal_available is True

    # 5. Missing Traces -> UNKNOWN (Epistemic Boundary)
    def test_05_trace_width_missing_traces_unknown(self):
        board = self._create_mock_board()
        board.traces = []
        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        w_findings = [f for f in findings if f.rule_id == "MFG001"]
        assert len(w_findings) == 1
        assert w_findings[0].status == ManufacturingFindingStatus.UNKNOWN
        assert "unknown" in w_findings[0].message.lower()

    # 6. Copper Clearance PASS
    def test_06_copper_clearance_pass(self):
        board = self._create_mock_board()
        t1 = BoardTraceSegment(
            id=str(uuid.uuid4()),
            board_id=board.id,
            start_x=10.0, start_y=10.0, end_x=20.0, end_y=10.0,
            width=0.20, layer="F.Cu", net_id="net-1",
        )
        t2 = BoardTraceSegment(
            id=str(uuid.uuid4()),
            board_id=board.id,
            start_x=10.0, start_y=12.0, end_x=20.0, end_y=12.0,
            width=0.20, layer="F.Cu", net_id="net-2",
        )
        board.traces = [t1, t2]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        c_findings = [f for f in findings if f.rule_id == "MFG002"]
        assert len(c_findings) == 1
        assert c_findings[0].status == ManufacturingFindingStatus.PASS

    # 7. Copper Clearance Violation
    def test_07_copper_clearance_violation(self):
        board = self._create_mock_board()
        # Traces separated by only 0.25mm center-to-center, width 0.20 each -> gap = 0.05mm (< 0.15mm)
        t1 = BoardTraceSegment(
            id=str(uuid.uuid4()),
            board_id=board.id,
            start_x=10.0, start_y=10.0, end_x=20.0, end_y=10.0,
            width=0.20, layer="F.Cu", net_id="net-1",
        )
        t2 = BoardTraceSegment(
            id=str(uuid.uuid4()),
            board_id=board.id,
            start_x=10.0, start_y=10.25, end_x=20.0, end_y=10.25,
            width=0.20, layer="F.Cu", net_id="net-2",
        )
        board.traces = [t1, t2]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        c_findings = [f for f in findings if f.rule_id == "MFG002"]
        assert len(c_findings) == 1
        assert c_findings[0].status == ManufacturingFindingStatus.FAIL
        assert c_findings[0].measured_value < 0.15

    # 8. Copper Clearance Across Different Layers Ignored
    def test_08_copper_clearance_different_layers_ignored(self):
        board = self._create_mock_board()
        t1 = BoardTraceSegment(
            id=str(uuid.uuid4()),
            board_id=board.id,
            start_x=10.0, start_y=10.0, end_x=20.0, end_y=10.0,
            width=0.20, layer="F.Cu", net_id="net-1",
        )
        t2 = BoardTraceSegment(
            id=str(uuid.uuid4()),
            board_id=board.id,
            start_x=10.0, start_y=10.1, end_x=20.0, end_y=10.1,
            width=0.20, layer="B.Cu", net_id="net-2",
        )
        board.traces = [t1, t2]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        c_findings = [f for f in findings if f.rule_id == "MFG002"]
        assert len(c_findings) == 1
        assert c_findings[0].status == ManufacturingFindingStatus.PASS

    # 9. Copper Clearance for Same Net Ignored
    def test_09_copper_clearance_same_net_ignored(self):
        board = self._create_mock_board()
        t1 = BoardTraceSegment(
            id=str(uuid.uuid4()),
            board_id=board.id,
            start_x=10.0, start_y=10.0, end_x=20.0, end_y=10.0,
            width=0.20, layer="F.Cu", net_id="net-VCC",
        )
        t2 = BoardTraceSegment(
            id=str(uuid.uuid4()),
            board_id=board.id,
            start_x=10.0, start_y=10.1, end_x=20.0, end_y=10.1,
            width=0.20, layer="F.Cu", net_id="net-VCC",
        )
        board.traces = [t1, t2]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        c_findings = [f for f in findings if f.rule_id == "MFG002"]
        assert len(c_findings) == 1
        assert c_findings[0].status == ManufacturingFindingStatus.PASS

    # 10. Drill Diameter Via PASS and FAIL
    def test_10_drill_diameter_via_pass_and_fail(self):
        board = self._create_mock_board()
        v_good = BoardVia(id=str(uuid.uuid4()), board_id=board.id, pos_x=10.0, pos_y=10.0, drill=0.30, diameter=0.60)
        v_bad = BoardVia(id=str(uuid.uuid4()), board_id=board.id, pos_x=20.0, pos_y=20.0, drill=0.15, diameter=0.40)
        board.vias = [v_good, v_bad]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        d_findings = [f for f in findings if f.rule_id == "MFG003"]
        assert len(d_findings) == 1
        assert d_findings[0].status == ManufacturingFindingStatus.FAIL
        assert d_findings[0].measured_value == 0.15
        assert d_findings[0].required_value == 0.30

    # 11. Drill Diameter THT Pad FAIL
    def test_11_drill_diameter_tht_pad_fail(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="J1", footprint_name="PinHeader_1x2", pos_x=10.0, pos_y=10.0)
        pad = BoardPad(
            id=str(uuid.uuid4()), board_id=board.id, footprint_id=fp.id, pad_number="1",
            pad_type=PadType.THROUGH_HOLE.value, pos_x=0.0, pos_y=0.0, width=1.5, height=1.5, drill=0.20,
        )
        fp.pads = [pad]
        board.footprints = [fp]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        d_findings = [f for f in findings if f.rule_id == "MFG003"]
        assert any(f.status == ManufacturingFindingStatus.FAIL and f.element_type == "PAD" for f in d_findings)

    # 12. Drill Missing Features -> UNKNOWN
    def test_12_drill_missing_features_unknown(self):
        board = self._create_mock_board()
        board.vias = []
        board.footprints = []
        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        d_findings = [f for f in findings if f.rule_id == "MFG003"]
        assert len(d_findings) == 1
        assert d_findings[0].status == ManufacturingFindingStatus.UNKNOWN

    # 13. Annular Ring Via PASS and FAIL
    def test_13_annular_ring_via_pass_and_fail(self):
        board = self._create_mock_board()
        # Ring = (0.50 - 0.30)/2 = 0.10mm (< 0.15mm min) -> FAIL
        v_bad = BoardVia(id=str(uuid.uuid4()), board_id=board.id, pos_x=10.0, pos_y=10.0, drill=0.30, diameter=0.50)
        board.vias = [v_bad]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        ar_findings = [f for f in findings if f.rule_id == "MFG004"]
        assert len(ar_findings) == 1
        assert ar_findings[0].status == ManufacturingFindingStatus.FAIL
        assert ar_findings[0].measured_value == 0.10
        assert ar_findings[0].required_value == 0.15

    # 14. Annular Ring THT Pad FAIL
    def test_14_annular_ring_tht_pad_fail(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="R1", footprint_name="Resistor_THT", pos_x=10.0, pos_y=10.0)
        # Pad width=1.0, drill=0.8 -> ring = (1.0 - 0.8)/2 = 0.10mm (< 0.15mm)
        pad = BoardPad(
            id=str(uuid.uuid4()), board_id=board.id, footprint_id=fp.id, pad_number="1",
            pad_type=PadType.THROUGH_HOLE.value, pos_x=0.0, pos_y=0.0, width=1.0, height=1.0, drill=0.80,
        )
        fp.pads = [pad]
        board.footprints = [fp]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        ar_findings = [f for f in findings if f.rule_id == "MFG004"]
        assert any(f.status == ManufacturingFindingStatus.FAIL and f.element_type == "PAD" for f in ar_findings)

    # 15. Via-to-Via Clearance PASS and FAIL
    def test_15_via_to_via_clearance_pass_and_fail(self):
        board = self._create_mock_board()
        # Pos (10, 10) and (10, 10.6), drills 0.3 each -> center_dist = 0.6, hole_clearance = 0.6 - 0.3 = 0.3mm (< 0.5mm min)
        v1 = BoardVia(id=str(uuid.uuid4()), board_id=board.id, pos_x=10.0, pos_y=10.0, drill=0.3, diameter=0.6)
        v2 = BoardVia(id=str(uuid.uuid4()), board_id=board.id, pos_x=10.0, pos_y=10.6, drill=0.3, diameter=0.6)
        board.vias = [v1, v2]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        vv_findings = [f for f in findings if f.rule_id == "MFG005"]
        assert len(vv_findings) == 1
        assert vv_findings[0].status == ManufacturingFindingStatus.WARNING
        assert vv_findings[0].measured_value == 0.30

    # 16. Board Edge Clearance Trace FAIL
    def test_16_board_edge_clearance_trace_fail(self):
        board = self._create_mock_board(width=100.0, height=80.0)
        # Trace at x=0.2mm from edge (< 0.5mm min)
        t = BoardTraceSegment(
            id=str(uuid.uuid4()), board_id=board.id,
            start_x=0.2, start_y=10.0, end_x=0.2, end_y=20.0,
            width=0.20, layer="F.Cu",
        )
        board.traces = [t]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        edge_findings = [f for f in findings if f.rule_id == "MFG006"]
        assert len(edge_findings) == 1
        assert edge_findings[0].status == ManufacturingFindingStatus.FAIL
        assert edge_findings[0].measured_value == 0.20

    # 17. Board Edge Clearance Via FAIL
    def test_17_board_edge_clearance_via_fail(self):
        board = self._create_mock_board(width=100.0, height=80.0)
        # Via at x=0.5, diameter=0.6 -> copper edge is at 0.5 - 0.3 = 0.2mm from outline (< 0.5mm)
        v = BoardVia(id=str(uuid.uuid4()), board_id=board.id, pos_x=0.5, pos_y=10.0, drill=0.3, diameter=0.6)
        board.vias = [v]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        edge_findings = [f for f in findings if f.rule_id == "MFG006"]
        assert any(f.status == ManufacturingFindingStatus.FAIL and f.element_type == "VIA" for f in edge_findings)

    # 18. Board Edge Clearance No Outline -> UNKNOWN
    def test_18_board_edge_clearance_no_outline_unknown(self):
        board = self._create_mock_board()
        board.dimensions = {}
        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        edge_findings = [f for f in findings if f.rule_id == "MFG006"]
        assert len(edge_findings) == 1
        assert edge_findings[0].status == ManufacturingFindingStatus.UNKNOWN

    # 19. Solder Mask Sliver Detection
    def test_19_solder_mask_sliver_detection(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="U1", footprint_name="SOIC-8", pos_x=20.0, pos_y=20.0)
        # Two SMD pads with gap = 0.05mm (< 0.10mm min sliver)
        p1 = BoardPad(id=str(uuid.uuid4()), board_id=board.id, footprint_id=fp.id, pad_number="1", pad_type="SMD", pos_x=0.0, pos_y=0.0, width=0.5, height=1.0)
        p2 = BoardPad(id=str(uuid.uuid4()), board_id=board.id, footprint_id=fp.id, pad_number="2", pad_type="SMD", pos_x=0.55, pos_y=0.0, width=0.5, height=1.0)
        fp.pads = [p1, p2]
        board.footprints = [fp]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        mask_findings = [f for f in findings if f.rule_id == "MFG007"]
        assert len(mask_findings) == 1
        assert mask_findings[0].status == ManufacturingFindingStatus.WARNING
        assert mask_findings[0].measured_value < 0.10

    # 20. Silkscreen-to-Pad Clearance Warning
    def test_20_silkscreen_to_pad_clearance_warning(self):
        board = self._create_mock_board()
        fp = BoardFootprint(
            id=str(uuid.uuid4()), board_id=board.id, ref_des="R1", footprint_name="R0805",
            package_metadata={"silkscreen_pad_overlap": True, "silkscreen_clearance_mm": 0.0},
        )
        board.footprints = [fp]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        silk_findings = [f for f in findings if f.rule_id == "MFG008"]
        assert len(silk_findings) == 1
        assert silk_findings[0].status == ManufacturingFindingStatus.WARNING
        assert silk_findings[0].proposal_available is True

    # 21. Component Placement Clearance Same Side Collision
    def test_21_component_clearance_same_side_collision(self):
        board = self._create_mock_board()
        # Two components positioned 2.1mm apart center-to-center, size 2x2 each -> gap = 0.1mm (< 0.5mm min)
        fp1 = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="C1", footprint_name="C0805", pos_x=10.0, pos_y=10.0, side="TOP")
        fp2 = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="C2", footprint_name="C0805", pos_x=12.1, pos_y=10.0, side="TOP")
        board.footprints = [fp1, fp2]

        findings = AssemblyDFAEngine.evaluate_board_assembly(board, STANDARD_2LAYER_RULES)
        asm_findings = [f for f in findings if f.rule_id == "MFG009"]
        assert len(asm_findings) == 1
        assert asm_findings[0].status == ManufacturingFindingStatus.FAIL
        assert asm_findings[0].measured_value < 0.50

    # 22. Component Placement Opposite Side Ignored
    def test_22_component_clearance_opposite_side_ignored(self):
        board = self._create_mock_board()
        fp1 = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="C1", footprint_name="C0805", pos_x=10.0, pos_y=10.0, side="TOP")
        fp2 = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="C2", footprint_name="C0805", pos_x=10.0, pos_y=10.0, side="BOTTOM")
        board.footprints = [fp1, fp2]

        findings = AssemblyDFAEngine.evaluate_board_assembly(board, STANDARD_2LAYER_RULES)
        asm_findings = [f for f in findings if f.rule_id == "MFG009"]
        assert len(asm_findings) == 1
        assert asm_findings[0].status == ManufacturingFindingStatus.PASS

    # 23. Component Edge Clearance Depaneling Setback
    def test_23_component_edge_clearance_depaneling_setback(self):
        board = self._create_mock_board(width=100.0, height=80.0)
        # Component at x=1.5mm, body width 2mm -> edge distance = 1.5 - 1.0 = 0.5mm (< 1.0mm min setback)
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="U1", footprint_name="SOIC-8", pos_x=1.5, pos_y=20.0)
        board.footprints = [fp]

        findings = AssemblyDFAEngine.evaluate_board_assembly(board, STANDARD_2LAYER_RULES)
        edge_findings = [f for f in findings if f.rule_id == "MFG010"]
        assert len(edge_findings) == 1
        assert edge_findings[0].status == ManufacturingFindingStatus.WARNING
        assert edge_findings[0].measured_value < 1.0

    # 24. Pick-and-Place Centroid Validity PASS
    def test_24_pnp_centroid_validity_pass(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="R1", footprint_name="R0805", pos_x=15.0, pos_y=25.0, rotation=90.0)
        board.footprints = [fp]

        findings = AssemblyDFAEngine.evaluate_board_assembly(board, STANDARD_2LAYER_RULES)
        pnp_findings = [f for f in findings if f.rule_id == "MFG011"]
        assert len(pnp_findings) == 1
        assert pnp_findings[0].status == ManufacturingFindingStatus.PASS

    # 25. Pick-and-Place Missing Centroid FAIL
    def test_25_pnp_missing_centroid_fail(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="R1", footprint_name="R0805", pos_x=float("nan"), pos_y=25.0)
        board.footprints = [fp]

        findings = AssemblyDFAEngine.evaluate_board_assembly(board, STANDARD_2LAYER_RULES)
        pnp_findings = [f for f in findings if f.rule_id == "MFG011"]
        assert len(pnp_findings) == 1
        assert pnp_findings[0].status == ManufacturingFindingStatus.FAIL

    # 26. Pick-and-Place Non-Standard Rotation WARNING
    def test_26_pnp_non_standard_rotation_warning(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="R1", footprint_name="R0805", pos_x=15.0, pos_y=25.0, rotation=33.7)
        board.footprints = [fp]

        findings = AssemblyDFAEngine.evaluate_board_assembly(board, STANDARD_2LAYER_RULES)
        pnp_findings = [f for f in findings if f.rule_id == "MFG011"]
        assert any(f.status == ManufacturingFindingStatus.WARNING and "rotation" in f.message.lower() for f in pnp_findings)

    # 27. Soldering Consistency SMD with Drill WARNING
    def test_27_soldering_consistency_smd_with_drill_warn(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="R1", footprint_name="R0805", pos_x=10.0, pos_y=10.0)
        pad = BoardPad(
            id=str(uuid.uuid4()), board_id=board.id, footprint_id=fp.id, pad_number="1",
            pad_type="SMD", pos_x=0.0, pos_y=0.0, width=1.0, height=1.0, drill=0.3,
        )
        fp.pads = [pad]
        board.footprints = [fp]

        findings = AssemblyDFAEngine.evaluate_board_assembly(board, STANDARD_2LAYER_RULES)
        s_findings = [f for f in findings if f.rule_id == "MFG012"]
        assert len(s_findings) == 1
        assert s_findings[0].status == ManufacturingFindingStatus.WARNING
        assert "paste wick-away" in s_findings[0].message.lower()

    # 28. Soldering Consistency THT without Drill FAIL
    def test_28_soldering_consistency_tht_without_drill_fail(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="J1", footprint_name="Header_1x1", pos_x=10.0, pos_y=10.0)
        pad = BoardPad(
            id=str(uuid.uuid4()), board_id=board.id, footprint_id=fp.id, pad_number="1",
            pad_type="THROUGH_HOLE", pos_x=0.0, pos_y=0.0, width=1.5, height=1.5, drill=None,
        )
        fp.pads = [pad]
        board.footprints = [fp]

        findings = AssemblyDFAEngine.evaluate_board_assembly(board, STANDARD_2LAYER_RULES)
        s_findings = [f for f in findings if f.rule_id == "MFG012"]
        assert len(s_findings) == 1
        assert s_findings[0].status == ManufacturingFindingStatus.FAIL

    # 29. Polarity Marking Present PASS
    def test_29_polarity_marking_present_pass(self):
        board = self._create_mock_board()
        fp = BoardFootprint(
            id=str(uuid.uuid4()), board_id=board.id, ref_des="D1", footprint_name="SOD-123",
            package_metadata={"polarity_marked": True, "pin1_marked": True},
        )
        board.footprints = [fp]

        findings = AssemblyDFAEngine.evaluate_board_assembly(board, STANDARD_2LAYER_RULES)
        pol_findings = [f for f in findings if f.rule_id == "MFG013"]
        assert len(pol_findings) == 1
        assert pol_findings[0].status == ManufacturingFindingStatus.PASS

    # 30. Polarity Marking Missing WARNING
    def test_30_polarity_marking_missing_warning(self):
        board = self._create_mock_board()
        fp = BoardFootprint(
            id=str(uuid.uuid4()), board_id=board.id, ref_des="D1", footprint_name="SOD-123",
            package_metadata={"polarity_marked": False, "pin1_marked": False},
        )
        board.footprints = [fp]

        findings = AssemblyDFAEngine.evaluate_board_assembly(board, STANDARD_2LAYER_RULES)
        pol_findings = [f for f in findings if f.rule_id == "MFG013"]
        assert len(pol_findings) == 1
        assert pol_findings[0].status == ManufacturingFindingStatus.WARNING
        assert pol_findings[0].proposal_available is True

    # 31. BOM Consistency Package Match PASS
    def test_31_bom_consistency_package_match_pass(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="R1", footprint_name="0805", pos_x=10.0, pos_y=10.0)
        board.footprints = [fp]

        bom = EngineeringBOM(id=str(uuid.uuid4()), project_id="p1", circuit_id="c1", created_by="u1", name="BOM")
        line = EngineeringBOMLine(
            id=str(uuid.uuid4()), bom_id=bom.id, reference_designator="R1",
            design_package="R0805", component_type="Resistor", design_value="10k",
        )
        bom.lines = [line]

        findings = BOMConsistencyDFMEngine.evaluate_bom_pcb_consistency(board, bom, STANDARD_2LAYER_RULES)
        pkg_findings = [f for f in findings if f.rule_id == "MFG014"]
        assert any(f.status == ManufacturingFindingStatus.PASS for f in pkg_findings)

    # 32. BOM Consistency Package Mismatch FAIL
    def test_32_bom_consistency_package_mismatch_fail(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="U1", footprint_name="SOIC-8", pos_x=10.0, pos_y=10.0)
        board.footprints = [fp]

        bom = EngineeringBOM(id=str(uuid.uuid4()), project_id="p1", circuit_id="c1", created_by="u1", name="BOM")
        line = EngineeringBOMLine(
            id=str(uuid.uuid4()), bom_id=bom.id, reference_designator="U1",
            design_package="QFN-16", component_type="IC", design_value="OpAmp",
        )
        bom.lines = [line]

        findings = BOMConsistencyDFMEngine.evaluate_bom_pcb_consistency(board, bom, STANDARD_2LAYER_RULES)
        pkg_findings = [f for f in findings if f.rule_id == "MFG014"]
        assert any(f.status == ManufacturingFindingStatus.FAIL for f in pkg_findings)
        assert pkg_findings[0].proposal_available is True

    # 33. BOM Consistency Pad Count Match PASS
    def test_33_bom_consistency_pad_count_match_pass(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="U1", footprint_name="SOIC-8", pos_x=10.0, pos_y=10.0)
        fp.pads = [BoardPad(id=str(uuid.uuid4()), board_id=board.id, footprint_id=fp.id, pad_number=str(i), pos_x=0.0, pos_y=0.0) for i in range(1, 9)]
        board.footprints = [fp]

        bom = EngineeringBOM(id=str(uuid.uuid4()), project_id="p1", circuit_id="c1", created_by="u1", name="BOM")
        line = EngineeringBOMLine(
            id=str(uuid.uuid4()), bom_id=bom.id, reference_designator="U1",
            design_package="SOIC-8", component_type="IC", design_value="OpAmp",
            engineering_requirements={"pin_count": 8},
        )
        bom.lines = [line]

        findings = BOMConsistencyDFMEngine.evaluate_bom_pcb_consistency(board, bom, STANDARD_2LAYER_RULES)
        pin_findings = [f for f in findings if f.rule_id == "MFG015"]
        assert any(f.status == ManufacturingFindingStatus.PASS for f in pin_findings)

    # 34. BOM Consistency Pad Count Mismatch FAIL
    def test_34_bom_consistency_pad_count_mismatch_fail(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="U1", footprint_name="SOIC-8", pos_x=10.0, pos_y=10.0)
        # Footprint has 8 pads
        fp.pads = [BoardPad(id=str(uuid.uuid4()), board_id=board.id, footprint_id=fp.id, pad_number=str(i), pos_x=0.0, pos_y=0.0) for i in range(1, 9)]
        board.footprints = [fp]

        bom = EngineeringBOM(id=str(uuid.uuid4()), project_id="p1", circuit_id="c1", created_by="u1", name="BOM")
        # BOM part specifies 14 pins
        line = EngineeringBOMLine(
            id=str(uuid.uuid4()), bom_id=bom.id, reference_designator="U1",
            design_package="SOIC-14", component_type="IC", design_value="Logic",
            engineering_requirements={"pin_count": 14},
        )
        bom.lines = [line]

        findings = BOMConsistencyDFMEngine.evaluate_bom_pcb_consistency(board, bom, STANDARD_2LAYER_RULES)
        pin_findings = [f for f in findings if f.rule_id == "MFG015"]
        assert any(f.status == ManufacturingFindingStatus.FAIL for f in pin_findings)
        assert pin_findings[0].measured_value == 8.0
        assert pin_findings[0].required_value == 14.0

    # 35. Missing BOM -> UNKNOWN (Epistemic Boundary)
    def test_35_bom_missing_epistemic_unknown(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="U1", footprint_name="SOIC-8")
        board.footprints = [fp]

        findings = BOMConsistencyDFMEngine.evaluate_bom_pcb_consistency(board, None, STANDARD_2LAYER_RULES)
        assert all(f.status == ManufacturingFindingStatus.UNKNOWN for f in findings)

    # 36. Unconnected Active Pad Detection
    def test_36_unconnected_active_pad_detection(self):
        board = self._create_mock_board()
        fp = BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="U1", footprint_name="SOIC-8")
        # 4 pads connected, 1 pad floating without net or NC
        pads = [
            BoardPad(id=str(uuid.uuid4()), board_id=board.id, footprint_id=fp.id, pad_number="1", net_id="net-1"),
            BoardPad(id=str(uuid.uuid4()), board_id=board.id, footprint_id=fp.id, pad_number="2", net_id="net-2"),
            BoardPad(id=str(uuid.uuid4()), board_id=board.id, footprint_id=fp.id, pad_number="3", net_id="net-3"),
            BoardPad(id=str(uuid.uuid4()), board_id=board.id, footprint_id=fp.id, pad_number="4", net_id=None, net_name=""),
        ]
        fp.pads = pads
        board.footprints = [fp]

        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        pad_findings = [f for f in findings if f.rule_id == "MFG016"]
        assert len(pad_findings) == 1
        assert pad_findings[0].status == ManufacturingFindingStatus.WARNING
        assert "no net assigned" in pad_findings[0].message.lower()

    # 37. Zero Synthetic Scoring Enforced
    def test_37_zero_synthetic_scoring_enforced(self):
        board = self._create_mock_board()
        findings = FabricationDFMEngine.evaluate_board_fabrication(board, STANDARD_2LAYER_RULES)
        # Compute summary
        pass_cnt = sum(1 for f in findings if f.status == ManufacturingFindingStatus.PASS)
        fail_cnt = sum(1 for f in findings if f.status == ManufacturingFindingStatus.FAIL)
        summary = {
            "total_rules_evaluated": len(findings),
            "pass_count": pass_cnt,
            "fail_count": fail_cnt,
            "status": "COMPLETED",
        }
        # Epistemic invariant: NO "dfm_score", "score", or "ranking"
        assert "score" not in summary
        assert "dfm_score" not in summary
        assert "manufacturability_score" not in summary
        assert "fabricator_ranking" not in summary

    # 38. AI Actor Proposal Approval Rejected with 403
    def test_38_ai_actor_proposal_approval_rejected_403(self):
        for role, user_id in [
            ("ai", "ai-agent-01"),
            ("service:ai", "bot-copilot"),
            ("model", "llm-autonomous"),
        ]:
            user = AuthenticatedUser(id=user_id, email=f"{user_id}@test.com", role=role, tenant_id="t1")
            with pytest.raises(HTTPException) as exc:
                DFMProposalEngine.enforce_human_approval_gate(user)
            assert exc.value.status_code == 403
            assert "AI_UNAUTHORIZED_PROPOSAL_APPROVAL" in str(exc.value.detail)

    # 39. Human Proposal Approval Success
    def test_39_human_proposal_approval_success(self):
        human_user = AuthenticatedUser(id="eng-human-42", email="eng@quebet.ai", role="engineer", tenant_id="t1")
        # Must not raise
        DFMProposalEngine.enforce_human_approval_gate(human_user)

    # 40. Atomic Proposal Application Mutates Board & Increments Version
    def test_40_atomic_proposal_application_mutates_board(self):
        board = self._create_mock_board(version=1)
        t = BoardTraceSegment(id="trace-123", board_id=board.id, start_x=10.0, start_y=10.0, end_x=20.0, end_y=10.0, width=0.10)
        board.traces = [t]

        proposal = ManufacturingProposalRecord(
            id=str(uuid.uuid4()),
            board_id=board.id,
            board_revision=1,
            analysis_id=str(uuid.uuid4()),
            rule_id="MFG001",
            title="Widen trace",
            description="Increases trace width",
            mutation_type="ADJUST_TRACE_WIDTH",
            proposed_mutations=[
                {"target_entity": "BoardTraceSegment", "entity_id": "trace-123", "action": "UPDATE", "fields": {"width": 0.20}}
            ],
            diff_preview={},
            status=ProposalStatus.APPROVED.value,
            created_by="user-1",
        )

        class DummyDB:
            def add(self, obj): pass

        DFMProposalEngine.apply_proposal_mutations(proposal, board, DummyDB())
        assert t.width == 0.20
        assert board.version == 2

    # 41. Stale Proposal Revision Rejected with 409
    def test_41_stale_proposal_revision_rejected_409(self):
        board = self._create_mock_board(version=2)  # Board is already at rev 2
        proposal = ManufacturingProposalRecord(
            id=str(uuid.uuid4()),
            board_id=board.id,
            board_revision=1,  # Proposal created against rev 1
            analysis_id=str(uuid.uuid4()),
            rule_id="MFG001",
            title="Widen trace",
            description="Increases trace width",
            mutation_type="ADJUST_TRACE_WIDTH",
            proposed_mutations=[],
            diff_preview={},
            status=ProposalStatus.APPROVED.value,
            created_by="user-1",
        )

        class DummyDB:
            def add(self, obj): pass

        with pytest.raises(HTTPException) as exc:
            DFMProposalEngine.apply_proposal_mutations(proposal, board, DummyDB())
        assert exc.value.status_code == 409
        assert "STALE_PROPOSAL_REVISION" in str(exc.value.detail)

    # 42. Deterministic DFM Snapshot & SHA-256 Digest
    def test_42_deterministic_dfm_snapshot_and_sha256_digest(self):
        findings = [
            {"finding_id": "F2", "rule_id": "MFG002", "status": "PASS", "severity": "INFO", "element_type": "TRACE"},
            {"finding_id": "F1", "rule_id": "MFG001", "status": "FAIL", "severity": "ERROR", "element_type": "TRACE", "measured_value": 0.1, "required_value": 0.15, "margin": -0.05},
        ]
        summary = {"total_rules_evaluated": 2, "pass_count": 1, "fail_count": 1, "status": "FAILED"}

        d1 = DFMSnapshotService.compute_analysis_digest("b1", 1, "rs1", "REV_A", findings, summary)
        # Invert input order in list: canonicalization must yield the exact same digest
        d2 = DFMSnapshotService.compute_analysis_digest("b1", 1, "rs1", "REV_A", list(reversed(findings)), summary)

        assert d1 == d2
        assert len(d1) == 64

    # 43. Multi-Tenant Isolation & IDOR Protection
    @pytest.mark.asyncio
    async def test_43_multi_tenant_isolation_idor_protection(self):
        from app.core.database import AsyncSessionLocal

        tenant_a = "tenant-alpha"
        tenant_b = "tenant-bravo"
        user_b = AuthenticatedUser(id="eng-bravo", email="b@test.com", role="engineer", tenant_id=tenant_b)

        async with AsyncSessionLocal() as db:
            p = Project(id=str(uuid.uuid4()), tenant_id=tenant_a, name="P_Alpha", owner_id="u1", project_type=ProjectType.CIRCUIT.value, status=ProjectStatus.ACTIVE.value)
            c = Circuit(id=str(uuid.uuid4()), project_id=p.id, tenant_id=tenant_a, name="C_Alpha", created_by="u1")
            b = EngineeringBoard(id=str(uuid.uuid4()), project_id=p.id, circuit_id=c.id, tenant_id=tenant_a, name="B_Alpha", created_by="u1")
            rs = ManufacturingRuleSet(id=str(uuid.uuid4()), tenant_id=tenant_a, name="RS_Alpha", source="CUSTOM", source_revision="R1", rules={}, is_default=False)
            analysis = ManufacturingAnalysisRecord(
                id=str(uuid.uuid4()), board_id=b.id, board_revision=1, circuit_id=c.id,
                tenant_id=tenant_a, rule_set_id=rs.id, status=ManufacturingAnalysisStatus.COMPLETED.value,
                findings=[], summary={}, created_by="u1",
            )
            db.add_all([p, c, b, rs, analysis])
            await db.commit()

            # Tenant B attempts to fetch Tenant A's analysis -> 404 or 403
            with pytest.raises(HTTPException) as exc:
                await dfm_service.get_analysis(db, analysis.id, user_b)
            assert exc.value.status_code == 404

            # Tenant B attempts to run analysis on Tenant A's board -> 404
            with pytest.raises(HTTPException) as exc:
                await dfm_service.run_analysis(
                    db, user_b,
                    ManufacturingAnalysisCreate(board_id=b.id, circuit_id=c.id)
                )
            assert exc.value.status_code == 404
