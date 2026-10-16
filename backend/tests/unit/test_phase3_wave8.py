"""
Phase 3 Wave 8 Test Suite: Advanced Engineering Validation, Cross-Domain Consistency & System-Level Verification.

Verifies strict non-negotiable invariants:
- Cross-domain consistency rules X001 through X020
- Epistemic boundaries:
  - UNKNOWN != PASS
  - CALCULATED != PHYSICALLY VERIFIED
  - SIMULATION_RESULT != PHYSICAL_MEASUREMENT
  - SIMULATION_RESULT != HARDWARE_VERIFICATION
  - HISTORICAL_VERIFICATION != CURRENT_VERIFICATION
  - IDENTITY_MATCH != ELECTRICAL_COMPATIBILITY
  - PAD_COUNT_MATCH != PINOUT_MATCH
  - PACKAGE_MATCH != FUNCTIONAL_COMPATIBILITY
  - PROVENANCE_AND_INTEGRITY_DIGEST != DIGITAL_SIGNATURE
- Zero synthetic scoring (no composite scores, no rankings, no winners)
- Simulation and DFM staleness detection
- Requirements substantiation: SATISFIED requires concrete evidence; AI explanation cannot substantiate compliance
- Multi-tenant isolation and IDOR protection
- Role authorization: viewer / read-only users rejected from initiating validation
"""
import hashlib
import json
import uuid
import pytest
from fastapi import HTTPException

from app.core.dependencies import AuthenticatedUser
from app.models.db.cross_domain import (
    CrossDomainSeverity,
    CrossDomainStatus,
    CrossDomainValidationRecord,
    CrossDomainValidationStatus,
    SourceClassification,
    ValidationDomain,
)
from app.models.db.circuit import Circuit
from app.models.db.component import Component
from app.models.db.net import Net
from app.models.db.connection import Connection
from app.models.db.pcb import (
    BoardFootprint,
    BoardLayer,
    BoardPad,
    BoardTraceSegment,
    BoardVia,
    EngineeringBoard,
)
from app.models.db.bom import (
    EngineeringBOM,
    EngineeringBOMLine,
    ComponentPartCandidate,
)
from app.models.db.simulation import SimulationJob, SimulationResultRecord
from app.models.db.dfm import ManufacturingAnalysisRecord
from app.models.db.decision import EngineeringRequirement
from app.models.db.verification import EngineeringDesignReview, EngineeringEvidence
from app.models.db.provenance import EngineeringSource
from app.models.db.project import Project, ProjectStatus, ProjectType

from app.services.ai.cross_domain.rule_registry import CROSS_DOMAIN_RULES
from app.services.ai.cross_domain.snapshot import CrossDomainSnapshotEngine
from app.services.ai.cross_domain.schematic_pcb_consistency import SchematicPCBConsistencyEngine
from app.services.ai.cross_domain.bom_consistency import BOMCrossDomainConsistencyEngine
from app.services.ai.cross_domain.operating_limits_consistency import OperatingLimitsConsistencyEngine
from app.services.ai.cross_domain.power_thermal_consistency import PowerThermalConsistencyEngine
from app.services.ai.cross_domain.simulation_consistency import SimulationConsistencyEngine
from app.services.ai.cross_domain.requirements_consistency import RequirementsConsistencyEngine
from app.services.ai.cross_domain.dfm_staleness_consistency import DFMStalenessConsistencyEngine
from app.services.ai.cross_domain.verification_consistency import VerificationConsistencyEngine
from app.services.ai.cross_domain.completeness_consistency import CompletenessConsistencyEngine
from app.services.ai.cross_domain.cross_domain_engine import CrossDomainValidationEngine
from app.services.cross_domain_service import CrossDomainService


