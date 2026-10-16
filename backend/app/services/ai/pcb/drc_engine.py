from typing import Any
from app.models.db.analysis import CircuitAnalysis
from app.models.db.circuit import Circuit
from app.models.db.pcb import EngineeringBoard
from app.models.schemas.pcb import PCBConstraintEvaluation, PCBFinding
from app.services.ai.pcb.connectivity_engine import PCBConnectivityEngine
from app.services.ai.pcb.consistency_engine import SchematicPCBConsistencyEngine
from app.services.ai.pcb.decoupling_engine import PCBDecouplingEngine
from app.services.ai.pcb.geometry_engine import PCBGeometryEngine
from app.services.ai.pcb.high_speed_engine import PCBHighSpeedEngine
from app.services.ai.pcb.placement_engine import PCBPlacementEngine
from app.services.ai.pcb.thermal_engine import PCBThermalEngine
from app.services.ai.pcb.trace_current_engine import PCBTraceCurrentEngine
from app.services.ai.pcb.via_engine import PCBViaEngine


class PCBRuleEngine:
    """
    Deterministic PCB Design Rule Check (DRC) and Constraint Orchestrator.
    Executes rules PCB001 through PCB016 without synthetic scoring.
    """

    RULESET_VERSION = "1.0-deterministic"

    @classmethod
    def run_drc(
        cls,
        circuit: Circuit,
        board: EngineeringBoard,
        analysis: CircuitAnalysis | None = None,
    ) -> tuple[list[PCBFinding], list[PCBConstraintEvaluation], dict[str, Any]]:
        all_findings: list[PCBFinding] = []
        all_evaluations: list[PCBConstraintEvaluation] = []

        # 1. Schematic <-> PCB Consistency (PCB001, PCB002, PCB003, PCB004, PCB012, PCB013)
        sync_findings = SchematicPCBConsistencyEngine.validate(circuit, board)
        all_findings.extend(sync_findings)

        # 2. Net Connectivity (PCB005, PCB006)
        conn_findings = PCBConnectivityEngine.analyze_connectivity(board)
        all_findings.extend(conn_findings)

        # 3. Geometric Clearance & Board Edge (PCB007, PCB008)
        geo_findings = PCBGeometryEngine.evaluate_clearances(board)
        all_findings.extend(geo_findings)

        # 4. Placement Constraints (PCB011)
        place_findings, place_evals = PCBPlacementEngine.evaluate(board)
        all_findings.extend(place_findings)
        all_evaluations.extend(place_evals)

        # 5. Trace Width & Current Capacity (PCB009)
        trace_findings = PCBTraceCurrentEngine.evaluate(board, analysis)
        all_findings.extend(trace_findings)

        # 6. Via Constraints (PCB010)
        via_findings = PCBViaEngine.evaluate(board)
        all_findings.extend(via_findings)

        # 7. Decoupling Proximity (PCB014)
        decouple_findings = PCBDecouplingEngine.evaluate(circuit, board)
        all_findings.extend(decouple_findings)

        # 8. High-Speed & Differential Pairs (PCB015)
        hs_findings = PCBHighSpeedEngine.evaluate(board)
        all_findings.extend(hs_findings)

        # 9. Thermal Hotspot Proximity (PCB016)
        thermal_findings = PCBThermalEngine.evaluate(board, analysis)
        all_findings.extend(thermal_findings)

        # Categorical metrics only (Zero synthetic scoring)
        error_count = sum(1 for f in all_findings if f.severity == "ERROR")
        warning_count = sum(1 for f in all_findings if f.severity == "WARNING")
        info_count = sum(1 for f in all_findings if f.severity == "INFO")

        metrics = {
            "total_findings": len(all_findings),
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "is_drc_clean": error_count == 0,
            "rules_evaluated": [
                "PCB001", "PCB002", "PCB003", "PCB004", "PCB005", "PCB006",
                "PCB007", "PCB008", "PCB009", "PCB010", "PCB011", "PCB012",
                "PCB013", "PCB014", "PCB015", "PCB016"
            ],
        }

        return all_findings, all_evaluations, metrics
