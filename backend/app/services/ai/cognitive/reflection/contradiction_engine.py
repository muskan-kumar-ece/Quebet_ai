import re
from typing import Any, Dict, List, Optional, Tuple
from app.models.db.cognitive import ReasoningFindingType, ReasoningFindingSeverity


class UnitNormalizer:
    """
    Normalizes electrical and physical units to base SI units for deterministic comparison,
    preventing false positives from formatting differences (e.g. 3.3V vs 3.30V, 500mA vs 0.5A).
    """

    VOLTAGE_UNITS = {"v": 1.0, "mv": 1e-3, "uv": 1e-6, "kv": 1e3}
    CURRENT_UNITS = {"a": 1.0, "ma": 1e-3, "ua": 1e-6, "ka": 1e3}
    POWER_UNITS = {"w": 1.0, "mw": 1e-3, "uw": 1e-6, "kw": 1e3}
    RESISTANCE_UNITS = {"ohm": 1.0, "mohm": 1e-3, "kohm": 1e3, "mohm_mega": 1e6, "k": 1e3}
    TEMP_UNITS = {"c": 1.0, "k": 1.0}
    CAPACITANCE_UNITS = {"f": 1.0, "mf": 1e-3, "uf": 1e-6, "nf": 1e-9, "pf": 1e-12}
    INDUCTANCE_UNITS = {"h": 1.0, "mh": 1e-3, "uh": 1e-6, "nh": 1e-9, "ph": 1e-12}
    FREQUENCY_UNITS = {"hz": 1.0, "khz": 1e3, "mhz": 1e6, "ghz": 1e9, "thz": 1e12}

    @classmethod
    def parse_value_unit(cls, raw: Any) -> Optional[Tuple[float, str]]:
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return float(raw), "unitless"

        text = str(raw).strip().lower()
        prefix_currency = False
        if text.startswith("$"):
            text = text[1:].strip()
            prefix_currency = True

        # Regex matching numbers with optional scientific notation and unit suffix
        match = re.match(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[e][-+]?\d+)?)\s*([a-z°%Ωµμkmawv\-_/$]*)$", text)
        if not match:
            return None

        val_str, unit_str = match.groups()
        try:
            val = float(val_str)
        except ValueError:
            return None

        unit = unit_str.replace("°", "").replace("ω", "ohm").replace("µ", "u").replace("μ", "u").strip()

        if prefix_currency or unit == "$":
            return round(val, 4), "$"
        if unit == "%":
            return round(val, 4), "%"
        if unit == "db":
            return round(val, 4), "dB"

        # Voltage
        if unit in cls.VOLTAGE_UNITS:
            return round(val * cls.VOLTAGE_UNITS[unit], 9), "V"
        # Current
        if unit in cls.CURRENT_UNITS:
            return round(val * cls.CURRENT_UNITS[unit], 9), "A"
        # Power
        if unit in cls.POWER_UNITS:
            return round(val * cls.POWER_UNITS[unit], 9), "W"
        # Resistance
        if unit in cls.RESISTANCE_UNITS or unit == "r":
            scale = 1.0
            if unit.startswith("k") or unit == "k":
                scale = 1e3
            elif unit.startswith("m") and "ohm" in unit and unit != "mohm":
                scale = 1e6
            elif unit == "mohm":
                scale = 1e-3
            return round(val * scale, 9), "Ohm"
        # Temperature
        if unit in ("c", "degc", "deg_c"):
            return round(val, 9), "°C"
        # Capacitance
        if unit in cls.CAPACITANCE_UNITS:
            return round(val * cls.CAPACITANCE_UNITS[unit], 18), "F"
        # Inductance
        if unit in cls.INDUCTANCE_UNITS:
            return round(val * cls.INDUCTANCE_UNITS[unit], 18), "H"
        # Frequency
        if unit in cls.FREQUENCY_UNITS:
            return round(val * cls.FREQUENCY_UNITS[unit], 9), "Hz"

        return val, unit or "unitless"

    @classmethod
    def parse_range(cls, raw: Any) -> Optional[Tuple[float, float, str]]:
        if raw is None:
            return None
        text = str(raw).strip()
        match = re.search(r"^(.*?)\s+(?:to|\.\.|\-)\s+(.*)$", text, re.IGNORECASE)
        if match:
            part1, part2 = match.groups()
            res1 = cls.parse_value_unit(part1.strip())
            res2 = cls.parse_value_unit(part2.strip())
            if res1 and res2:
                v1, u1 = res1
                v2, u2 = res2
                unit = u2 if u2 != "unitless" else u1
                return min(v1, v2), max(v1, v2), unit
        return None


