from typing import Any
from app.models.db.analysis import CircuitAnalysis
from app.models.db.circuit import Circuit
from app.models.schemas.simulation import (
    SimulationConstraintEvaluation,
    SimulationDiscrepancy,
)
from app.services.ai.analysis.spec_resolver import ComponentSpecificationResolver


class SimulationInterpretationService:
    """
    Deterministic cross-comparison and constraint evaluation for SPICE simulation outputs.
    Compares simulation results against analytical calculations (Wave 3) and component ratings (Wave 2).
    Enforces ZERO synthetic scoring: reports only physical quantities, margins, and categorical flags.
    """

    # Strictly a diagnostic discrepancy threshold for triggering human review.
    # NOT a universal engineering tolerance, correctness threshold, safety threshold, or verification gate.
    DIAGNOSTIC_DISCREPANCY_THRESHOLD = 0.05
    DISCREPANCY_THRESHOLD = DIAGNOSTIC_DISCREPANCY_THRESHOLD

    @classmethod
    def compare_with_analytical_analysis(
        cls,
        analysis: CircuitAnalysis | None,
        node_voltages: dict[str, float],
        branch_currents: dict[str, float],
    ) -> list[SimulationDiscrepancy]:
        """
        Compares simulation results against Wave 3 deterministic analytical calculations.
        Returns categorical comparison findings.
        """
        discrepancies: list[SimulationDiscrepancy] = []
        if not analysis or not analysis.calculations:
            return discrepancies

        # Normalize lookup keys for case-insensitive match
        norm_voltages = {k.lower(): v for k, v in node_voltages.items()}
        norm_currents = {k.lower(): v for k, v in branch_currents.items()}

        for calc in analysis.calculations:
            calc_type = calc.get("type", "").upper()
            target = calc.get("target") or calc.get("node") or calc.get("component") or ""
            target_norm = target.lower()
            unit = calc.get("unit", "")
            anal_val = calc.get("value")

            if anal_val is None or not isinstance(anal_val, (int, float)):
                continue

            sim_val = None
            param_name = ""

            if "VOLTAGE" in calc_type:
                param_name = "voltage"
                sim_val = norm_voltages.get(target_norm) or norm_voltages.get(f"v({target_norm})")
            elif "CURRENT" in calc_type:
                param_name = "current"
                sim_val = norm_currents.get(target_norm) or norm_currents.get(f"i({target_norm})")
            elif "POWER" in calc_type:
                param_name = "power"
                # If component power was calculated
                sim_i = norm_currents.get(target_norm)
                if sim_i is not None:
                    # Approximation or derived metric
                    sim_val = abs(sim_i * anal_val)  # fallback

            if sim_val is None:
                continue

            # Compute relative discrepancy
            denom = max(abs(anal_val), 1e-9)
            rel_delta = abs(sim_val - anal_val) / denom

            is_discrepancy = rel_delta > cls.DISCREPANCY_THRESHOLD
            flag = "ANALYSIS_SIMULATION_DISCREPANCY" if is_discrepancy else "MATCH"

            desc = (
                f"Discrepancy of {rel_delta*100:.1f}% between analytical calculation ({anal_val}{unit}) "
                f"and SPICE simulation ({sim_val:.4g}{unit}) for {target}."
                if is_discrepancy
                else f"Simulation matches analytical calculation within {rel_delta*100:.2f}% for {target}."
            )

            discrepancies.append(
                SimulationDiscrepancy(
                    element_or_node=target,
                    parameter=param_name,
                    analytical_value=float(anal_val),
                    simulation_value=float(sim_val),
                    unit=unit,
                    relative_delta=round(rel_delta, 4),
                    flag=flag,
                    description=desc,
                )
            )

        return discrepancies

    @classmethod
    def evaluate_constraints(
        cls,
        circuit: Circuit,
        node_voltages: dict[str, float],
        branch_currents: dict[str, float],
    ) -> list[SimulationConstraintEvaluation]:
        """
        Evaluates simulation outputs against component operating limits and ratings.
        Categorical evaluation: SATISFIED, VIOLATED, or UNKNOWN.
        """
        evaluations: list[SimulationConstraintEvaluation] = []
        norm_voltages = {k.lower(): v for k, v in node_voltages.items()}
        norm_currents = {k.lower(): v for k, v in branch_currents.items()}

        for comp in circuit.components:
            ref = (getattr(comp, "ref_des", None) or getattr(comp, "designator", None) or getattr(comp, "name", None) or "").lower()
            spec = ComponentSpecificationResolver.resolve(comp)

            # Check Maximum Operating Voltage
            max_v = spec.max_voltage
            if max_v is not None and max_v > 0:
                sim_v = norm_voltages.get(ref)
                if sim_v is not None:
                    abs_v = abs(sim_v)
                    is_violated = abs_v > max_v
                    margin = (max_v - abs_v) / max_v if max_v > 0 else 0.0
                    evaluations.append(
                        SimulationConstraintEvaluation(
                            constraint_id=f"V_MAX_{comp.id}",
                            component_id=comp.id,
                            parameter="voltage",
                            simulated_value=round(abs_v, 4),
                            limit_value=round(max_v, 4),
                            unit="V",
                            limit_type="MAX",
                            status="VIOLATED" if is_violated else "SATISFIED",
                            margin=round(margin, 4),
                            note="Operating voltage exceeds maximum rating" if is_violated else "Voltage within safe operating limits",
                        )
                    )

            # Check Maximum Operating Current
            max_i = spec.max_current
            if max_i is not None and max_i > 0:
                sim_i = norm_currents.get(ref)
                if sim_i is not None:
                    abs_i = abs(sim_i)
                    is_violated = abs_i > max_i
                    margin = (max_i - abs_i) / max_i if max_i > 0 else 0.0
                    evaluations.append(
                        SimulationConstraintEvaluation(
                            constraint_id=f"I_MAX_{comp.id}",
                            component_id=comp.id,
                            parameter="current",
                            simulated_value=round(abs_i, 6),
                            limit_value=round(max_i, 6),
                            unit="A",
                            limit_type="MAX",
                            status="VIOLATED" if is_violated else "SATISFIED",
                            margin=round(margin, 4),
                            note="Branch current exceeds maximum rating" if is_violated else "Current within safe operating limits",
                        )
                    )

            # Check Power Dissipation Limit
            max_p = spec.power_rating
            if max_p is not None and max_p > 0:
                sim_i = norm_currents.get(ref)
                sim_v = norm_voltages.get(ref)
                if sim_i is not None and sim_v is not None:
                    sim_p = abs(sim_v * sim_i)
                    is_violated = sim_p > max_p
                    margin = (max_p - sim_p) / max_p if max_p > 0 else 0.0
                    evaluations.append(
                        SimulationConstraintEvaluation(
                            constraint_id=f"P_MAX_{comp.id}",
                            component_id=comp.id,
                            parameter="power",
                            simulated_value=round(sim_p, 4),
                            limit_value=round(max_p, 4),
                            unit="W",
                            limit_type="MAX",
                            status="VIOLATED" if is_violated else "SATISFIED",
                            margin=round(margin, 4),
                            note="Power dissipation exceeds rating" if is_violated else "Power dissipation within thermal limits",
                        )
                    )

        return evaluations
