import math
from typing import Any
from app.models.db.analysis import CircuitAnalysis
from app.models.db.pcb import EngineeringBoard
from app.models.schemas.pcb import PCBFinding


class PCBThermalEngine:
    """
    Thermal PCB placement intelligence engine.
    Connects Wave 3 component power dissipation calculations to physical placement.
    Identifies high-power hotspot clustering risks.
    Strict Invariant:
    Never fabricates junction temperatures or thermal conductivity values.
    Rule:
    - PCB016: Thermal placement issue
    """

    POWER_HOTSPOT_THRESHOLD_W = 0.5  # Components dissipating > 0.5W considered thermal sources
    HOTSPOT_SEPARATION_MIN_MM = 10.0  # Minimum 10mm separation between concentrated heat sources

    @classmethod
    def evaluate(
        cls,
        board: EngineeringBoard,
        analysis: CircuitAnalysis | None = None,
        min_separation_mm: float | None = None,
    ) -> list[PCBFinding]:
        findings: list[PCBFinding] = []
        min_sep = min_separation_mm or cls.HOTSPOT_SEPARATION_MIN_MM

        footprints = getattr(board, "footprints", [])
        fp_by_ref = {fp.ref_des.upper(): fp for fp in footprints}

        # Extract calculated powers from Wave 3 analysis
        comp_powers: dict[str, float] = {}
        if analysis and analysis.calculations:
            for calc in analysis.calculations:
                if "POWER" in calc.get("type", "").upper():
                    target = str(calc.get("target") or calc.get("component") or "").upper()
                    val = calc.get("value")
                    if val is not None and isinstance(val, (int, float)):
                        comp_powers[target] = float(val)

        # Identify hot components placed on PCB
        hot_components: list[tuple[str, Any, float]] = []
        for ref, fp in fp_by_ref.items():
            power = comp_powers.get(ref, 0.0)
            if power >= cls.POWER_HOTSPOT_THRESHOLD_W:
                hot_components.append((ref, fp, power))

        # Check proximity between hot components
        for i in range(len(hot_components)):
            ref1, fp1, p1 = hot_components[i]
            for j in range(i + 1, len(hot_components)):
                ref2, fp2, p2 = hot_components[j]
                dist = math.hypot(fp1.pos_x - fp2.pos_x, fp1.pos_y - fp2.pos_y)
                if dist < min_sep:
                    findings.append(
                        PCBFinding(
                            rule_id="PCB016",
                            severity="WARNING",
                            category="THERMAL",
                            element_ref=f"{ref1} <-> {ref2}",
                            actual_value=round(dist, 2),
                            required_limit=min_sep,
                            unit="mm",
                            status="VIOLATED",
                            message=(
                                f"Thermal hotspot concentration: heat-dissipating components {ref1} ({p1:.2f}W) "
                                f"and {ref2} ({p2:.2f}W) are placed only {dist:.2f} mm apart (< {min_sep} mm)."
                            ),
                        )
                    )

        return findings