class EngineeringContradictionEngine:
    """
    Deterministic contradiction detector comparing physical parameters,
    operating points, absolute maximum ratings, and explicit engineering assumptions.
    """

    TOLERANCE_EPSILON = 1e-6

    @classmethod
    def check_contradictions(
        cls,
        execution_results: List[Dict[str, Any]],
        requirements: List[Dict[str, Any]],
        assumptions: List[Dict[str, Any]],
        context_payload: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        # 1. Operating Current vs Requirement / Maximum Limit
        findings.extend(cls._check_electrical_limits(execution_results, requirements))

        # 2. Voltage Tolerances & Operating Points
        findings.extend(cls._check_voltage_contradictions(execution_results, requirements))

        # 3. Conflicting Engineering Assumptions
        findings.extend(cls._check_assumption_conflicts(assumptions))

        # 4. Context Payload / Component Ratings vs Calculated Stress
        if context_payload:
            findings.extend(cls._check_component_stress_limits(execution_results, context_payload))

        return findings

    @classmethod
    def _check_electrical_limits(
        cls,
        execution_results: List[Dict[str, Any]],
        requirements: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        findings = []

        # Build requirement lookup by name or key
        req_limits: Dict[str, Tuple[float, str, str]] = {}  # key -> (normalized_limit, unit, original_req_id)
        for req in requirements:
            req_id = req.get("id") or req.get("name") or "REQ"
            # Look for max current / power / voltage constraints
            target = req.get("target_property") or req.get("property") or req.get("name", "")
            limit_val = req.get("max_value") or req.get("limit") or req.get("value")
            if target and limit_val is not None:
                parsed = UnitNormalizer.parse_value_unit(limit_val)
                if parsed:
                    req_limits[str(target).lower()] = (parsed[0], parsed[1], str(req_id))

        for res in execution_results:
            details = res.get("details", {})
            if not isinstance(details, dict):
                continue

            for prop, val in details.items():
                prop_key = str(prop).lower()
                parsed_val = UnitNormalizer.parse_value_unit(val)
                if not parsed_val:
                    continue

                val_base, unit = parsed_val

                # Check against matching requirement limit
                matching_limit = None
                for req_key, (lim_base, lim_unit, req_id) in req_limits.items():
                    if (req_key in prop_key or prop_key in req_key) and unit == lim_unit:
                        matching_limit = (lim_base, lim_unit, req_id, req_key)
                        break

                if matching_limit:
                    lim_base, lim_unit, req_id, req_key = matching_limit
                    # If calculated value strictly exceeds requirement upper limit
                    if val_base > lim_base + cls.TOLERANCE_EPSILON:
                        findings.append({
                            "finding_type": ReasoningFindingType.CONTRADICTORY_RESULT.value,
                            "severity": ReasoningFindingSeverity.CRITICAL.value,
                            "title": f"Electrical Parameter Violation: {prop} exceeds requirement",
                            "description": (
                                f"Calculated value for '{prop}' ({val}) exceeds requirement '{req_key}' "
                                f"limit of {lim_base} {lim_unit} by {(val_base - lim_base):.4g} {lim_unit}."
                            ),
                            "affected_entity_type": "REQUIREMENT",
                            "affected_entity_id": req_id,
                            "evidence_references": [res.get("task_id", "execution_result")],
                            "deterministic_facts": {
                                "property": prop,
                                "calculated_normalized": val_base,
                                "requirement_limit_normalized": lim_base,
                                "unit": lim_unit,
                                "raw_calculated": val,
                            },
                            "recommended_remedy": f"Recalculate operating parameters or adjust component sizing to maintain {prop} within {lim_base} {lim_unit}.",
                            "follow_up_capability": "operating_point_recalculation",
                        })

        return findings

    @classmethod
    def _check_voltage_contradictions(
        cls,
        execution_results: List[Dict[str, Any]],
        requirements: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        findings = []
        for res in execution_results:
            violations = res.get("violations", [])
            for v in violations:
                if isinstance(v, dict) and "voltage" in str(v).lower():
                    findings.append({
                        "finding_type": ReasoningFindingType.CONTRADICTORY_RESULT.value,
                        "severity": ReasoningFindingSeverity.CRITICAL.value,
                        "title": f"Deterministic Voltage Contradiction: {v.get('rule', 'Voltage Rail Limit')}",
                        "description": v.get("message", "Calculated operating voltage violates design rail tolerances."),
                        "affected_entity_type": "CIRCUIT",
                        "affected_entity_id": v.get("ref_des"),
                        "evidence_references": [res.get("task_id", "analysis_task")],
                        "deterministic_facts": v,
                        "recommended_remedy": "Reconfigure voltage divider or regulator feedback network.",
                        "follow_up_capability": "operating_point_recalculation",
                    })
        return findings

    @classmethod
    def _check_assumption_conflicts(
        cls,
        assumptions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        findings = []
        ambient_temps: Dict[str, float] = {}

        for a in assumptions:
            name = str(a.get("name", "")).lower()
            text = str(a.get("statement", "") or a.get("description", "")).lower()
            a_id = str(a.get("id") or a.get("name") or "ASSUMPTION")

            if "ambient" in name or "ambient" in text or "temperature" in name:
                parsed = UnitNormalizer.parse_value_unit(a.get("value") or text)
                if parsed and parsed[1] in ("°C", "unitless"):
                    ambient_temps[a_id] = parsed[0]

        if len(ambient_temps) > 1:
            vals = list(ambient_temps.values())
            if max(vals) - min(vals) > cls.TOLERANCE_EPSILON:
                keys = list(ambient_temps.keys())
                findings.append({
                    "finding_type": ReasoningFindingType.ASSUMPTION_CONFLICT.value,
                    "severity": ReasoningFindingSeverity.WARNING.value,
                    "title": "Conflicting Ambient Temperature Assumptions Detected",
                    "description": (
                        f"Mutually contradictory ambient operating temperatures assumed across subsystems: "
                        f"{', '.join(f'{k}={v}°C' for k, v in ambient_temps.items())}."
                    ),
                    "affected_entity_type": "ASSUMPTION",
                    "affected_entity_id": keys[0],
                    "evidence_references": keys,
                    "deterministic_facts": {"ambient_temperatures": ambient_temps},
                    "recommended_remedy": "Harmonize operating temperature assumptions across all design subsystems.",
                    "follow_up_capability": "knowledge_lookup",
                })

        return findings

    @classmethod
    def _check_component_stress_limits(
        cls,
        execution_results: List[Dict[str, Any]],
        context_payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        findings = []
        components = context_payload.get("components", [])

        # Map component absolute ratings
        ratings: Dict[str, Dict[str, Any]] = {}
        for c in components:
            ref_des = c.get("ref_des")
            if ref_des:
                ratings[ref_des] = c.get("maximum_ratings", {})

        for res in execution_results:
            details = res.get("details", {})
            ref_des = details.get("ref_des") or res.get("ref_des")
            if ref_des and ref_des in ratings:
                c_ratings = ratings[ref_des]
                # Compare max current
                if "max_current" in c_ratings and "operating_current" in details:
                    max_i = UnitNormalizer.parse_value_unit(c_ratings["max_current"])
                    act_i = UnitNormalizer.parse_value_unit(details["operating_current"])
                    if max_i and act_i and max_i[1] == act_i[1] and act_i[0] > max_i[0]:
                        findings.append({
                            "finding_type": ReasoningFindingType.CONTRADICTORY_RESULT.value,
                            "severity": ReasoningFindingSeverity.CRITICAL.value,
                            "title": f"Component Absolute Maximum Exceeded: {ref_des}",
                            "description": (
                                f"Component {ref_des} operating current ({details['operating_current']}) "
                                f"exceeds absolute maximum rating of {c_ratings['max_current']}."
                            ),
                            "affected_entity_type": "CIRCUIT",
                            "affected_entity_id": ref_des,
                            "evidence_references": [ref_des],
                            "deterministic_facts": {
                                "ref_des": ref_des,
                                "operating_current": act_i[0],
                                "max_rating": max_i[0],
                                "unit": max_i[1],
                            },
                            "recommended_remedy": f"Select higher-rated component or reduce load on {ref_des}.",
                            "follow_up_capability": "component_derating_check",
                        })

        return findings
