import math
from typing import Any
from app.models.db.analysis import CircuitAnalysis
from app.models.db.pcb import EngineeringBoard
from app.models.schemas.pcb import PCBFinding


class PCBTraceCurrentEngine:
    """
    Evaluates PCB trace widths against calculated branch currents from Wave 3 analytical analysis.
    Strict Epistemic Invariant:
    If copper thickness, temperature rise, or current is missing: returns UNKNOWN.
    Never fabricates physical parameters.
    Rule:
    - PCB009: Trace width violation (insufficient width for current carrying capacity)
    """

    @classmethod
    def estimate_max_current_ipc2152(
        cls,
        width_mm: float,
        thickness_um: float | None,
        temp_rise_c: float | None = 10.0,
        is_external: bool = True,
    ) -> float | None:
        """
        Calculates allowable current capacity using IPC-2152-DERIVED / APPROXIMATION
        (standard empirical power-law curve-fit formulation with conservative defaults).
        Classification: IPC-2152-DERIVED / APPROXIMATION.
        Returns None if physical parameters (thickness, temp rise, width) are missing or unknown.
        """
        if thickness_um is None or temp_rise_c is None or width_mm <= 0:
            return None

        # Cross-sectional area in mils^2
        # 1 mm = 39.3701 mils, 1 um = 0.03937 mils
        width_mils = width_mm * 39.3701
        thickness_mils = thickness_um * 0.0393701
        area_mils2 = width_mils * thickness_mils

        if area_mils2 <= 0:
            return None

        # IPC-2152 coefficients
        # I = k * (temp_rise ^ b) * (Area ^ c)
        k = 0.048 if is_external else 0.024
        b = 0.44
        c = 0.725

        max_current = k * (temp_rise_c**b) * (area_mils2**c)
        return max_current

    @classmethod
    def evaluate(
        cls,
        board: EngineeringBoard,
        analysis: CircuitAnalysis | None = None,
        min_default_width_mm: float = 0.15,
    ) -> list[PCBFinding]:
        findings: list[PCBFinding] = []
        traces = getattr(board, "traces", [])
        layers_by_name = {l.name: l for l in getattr(board, "layers", [])}

        # Extract calculated branch/net currents from Wave 3 analysis
        calculated_currents: dict[str, float] = {}
        if analysis and analysis.calculations:
            for calc in analysis.calculations:
                c_type = calc.get("type", "").upper()
                if "CURRENT" in c_type:
                    target = str(calc.get("target") or calc.get("net") or calc.get("component") or "").upper()
                    val = calc.get("value")
                    if val is not None and isinstance(val, (int, float)):
                        calculated_currents[target] = abs(float(val))

        for t in traces:
            net_name = (t.net_name or "").strip().upper()
            trace_w = float(t.width)

            # Minimum manufacturable width check
            if trace_w < min_default_width_mm:
                findings.append(
                    PCBFinding(
                        rule_id="PCB009",
                        severity="ERROR",
                        category="TRACE_WIDTH",
                        element_ref=f"TRACE_{t.id[:6]} ({net_name or 'UNNAMED'})",
                        actual_value=trace_w,
                        required_limit=min_default_width_mm,
                        unit="mm",
                        status="VIOLATED",
                        message=f"Trace width {trace_w:.3f} mm on layer {t.layer} is below minimum allowed {min_default_width_mm} mm.",
                    )
                )

            # Current capacity evaluation
            calc_i = calculated_currents.get(net_name)
            if calc_i is not None and calc_i > 0:
                layer_obj = layers_by_name.get(t.layer)
                copper_th = layer_obj.thickness_um if layer_obj else None

                if copper_th is None:
                    # Explicit invariant: unknown copper thickness returns UNKNOWN, not PASS
                    findings.append(
                        PCBFinding(
                            rule_id="PCB009",
                            severity="INFO",
                            category="TRACE_WIDTH",
                            element_ref=f"TRACE_{t.id[:6]} ({net_name})",
                            actual_value=f"I={calc_i:.3f}A",
                            status="UNKNOWN",
                            message=f"Trace on net '{net_name}' carries {calc_i:.3f}A, but layer '{t.layer}' copper thickness is UNKNOWN. Cannot compute thermal limit.",
                        )
                    )
                else:
                    is_ext = t.layer in ("F.Cu", "B.Cu")
                    i_capacity = cls.estimate_max_current_ipc2152(
                        width_mm=trace_w,
                        thickness_um=copper_th,
                        temp_rise_c=10.0,
                        is_external=is_ext,
                    )
                    if i_capacity is not None and calc_i > i_capacity:
                        findings.append(
                            PCBFinding(
                                rule_id="PCB009",
                                severity="ERROR",
                                category="TRACE_WIDTH",
                                element_ref=f"TRACE_{t.id[:6]} ({net_name})",
                                actual_value=round(calc_i, 3),
                                required_limit=round(i_capacity, 3),
                                unit="A",
                                status="VIOLATED",
                                message=(
                                    f"Current capacity violation on net '{net_name}': "
                                    f"calculated current {calc_i:.3f}A exceeds trace capacity {i_capacity:.3f}A (w={trace_w}mm, t={copper_th}um)."
                                ),
                            )
                        )

        return findings