class TestPhase3Wave8CrossDomain:
    """Test suite covering the 60 validation scenarios and invariants of Phase 3 Wave 8."""

    def _create_mock_circuit(self, version: int = 1) -> Circuit:
        c = Circuit(
            id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            name="Power Supply Schematic",
            version=version,
        )
        c.components = [
            Component(
                id=str(uuid.uuid4()),
                circuit_id=c.id,
                ref_des="U1",
                component_type="IC",
                value="LM317",
                metadata_={"operating_voltage": 12.0, "voltage_rating": 37.0, "abs_max_voltage": 40.0, "power_dissipation_w": 1.2, "r_theta_ja": 25.0, "tj_max_c": 125.0},
            ),
            Component(
                id=str(uuid.uuid4()),
                circuit_id=c.id,
                ref_des="C1",
                component_type="CAPACITOR",
                value="10uF",
                metadata_={"operating_voltage": 12.0, "voltage_rating": 25.0, "abs_max_voltage": 30.0},
            ),
            Component(
                id=str(uuid.uuid4()),
                circuit_id=c.id,
                ref_des="R1",
                component_type="RESISTOR",
                value="240",
                metadata_={"operating_voltage": 1.25, "voltage_rating": 50.0, "abs_max_voltage": 100.0},
            ),
        ]
        c.nets = [
            Net(id=str(uuid.uuid4()), circuit_id=c.id, name="VCC"),
            Net(id=str(uuid.uuid4()), circuit_id=c.id, name="GND"),
            Net(id=str(uuid.uuid4()), circuit_id=c.id, name="VOUT"),
        ]
        c.properties = {
            "power_rails": {
                "VCC": {"source_capacity_a": 2.0, "total_load_a": 0.8},
                "VOUT": {"source_capacity_a": 1.5, "total_load_a": 0.5},
            }
        }
        return c

    def _create_mock_board(self, revision: int = 1) -> EngineeringBoard:
        b = EngineeringBoard(
            id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            circuit_id=str(uuid.uuid4()),
            circuit_version=1,
            tenant_id="tenant-1",
            name="Power Supply PCB",
            version=revision,
            units="mm",
            created_by="user-1",
        )
        b.footprints = [
            BoardFootprint(
                id=str(uuid.uuid4()),
                board_id=b.id,
                ref_des="U1",
                footprint_name="TO-220-3",
                pads=[
                    BoardPad(id=str(uuid.uuid4()), pad_number="1", net_name="VCC", pad_type="THROUGH_HOLE", drill=1.0),
                    BoardPad(id=str(uuid.uuid4()), pad_number="2", net_name="VOUT", pad_type="THROUGH_HOLE", drill=1.0),
                    BoardPad(id=str(uuid.uuid4()), pad_number="3", net_name="GND", pad_type="THROUGH_HOLE", drill=1.0),
                ],
            ),
            BoardFootprint(
                id=str(uuid.uuid4()),
                board_id=b.id,
                ref_des="C1",
                footprint_name="C0805",
                pads=[
                    BoardPad(id=str(uuid.uuid4()), pad_number="1", net_name="VCC", pad_type="SMD"),
                    BoardPad(id=str(uuid.uuid4()), pad_number="2", net_name="GND", pad_type="SMD"),
                ],
            ),
            BoardFootprint(
                id=str(uuid.uuid4()),
                board_id=b.id,
                ref_des="R1",
                footprint_name="R0805",
                pads=[
                    BoardPad(id=str(uuid.uuid4()), pad_number="1", net_name="VOUT", pad_type="SMD"),
                    BoardPad(id=str(uuid.uuid4()), pad_number="2", net_name="GND", pad_type="SMD"),
                ],
            ),
        ]
        b.traces = [
            BoardTraceSegment(id=str(uuid.uuid4()), board_id=b.id, net_name="VCC", width=0.5, layer="F.Cu"),
            BoardTraceSegment(id=str(uuid.uuid4()), board_id=b.id, net_name="GND", width=0.8, layer="B.Cu"),
            BoardTraceSegment(id=str(uuid.uuid4()), board_id=b.id, net_name="VOUT", width=0.5, layer="F.Cu"),
        ]
        b.vias = [
            BoardVia(id=str(uuid.uuid4()), board_id=b.id, net_name="GND_THERMAL", drill=0.3, via_type="THERMAL"),
            BoardVia(id=str(uuid.uuid4()), board_id=b.id, net_name="GND_THERMAL", drill=0.3, via_type="THERMAL"),
        ]
        return b

    def _create_mock_bom(self, revision: int = 1) -> EngineeringBOM:
        bom = EngineeringBOM(
            id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            circuit_id=str(uuid.uuid4()),
            tenant_id="tenant-1",
            name="Power Supply BOM",
            version=revision,
            created_by="user-1",
        )
        l1 = EngineeringBOMLine(
            id=str(uuid.uuid4()),
            bom_id=bom.id,
            reference_designator="U1",
            component_type="IC",
            design_value="LM317",
            manufacturer_part_number="LM317T",
            design_package="TO220",
        )
        l1.candidates = [
            ComponentPartCandidate(id=str(uuid.uuid4()), bom_line_id=l1.id, manufacturer="TI", mpn="LM317T")
        ]

        l2 = EngineeringBOMLine(
            id=str(uuid.uuid4()),
            bom_id=bom.id,
            reference_designator="C1",
            component_type="CAPACITOR",
            design_value="10uF",
            manufacturer_part_number="GRM21BR61E106MA73L",
            design_package="0805",
        )
        l2.candidates = [
            ComponentPartCandidate(id=str(uuid.uuid4()), bom_line_id=l2.id, manufacturer="Murata", mpn="GRM21BR61E106MA73L")
        ]

        l3 = EngineeringBOMLine(
            id=str(uuid.uuid4()),
            bom_id=bom.id,
            reference_designator="R1",
            component_type="RESISTOR",
            design_value="240",
            manufacturer_part_number="CRCW0805240RFKEA",
            design_package="0805",
        )
        l3.candidates = [
            ComponentPartCandidate(id=str(uuid.uuid4()), bom_line_id=l3.id, manufacturer="Vishay", mpn="CRCW0805240RFKEA")
        ]

        bom.lines = [l1, l2, l3]
        return bom


    # =========================================================================
    # 1. SCHEMATIC <-> PCB CONSISTENCY (X001, X002)
    # =========================================================================

    def test_x001_missing_circuit_evaluates_unknown(self):
        board = self._create_mock_board()
        findings = SchematicPCBConsistencyEngine.evaluate("proj-1", None, board, CROSS_DOMAIN_RULES)
        x001 = [f for f in findings if f.rule_id == "X001"]
        assert len(x001) == 1
        assert x001[0].status == CrossDomainStatus.UNKNOWN
        assert "circuit model is missing" in x001[0].explanation.lower()

    def test_x001_missing_board_evaluates_unknown(self):
        circuit = self._create_mock_circuit()
        findings = SchematicPCBConsistencyEngine.evaluate("proj-1", circuit, None, CROSS_DOMAIN_RULES)
        x001 = [f for f in findings if f.rule_id == "X001"]
        assert len(x001) == 1
        assert x001[0].status == CrossDomainStatus.UNKNOWN

    def test_x001_unrouted_schematic_net_flags_warning(self):
        circuit = self._create_mock_circuit()
        circuit.nets.append(Net(id=str(uuid.uuid4()), circuit_id=circuit.id, name="UNROUTED_SIGNAL"))
        board = self._create_mock_board()
        findings = SchematicPCBConsistencyEngine.evaluate("proj-1", circuit, board, CROSS_DOMAIN_RULES)
        warn = [f for f in findings if f.rule_id == "X001" and f.status == CrossDomainStatus.WARNING]
        assert len(warn) == 1
        assert "UNROUTED_SIGNAL" in warn[0].explanation

    def test_x001_fully_routed_nets_pass(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        findings = SchematicPCBConsistencyEngine.evaluate("proj-1", circuit, board, CROSS_DOMAIN_RULES)
        x001_pass = [f for f in findings if f.rule_id == "X001" and f.status == CrossDomainStatus.PASS]
        assert len(x001_pass) == 1
        assert "all 3 schematic electrical nets" in x001_pass[0].explanation.lower()

    def test_x002_missing_footprint_flags_critical_fail(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        # Remove U1 from board
        board.footprints = [fp for fp in board.footprints if fp.ref_des != "U1"]
        findings = SchematicPCBConsistencyEngine.evaluate("proj-1", circuit, board, CROSS_DOMAIN_RULES)
        fail = [f for f in findings if f.rule_id == "X002" and f.status == CrossDomainStatus.FAIL]
        assert len(fail) == 1
        assert fail[0].severity == CrossDomainSeverity.CRITICAL
        assert "U1" in fail[0].explanation

    def test_x002_unmapped_pcb_footprint_flags_warning(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        board.footprints.append(BoardFootprint(id=str(uuid.uuid4()), board_id=board.id, ref_des="TP1", footprint_name="TEST_PAD"))
        findings = SchematicPCBConsistencyEngine.evaluate("proj-1", circuit, board, CROSS_DOMAIN_RULES)
        warn = [f for f in findings if f.rule_id == "X002" and f.status == CrossDomainStatus.WARNING]
        assert len(warn) == 1
        assert "TP1" in warn[0].explanation

    def test_x002_all_components_placed_pass(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        findings = SchematicPCBConsistencyEngine.evaluate("proj-1", circuit, board, CROSS_DOMAIN_RULES)
        x002_pass = [f for f in findings if f.rule_id == "X002" and f.status == CrossDomainStatus.PASS]
        assert len(x002_pass) == 1
        assert x002_pass[0].status == CrossDomainStatus.PASS

    # =========================================================================
    # 2. BOM CROSS-DOMAIN CONSISTENCY (X003, X004, X005, X019)
    # =========================================================================

    def test_x003_missing_bom_evaluates_unknown(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        findings = BOMCrossDomainConsistencyEngine.evaluate("proj-1", circuit, board, None, CROSS_DOMAIN_RULES)
        x003 = [f for f in findings if f.rule_id == "X003"]
        assert len(x003) == 1
        assert x003[0].status == CrossDomainStatus.UNKNOWN

    def test_x003_unlisted_bom_component_flags_fail(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        bom = self._create_mock_bom()
        # Drop C1 from BOM
        bom.lines = [line for line in bom.lines if line.reference_designator != "C1"]
        findings = BOMCrossDomainConsistencyEngine.evaluate("proj-1", circuit, board, bom, CROSS_DOMAIN_RULES)
        fail = [f for f in findings if f.rule_id == "X003" and f.status == CrossDomainStatus.FAIL]
        assert len(fail) == 1
        assert "C1" in fail[0].explanation

    def test_x004_bom_package_mismatch_flags_fail(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        bom = self._create_mock_bom()
        # Change U1 in BOM to QFN16
        for line in bom.lines:
            if line.reference_designator == "U1":
                line.design_package = "QFN16"
        findings = BOMCrossDomainConsistencyEngine.evaluate("proj-1", circuit, board, bom, CROSS_DOMAIN_RULES)
        fail = [f for f in findings if f.rule_id == "X004" and f.status == CrossDomainStatus.FAIL]
        assert len(fail) == 1
        assert "QFN16" in fail[0].explanation
        assert "PACKAGE_MATCH != FUNCTIONAL_COMPATIBILITY" in fail[0].explanation

    def test_x004_asserts_package_match_not_functional_compatibility(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        bom = self._create_mock_bom()
        findings = BOMCrossDomainConsistencyEngine.evaluate("proj-1", circuit, board, bom, CROSS_DOMAIN_RULES)
        pass_004 = [f for f in findings if f.rule_id == "X004" and f.status == CrossDomainStatus.PASS]
        assert len(pass_004) == 1
        assert "PACKAGE_MATCH != FUNCTIONAL_COMPATIBILITY" in pass_004[0].explanation

    def test_x005_pad_count_mismatch_flags_fail(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        bom = self._create_mock_bom()
        # Set U1 BOM package to SOIC8 (8 pins), but footprint has 3 pads
        for line in bom.lines:
            if line.reference_designator == "U1":
                line.design_package = "SOIC-8"
        findings = BOMCrossDomainConsistencyEngine.evaluate("proj-1", circuit, board, bom, CROSS_DOMAIN_RULES)
        fail = [f for f in findings if f.rule_id == "X005" and f.status == CrossDomainStatus.FAIL]
        assert len(fail) == 1
        assert fail[0].status == CrossDomainStatus.FAIL
        assert "PAD_COUNT_MATCH != PINOUT_MATCH" in fail[0].explanation
        assert fail[0].quantitative_values["bom_pin_count"] == 8
        assert fail[0].quantitative_values["pcb_pad_count"] == 3

    def test_x005_pad_count_pass_retains_pinout_disclaimer(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        bom = self._create_mock_bom()
        findings = BOMCrossDomainConsistencyEngine.evaluate("proj-1", circuit, board, bom, CROSS_DOMAIN_RULES)
        pass_005 = [f for f in findings if f.rule_id == "X005" and f.status == CrossDomainStatus.PASS]
        assert len(pass_005) == 1
        assert "PAD_COUNT_MATCH != PINOUT_MATCH" in pass_005[0].explanation

    def test_x019_procurement_candidate_mpn_mismatch(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        bom = self._create_mock_bom()
        # Set selected candidate MPN different from design MPN
        bom.lines[0].candidates[0].mpn = "LM317-SUBSTITUTE"
        findings = BOMCrossDomainConsistencyEngine.evaluate("proj-1", circuit, board, bom, CROSS_DOMAIN_RULES)
        warn = [f for f in findings if f.rule_id == "X019" and f.status == CrossDomainStatus.WARNING]
        assert len(warn) == 1
        assert "IDENTITY_MATCH != ELECTRICAL_COMPATIBILITY" in warn[0].explanation

    def test_x019_matching_procurement_identity_passes(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        bom = self._create_mock_bom()
        findings = BOMCrossDomainConsistencyEngine.evaluate("proj-1", circuit, board, bom, CROSS_DOMAIN_RULES)
        pass_019 = [f for f in findings if f.rule_id == "X019" and f.status == CrossDomainStatus.PASS]
        assert len(pass_019) == 1
        assert "IDENTITY_MATCH != ELECTRICAL_COMPATIBILITY" in pass_019[0].explanation

    # =========================================================================
    # 3. COMPONENT OPERATING LIMITS & ABSOLUTE MAXIMUM (X006, X007)
    # =========================================================================

    def test_x006_missing_rating_evaluates_unknown(self):
        circuit = self._create_mock_circuit()
        circuit.components[0].properties = {"operating_voltage": 12.0}  # missing voltage_rating
        findings = OperatingLimitsConsistencyEngine.evaluate("proj-1", circuit, None, CROSS_DOMAIN_RULES)
        unk = [f for f in findings if f.rule_id == "X006" and f.status == CrossDomainStatus.UNKNOWN and "U1" in f.explanation]
        assert len(unk) == 1

    def test_x006_operating_voltage_exceeds_rating_flags_fail(self):
        circuit = self._create_mock_circuit()
        circuit.components[1].properties = {"operating_voltage": 35.0, "voltage_rating": 25.0}
        findings = OperatingLimitsConsistencyEngine.evaluate("proj-1", circuit, None, CROSS_DOMAIN_RULES)
        fail = [f for f in findings if f.rule_id == "X006" and f.status == CrossDomainStatus.FAIL]
        assert len(fail) == 1
        assert fail[0].margin < 0
        assert "exceeds continuous rating" in fail[0].explanation

    def test_x006_compliant_operating_limits_pass(self):
        circuit = self._create_mock_circuit()
        findings = OperatingLimitsConsistencyEngine.evaluate("proj-1", circuit, None, CROSS_DOMAIN_RULES)
        p = [f for f in findings if f.rule_id == "X006" and f.status == CrossDomainStatus.PASS]
        assert len(p) == 1

    def test_x007_missing_abs_max_evaluates_unknown(self):
        circuit = self._create_mock_circuit()
        circuit.components[0].metadata_.pop("abs_max_voltage")
        findings = OperatingLimitsConsistencyEngine.evaluate("proj-1", circuit, None, CROSS_DOMAIN_RULES)
        unk = [f for f in findings if f.rule_id == "X007" and f.status == CrossDomainStatus.UNKNOWN and "U1" in f.explanation]
        assert len(unk) == 1

    def test_x007_operating_voltage_violates_abs_max_critical_fail(self):
        circuit = self._create_mock_circuit()
        circuit.components[0].metadata_["operating_voltage"] = 45.0  # abs max is 40.0
        findings = OperatingLimitsConsistencyEngine.evaluate("proj-1", circuit, None, CROSS_DOMAIN_RULES)
        fail = [f for f in findings if f.rule_id == "X007" and f.status == CrossDomainStatus.FAIL]
        assert len(fail) == 1
        assert fail[0].severity == CrossDomainSeverity.CRITICAL
        assert "Permanent silicon damage risk" in fail[0].explanation

    def test_x007_safe_margin_below_abs_max_pass(self):
        circuit = self._create_mock_circuit()
        findings = OperatingLimitsConsistencyEngine.evaluate("proj-1", circuit, None, CROSS_DOMAIN_RULES)
        p = [f for f in findings if f.rule_id == "X007" and f.status == CrossDomainStatus.PASS]
        assert len(p) == 1

    # =========================================================================
    # 4. POWER & THERMAL CONSISTENCY (X008, X009, X010)
    # =========================================================================

    def test_x008_unconfigured_rails_evaluate_unknown(self):
        circuit = self._create_mock_circuit()
        circuit.properties = {}
        findings = PowerThermalConsistencyEngine.evaluate("proj-1", circuit, None, CROSS_DOMAIN_RULES)
        unk = [f for f in findings if f.rule_id == "X008" and f.status == CrossDomainStatus.UNKNOWN]
        assert len(unk) == 1

    def test_x008_power_rail_overload_flags_critical_fail(self):
        circuit = self._create_mock_circuit()
        circuit.properties["power_rails"]["VCC"]["total_load_a"] = 3.5  # capacity is 2.0A
        findings = PowerThermalConsistencyEngine.evaluate("proj-1", circuit, None, CROSS_DOMAIN_RULES)
        fail = [f for f in findings if f.rule_id == "X008" and f.status == CrossDomainStatus.FAIL]
        assert len(fail) == 1
        assert fail[0].severity == CrossDomainSeverity.CRITICAL
        assert fail[0].margin < 0

    def test_x008_power_rail_sufficient_capacity_pass(self):
        circuit = self._create_mock_circuit()
        findings = PowerThermalConsistencyEngine.evaluate("proj-1", circuit, None, CROSS_DOMAIN_RULES)
        p = [f for f in findings if f.rule_id == "X008" and f.status == CrossDomainStatus.PASS]
        assert len(p) == 1

    def test_x009_missing_thermal_resistance_evaluates_unknown(self):
        circuit = self._create_mock_circuit()
        # High power dissipation but missing r_theta_ja
        circuit.components[0].metadata_ = {"power_dissipation_w": 2.0}
        findings = PowerThermalConsistencyEngine.evaluate("proj-1", circuit, None, CROSS_DOMAIN_RULES)
        unk = [f for f in findings if f.rule_id == "X009" and f.status == CrossDomainStatus.UNKNOWN]
        assert len(unk) == 1
        assert "silent default substitution strictly forbidden" in unk[0].explanation

    def test_x009_junction_temperature_overheating_flags_fail(self):
        circuit = self._create_mock_circuit()
        # Pd=5W, Rth=30C/W, Ta=25C -> Tj = 25 + 150 = 175C > 125C max
        circuit.components[0].properties = {
            "power_dissipation_w": 5.0,
            "r_theta_ja": 30.0,
            "tj_max_c": 125.0,
            "ambient_temp_c": 25.0,
        }
        findings = PowerThermalConsistencyEngine.evaluate("proj-1", circuit, None, CROSS_DOMAIN_RULES)
        fail = [f for f in findings if f.rule_id == "X009" and f.status == CrossDomainStatus.FAIL]
        assert len(fail) == 1
        assert fail[0].quantitative_values["t_junction_c"] == 175.0
        assert fail[0].margin == -50.0

    def test_x009_junction_temperature_compliant_pass(self):
        circuit = self._create_mock_circuit()
        findings = PowerThermalConsistencyEngine.evaluate("proj-1", circuit, None, CROSS_DOMAIN_RULES)
        p = [f for f in findings if f.rule_id == "X009" and f.status == CrossDomainStatus.PASS]
        assert len(p) == 1

    def test_x010_high_power_component_lacking_thermal_features_warns(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        board.vias = []  # No thermal vias
        findings = PowerThermalConsistencyEngine.evaluate("proj-1", circuit, board, CROSS_DOMAIN_RULES)
        warn = [f for f in findings if f.rule_id == "X010" and f.status == CrossDomainStatus.WARNING]
        assert len(warn) == 1
        assert "thermal vias" in warn[0].explanation.lower()

    def test_x010_thermal_dissipation_features_pass(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        findings = PowerThermalConsistencyEngine.evaluate("proj-1", circuit, board, CROSS_DOMAIN_RULES)
        p = [f for f in findings if f.rule_id == "X010" and f.status == CrossDomainStatus.PASS]
        assert len(p) == 1

    # =========================================================================
    # 5. SIMULATION STALENESS & CONSISTENCY (X011, X012)
    # =========================================================================

    def test_x011_missing_simulation_evaluates_unknown(self):
        circuit = self._create_mock_circuit()
        findings = SimulationConsistencyEngine.evaluate("proj-1", circuit, None, None, CROSS_DOMAIN_RULES)
        unk = [f for f in findings if f.rule_id == "X011" and f.status == CrossDomainStatus.UNKNOWN]
        assert len(unk) == 1
        assert "no spice simulation" in unk[0].explanation.lower()

    def test_x011_stale_simulation_revision_evaluates_unknown_stale(self):
        circuit = self._create_mock_circuit(version=2)
        sim_job = SimulationJob(
            id=str(uuid.uuid4()),
            project_id="proj-1",
            circuit_id=circuit.id,
            circuit_version=1,  # Stale: circuit was updated to v2
            status="COMPLETED",
        )
        findings = SimulationConsistencyEngine.evaluate("proj-1", circuit, sim_job, None, CROSS_DOMAIN_RULES)
        stale = [f for f in findings if f.rule_id == "X011" and f.status == CrossDomainStatus.UNKNOWN]
        assert len(stale) == 1
        assert "STALE SIMULATION" in stale[0].explanation
        assert "SIMULATION_RESULT != CURRENT_VERIFICATION" in stale[0].explanation

    def test_x011_current_simulation_matches_circuit_revision(self):
        circuit = self._create_mock_circuit(version=1)
        sim_job = SimulationJob(
            id=str(uuid.uuid4()),
            project_id="proj-1",
            circuit_id=circuit.id,
            circuit_version=1,
            status="COMPLETED",
        )
        findings = SimulationConsistencyEngine.evaluate("proj-1", circuit, sim_job, None, CROSS_DOMAIN_RULES)
        p = [f for f in findings if f.rule_id == "X011" and f.status == CrossDomainStatus.PASS]
        assert len(p) == 1
        assert "SIMULATION_RESULT != PHYSICAL_MEASUREMENT" in p[0].explanation

    def test_x012_simulation_non_convergence_flags_fail(self):
        circuit = self._create_mock_circuit(version=1)
        sim_job = SimulationJob(id=str(uuid.uuid4()), project_id="proj-1", circuit_id=circuit.id, circuit_version=1, status="COMPLETED")
        sim_res = SimulationResultRecord(
            id=str(uuid.uuid4()),
            simulation_job_id=sim_job.id,
            circuit_id=circuit.id,
            convergence_status="SINGULAR_MATRIX",
        )
        findings = SimulationConsistencyEngine.evaluate("proj-1", circuit, sim_job, sim_res, CROSS_DOMAIN_RULES)
        fail = [f for f in findings if f.rule_id == "X012" and f.status == CrossDomainStatus.FAIL]
        assert len(fail) == 1
        assert "SINGULAR_MATRIX" in fail[0].explanation

    def test_x012_converged_simulation_passes_with_disclaimer(self):
        circuit = self._create_mock_circuit(version=1)
        sim_job = SimulationJob(id=str(uuid.uuid4()), project_id="proj-1", circuit_id=circuit.id, circuit_version=1, status="COMPLETED")
        sim_res = SimulationResultRecord(
            id=str(uuid.uuid4()),
            simulation_job_id=sim_job.id,
            circuit_id=circuit.id,
            convergence_status="CONVERGED",
        )
        findings = SimulationConsistencyEngine.evaluate("proj-1", circuit, sim_job, sim_res, CROSS_DOMAIN_RULES)
        p = [f for f in findings if f.rule_id == "X012" and f.status == CrossDomainStatus.PASS]
        assert len(p) == 1
        assert "SIMULATION_RESULT != PHYSICAL_MEASUREMENT" in p[0].explanation

    # =========================================================================
    # 6. REQUIREMENTS & DESIGN CONSTRAINTS (X013, X014)
    # =========================================================================

    def test_x013_missing_requirements_evaluates_unknown(self):
        findings = RequirementsConsistencyEngine.evaluate("proj-1", None, None, None, CROSS_DOMAIN_RULES)
        unk = [f for f in findings if f.rule_id == "X013" and f.status == CrossDomainStatus.UNKNOWN]
        assert len(unk) == 1

    def test_x013_satisfied_requirement_lacking_evidence_evaluates_unknown(self):
        req = EngineeringRequirement(
            id=str(uuid.uuid4()),
            system_id="sys-1",
            title="Max Ripple Voltage",
            status="SATISFIED",
        )
        req.evidence_ids = []  # No substantiated evidence!
        findings = RequirementsConsistencyEngine.evaluate("proj-1", [req], None, None, CROSS_DOMAIN_RULES)
        unk = [f for f in findings if f.rule_id == "X013" and f.status == CrossDomainStatus.UNKNOWN]
        assert len(unk) == 1
        assert "AI explanation cannot substantiate compliance" in unk[0].explanation

    def test_x013_violated_requirement_flags_fail(self):
        req = EngineeringRequirement(
            id=str(uuid.uuid4()),
            system_id="sys-1",
            title="Standby Power",
            status="VIOLATED",
        )
        findings = RequirementsConsistencyEngine.evaluate("proj-1", [req], None, None, CROSS_DOMAIN_RULES)
        fail = [f for f in findings if f.rule_id == "X013" and f.status == CrossDomainStatus.FAIL]
        assert len(fail) == 1

    def test_x013_requirement_with_evidence_passes(self):
        req = EngineeringRequirement(
            id=str(uuid.uuid4()),
            system_id="sys-1",
            title="Operating Efficiency",
            status="SATISFIED",
        )
        req.evidence_ids = ["ev-123"]
        findings = RequirementsConsistencyEngine.evaluate("proj-1", [req], None, None, CROSS_DOMAIN_RULES)
        p = [f for f in findings if f.rule_id == "X013" and f.status == CrossDomainStatus.PASS]
        assert len(p) == 1

    def test_x014_trace_width_violates_fabrication_capability(self):
        board = self._create_mock_board()
        board.traces[0].width = 0.08  # 0.08mm < 0.15mm min fab capability
        findings = RequirementsConsistencyEngine.evaluate("proj-1", [], board, {"MFG001": {"parameters": {"min_trace_width_mm": 0.15}}}, CROSS_DOMAIN_RULES)
        fail = [f for f in findings if f.rule_id == "X014" and f.status == CrossDomainStatus.FAIL]
        assert len(fail) == 1
        assert fail[0].margin < 0

    def test_x014_layout_constraints_satisfy_manufacturing(self):
        board = self._create_mock_board()
        findings = RequirementsConsistencyEngine.evaluate("proj-1", [], board, {"MFG001": {"parameters": {"min_trace_width_mm": 0.15}}}, CROSS_DOMAIN_RULES)
        p = [f for f in findings if f.rule_id == "X014" and f.status == CrossDomainStatus.PASS]
        assert len(p) == 1

    # =========================================================================
    # 7. DFM STALENESS & REVISION CONSISTENCY (X015)
    # =========================================================================

    def test_x015_missing_dfm_analysis_evaluates_unknown(self):
        board = self._create_mock_board()
        findings = DFMStalenessConsistencyEngine.evaluate("proj-1", board, None, None, CROSS_DOMAIN_RULES)
        unk = [f for f in findings if f.rule_id == "X015" and f.status == CrossDomainStatus.UNKNOWN]
        assert len(unk) == 1

    def test_x015_stale_dfm_revision_evaluates_unknown_stale(self):
        board = self._create_mock_board(revision=2)
        dfm_record = ManufacturingAnalysisRecord(
            id=str(uuid.uuid4()),
            board_id=board.id,
            board_revision=1,  # Stale! Board is revision 2
            circuit_id="c-1",
            circuit_revision=1,
            rule_set_id="rs-1",
            rule_set_revision="REV_A",
            status="COMPLETED",
        )
        findings = DFMStalenessConsistencyEngine.evaluate("proj-1", board, dfm_record, None, CROSS_DOMAIN_RULES)
        stale = [f for f in findings if f.rule_id == "X015" and f.status == CrossDomainStatus.UNKNOWN]
        assert len(stale) == 1
        assert "STALE DFM" in stale[0].explanation

    def test_x015_current_dfm_passes_with_disclaimer(self):
        board = self._create_mock_board(revision=1)
        dfm_record = ManufacturingAnalysisRecord(
            id=str(uuid.uuid4()),
            board_id=board.id,
            board_revision=1,
            circuit_id="c-1",
            circuit_revision=1,
            rule_set_id="rs-1",
            rule_set_revision="REV_A",
            status="COMPLETED",
        )
        findings = DFMStalenessConsistencyEngine.evaluate("proj-1", board, dfm_record, None, CROSS_DOMAIN_RULES)
        p = [f for f in findings if f.rule_id == "X015" and f.status == CrossDomainStatus.PASS]
        assert len(p) == 1
        assert "DFM_ANALYSIS != MANUFACTURER_ACCEPTANCE" in p[0].explanation

    # =========================================================================
    # 8. VERIFICATION & SOURCE CONSISTENCY (X016, X017, X018)
    # =========================================================================

    def test_x016_stale_verification_evidence_flags_warning(self):
        circuit = self._create_mock_circuit(version=2)
        ev = EngineeringEvidence(
            id=str(uuid.uuid4()),
            verification_requirement_id=str(uuid.uuid4()),
            review_id=str(uuid.uuid4()),
            evidence_type="LAB_MEASUREMENT",
            source="OSCILLOSCOPE",
            description="Oscilloscope Trace",
            provided_by="engineer-1",
        )
        ev.circuit_version = 1  # Stale! Circuit is v2
        findings = VerificationConsistencyEngine.evaluate("proj-1", circuit, [], [ev], [], CROSS_DOMAIN_RULES)
        warn = [f for f in findings if f.rule_id == "X016" and f.status == CrossDomainStatus.WARNING]
        assert len(warn) == 1

    def test_x017_historical_verification_does_not_verify_current_revision(self):
        circuit = self._create_mock_circuit(version=2)
        review = EngineeringDesignReview(
            id=str(uuid.uuid4()),
            project_id="proj-1",
            circuit_id=circuit.id,
            circuit_revision=1,
            analysis_id=str(uuid.uuid4()),
            created_by="user-1",
            status="VERIFIED",
        )
        findings = VerificationConsistencyEngine.evaluate("proj-1", circuit, [review], [], [], CROSS_DOMAIN_RULES)
        unk = [f for f in findings if f.rule_id == "X017" and f.status == CrossDomainStatus.UNKNOWN]
        assert len(unk) == 1
        assert "HISTORICAL_VERIFICATION != CURRENT_VERIFICATION" in unk[0].explanation

    def test_x018_superseded_source_flags_warning(self):
        source = EngineeringSource(
            id=str(uuid.uuid4()),
            source_type="DATASHEET",
            title="Legacy Datasheet Rev A",
            publisher="TI",
            document_identifier="SNVS022E",
            status="SUPERSEDED",
        )
        findings = VerificationConsistencyEngine.evaluate("proj-1", None, [], [], [source], CROSS_DOMAIN_RULES)
        warn = [f for f in findings if f.rule_id == "X018" and f.status == CrossDomainStatus.WARNING]
        assert len(warn) == 1

    # =========================================================================
    # 9. CROSS-DOMAIN COMPLETENESS (X020)
    # =========================================================================

    def test_x020_missing_domains_evaluates_unknown(self):
        circuit = self._create_mock_circuit()
        findings = CompletenessConsistencyEngine.evaluate("proj-1", circuit, None, None, None, None, None, None, CROSS_DOMAIN_RULES)
        unk = [f for f in findings if f.rule_id == "X020" and f.status == CrossDomainStatus.UNKNOWN]
        assert len(unk) == 1
        assert "missing domain artifacts" in unk[0].explanation.lower()

    def test_x020_all_domains_populated_passes(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        bom = self._create_mock_bom()
        sim_job = SimulationJob(id=str(uuid.uuid4()), project_id="proj-1", circuit_id=circuit.id, status="COMPLETED")
        dfm_rec = ManufacturingAnalysisRecord(
            id=str(uuid.uuid4()),
            board_id=board.id,
            board_revision=1,
            circuit_id=circuit.id,
            rule_set_id="rs-1",
            rule_set_revision="REV_A",
            status="COMPLETED",
        )
        reqs = [EngineeringRequirement(id=str(uuid.uuid4()), system_id="sys-1", title="Req 1")]
        vers = [
            EngineeringDesignReview(
                id=str(uuid.uuid4()),
                project_id="proj-1",
                circuit_id=circuit.id,
                circuit_revision=1,
                analysis_id=str(uuid.uuid4()),
                created_by="user-1",
                status="COMPLETED",
            )
        ]

        findings = CompletenessConsistencyEngine.evaluate("proj-1", circuit, board, bom, sim_job, dfm_rec, reqs, vers, CROSS_DOMAIN_RULES)
        p = [f for f in findings if f.rule_id == "X020" and f.status == CrossDomainStatus.PASS]
        assert len(p) == 1
        assert p[0].quantitative_values["available_domains"] == 7

    # =========================================================================
    # 10. SYSTEM-LEVEL INVARIANTS, SNAPSHOT DETERMINISM & ZERO SCORING
    # =========================================================================

    def test_zero_synthetic_scoring_invariant(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        bom = self._create_mock_bom()

        summary, findings, digest, _ = CrossDomainValidationEngine.run_cross_domain_validation(
            project_id="proj-1",
            circuit=circuit,
            board=board,
            bom=bom,
        )

        # Ensure summary contains strictly categorical counts, NO scalar score
        summary_dict = summary.model_dump()
        assert "score" not in summary_dict
        assert "rank" not in summary_dict
        assert "winner" not in summary_dict
        assert "total_findings" in summary_dict
        assert "pass_count" in summary_dict
        assert "fail_count" in summary_dict

        # Verify findings have no scores
        for f in findings:
            f_dict = f.model_dump()
            assert "score" not in f_dict
            assert "grade" not in f_dict
            assert f.status in (CrossDomainStatus.PASS, CrossDomainStatus.FAIL, CrossDomainStatus.WARNING, CrossDomainStatus.UNKNOWN, CrossDomainStatus.NOT_APPLICABLE)

    def test_canonical_snapshot_deterministic_sha256(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        bom = self._create_mock_bom()

        snap1 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", circuit, board, bom)
        digest1 = CrossDomainSnapshotEngine.compute_canonical_digest(snap1)

        snap2 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", circuit, board, bom)
        digest2 = CrossDomainSnapshotEngine.compute_canonical_digest(snap2)

        assert digest1 == digest2
        assert len(digest1) == 64
        # Verify valid hex string
        int(digest1, 16)

    def test_provenance_digest_disclaimer_assertion(self):
        doc = CrossDomainValidationRecord.__table__.columns["snapshot_digest"].doc
        assert "PROVENANCE_AND_INTEGRITY_DIGEST" in doc
        assert "NOT a digital signature" in doc

    @pytest.mark.asyncio
    async def test_read_only_role_rejected_from_initiating_validation(self):
        from app.core.database import AsyncSessionLocal
        from app.api.v1.routes.cross_domain import run_cross_domain_validation
        user_viewer = AuthenticatedUser(
            id=str(uuid.uuid4()),
            email="viewer@example.com",
            role="viewer",
            tenant_id="tenant-1",
        )
        async with AsyncSessionLocal() as db:
            p = Project(
                id=str(uuid.uuid4()),
                tenant_id="tenant-1",
                name="Project Viewer",
                project_type=ProjectType.CIRCUIT.value,
                owner_id=str(uuid.uuid4()),
            )
            db.add(p)
            await db.commit()

            with pytest.raises(HTTPException) as exc_info:
                await run_cross_domain_validation(
                    project_id=p.id,
                    current_user=user_viewer,
                    db=db,
                )
            assert exc_info.value.status_code == 403
            assert "Read-only" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_tenant_isolation_cross_project_rejection(self):
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            # Create project under tenant-A
            proj_a = Project(
                id=str(uuid.uuid4()),
                tenant_id="tenant-A",
                name="Project A",
                project_type=ProjectType.CIRCUIT.value,
                owner_id=str(uuid.uuid4()),
            )
            db.add(proj_a)
            await db.commit()

            # User belonging to tenant-B attempts to validate project A
            user_b = AuthenticatedUser(
                id=str(uuid.uuid4()),
                email="user_b@tenantb.com",
                role="engineer",
                tenant_id="tenant-B",
            )
            service = CrossDomainService(db)
            with pytest.raises(HTTPException) as exc_info:
                await service.validate_project(project_id=proj_a.id, tenant_id=user_b.tenant_id)
            assert exc_info.value.status_code == 404

    def test_canonical_snapshot_changes_when_component_parameter_mutates(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        bom = self._create_mock_bom()

        snap1 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", circuit, board, bom)
        digest1 = CrossDomainSnapshotEngine.compute_canonical_digest(snap1)

        # Mutate component operating voltage
        circuit.components[0].metadata_["operating_voltage"] = 35.0
        snap2 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", circuit, board, bom)
        digest2 = CrossDomainSnapshotEngine.compute_canonical_digest(snap2)

        assert digest1 != digest2, "Snapshot digest must change when an engineering component parameter changes"

    def test_canonical_snapshot_changes_when_power_rail_mutates(self):
        circuit = self._create_mock_circuit()
        board = self._create_mock_board()
        bom = self._create_mock_bom()

        snap1 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", circuit, board, bom)
        digest1 = CrossDomainSnapshotEngine.compute_canonical_digest(snap1)

        # Mutate power rail load
        circuit.properties["power_rails"]["VCC"]["total_load_a"] = 2.5
        snap2 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", circuit, board, bom)
        digest2 = CrossDomainSnapshotEngine.compute_canonical_digest(snap2)

        assert digest1 != digest2, "Snapshot digest must change when power rail parameters change"

    def test_x012_convergence_does_not_imply_engineering_correctness(self):
        circuit = self._create_mock_circuit()
        sim_job = SimulationJob(id=str(uuid.uuid4()), project_id="proj-1", circuit_id=circuit.id, status="COMPLETED")
        sim_result = SimulationResultRecord(
            id=str(uuid.uuid4()),
            simulation_job_id=sim_job.id,
            circuit_id=circuit.id,
            convergence_status="CONVERGED",
        )
        findings = SimulationConsistencyEngine.evaluate("proj-1", circuit, sim_job, sim_result, CROSS_DOMAIN_RULES)
        pass_f = [f for f in findings if f.rule_id == "X012" and f.status == CrossDomainStatus.PASS]
        assert len(pass_f) == 1
        assert "CONVERGENCE != ENGINEERING_CORRECTNESS" in pass_f[0].explanation
        assert "SIMULATION_RESULT != PHYSICAL_MEASUREMENT" in pass_f[0].explanation

    @pytest.mark.asyncio
    async def test_cross_tenant_validation_id_access_rejected(self):
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            proj_a = Project(
                id=str(uuid.uuid4()),
                tenant_id="tenant-A",
                name="Project A",
                project_type=ProjectType.CIRCUIT.value,
                owner_id=str(uuid.uuid4()),
            )
            db.add(proj_a)
            rec_a = CrossDomainValidationRecord(
                id=str(uuid.uuid4()),
                tenant_id="tenant-A",
                project_id=proj_a.id,
                validation_status=CrossDomainValidationStatus.COMPLETED,
                summary={},
                findings=[],
                domain_snapshots={},
                snapshot_digest="a" * 64,
            )
            db.add(rec_a)
            await db.commit()

            service = CrossDomainService(db)
            with pytest.raises(HTTPException) as exc_info:
                await service.get_validation(validation_id=rec_a.id, project_id=proj_a.id, tenant_id="tenant-B")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_project_validation_id_mismatch_rejected(self):
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            proj_a = Project(
                id=str(uuid.uuid4()),
                tenant_id="tenant-A",
                name="Project A",
                project_type=ProjectType.CIRCUIT.value,
                owner_id=str(uuid.uuid4()),
            )
            proj_b = Project(
                id=str(uuid.uuid4()),
                tenant_id="tenant-A",
                name="Project B",
                project_type=ProjectType.CIRCUIT.value,
                owner_id=str(uuid.uuid4()),
            )
            db.add_all([proj_a, proj_b])
            rec_a = CrossDomainValidationRecord(
                id=str(uuid.uuid4()),
                tenant_id="tenant-A",
                project_id=proj_a.id,
                validation_status=CrossDomainValidationStatus.COMPLETED,
                summary={},
                findings=[],
                domain_snapshots={},
                snapshot_digest="b" * 64,
            )
            db.add(rec_a)
            await db.commit()

            service = CrossDomainService(db)
            with pytest.raises(HTTPException) as exc_info:
                # Attempt to access rec_a under project B
                await service.get_validation(validation_id=rec_a.id, project_id=proj_b.id, tenant_id="tenant-A")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_latest_validation_endpoint(self):
        from app.core.database import AsyncSessionLocal
        from app.api.v1.routes.cross_domain import get_latest_cross_domain_validation
        user_eng = AuthenticatedUser(
            id=str(uuid.uuid4()),
            email="eng@example.com",
            role="engineer",
            tenant_id="tenant-1",
        )
        async with AsyncSessionLocal() as db:
            p = Project(
                id=str(uuid.uuid4()),
                tenant_id="tenant-1",
                name="Project Latest",
                project_type=ProjectType.CIRCUIT.value,
                owner_id=str(uuid.uuid4()),
            )
            db.add(p)
            await db.commit()

            # Calling latest when no record exists raises 404
            with pytest.raises(HTTPException) as exc_info:
                await get_latest_cross_domain_validation(project_id=p.id, current_user=user_eng, db=db)
            assert exc_info.value.status_code == 404

            # Add validation record
            rec = CrossDomainValidationRecord(
                id=str(uuid.uuid4()),
                tenant_id="tenant-1",
                project_id=p.id,
                validation_status=CrossDomainValidationStatus.COMPLETED,
                summary={
                    "total_findings": 1,
                    "pass_count": 1,
                    "fail_count": 0,
                    "warning_count": 0,
                    "unknown_count": 0,
                    "not_applicable_count": 0,
                    "severity_breakdown": {},
                    "domain_breakdown": {},
                    "rule_results": {},
                },
                findings=[],
                domain_snapshots={},
                snapshot_digest="c" * 64,
            )
            db.add(rec)
            await db.commit()

            # Now latest returns the record
            res = await get_latest_cross_domain_validation(project_id=p.id, current_user=user_eng, db=db)
            assert res.success is True
            assert res.data.id == rec.id
            assert res.data.snapshot_digest == "c" * 64

    def test_x011_missing_circuit_revision_evaluates_unknown(self):
        """Adversarial test verifying that missing revision information evaluates to UNKNOWN without fabricated fallback."""
        circuit = self._create_mock_circuit()
        circuit.version = None  # Missing revision on circuit

        sim_job = SimulationJob(
            id=str(uuid.uuid4()),
            project_id=circuit.project_id,
            circuit_id=circuit.id,
            circuit_version=None,  # Missing revision on simulation job
            status="COMPLETED",
        )

        findings = SimulationConsistencyEngine.evaluate(
            circuit.project_id, circuit, sim_job, None, CROSS_DOMAIN_RULES
        )
        x011_findings = [f for f in findings if f.rule_id == "X011"]
        assert len(x011_findings) == 1
        finding = x011_findings[0]
        assert finding.status == CrossDomainStatus.UNKNOWN
        assert "X011_MISSING_REVISION" in finding.finding_id
        assert "MISSING REVISION" in finding.explanation
        assert "UNKNOWN != PASS" in finding.explanation or "UNKNOWN != SATISFIED" in finding.explanation

    def test_snapshot_coverage_matrix_all_10_inputs_mutate_digest(self):
        """
        Verifies that each of the 10 multi-domain engineering inputs independently
        mutates the canonical snapshot digest.
        """
        circuit = self._create_mock_circuit()
        circuit.connections = [
            Connection(id=str(uuid.uuid4()), circuit_id=circuit.id, component_id=circuit.components[0].id, pin_number="1", net_id=circuit.nets[0].id),
            Connection(id=str(uuid.uuid4()), circuit_id=circuit.id, component_id=circuit.components[1].id, pin_number="1", net_id=circuit.nets[0].id),
        ]
        board = self._create_mock_board()
        board.layers = [
            BoardLayer(id=str(uuid.uuid4()), board_id=board.id, name="F.Cu", layer_type="COPPER", layer_order=1, thickness_um=35.0, copper_weight_oz=1.0),
            BoardLayer(id=str(uuid.uuid4()), board_id=board.id, name="B.Cu", layer_type="COPPER", layer_order=2, thickness_um=35.0, copper_weight_oz=1.0),
        ]
        bom = self._create_mock_bom()
        sim_job = SimulationJob(id=str(uuid.uuid4()), project_id="proj-1", circuit_id=circuit.id, status="COMPLETED", simulation_type="DC_OP", simulator="NGSPICE")
        dfm_analysis = ManufacturingAnalysisRecord(
            id=str(uuid.uuid4()),
            board_id=board.id,
            board_revision=1,
            circuit_id=circuit.id,
            rule_set_id=str(uuid.uuid4()),
            created_by="user-1",
            status="COMPLETED",
            provenance_digest="d"*64,
        )
        reqs = [EngineeringRequirement(id=str(uuid.uuid4()), project_id="proj-1", title="Req 1")]
        vers = [EngineeringDesignReview(id=str(uuid.uuid4()), project_id="proj-1", circuit_id=circuit.id, circuit_revision=1, analysis_id=str(uuid.uuid4()), created_by="user-1")]
        dfm_rules = {"min_trace_width_mm": 0.15, "min_clearance_mm": 0.15}

        # Baseline digest
        base_snap = CrossDomainSnapshotEngine.serialize_domain_state(
            "proj-1", circuit, board, bom, sim_job, dfm_analysis, reqs, vers, dfm_rules=dfm_rules
        )
        base_digest = CrossDomainSnapshotEngine.compute_canonical_digest(base_snap)

        # 1. Component electrical rating mutation
        c_mod1 = self._create_mock_circuit()
        c_mod1.components[0].metadata_["operating_voltage"] = 28.0
        s1 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", c_mod1, board, bom, sim_job, dfm_analysis, reqs, vers, dfm_rules=dfm_rules)
        assert CrossDomainSnapshotEngine.compute_canonical_digest(s1) != base_digest, "Digest must change on component electrical rating change"

        # 2. Component thermal parameter mutation
        c_mod2 = self._create_mock_circuit()
        c_mod2.components[0].metadata_["power_dissipation_w"] = 3.5
        s2 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", c_mod2, board, bom, sim_job, dfm_analysis, reqs, vers, dfm_rules=dfm_rules)
        assert CrossDomainSnapshotEngine.compute_canonical_digest(s2) != base_digest, "Digest must change on component thermal parameter change"

        # 3. Power rail voltage/capacity mutation
        c_mod3 = self._create_mock_circuit()
        c_mod3.properties["power_rails"]["VCC"]["source_capacity_a"] = 5.0
        s3 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", c_mod3, board, bom, sim_job, dfm_analysis, reqs, vers, dfm_rules=dfm_rules)
        assert CrossDomainSnapshotEngine.compute_canonical_digest(s3) != base_digest, "Digest must change on power rail capacity change"

        # 4. Schematic connectivity mutation (pin rewired)
        c_mod4 = self._create_mock_circuit()
        c_mod4.connections = [
            Connection(id=str(uuid.uuid4()), circuit_id=c_mod4.id, component_id=c_mod4.components[0].id, pin_number="1", net_id=c_mod4.nets[1].id), # Changed net to nets[1]
        ]
        s4 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", c_mod4, board, bom, sim_job, dfm_analysis, reqs, vers, dfm_rules=dfm_rules)
        assert CrossDomainSnapshotEngine.compute_canonical_digest(s4) != base_digest, "Digest must change on schematic connectivity change"

        # 5. PCB geometry/routing mutation (trace width changed)
        b_mod5 = self._create_mock_board()
        b_mod5.traces[0].width = 1.2
        s5 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", circuit, b_mod5, bom, sim_job, dfm_analysis, reqs, vers, dfm_rules=dfm_rules)
        assert CrossDomainSnapshotEngine.compute_canonical_digest(s5) != base_digest, "Digest must change on PCB routing trace width change"

        # 6. PCB stackup mutation (copper thickness changed)
        b_mod6 = self._create_mock_board()
        b_mod6.layers = [
            BoardLayer(id=str(uuid.uuid4()), board_id=b_mod6.id, name="F.Cu", layer_type="COPPER", layer_order=1, thickness_um=70.0, copper_weight_oz=2.0),
        ]
        s6 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", circuit, b_mod6, bom, sim_job, dfm_analysis, reqs, vers, dfm_rules=dfm_rules)
        assert CrossDomainSnapshotEngine.compute_canonical_digest(s6) != base_digest, "Digest must change on PCB stackup change"

        # 7. Relevant BOM identity mutation (quantity changed)
        bom_mod7 = self._create_mock_bom()
        bom_mod7.lines[0].quantity = 5
        s7 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", circuit, board, bom_mod7, sim_job, dfm_analysis, reqs, vers, dfm_rules=dfm_rules)
        assert CrossDomainSnapshotEngine.compute_canonical_digest(s7) != base_digest, "Digest must change on BOM identity/quantity change"

        # 8. Applicable DFM rule configuration mutation
        dfm_rules_mod8 = {"min_trace_width_mm": 0.20, "min_clearance_mm": 0.20}
        s8 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", circuit, board, bom, sim_job, dfm_analysis, reqs, vers, dfm_rules=dfm_rules_mod8)
        assert CrossDomainSnapshotEngine.compute_canonical_digest(s8) != base_digest, "Digest must change on DFM rule configuration change"

        # 9. Simulation configuration mutation
        sim_job_mod9 = SimulationJob(id=str(uuid.uuid4()), project_id="proj-1", circuit_id=circuit.id, status="COMPLETED", simulation_type="AC_SWEEP", simulator="NGSPICE")
        s9 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", circuit, board, bom, sim_job_mod9, dfm_analysis, reqs, vers, dfm_rules=dfm_rules)
        assert CrossDomainSnapshotEngine.compute_canonical_digest(s9) != base_digest, "Digest must change on simulation configuration change"

        # 10. Requirement and verification revision references mutation
        reqs_mod10 = reqs + [EngineeringRequirement(id=str(uuid.uuid4()), project_id="proj-1", title="Req 2")]
        s10 = CrossDomainSnapshotEngine.serialize_domain_state("proj-1", circuit, board, bom, sim_job, dfm_analysis, reqs_mod10, vers, dfm_rules=dfm_rules)
        assert CrossDomainSnapshotEngine.compute_canonical_digest(s10) != base_digest, "Digest must change on requirement reference change"

    @pytest.mark.asyncio
    async def test_stale_latest_validation_flagged_on_circuit_mutation(self):
        """Verifies that when design state changes, get_latest_validation marks the record visibly as stale."""
        from app.core.database import AsyncSessionLocal
        from app.api.v1.routes.cross_domain import get_latest_cross_domain_validation
        user_eng = AuthenticatedUser(
            id=str(uuid.uuid4()),
            email="eng2@example.com",
            role="engineer",
            tenant_id="tenant-stale",
        )
        async with AsyncSessionLocal() as db:
            p = Project(
                id=str(uuid.uuid4()),
                tenant_id="tenant-stale",
                name="Project Dynamic Staleness",
                project_type=ProjectType.CIRCUIT.value,
                owner_id=str(uuid.uuid4()),
            )
            c = Circuit(
                id=str(uuid.uuid4()),
                project_id=p.id,
                tenant_id="tenant-stale",
                name="Circuit Stale Test",
                version=1,
                created_by=user_eng.id,
            )
            comp = Component(
                id=str(uuid.uuid4()),
                circuit_id=c.id,
                ref_des="R1",
                component_type="RESISTOR",
                value="10k",
                metadata_={"operating_voltage": 5.0},
            )
            c.components = [comp]
            db.add_all([p, c, comp])
            await db.commit()

            service = CrossDomainService(db)
            rec = await service.validate_project(project_id=p.id, tenant_id=user_eng.tenant_id)
            assert rec.is_stale is False

            # Check latest returns non-stale
            res1 = await get_latest_cross_domain_validation(project_id=p.id, current_user=user_eng, db=db)
            assert res1.data.is_stale is False
            assert len(res1.data.staleness_reasons) == 0

            # Mutate component operating voltage in DB
            comp.metadata_ = {"operating_voltage": 12.0}
            await db.commit()

            # Now latest MUST return visibly stale with reasons
            res2 = await get_latest_cross_domain_validation(project_id=p.id, current_user=user_eng, db=db)
            assert res2.data.is_stale is True
            assert len(res2.data.staleness_reasons) > 0
            assert any("mismatch" in r.lower() for r in res2.data.staleness_reasons)

    @pytest.mark.asyncio
    async def test_foreign_tenant_and_project_authorization_all_routes(self):
        """Verifies strict 404/403 authorization boundaries across tenant and project IDs."""
        from app.core.database import AsyncSessionLocal
        from app.api.v1.routes.cross_domain import (
            get_latest_cross_domain_validation,
            get_cross_domain_validation,
            list_cross_domain_validations,
            run_cross_domain_validation,
        )
        user_a = AuthenticatedUser(id=str(uuid.uuid4()), email="a@tenant-a.com", role="engineer", tenant_id="tenant-A")
        user_b = AuthenticatedUser(id=str(uuid.uuid4()), email="b@tenant-b.com", role="engineer", tenant_id="tenant-B")
        user_readonly = AuthenticatedUser(id=str(uuid.uuid4()), email="ro@tenant-a.com", role="viewer", tenant_id="tenant-A")

        async with AsyncSessionLocal() as db:
            p_a = Project(id=str(uuid.uuid4()), tenant_id="tenant-A", name="Project A", project_type=ProjectType.CIRCUIT.value, owner_id=user_a.id)
            db.add(p_a)
            await db.commit()

            # 1. Foreign tenant cannot access latest route
            with pytest.raises(HTTPException) as exc1:
                await get_latest_cross_domain_validation(project_id=p_a.id, current_user=user_b, db=db)
            assert exc1.value.status_code == 404

            # 2. Foreign tenant cannot access validations list route
            with pytest.raises(HTTPException) as exc2:
                await list_cross_domain_validations(project_id=p_a.id, current_user=user_b, db=db)
            assert exc2.value.status_code == 404

            # 3. Read-only user cannot execute validation (403 Forbidden)
            with pytest.raises(HTTPException) as exc3:
                await run_cross_domain_validation(project_id=p_a.id, current_user=user_readonly, db=db)
            assert exc3.value.status_code == 403


