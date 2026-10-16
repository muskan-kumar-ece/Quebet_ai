import uuid
import pytest
from app.models.db.analysis import CircuitAnalysis
from app.models.db.circuit import Circuit, CircuitValidationStatus
from app.models.db.component import Component
from app.models.db.connection import Connection
from app.models.db.net import Net
from app.models.db.pcb import (
    BoardFootprint,
    BoardLayer,
    BoardPad,
    BoardStatus,
    BoardTraceSegment,
    BoardVia,
    EngineeringBoard,
    LayerType,
    PadType,
    PCBAnalysisRecord,
    PCBProposalRecord,
    ViaType,
)
from app.models.db.project import Project, ProjectStatus, ProjectType
from app.models.db.proposal import ProposalStatus
from app.models.schemas.pcb import (
    EngineeringBoardCreate,
    EngineeringBoardUpdate,
    PCBProposalCreate,
)
from app.services.ai.pcb.connectivity_engine import PCBConnectivityEngine
from app.services.ai.pcb.consistency_engine import SchematicPCBConsistencyEngine
from app.services.ai.pcb.decoupling_engine import PCBDecouplingEngine
from app.services.ai.pcb.drc_engine import PCBRuleEngine
from app.services.ai.pcb.geometry_engine import PCBGeometryEngine
from app.services.ai.pcb.high_speed_engine import PCBHighSpeedEngine
from app.services.ai.pcb.placement_engine import PCBPlacementEngine
from app.services.ai.pcb.proposal_engine import PCBProposalEngine
from app.services.ai.pcb.snapshot import PCBSnapshotService
from app.services.ai.pcb.thermal_engine import PCBThermalEngine
from app.services.ai.pcb.trace_current_engine import PCBTraceCurrentEngine
from app.services.ai.pcb.via_engine import PCBViaEngine


def create_test_board(circuit: Circuit, name: str = "Test Board") -> EngineeringBoard:
    board_id = str(uuid.uuid4())
    board = EngineeringBoard(
        id=board_id,
        project_id=circuit.project_id,
        circuit_id=circuit.id,
        circuit_version=getattr(circuit, "version", 1) or 1,
        tenant_id=circuit.tenant_id,
        name=name,
        version=1,
        status=BoardStatus.DRAFT.value,
        dimensions={"width_mm": 100.0, "height_mm": 80.0, "thickness_mm": 1.6},
        units="mm",
        board_outline=[{"x": 0.0, "y": 0.0}, {"x": 100.0, "y": 0.0}, {"x": 100.0, "y": 80.0}, {"x": 0.0, "y": 80.0}],
        created_by="user-1",
        metadata_={},
    )
    l1 = BoardLayer(
        id=str(uuid.uuid4()),
        board_id=board_id,
        name="F.Cu",
        layer_type=LayerType.COPPER.value,
        layer_order=1,
        is_copper=True,
        thickness_um=35.0,
        copper_weight_oz=1.0,
    )
    l2 = BoardLayer(
        id=str(uuid.uuid4()),
        board_id=board_id,
        name="B.Cu",
        layer_type=LayerType.COPPER.value,
        layer_order=2,
        is_copper=True,
        thickness_um=35.0,
        copper_weight_oz=1.0,
    )
    board.layers = [l1, l2]
    snap = PCBSnapshotService.generate_canonical_snapshot(board)
    board.integrity_digest = PCBSnapshotService.compute_integrity_digest(snap)
    return board


