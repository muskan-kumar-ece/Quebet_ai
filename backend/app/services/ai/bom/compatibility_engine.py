"""
BOM Compatibility Engine.

Deterministic engineering compatibility evaluator for BOM lines and part candidates.
Strict Invariants:
- UNKNOWN != SATISFIED
- AVAILABLE != ENGINEERING_COMPATIBLE
- ZERO SYNTHETIC SCORING
- Returns structured categorical status and parameter-by-parameter findings.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.models.db.bom import ParameterEvaluationStatus, PartCompatibilityStatus
from app.models.schemas.bom import ParameterCompatibilityEvaluation
from app.services.ai.bom.package_compatibility_engine import BOMPackageCompatibilityEngine


class CompatibilityResult(BaseModel):
    """Encapsulates overall categorical status and per-parameter evaluations."""
    overall_status: PartCompatibilityStatus
    evaluations: List[ParameterCompatibilityEvaluation]
    parameter_evaluations: Dict[str, ParameterCompatibilityEvaluation] = Field(default_factory=dict)


class BOMCompatibilityEngine:
    """
    Deterministic engineering compatibility evaluator for BOM lines and part candidates.
    Evaluates nominal value, voltage, current, power ratings, tolerances, packages, and temperatures.
    """

    @classmethod
    def normalize_numeric_value(cls, val: Any) -> Optional[float]:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip()
        match = re.search(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?", s)
        if match:
            return float(match.group(0))
        return None

    @classmethod
    def evaluate(
        cls,
        requirements: Dict[str, Any],
        candidate_parameters: Dict[str, Any],
        candidate_package: Optional[str] = None,
        candidate_mpn: Optional[str] = None,
    ) -> Tuple[str, List[ParameterCompatibilityEvaluation]]:
        """
        Evaluates candidate engineering parameters against design requirements.
        Returns: (compatibility_status, list of evaluations)
        """
        evaluations: List[ParameterCompatibilityEvaluation] = []

        # 1. Nominal Value Check (Resistance / Capacitance / Inductance)
        req_nom = requirements.get("nominal_value")
        cand_nom = candidate_parameters.get("nominal_value") or candidate_parameters.get("value")
        if req_nom is not None:
            if cand_nom is None:
                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="nominal_value",
                        required_value=req_nom,
                        actual_value=None,
                        status=ParameterEvaluationStatus.UNKNOWN.value,
                        message="Candidate nominal value is UNKNOWN",
                    )
                )
            else:
                req_num = cls.normalize_numeric_value(req_nom)
                cand_num = cls.normalize_numeric_value(cand_nom)
                if req_num is not None and cand_num is not None:
                    is_match = abs(req_num - cand_num) <= 1e-4 * max(abs(req_num), 1.0)
                else:
                    is_match = str(req_nom).strip().upper() == str(cand_nom).strip().upper()

                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="nominal_value",
                        required_value=req_nom,
                        actual_value=cand_nom,
                        status=ParameterEvaluationStatus.SATISFIED.value
                        if is_match
                        else ParameterEvaluationStatus.CONFLICT.value,
                        message=f"Candidate nominal value {cand_nom} {'matches' if is_match else 'does not match'} required {req_nom}",
                    )
                )

        # 2. Voltage Rating (Candidate must be >= required)
        req_v = requirements.get("min_voltage_rating_v")
        if req_v is None:
            req_v = requirements.get("voltage_rating") or requirements.get("voltage_rating_v")
        cand_v = candidate_parameters.get("voltage_rating_v") or candidate_parameters.get("voltage_rating")
        if req_v is not None:
            cand_v_num = cls.normalize_numeric_value(cand_v)
            if cand_v_num is None:
                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="voltage_rating",
                        required_value=f">={req_v}V",
                        actual_value=cand_v,
                        status=ParameterEvaluationStatus.UNKNOWN.value,
                        unit="V",
                        message="Candidate voltage rating unknown",
                    )
                )
            else:
                is_v_ok = cand_v_num >= float(req_v)
                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="voltage_rating",
                        required_value=f">={req_v}V",
                        actual_value=f"{cand_v_num}V",
                        status=ParameterEvaluationStatus.SATISFIED.value
                        if is_v_ok
                        else ParameterEvaluationStatus.CONFLICT.value,
                        unit="V",
                        message=(
                            f"Candidate voltage rating {cand_v_num}V is sufficient (required >={req_v}V)"
                            if is_v_ok
                            else f"Insufficient voltage rating: candidate has {cand_v_num}V < required {req_v}V"
                        ),
                    )
                )

        # 3. Power Rating (Candidate must be >= required)
        req_p = requirements.get("min_power_rating_w")
        if req_p is None:
            req_p = requirements.get("power_rating") or requirements.get("power_rating_w")
        cand_p = candidate_parameters.get("power_rating_w") or candidate_parameters.get("power_rating")
        if req_p is not None:
            cand_p_num = cls.normalize_numeric_value(cand_p)
            if cand_p_num is None:
                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="power_rating",
                        required_value=f">={req_p}W",
                        actual_value=cand_p,
                        status=ParameterEvaluationStatus.UNKNOWN.value,
                        unit="W",
                        message="Candidate power rating unknown",
                    )
                )
            else:
                is_p_ok = cand_p_num >= float(req_p)
                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="power_rating",
                        required_value=f">={req_p}W",
                        actual_value=f"{cand_p_num}W",
                        status=ParameterEvaluationStatus.SATISFIED.value
                        if is_p_ok
                        else ParameterEvaluationStatus.CONFLICT.value,
                        unit="W",
                        message=(
                            f"Candidate power rating {cand_p_num}W is sufficient (required >={req_p}W)"
                            if is_p_ok
                            else f"Insufficient power rating: candidate has {cand_p_num}W < required {req_p}W"
                        ),
                    )
                )

        # 4. Current Rating (Candidate must be >= required)
        req_i = requirements.get("min_current_rating_a")
        if req_i is None:
            req_i = requirements.get("current_rating") or requirements.get("current_rating_a")
        cand_i = candidate_parameters.get("current_rating_a") or candidate_parameters.get("current_rating")
        if req_i is not None:
            cand_i_num = cls.normalize_numeric_value(cand_i)
            if cand_i_num is None:
                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="current_rating",
                        required_value=f">={req_i}A",
                        actual_value=cand_i,
                        status=ParameterEvaluationStatus.UNKNOWN.value,
                        unit="A",
                        message="Candidate current rating unknown",
                    )
                )
            else:
                is_i_ok = cand_i_num >= float(req_i)
                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="current_rating",
                        required_value=f">={req_i}A",
                        actual_value=f"{cand_i_num}A",
                        status=ParameterEvaluationStatus.SATISFIED.value
                        if is_i_ok
                        else ParameterEvaluationStatus.CONFLICT.value,
                        unit="A",
                        message=(
                            f"Candidate current rating {cand_i_num}A is sufficient (required >={req_i}A)"
                            if is_i_ok
                            else f"Insufficient current rating: candidate has {cand_i_num}A < required {req_i}A"
                        ),
                    )
                )

        # 5. Tolerance (Candidate tolerance must be <= required max tolerance)
        req_tol = requirements.get("max_tolerance_percent")
        if req_tol is None:
            req_tol = requirements.get("tolerance") or requirements.get("tolerance_pct")
        cand_tol = candidate_parameters.get("tolerance_percent") or candidate_parameters.get("tolerance")
        if req_tol is not None:
            cand_tol_num = cls.normalize_numeric_value(cand_tol)
            if cand_tol_num is None:
                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="tolerance",
                        required_value=f"<={req_tol}%",
                        actual_value=cand_tol,
                        status=ParameterEvaluationStatus.UNKNOWN.value,
                        unit="%",
                        message="Candidate tolerance unknown",
                    )
                )
            else:
                is_tol_ok = cand_tol_num <= float(req_tol)
                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="tolerance",
                        required_value=f"<={req_tol}%",
                        actual_value=f"{cand_tol_num}%",
                        status=ParameterEvaluationStatus.SATISFIED.value
                        if is_tol_ok
                        else ParameterEvaluationStatus.CONFLICT.value,
                        unit="%",
                        message=(
                            f"Candidate tolerance {cand_tol_num}% satisfies required <={req_tol}%"
                            if is_tol_ok
                            else f"Tolerance mismatch: candidate has ±{cand_tol_num}% > required max ±{req_tol}%"
                        ),
                    )
                )

        # 6. Physical Package / Footprint Compatibility
        req_pkg = requirements.get("package")
        req_fp = requirements.get("footprint")
        cand_pkg = candidate_package or candidate_parameters.get("package")
        if req_pkg or req_fp:
            pkg_status, pkg_msg = BOMPackageCompatibilityEngine.evaluate_package_compatibility(
                required_package=req_pkg,
                candidate_package=cand_pkg,
                pcb_footprint=req_fp,
            )
            evaluations.append(
                ParameterCompatibilityEvaluation(
                    parameter="package_footprint",
                    required_value=req_pkg or req_fp,
                    actual_value=cand_pkg,
                    status=pkg_status if pkg_status != ParameterEvaluationStatus.NOT_SATISFIED.value else ParameterEvaluationStatus.CONFLICT.value,
                    message=pkg_msg,
                )
            )

        # 7. Pin Count Check
        req_pins = requirements.get("pin_count")
        cand_pins = candidate_parameters.get("pin_count")
        if req_pins is not None:
            if cand_pins is None:
                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="pin_count",
                        required_value=req_pins,
                        actual_value=None,
                        status=ParameterEvaluationStatus.UNKNOWN.value,
                        message="Candidate pin count is UNKNOWN",
                    )
                )
            else:
                is_pins_ok = int(req_pins) == int(cand_pins)
                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="pin_count",
                        required_value=req_pins,
                        actual_value=cand_pins,
                        status=ParameterEvaluationStatus.SATISFIED.value
                        if is_pins_ok
                        else ParameterEvaluationStatus.CONFLICT.value,
                        message=(
                            f"Pin count match: {cand_pins} pins"
                            if is_pins_ok
                            else f"Pin count mismatch: candidate has {cand_pins} pins, required {req_pins}"
                        ),
                    )
                )

        # 8. Operating Temperature Range
        req_tmin = requirements.get("temp_min_c")
        req_tmax = requirements.get("temp_max_c")
        if req_tmin is None and req_tmax is None:
            req_temp = requirements.get("temp_range_c")
            if req_temp and isinstance(req_temp, (list, tuple)) and len(req_temp) == 2:
                req_tmin, req_tmax = float(req_temp[0]), float(req_temp[1])

        cand_tmin = candidate_parameters.get("temp_min_c")
        cand_tmax = candidate_parameters.get("temp_max_c")
        if cand_tmin is None and cand_tmax is None:
            cand_temp = candidate_parameters.get("operating_temperature") or candidate_parameters.get("temp_range_c")
            if cand_temp and isinstance(cand_temp, (list, tuple)) and len(cand_temp) == 2:
                cand_tmin, cand_tmax = float(cand_temp[0]), float(cand_temp[1])

        if req_tmin is not None and req_tmax is not None:
            if cand_tmin is None or cand_tmax is None:
                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="temperature_range",
                        required_value=f"[{req_tmin}..{req_tmax}]°C",
                        actual_value=None,
                        status=ParameterEvaluationStatus.UNKNOWN.value,
                        unit="°C",
                        message="Candidate operating temperature range is UNKNOWN",
                    )
                )
            else:
                is_temp_ok = (float(cand_tmin) <= float(req_tmin)) and (float(cand_tmax) >= float(req_tmax))
                evaluations.append(
                    ParameterCompatibilityEvaluation(
                        parameter="temperature_range",
                        required_value=f"[{req_tmin}..{req_tmax}]°C",
                        actual_value=f"[{cand_tmin}..{cand_tmax}]°C",
                        status=ParameterEvaluationStatus.SATISFIED.value
                        if is_temp_ok
                        else ParameterEvaluationStatus.CONFLICT.value,
                        unit="°C",
                        message=(
                            f"Temperature range [{cand_tmin}..{cand_tmax}]°C covers required [{req_tmin}..{req_tmax}]°C"
                            if is_temp_ok
                            else f"Insufficient temperature range: candidate [{cand_tmin}..{cand_tmax}]°C does not cover required [{req_tmin}..{req_tmax}]°C"
                        ),
                    )
                )

        # Derive categorical compatibility status
        if not evaluations:
            return PartCompatibilityStatus.UNKNOWN.value, evaluations

        has_violation = any(
            e.status in (ParameterEvaluationStatus.NOT_SATISFIED.value, ParameterEvaluationStatus.CONFLICT.value)
            for e in evaluations
        )
        has_unknown = any(e.status == ParameterEvaluationStatus.UNKNOWN.value for e in evaluations)

        if has_violation:
            overall_status = PartCompatibilityStatus.NOT_COMPATIBLE.value
        elif has_unknown:
            satisfied_count = sum(1 for e in evaluations if e.status == ParameterEvaluationStatus.SATISFIED.value)
            if satisfied_count > 0:
                overall_status = PartCompatibilityStatus.PARTIALLY_EVALUATED.value
            else:
                overall_status = PartCompatibilityStatus.UNKNOWN.value
        else:
            overall_status = PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value

        return overall_status, evaluations

    @classmethod
    def evaluate_candidate(
        cls,
        required_specs: Dict[str, Any],
        candidate_specs: Dict[str, Any],
        required_package: Optional[str] = None,
        candidate_package: Optional[str] = None,
        required_pin_count: Optional[int] = None,
        candidate_pin_count: Optional[int] = None,
    ) -> CompatibilityResult:
        req = dict(required_specs)
        if required_package and "package" not in req:
            req["package"] = required_package
        if required_pin_count and "pin_count" not in req:
            req["pin_count"] = required_pin_count

        cand = dict(candidate_specs)
        if candidate_package and "package" not in cand:
            cand["package"] = candidate_package
        if candidate_pin_count and "pin_count" not in cand:
            cand["pin_count"] = candidate_pin_count

        overall_str, evals = cls.evaluate(
            requirements=req,
            candidate_parameters=cand,
            candidate_package=cand.get("package"),
            candidate_mpn=cand.get("mpn"),
        )
        param_evals = {e.parameter: e for e in evals}
        return CompatibilityResult(
            overall_status=PartCompatibilityStatus(overall_str),
            evaluations=evals,
            parameter_evaluations=param_evals,
        )
