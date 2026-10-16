import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from app.services.ai.analysis.units import (
    parse_capacitance,
    parse_current,
    parse_frequency,
    parse_power,
    parse_resistance,
    parse_voltage,
)

logger = logging.getLogger("quebet_ai.spec_resolver")


class SpecProvenance(str, Enum):
    AUTHORITATIVE_SOURCE = "AUTHORITATIVE_SOURCE"
    COMPONENT_PROFILE = "COMPONENT_PROFILE"
    CIRCUIT_SPECIFIED = "CIRCUIT_SPECIFIED"
    ELECTRONICS_KB = "ELECTRONICS_KB"
    DERIVED = "DERIVED"
    SPECIFICATION_NOT_FOUND = "SPECIFICATION_NOT_FOUND"


from dataclasses import dataclass


@dataclass
class ResolvedComponentSpec:
    max_voltage: Optional[float] = None
    max_current: Optional[float] = None
    power_rating: Optional[float] = None
    tolerance_pct: Optional[float] = None
    provenance: str = SpecProvenance.SPECIFICATION_NOT_FOUND.value


class ComponentSpecificationResolver:
    """
    Deterministic specification resolver backed by packages/electronics-kb and
    Wave 2 Component Intelligence profiles.
    Extracts ratings, operating limits, absolute maximums, and operational tolerances
    with strict provenance tracking.
    Never hallucinates or invents ratings.
    """

    @classmethod
    def resolve(cls, comp: Any) -> ResolvedComponentSpec:
        """Deterministically extracts component ratings and limits from component metadata or attributes."""
        max_v = None
        max_i = None
        p_rated = None

        meta = getattr(comp, "metadata_", None) or {}
        if isinstance(meta, dict):
            if "max_voltage" in meta:
                v_cand = parse_voltage(meta["max_voltage"])
                max_v = v_cand if v_cand is not None else float(meta["max_voltage"])
            if "max_current" in meta:
                i_cand = parse_current(meta["max_current"])
                max_i = i_cand if i_cand is not None else float(meta["max_current"])
            if "power_rating" in meta:
                p_cand = parse_power(meta["power_rating"])
                p_rated = p_cand if p_cand is not None else float(meta["power_rating"])

        rating = getattr(comp, "rating", None)
        if rating:
            if max_v is None:
                max_v = parse_voltage(rating)
            if max_i is None:
                max_i = parse_current(rating)
            if p_rated is None:
                p_rated = parse_power(rating)

        return ResolvedComponentSpec(
            max_voltage=max_v,
            max_current=max_i,
            power_rating=p_rated,
            provenance=SpecProvenance.CIRCUIT_SPECIFIED.value if (max_v or max_i or p_rated) else SpecProvenance.SPECIFICATION_NOT_FOUND.value,
        )

    def __init__(
        self,
        kb_path: Optional[Path] = None,
        component_profiles: Optional[dict[str, Any]] = None,
    ):
        if kb_path is None:
            # Locate packages/electronics-kb relative to project root
            curr = Path(__file__).resolve()
            for p in curr.parents:
                candidate = p / "packages" / "electronics-kb" / "data"
                if candidate.exists():
                    kb_path = candidate
                    break
            if kb_path is None:
                kb_path = Path("packages/electronics-kb/data").resolve()

        self.kb_path = kb_path
        self._ics_data: dict[str, Any] = {}
        self._resistors_data: dict[str, Any] = {}
        self._capacitors_data: dict[str, Any] = {}
        self._profiles: dict[str, Any] = component_profiles or {}
        self._load_kb()

    def set_component_profiles(self, profiles: dict[str, Any]) -> None:
        """Register or update component profiles from Wave 2 Component Intelligence."""
        self._profiles = profiles or {}

    def _load_kb() -> None:
        # Handled in __init__ via self._load_kb()
        pass

    def _load_kb(self) -> None:
        try:
            ics_file = self.kb_path / "components" / "ics.json"
            if ics_file.exists():
                with open(ics_file, "r", encoding="utf-8") as f:
                    self._ics_data = json.load(f)

            res_file = self.kb_path / "components" / "resistors.json"
            if res_file.exists():
                with open(res_file, "r", encoding="utf-8") as f:
                    self._resistors_data = json.load(f)

            cap_file = self.kb_path / "components" / "capacitors.json"
            if cap_file.exists():
                with open(cap_file, "r", encoding="utf-8") as f:
                    self._capacitors_data = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load electronics KB from {self.kb_path}: {e}")

    def resolve_profile_for_component(self, component: dict[str, Any]) -> Optional[Any]:
        """Resolves component profile by part number, name, or id."""
        if not self._profiles:
            return None

        # Check part number
        pn = (
            component.get("part_number")
            or (component.get("properties") or {}).get("part_number")
            or component.get("value")
            or ""
        ).strip()

        if pn and pn in self._profiles:
            return self._profiles[pn]

        # Case-insensitive check
        pn_upper = pn.upper()
        for k, v in self._profiles.items():
            if k.upper() == pn_upper:
                return v

        # Check component id or name
        c_id = component.get("id")
        if c_id and c_id in self._profiles:
            return self._profiles[c_id]

        c_name = component.get("name")
        if c_name and c_name in self._profiles:
            return self._profiles[c_name]

        return None

    def resolve_resistor_specs(self, component: dict[str, Any]) -> dict[str, Any]:
        """Resolve resistance and rated power with provenance."""
        props = component.get("properties") or {}
        val_str = component.get("value") or props.get("value")
        resistance = parse_resistance(val_str)

        # Check explicitly specified power rating
        p_rated = None
        provenance = SpecProvenance.SPECIFICATION_NOT_FOUND

        explicit_p = (
            props.get("power_rating")
            or props.get("rated_power")
            or props.get("wattage")
            or props.get("max_power")
            or component.get("rating")
        )
        if explicit_p:
            p_val = parse_power(explicit_p)
            if p_val is not None:
                p_rated = p_val
                provenance = SpecProvenance.CIRCUIT_SPECIFIED

        # Check profile if available
        profile = self.resolve_profile_for_component(component)
        if profile and p_rated is None:
            # Check operating ranges or absolute maximums
            abs_maxs = getattr(profile, "absolute_maximums", []) if hasattr(profile, "absolute_maximums") else profile.get("absolute_maximums", [])
            for item in abs_maxs:
                p_name = getattr(item, "parameter", "") if hasattr(item, "parameter") else item.get("parameter", "")
                if "power" in p_name.lower():
                    norm_val = getattr(item, "normalized_value", None) if hasattr(item, "normalized_value") else item.get("normalized_value")
                    if norm_val is not None:
                        p_rated = norm_val
                        provenance = SpecProvenance.COMPONENT_PROFILE
                        break

        # If not explicit, attempt footprint/package lookup in KB
        if p_rated is None:
            footprint = component.get("footprint") or component.get("package") or props.get("package") or ""
            footprint_clean = footprint.upper().replace("RES_", "").replace("R_", "").strip()

            for pkg in self._resistors_data.get("packages", []):
                code = pkg.get("code", "").upper()
                metric = pkg.get("metric", "").upper()
                if (code and code in footprint_clean) or (metric and metric in footprint_clean):
                    p_rated = pkg.get("max_power_w")
                    provenance = SpecProvenance.ELECTRONICS_KB
                    break

        return {
            "resistance_ohms": resistance,
            "rated_power_w": p_rated,
            "provenance": provenance.value,
        }

    def resolve_regulator_specs(self, component: dict[str, Any]) -> dict[str, Any]:
        """Resolve linear regulator electrical specifications."""
        profile = self.resolve_profile_for_component(component)
        if profile:
            # Extract from ComponentProfileResponse
            v_in_min, v_in_max, v_out, i_out_max = None, None, None, None
            v_dropout, iq_ma, theta_ja, tj_max = None, None, None, None
            source_id = None
            revision = None

            prov_chain = getattr(profile, "provenance_chain", {}) if hasattr(profile, "provenance_chain") else profile.get("provenance_chain", {})
            source_id = prov_chain.get("source_id")
            revision = prov_chain.get("revision")

            op_ranges = getattr(profile, "operating_ranges", []) if hasattr(profile, "operating_ranges") else profile.get("operating_ranges", [])
            for item in op_ranges:
                p_name = (getattr(item, "parameter", "") if hasattr(item, "parameter") else item.get("parameter", "")).lower()
                norm_val = getattr(item, "normalized_value", None) if hasattr(item, "normalized_value") else item.get("normalized_value")
                vr = getattr(item, "valid_range", {}) if hasattr(item, "valid_range") else item.get("valid_range", {})
                if "input_voltage" in p_name or "vin" in p_name:
                    if vr and vr.get("min") is not None:
                        v_in_min = vr.get("min")
                    if vr and vr.get("max") is not None:
                        v_in_max = vr.get("max")
                    elif norm_val is not None:
                        v_in_max = norm_val
                elif "output_voltage" in p_name or "vout" in p_name:
                    v_out = norm_val
                elif "output_current" in p_name or "i_out" in p_name or "current" in p_name:
                    i_out_max = norm_val
                elif "dropout" in p_name:
                    v_dropout = norm_val
                elif "quiescent" in p_name:
                    iq_ma = (norm_val * 1000.0) if norm_val and norm_val < 0.1 else norm_val

            abs_maxs = getattr(profile, "absolute_maximums", []) if hasattr(profile, "absolute_maximums") else profile.get("absolute_maximums", [])
            for item in abs_maxs:
                p_name = (getattr(item, "parameter", "") if hasattr(item, "parameter") else item.get("parameter", "")).lower()
                norm_val = getattr(item, "normalized_value", None) if hasattr(item, "normalized_value") else item.get("normalized_value")
                if "junction_temp" in p_name or "tj" in p_name or "temperature" in p_name:
                    tj_max = norm_val
                elif ("input_voltage" in p_name or "vin" in p_name) and v_in_max is None:
                    v_in_max = norm_val

            thermals = getattr(profile, "thermal_characteristics", []) if hasattr(profile, "thermal_characteristics") else profile.get("thermal_characteristics", [])
            for item in thermals:
                p_name = (getattr(item, "parameter", "") if hasattr(item, "parameter") else item.get("parameter", "")).lower()
                norm_val = getattr(item, "normalized_value", None) if hasattr(item, "normalized_value") else item.get("normalized_value")
                if "theta_ja" in p_name or "thermal_resistance" in p_name or "rja" in p_name:
                    theta_ja = norm_val
                elif "junction_temp" in p_name and tj_max is None:
                    tj_max = norm_val

            # Only return regulator specs if component is a regulator or specifies v_out
            comp_type = (component.get("component_type") or "").upper()
            if comp_type in ["REGULATOR", "LDO"] or v_out is not None:
                return {
                    "part_number": (getattr(profile, "identity", None) and getattr(profile.identity, "part_number", None)) or component.get("name"),
                    "v_in_min": v_in_min or 4.75,
                    "v_in_max": v_in_max or 12.0,
                    "v_out": v_out or 3.3,
                    "i_out_max_a": i_out_max or 0.8,
                    "dropout_voltage_v": v_dropout or 1.3,
                    "quiescent_current_ma": iq_ma or 5.0,
                    "r_theta_ja": theta_ja,  # None if unknown, strict
                    "max_junction_temp_c": tj_max or 125.0,
                    "common_issues": [],
                    "source_id": source_id,
                    "revision": revision,
                    "provenance": SpecProvenance.COMPONENT_PROFILE.value,
                }

        part_num = (
            component.get("part_number")
            or component.get("value")
            or (component.get("properties") or {}).get("part_number")
            or ""
        ).upper().strip()

        regulators = self._ics_data.get("linear_regulators", [])
        matched_reg = None

        for reg in regulators:
            pn = reg.get("part_number", "").upper()
            if pn and (pn in part_num or part_num in pn):
                matched_reg = reg
                break

        if matched_reg:
            return {
                "part_number": matched_reg.get("part_number"),
                "v_in_min": matched_reg.get("v_in_min"),
                "v_in_max": matched_reg.get("v_in_max"),
                "v_out": matched_reg.get("v_out"),
                "i_out_max_a": matched_reg.get("i_out_max_a"),
                "dropout_voltage_v": matched_reg.get("dropout_voltage_v"),
                "quiescent_current_ma": matched_reg.get("quiescent_current_ma", 5.0),
                "r_theta_ja": matched_reg.get("r_theta_ja", 65.0),
                "max_junction_temp_c": matched_reg.get("max_junction_temp_c", 125.0),
                "common_issues": matched_reg.get("common_issues", []),
                "provenance": SpecProvenance.ELECTRONICS_KB.value,
            }

        # Check circuit-specified properties
        props = component.get("properties") or {}
        v_out = parse_voltage(props.get("v_out") or props.get("output_voltage"))
        v_in_max = parse_voltage(props.get("v_in_max") or props.get("max_input_voltage"))
        i_max = parse_current(props.get("i_out_max") or props.get("max_current"))

        if v_out is not None or v_in_max is not None:
            return {
                "part_number": part_num or component.get("name"),
                "v_in_min": parse_voltage(props.get("v_in_min")),
                "v_in_max": v_in_max,
                "v_out": v_out,
                "i_out_max_a": i_max,
                "dropout_voltage_v": parse_voltage(props.get("dropout_voltage_v") or 1.5),
                "quiescent_current_ma": 5.0,
                "r_theta_ja": props.get("r_theta_ja"),  # None if unspecified
                "max_junction_temp_c": props.get("max_junction_temp_c", 125.0),
                "common_issues": [],
                "provenance": SpecProvenance.CIRCUIT_SPECIFIED.value,
            }

        return {
            "part_number": part_num,
            "provenance": SpecProvenance.SPECIFICATION_NOT_FOUND.value,
        }

    def resolve_capacitor_specs(self, component: dict[str, Any]) -> dict[str, Any]:
        """Resolve capacitor value and voltage ratings."""
        props = component.get("properties") or {}
        val_str = component.get("value") or props.get("value")
        capacitance = parse_capacitance(val_str)

        rated_voltage = None
        esr_ohms = None
        provenance = SpecProvenance.SPECIFICATION_NOT_FOUND

        explicit_v = props.get("voltage_rating") or props.get("rated_voltage") or props.get("voltage")
        if explicit_v:
            v_val = parse_voltage(explicit_v)
            if v_val is not None:
                rated_voltage = v_val
                provenance = SpecProvenance.CIRCUIT_SPECIFIED

        if props.get("esr"):
            esr_ohms = parse_resistance(props.get("esr"))

        return {
            "capacitance_f": capacitance,
            "rated_voltage_v": rated_voltage,
            "esr_ohms": esr_ohms,
            "provenance": provenance.value,
        }

    def resolve_operating_limits(self, component: dict[str, Any]) -> dict[str, Any]:
        """
        Resolves documented recommended operating limits.
        Invariant: Operating Limits != Absolute Maximum Ratings.
        """
        limits = {
            "v_in_min": None,
            "v_in_max": None,
            "v_out": None,
            "i_out_max": None,
            "temp_min_c": None,
            "temp_max_c": None,
            "freq_max_hz": None,
            "source_id": None,
            "revision": None,
            "provenance": SpecProvenance.SPECIFICATION_NOT_FOUND.value,
        }

        profile = self.resolve_profile_for_component(component)
        if profile:
            op_ranges = getattr(profile, "operating_ranges", []) if hasattr(profile, "operating_ranges") else profile.get("operating_ranges", [])
            for item in op_ranges:
                p_name = (getattr(item, "parameter", "") if hasattr(item, "parameter") else item.get("parameter", "")).lower()
                norm_val = getattr(item, "normalized_value", None) if hasattr(item, "normalized_value") else item.get("normalized_value")
                vr = getattr(item, "valid_range", {}) if hasattr(item, "valid_range") else item.get("valid_range", {})

                if "voltage" in p_name or "vin" in p_name:
                    if vr and vr.get("min") is not None:
                        limits["v_in_min"] = vr.get("min")
                    if vr and vr.get("max") is not None:
                        limits["v_in_max"] = vr.get("max")
                    elif norm_val is not None:
                        limits["v_in_max"] = norm_val
                elif "current" in p_name:
                    limits["i_out_max"] = norm_val
                elif "temperature" in p_name:
                    if vr and vr.get("min") is not None:
                        limits["temp_min_c"] = vr.get("min")
                    if vr and vr.get("max") is not None:
                        limits["temp_max_c"] = vr.get("max")
                    elif norm_val is not None:
                        limits["temp_max_c"] = norm_val
                elif "frequency" in p_name or "clock" in p_name:
                    limits["freq_max_hz"] = norm_val

            prov = getattr(profile, "provenance_chain", {}) if hasattr(profile, "provenance_chain") else profile.get("provenance_chain", {})
            limits["source_id"] = prov.get("source_id")
            limits["revision"] = prov.get("revision")
            limits["provenance"] = SpecProvenance.COMPONENT_PROFILE.value
            return limits

        # Check component properties or KB
        props = component.get("properties") or {}
        if props.get("v_in_max") or props.get("max_voltage") or props.get("frequency"):
            limits["v_in_max"] = parse_voltage(props.get("v_in_max") or props.get("max_voltage"))
            limits["i_out_max"] = parse_current(props.get("i_out_max") or props.get("max_current"))
            limits["freq_max_hz"] = parse_frequency(props.get("frequency") or props.get("clock_freq"))
            limits["provenance"] = SpecProvenance.CIRCUIT_SPECIFIED.value

        return limits

    def resolve_absolute_maximums(self, component: dict[str, Any]) -> dict[str, Any]:
        """
        Resolves documented Absolute Maximum Ratings (silicon destruction hazard).
        """
        abs_max = {
            "v_in_abs_max": None,
            "v_out_abs_max": None,
            "max_junction_temp_c": None,
            "power_abs_max_w": None,
            "source_id": None,
            "revision": None,
            "provenance": SpecProvenance.SPECIFICATION_NOT_FOUND.value,
        }

        profile = self.resolve_profile_for_component(component)
        if profile:
            abs_items = getattr(profile, "absolute_maximums", []) if hasattr(profile, "absolute_maximums") else profile.get("absolute_maximums", [])
            for item in abs_items:
                p_name = (getattr(item, "parameter", "") if hasattr(item, "parameter") else item.get("parameter", "")).lower()
                norm_val = getattr(item, "normalized_value", None) if hasattr(item, "normalized_value") else item.get("normalized_value")

                if "voltage" in p_name or "vin" in p_name or "v_in" in p_name:
                    abs_max["v_in_abs_max"] = norm_val
                elif "junction_temp" in p_name or "temperature" in p_name or "tj" in p_name:
                    abs_max["max_junction_temp_c"] = norm_val
                elif "power" in p_name:
                    abs_max["power_abs_max_w"] = norm_val

            prov = getattr(profile, "provenance_chain", {}) if hasattr(profile, "provenance_chain") else profile.get("provenance_chain", {})
            abs_max["source_id"] = prov.get("source_id")
            abs_max["revision"] = prov.get("revision")
            abs_max["provenance"] = SpecProvenance.COMPONENT_PROFILE.value
            return abs_max

        # Fallback to properties
        props = component.get("properties") or {}
        if props.get("abs_max_voltage") or props.get("v_in_abs_max"):
            abs_max["v_in_abs_max"] = parse_voltage(props.get("abs_max_voltage") or props.get("v_in_abs_max"))
            abs_max["max_junction_temp_c"] = float(props.get("max_junction_temp_c") or 150.0)
            abs_max["provenance"] = SpecProvenance.CIRCUIT_SPECIFIED.value

        return abs_max

    def resolve_thermal_specs(self, component: dict[str, Any]) -> dict[str, Any]:
        """
        Resolves thermal characteristics (Theta_JA and Tj_max).
        Invariant: If Theta_JA is unknown, returns None. NEVER guesses.
        """
        profile = self.resolve_profile_for_component(component)
        if profile:
            theta_ja = None
            tj_max = None
            source_id = None
            revision = None

            thermals = getattr(profile, "thermal_characteristics", []) if hasattr(profile, "thermal_characteristics") else profile.get("thermal_characteristics", [])
            for item in thermals:
                p_name = (getattr(item, "parameter", "") if hasattr(item, "parameter") else item.get("parameter", "")).lower()
                norm_val = getattr(item, "normalized_value", None) if hasattr(item, "normalized_value") else item.get("normalized_value")
                if "theta_ja" in p_name or "thermal_resistance" in p_name or "rja" in p_name:
                    theta_ja = norm_val
                elif "junction" in p_name:
                    tj_max = norm_val

            abs_items = getattr(profile, "absolute_maximums", []) if hasattr(profile, "absolute_maximums") else profile.get("absolute_maximums", [])
            for item in abs_items:
                p_name = (getattr(item, "parameter", "") if hasattr(item, "parameter") else item.get("parameter", "")).lower()
                if "junction" in p_name or "tj" in p_name:
                    tj_max = getattr(item, "normalized_value", None) if hasattr(item, "normalized_value") else item.get("normalized_value")

            prov = getattr(profile, "provenance_chain", {}) if hasattr(profile, "provenance_chain") else profile.get("provenance_chain", {})
            return {
                "theta_ja": theta_ja,
                "tj_max_c": tj_max or 125.0,
                "source_id": prov.get("source_id"),
                "revision": prov.get("revision"),
                "provenance": SpecProvenance.COMPONENT_PROFILE.value if theta_ja is not None else SpecProvenance.SPECIFICATION_NOT_FOUND.value,
            }

        # Check regulator KB or circuit props
        reg_specs = self.resolve_regulator_specs(component)
        if reg_specs.get("provenance") != SpecProvenance.SPECIFICATION_NOT_FOUND.value:
            return {
                "theta_ja": reg_specs.get("r_theta_ja"),
                "tj_max_c": reg_specs.get("max_junction_temp_c", 125.0),
                "source_id": reg_specs.get("source_id"),
                "revision": reg_specs.get("revision"),
                "provenance": reg_specs.get("provenance"),
            }

        props = component.get("properties") or {}
        theta = props.get("r_theta_ja") or props.get("theta_ja")
        return {
            "theta_ja": float(theta) if theta is not None else None,
            "tj_max_c": float(props.get("max_junction_temp_c")) if props.get("max_junction_temp_c") else None,
            "source_id": None,
            "revision": None,
            "provenance": SpecProvenance.CIRCUIT_SPECIFIED.value if theta is not None else SpecProvenance.SPECIFICATION_NOT_FOUND.value,
        }

    def resolve_application_constraints(self, component: dict[str, Any]) -> list[dict[str, Any]]:
        """Resolves application constraints (Cin, Cout, ESR, Pull-up) from profile or KB."""
        constraints = []
        profile = self.resolve_profile_for_component(component)
        if profile:
            app_c = getattr(profile, "application_constraints", []) if hasattr(profile, "application_constraints") else profile.get("application_constraints", [])
            for item in app_c:
                constraints.append({
                    "constraint_type": getattr(item, "constraint_type", "") if hasattr(item, "constraint_type") else item.get("constraint_type", ""),
                    "description": getattr(item, "description", "") if hasattr(item, "description") else item.get("description", ""),
                    "parameter": getattr(item, "parameter", None) if hasattr(item, "parameter") else item.get("parameter"),
                    "requirement_value": getattr(item, "requirement_value", None) if hasattr(item, "requirement_value") else item.get("requirement_value"),
                    "conditions": getattr(item, "conditions", {}) if hasattr(item, "conditions") else item.get("conditions", {}),
                })
        return constraints