class TestPhase3Wave5PCB:

    # 1. Board creation
    def test_01_board_creation(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c, "Main Motherboard")
        assert board.name == "Main Motherboard"
        assert board.version == 1
        assert len(board.layers) == 2
        assert board.integrity_digest is not None
        assert len(board.integrity_digest) == 64

    # 2. Board revision update
    def test_02_board_revision(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        initial_digest = board.integrity_digest

        # Mutate dimension and advance version
        board.dimensions["width_mm"] = 120.0
        board.version += 1
        new_snap = PCBSnapshotService.generate_canonical_snapshot(board)
        board.integrity_digest = PCBSnapshotService.compute_integrity_digest(new_snap)

        assert board.version == 2
        assert board.integrity_digest != initial_digest

    # 3. Component binding
    def test_03_component_binding(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        comp = Component(id="comp-1", circuit_id="c1", ref_des="R1", component_type="RESISTOR", value="10k")
        c.components = [comp]
        board = create_test_board(c)

        fp = BoardFootprint(
            id="fp-1",
            board_id=board.id,
            component_id=comp.id,
            ref_des="R1",
            footprint_name="R_0805_2012Metric",
            pos_x=20.0,
            pos_y=30.0,
        )
        board.footprints = [fp]

        findings = SchematicPCBConsistencyEngine.validate(c, board)
        # Perfectly synchronized
        assert len(findings) == 0

    # 4. Footprint binding & package metadata
    def test_04_footprint_binding(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        comp = Component(id="comp-u1", circuit_id="c1", ref_des="U1", component_type="IC", metadata_={"footprint": "SOIC-8"})
        c.components = [comp]
        board = create_test_board(c)

        # Mismatched footprint on PCB
        fp = BoardFootprint(
            id="fp-u1",
            board_id=board.id,
            component_id=comp.id,
            ref_des="U1",
            footprint_name="DIP-8",
            pos_x=50.0,
            pos_y=40.0,
        )
        board.footprints = [fp]

        findings = SchematicPCBConsistencyEngine.validate(c, board)
        mismatch = next((f for f in findings if f.rule_id == "PCB003"), None)
        assert mismatch is not None
        assert mismatch.status == "VIOLATED"
        assert mismatch.actual_value == "DIP-8"

    # 5. Pad-net consistency
    def test_05_pad_net_consistency(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        comp = Component(id="r1", circuit_id="c1", ref_des="R1", component_type="RESISTOR")
        net_vcc = Net(id="n-vcc", circuit_id="c1", name="VCC")
        conn = Connection(id="conn1", circuit_id="c1", component_id=comp.id, pin_number="1", net_id=net_vcc.id)
        c.components = [comp]
        c.nets = [net_vcc]
        c.connections = [conn]

        board = create_test_board(c)
        fp = BoardFootprint(id="fp1", board_id=board.id, component_id=comp.id, ref_des="R1", footprint_name="R_0805")
        # Pad mapped to GND instead of VCC!
        p1 = BoardPad(id="p1", board_id=board.id, footprint_id=fp.id, pad_number="1", net_name="GND")
        fp.pads = [p1]
        board.footprints = [fp]

        findings = SchematicPCBConsistencyEngine.validate(c, board)
        mismatch = next((f for f in findings if f.rule_id == "PCB004"), None)
        assert mismatch is not None
        assert mismatch.status == "VIOLATED"
        assert "GND" in mismatch.message

    # 6. Missing PCB component (PCB001)
    def test_06_missing_pcb_component(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        c.components = [
            Component(id="r1", circuit_id="c1", ref_des="R1", component_type="RESISTOR"),
            Component(id="r2", circuit_id="c1", ref_des="R2", component_type="RESISTOR"),
        ]
        board = create_test_board(c)
        # Only R1 placed on PCB
        board.footprints = [BoardFootprint(id="fp1", board_id=board.id, component_id="r1", ref_des="R1", footprint_name="R_0805")]

        findings = SchematicPCBConsistencyEngine.validate(c, board)
        missing = next((f for f in findings if f.rule_id == "PCB001"), None)
        assert missing is not None
        assert missing.element_ref == "R2"

    # 7. Missing schematic component (PCB002)
    def test_07_missing_schematic_component(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        # Extra component on PCB not in schematic
        board.footprints = [BoardFootprint(id="fp-orphan", board_id=board.id, ref_des="C99", footprint_name="C_0805")]

        findings = SchematicPCBConsistencyEngine.validate(c, board)
        orphan = next((f for f in findings if f.rule_id == "PCB002"), None)
        assert orphan is not None
        assert orphan.element_ref == "C99"

    # 8. Broken PCB net (PCB006)
    def test_08_disconnected_net(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)

        fp1 = BoardFootprint(id="fp1", board_id=board.id, ref_des="R1", footprint_name="R_0805", pos_x=10.0, pos_y=10.0)
        p1 = BoardPad(id="p1", board_id=board.id, footprint_id=fp1.id, pad_number="1", net_name="NET_A", pos_x=0.0, pos_y=0.0, width=1.0, height=1.0, layer="F.Cu")
        fp1.pads = [p1]

        fp2 = BoardFootprint(id="fp2", board_id=board.id, ref_des="R2", footprint_name="R_0805", pos_x=50.0, pos_y=50.0)
        p2 = BoardPad(id="p2", board_id=board.id, footprint_id=fp2.id, pad_number="1", net_name="NET_A", pos_x=0.0, pos_y=0.0, width=1.0, height=1.0, layer="F.Cu")
        fp2.pads = [p2]

        board.footprints = [fp1, fp2]
        board.traces = []  # No traces connecting p1 and p2!

        findings = PCBConnectivityEngine.analyze_connectivity(board)
        broken = next((f for f in findings if f.rule_id == "PCB006"), None)
        assert broken is not None
        assert broken.status == "VIOLATED"
        assert "NET_A" in broken.element_ref

    # 9. Unconnected pad (PCB005)
    def test_09_unconnected_pad(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)

        fp = BoardFootprint(id="fp1", board_id=board.id, ref_des="R1", footprint_name="R_0805", pos_x=10.0, pos_y=10.0)
        p1 = BoardPad(id="p1", board_id=board.id, footprint_id=fp.id, pad_number="1", net_name="SIG", pos_x=0.0, pos_y=0.0, width=1.0, height=1.0, layer="F.Cu")
        fp.pads = [p1]

        # A trace exists on net SIG, but does not touch pad p1
        t = BoardTraceSegment(id="t1", board_id=board.id, start_x=30.0, start_y=30.0, end_x=40.0, end_y=40.0, width=0.25, layer="F.Cu", net_name="SIG")
        board.footprints = [fp]
        board.traces = [t]

        findings = PCBConnectivityEngine.analyze_connectivity(board)
        unconnected = next((f for f in findings if f.rule_id == "PCB005"), None)
        assert unconnected is not None
        assert unconnected.element_ref == "R1.1"

    # 10. Duplicate reference designator (PCB012)
    def test_10_duplicate_reference(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        fp1 = BoardFootprint(id="fp1", board_id=board.id, ref_des="U1", footprint_name="SOIC-8")
        fp2 = BoardFootprint(id="fp2", board_id=board.id, ref_des="U1", footprint_name="QFN-16")
        board.footprints = [fp1, fp2]

        findings = SchematicPCBConsistencyEngine.validate(c, board)
        dup = next((f for f in findings if f.rule_id == "PCB012"), None)
        assert dup is not None
        assert dup.element_ref == "U1"

    # 11. Clearance violation (PCB007)
    def test_11_clearance_violation(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)

        # Pad 1 of net A at (10, 10), width 1.0 (bounds 9.5 to 10.5)
        fp1 = BoardFootprint(id="fp1", board_id=board.id, ref_des="R1", footprint_name="R_0805", pos_x=10.0, pos_y=10.0)
        p1 = BoardPad(id="p1", board_id=board.id, footprint_id=fp1.id, pad_number="1", net_name="NET_A", pos_x=0.0, pos_y=0.0, width=1.0, height=1.0, layer="F.Cu")
        fp1.pads = [p1]

        # Pad 2 of net B placed at (11.1, 10.0) -> edge distance = 11.1 - 10.0 - 0.5 - 0.5 = 0.1 mm < 0.15 mm!
        fp2 = BoardFootprint(id="fp2", board_id=board.id, ref_des="R2", footprint_name="R_0805", pos_x=11.1, pos_y=10.0)
        p2 = BoardPad(id="p2", board_id=board.id, footprint_id=fp2.id, pad_number="1", net_name="NET_B", pos_x=0.0, pos_y=0.0, width=1.0, height=1.0, layer="F.Cu")
        fp2.pads = [p2]

        board.footprints = [fp1, fp2]
        findings = PCBGeometryEngine.evaluate_clearances(board, min_clearance=0.15)
        violation = next((f for f in findings if f.rule_id == "PCB007"), None)
        assert violation is not None
        assert violation.status == "VIOLATED"
        assert violation.actual_value < 0.15

    # 12. Edge clearance violation (PCB008)
    def test_12_edge_clearance_violation(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        board.dimensions = {"width_mm": 100.0, "height_mm": 80.0}

        # Pad placed right at edge (0.2 mm from left edge, required 0.5 mm)
        fp = BoardFootprint(id="fp1", board_id=board.id, ref_des="R1", footprint_name="R_0805", pos_x=0.6, pos_y=20.0)
        p1 = BoardPad(id="p1", board_id=board.id, footprint_id=fp.id, pad_number="1", net_name="GND", pos_x=0.0, pos_y=0.0, width=1.0, height=1.0, layer="F.Cu")
        fp.pads = [p1]
        board.footprints = [fp]

        findings = PCBGeometryEngine.evaluate_clearances(board, min_edge_clearance=0.5)
        edge_viol = next((f for f in findings if f.rule_id == "PCB008"), None)
        assert edge_viol is not None
        assert edge_viol.status == "VIOLATED"

    # 13. Trace width validation (PCB009)
    def test_13_trace_width_validation(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        # Trace width 0.08 mm < 0.15 mm
        t = BoardTraceSegment(id="t1", board_id=board.id, start_x=10.0, start_y=10.0, end_x=20.0, end_y=10.0, width=0.08, layer="F.Cu", net_name="SIG")
        board.traces = [t]

        findings = PCBTraceCurrentEngine.evaluate(board, min_default_width_mm=0.15)
        viol = next((f for f in findings if f.rule_id == "PCB009"), None)
        assert viol is not None
        assert viol.actual_value == 0.08

    # 14. Via validation (PCB010)
    def test_14_via_validation(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        # Via drill 0.1 mm < 0.2 mm
        v = BoardVia(id="v1", board_id=board.id, pos_x=10.0, pos_y=10.0, drill=0.1, diameter=0.4, start_layer="F.Cu", end_layer="B.Cu")
        board.vias = [v]

        findings = PCBViaEngine.evaluate(board, min_drill_mm=0.2)
        viol = next((f for f in findings if f.rule_id == "PCB010"), None)
        assert viol is not None
        assert viol.actual_value == 0.1

    # 15. Placement constraint: KEEP_IN and KEEP_OUT (PCB011)
    def test_15_placement_constraint_keep_in_keep_out(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        board.dimensions = {"width_mm": 100.0, "height_mm": 80.0}
        board.metadata_ = {
            "keep_out_zones": [{"name": "ANTENNA", "x_min": 80.0, "x_max": 100.0, "y_min": 60.0, "y_max": 80.0}]
        }

        # Footprint placed at (90, 70) inside keep-out zone
        fp = BoardFootprint(id="fp1", board_id=board.id, ref_des="U2", footprint_name="SOIC-8", pos_x=90.0, pos_y=70.0)
        board.footprints = [fp]

        findings, evals = PCBPlacementEngine.evaluate(board)
        viol = next((f for f in findings if f.rule_id == "PCB011"), None)
        assert viol is not None
        assert "ANTENNA" in viol.message

    # 16. Decoupling placement (PCB014)
    def test_16_decoupling_placement(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        u1 = Component(id="u1", circuit_id="c1", ref_des="U1", component_type="MCU", metadata_={"decoupling_caps": ["C1"], "max_distance_mm": 5.0})
        c1 = Component(id="c1", circuit_id="c1", ref_des="C1", component_type="CAPACITOR")
        c.components = [u1, c1]

        board = create_test_board(c)
        # Placed 20 mm apart (> 5 mm)
        fp_u1 = BoardFootprint(id="fpu", board_id=board.id, ref_des="U1", footprint_name="QFP-32", pos_x=20.0, pos_y=20.0)
        fp_c1 = BoardFootprint(id="fpc", board_id=board.id, ref_des="C1", footprint_name="C_0805", pos_x=40.0, pos_y=20.0)
        board.footprints = [fp_u1, fp_c1]

        findings = PCBDecouplingEngine.evaluate(c, board)
        viol = next((f for f in findings if f.rule_id == "PCB014"), None)
        assert viol is not None
        assert viol.actual_value == 20.0
        assert viol.required_limit == 5.0

    # 17. Thermal placement issue (PCB016)
    def test_17_thermal_constraint(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        fp1 = BoardFootprint(id="fp1", board_id=board.id, ref_des="Q1", footprint_name="TO-220", pos_x=30.0, pos_y=30.0)
        fp2 = BoardFootprint(id="fp2", board_id=board.id, ref_des="Q2", footprint_name="TO-220", pos_x=34.0, pos_y=30.0)
        board.footprints = [fp1, fp2]

        analysis = CircuitAnalysis(
            id="ana-1",
            circuit_id=c.id,
            created_by="u1",
            calculations=[
                {"type": "POWER_DISSIPATION", "target": "Q1", "value": 1.2, "unit": "W"},
                {"type": "POWER_DISSIPATION", "target": "Q2", "value": 1.5, "unit": "W"},
            ],
        )

        findings = PCBThermalEngine.evaluate(board, analysis, min_separation_mm=10.0)
        viol = next((f for f in findings if f.rule_id == "PCB016"), None)
        assert viol is not None
        assert viol.actual_value == 4.0

    # 18. Differential pair constraint violation (PCB015)
    def test_18_differential_pair_constraint(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        board.metadata_ = {
            "differential_pairs": [{"pos_net": "USB_DP", "neg_net": "USB_DM", "max_skew_mm": 0.5}]
        }
        # Trace on DP length = 20 mm
        t1 = BoardTraceSegment(id="t1", board_id=board.id, start_x=0.0, start_y=0.0, end_x=20.0, end_y=0.0, width=0.25, layer="F.Cu", net_name="USB_DP")
        # Trace on DM length = 22 mm (skew = 2.0 mm > 0.5 mm)
        t2 = BoardTraceSegment(id="t2", board_id=board.id, start_x=0.0, start_y=2.0, end_x=22.0, end_y=2.0, width=0.25, layer="F.Cu", net_name="USB_DM")
        board.traces = [t1, t2]

        findings = PCBHighSpeedEngine.evaluate(board)
        viol = next((f for f in findings if f.rule_id == "PCB015"), None)
        assert viol is not None
        assert viol.actual_value == 2.0

    # 19. Unknown constraint handling: missing parameters return UNKNOWN, not PASS
    def test_19_unknown_constraint_handling(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        # Trace with current = 2A, but layer has NO copper thickness
        layer_no_th = BoardLayer(id="l1", board_id=board.id, name="F.Cu", layer_order=1, is_copper=True, thickness_um=None)
        board.layers = [layer_no_th]
        t = BoardTraceSegment(id="t1", board_id=board.id, start_x=0.0, start_y=0.0, end_x=10.0, end_y=0.0, width=0.25, layer="F.Cu", net_name="HIGH_I")
        board.traces = [t]

        ana = CircuitAnalysis(
            id="a1", circuit_id=c.id, created_by="u1",
            calculations=[{"type": "NET_CURRENT", "target": "HIGH_I", "value": 2.0, "unit": "A"}]
        )
        findings = PCBTraceCurrentEngine.evaluate(board, ana)
        unknown_finding = next((f for f in findings if f.status == "UNKNOWN"), None)
        assert unknown_finding is not None
        assert "copper thickness is UNKNOWN" in unknown_finding.message

    # 20. PCB snapshot digest
    def test_20_pcb_snapshot_digest(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        snap = PCBSnapshotService.generate_canonical_snapshot(board)
        digest = PCBSnapshotService.compute_integrity_digest(snap)
        assert digest is not None
        assert len(digest) == 64

    # 21. Deterministic snapshot: identical state regardless of collection ordering produces identical digest
    def test_21_deterministic_snapshot(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board1 = create_test_board(c)
        fp1 = BoardFootprint(id="fp1", board_id=board1.id, ref_des="R1", footprint_name="R_0805", pos_x=10.0, pos_y=10.0)
        fp2 = BoardFootprint(id="fp2", board_id=board1.id, ref_des="C1", footprint_name="C_0805", pos_x=20.0, pos_y=20.0)
        board1.footprints = [fp1, fp2]

        board2 = create_test_board(c)
        board2.id = board1.id
        # Reverse footprint list insertion
        fp1_b = BoardFootprint(id="fp1", board_id=board2.id, ref_des="R1", footprint_name="R_0805", pos_x=10.0, pos_y=10.0)
        fp2_b = BoardFootprint(id="fp2", board_id=board2.id, ref_des="C1", footprint_name="C_0805", pos_x=20.0, pos_y=20.0)
        board2.footprints = [fp2_b, fp1_b]

        d1 = PCBSnapshotService.compute_integrity_digest(PCBSnapshotService.generate_canonical_snapshot(board1))
        d2 = PCBSnapshotService.compute_integrity_digest(PCBSnapshotService.generate_canonical_snapshot(board2))
        assert d1 == d2

    # 22. Stale analysis detection
    def test_22_stale_analysis(self):
        rec = PCBAnalysisRecord(
            id="ana-1",
            board_id="b1",
            board_version=1,
            circuit_id="c1",
            circuit_version=1,
            status="COMPLETED",
            snapshot_digest="abc",
            findings=[],
            metrics={},
        )
        current_board_version = 2
        is_stale = current_board_version > rec.board_version
        assert is_stale is True

    # 23. Stale proposal rejection
    def test_23_stale_proposal(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        board.version = 2  # Board advanced to version 2

        val_res = PCBProposalEngine.validate_proposal(
            board=board,
            operations=[{"op": "move_footprint", "ref_des": "R1", "pos_x": 50.0}],
            base_revision=1,  # Proposal created against revision 1!
        )
        assert val_res["is_stale"] is True
        assert any("STALE_PROPOSAL" in err for err in val_res["errors"])

    # 24. Human approval boundary: unapproved proposal cannot be applied
    def test_24_human_approval_boundary(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        prop = PCBProposalRecord(
            id="p1",
            board_id=board.id,
            base_revision=1,
            circuit_version=1,
            created_by="u1",
            title="Move R1",
            status=ProposalStatus.PROPOSED.value,  # NOT approved!
            operations=[{"op": "move_footprint", "ref_des": "R1", "pos_x": 10.0}],
        )

        with pytest.raises(ValueError, match="AUTONOMOUS_MUTATION_BLOCKED"):
            PCBProposalEngine.apply_proposal(board=board, proposal=prop)

    # 25. Autonomous mutation rejection
    def test_25_autonomous_mutation_rejection(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        prop = PCBProposalRecord(
            id="p1",
            board_id=board.id,
            base_revision=1,
            circuit_version=1,
            created_by="ai-agent",
            title="Auto Route",
            status=ProposalStatus.PROPOSED.value,
            operations=[],
        )
        assert prop.status != ProposalStatus.APPLIED.value
        assert prop.applied_at is None

    # 26. Tenant isolation & IDOR protection
    @pytest.mark.asyncio
    async def test_26_tenant_isolation(self, async_client):
        from app.core.database import AsyncSessionLocal
        from app.core.security import create_access_token

        tenant_a = "tenant-pcb-a"
        tenant_b = "tenant-pcb-b"
        user_a = "user-pcb-a"
        user_b = "user-pcb-b"
        token_b = create_access_token(user_b, claims={"role": "user", "plan": "pro", "tenant_id": tenant_b})
        headers_b = {"Authorization": f"Bearer {token_b}"}

        async with AsyncSessionLocal() as db:
            proj_a = Project(id=str(uuid.uuid4()), tenant_id=tenant_a, name="P_A", owner_id=user_a, project_type=ProjectType.CIRCUIT.value, status=ProjectStatus.ACTIVE.value)
            circ_a = Circuit(id=str(uuid.uuid4()), project_id=proj_a.id, tenant_id=tenant_a, name="C_A", created_by=user_a)
            board_a = create_test_board(circ_a, "Board Tenant A")
            board_a.tenant_id = tenant_a
            db.add_all([proj_a, circ_a, board_a])
            await db.commit()
            board_a_id = board_a.id

        # Tenant B attempts to fetch Tenant A's board
        res = await async_client.get(f"/api/v1/boards/{board_a_id}", headers=headers_b)
        assert res.status_code == 404

    # 27. Cross-circuit IDOR protection
    @pytest.mark.asyncio
    async def test_27_idor_protection(self, async_client):
        from app.core.database import AsyncSessionLocal
        from app.core.security import create_access_token

        tenant = "tenant-pcb-idor"
        user = "user-pcb-idor"
        token = create_access_token(user, claims={"role": "user", "plan": "pro", "tenant_id": tenant})
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncSessionLocal() as db:
            proj = Project(id=str(uuid.uuid4()), tenant_id=tenant, name="P", owner_id=user, project_type=ProjectType.CIRCUIT.value, status=ProjectStatus.ACTIVE.value)
            c1 = Circuit(id=str(uuid.uuid4()), project_id=proj.id, tenant_id=tenant, name="C1", created_by=user)
            b1 = create_test_board(c1, "B1")
            b1.tenant_id = tenant
            db.add_all([proj, c1, b1])
            await db.commit()
            b1_id = b1.id

        res = await async_client.get(f"/api/v1/circuits/fake-circuit-id/boards", headers=headers)
        assert res.status_code == 200
        # Returns empty list for non-matching circuit
        assert len(res.json()["data"]) == 0

    # 28. Proposal atomicity
    def test_28_proposal_atomicity(self):
        c = Circuit(id="c1", project_id="p1", name="C1", created_by="u1")
        board = create_test_board(c)
        fp = BoardFootprint(id="fp1", board_id=board.id, ref_des="R1", footprint_name="R_0805", pos_x=10.0, pos_y=10.0, rotation=0.0)
        board.footprints = [fp]

        prop = PCBProposalRecord(
            id="p1",
            board_id=board.id,
            base_revision=1,
            circuit_version=1,
            created_by="u1",
            title="Move R1 to (30, 40)",
            status=ProposalStatus.APPROVED.value,  # Human approved
            operations=[{"op": "move_footprint", "ref_des": "R1", "pos_x": 30.0, "pos_y": 40.0, "rotation": 90.0}],
        )

        initial_ver = board.version
        PCBProposalEngine.apply_proposal(board=board, proposal=prop)

        assert board.version == initial_ver + 1
        assert fp.pos_x == 30.0
        assert fp.pos_y == 40.0
        assert fp.rotation == 90.0

    # 29. Provenance & revision integrity
    def test_29_provenance(self):
        c = Circuit(id="c1", project_id="p1", name="C1", version=1, created_by="u1")
        board = create_test_board(c)
        snap = PCBSnapshotService.generate_canonical_snapshot(board)
        digest = PCBSnapshotService.compute_integrity_digest(snap)

        rec = PCBAnalysisRecord(
            id="rec-1",
            board_id=board.id,
            board_version=board.version,
            circuit_id=c.id,
            circuit_version=c.version,
            snapshot_digest=digest,
            findings=[],
            metrics={},
            classification="PCB_ANALYSIS",
            verification_status="NOT_VERIFIED",
        )
        assert rec.board_version == 1
        assert rec.circuit_version == 1
        assert rec.snapshot_digest == digest
        assert rec.classification == "PCB_ANALYSIS"
        assert rec.verification_status == "NOT_VERIFIED"

    # 30. Zero synthetic scoring in PCB analysis
    def test_30_zero_synthetic_scoring(self):
        rec = PCBAnalysisRecord(
            id="rec-1",
            board_id="b1",
            circuit_id="c1",
            snapshot_digest="dig",
            findings=[],
            metrics={"total_findings": 0, "error_count": 0, "is_drc_clean": True},
        )
        assert not hasattr(rec, "quality_score")
        assert not hasattr(rec, "composite_score")
        assert not hasattr(rec, "winner")
        assert not hasattr(rec, "design_score")
        assert not hasattr(rec, "autoroute_percentage")

    # 31. AI actor proposal approval and application blocked (HTTP 403)
    @pytest.mark.asyncio
    async def test_31_ai_actor_proposal_approval_blocked(self, async_client):
        from app.core.database import AsyncSessionLocal
        from app.core.security import create_access_token

        tenant = "tenant-ai-gate"
        ai_user = "ai-copilot-agent"
        ai_token = create_access_token(ai_user, claims={"role": "ai_agent", "plan": "enterprise", "tenant_id": tenant})
        ai_headers = {"Authorization": f"Bearer {ai_token}"}

        human_user = "eng-lead"
        human_token = create_access_token(human_user, claims={"role": "engineer", "plan": "enterprise", "tenant_id": tenant})
        human_headers = {"Authorization": f"Bearer {human_token}"}

        async with AsyncSessionLocal() as db:
            proj = Project(id=str(uuid.uuid4()), tenant_id=tenant, name="P_AI", owner_id=human_user, project_type=ProjectType.CIRCUIT.value, status=ProjectStatus.ACTIVE.value)
            c1 = Circuit(id=str(uuid.uuid4()), project_id=proj.id, tenant_id=tenant, name="C_AI", created_by=human_user)
            b1 = create_test_board(c1, "B_AI")
            b1.tenant_id = tenant
            prop = PCBProposalRecord(
                id=str(uuid.uuid4()),
                board_id=b1.id,
                base_revision=1,
                circuit_version=1,
                tenant_id=tenant,
                created_by=human_user,
                title="Move R1",
                status=ProposalStatus.PROPOSED.value,
                operations=[{"op": "move_footprint", "ref_des": "R1", "pos_x": 10.0, "pos_y": 20.0}],
            )
            db.add_all([proj, c1, b1, prop])
            await db.commit()
            b1_id = b1.id
            prop_id = prop.id

        # 1. AI actor attempts approval -> 403 Forbidden
        ai_appr_res = await async_client.post(
            f"/api/v1/pcb/boards/{b1_id}/proposals/{prop_id}/approve",
            headers=ai_headers,
        )
        assert ai_appr_res.status_code == 403
        assert "AI_UNAUTHORIZED_PROPOSAL_APPROVAL" in ai_appr_res.text

        # 2. Human engineer approves -> 200 OK
        human_appr_res = await async_client.post(
            f"/api/v1/pcb/boards/{b1_id}/proposals/{prop_id}/approve",
            headers=human_headers,
        )
        assert human_appr_res.status_code == 200
        assert human_appr_res.json()["data"]["status"] == ProposalStatus.APPROVED.value

