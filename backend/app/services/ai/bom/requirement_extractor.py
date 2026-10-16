"""
BOM Requirement Extractor.

Extracts structured engineering requirements from design component state.
Strict Invariant:
Only extracts requirements actually present in component value, rating, tolerance,
metadata, or operating limits.
Never invents missing parameters; unknown parameters remain UNKNOWN.
"""

import re
from typing import Any, Optional, Tuple, Union
from app.models.db.component import Component


class BOMRequirementExtractor:
    """Extracts structured engineering requirements from design component state."""

    METRIC_PREFIXES = {
        "p": 1e-12,
        "n": 1e-9,
        "u": 1e-6,
        "µ": 1e-6,
        "m": 1e-3,
        "k": 1e3,
        "K": 1e3,
        "M": 1e6,
        "G": 1e9,
    }

    @classmethod
    def parse_value_with_unit(cls, val_str: str | None) -> Tuple[Optional[float], Optional[str]]:
        if not val_str:
            return None, None
        s = str(val_str).strip()
        match = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([a-zA-ZµΩ]*)$", s)
        if not match:
            return None, None
        num = float(match.group(1))
        unit = match.group(2)
        return num, unit

    @classmethod
    def parse_tolerance_percent(cls, tol_str: Any) -> Optional[float]:
        if tol_str is None:
            return None
        s = str(tol_str).strip().replace("±", "").replace("%", "")
        try:
            return float(s)
        except ValueError:
            return None

    @classmethod
    def parse_power_rating_w(cls, rating_str: Any) -> Optional[float]:
        if not rating_str:
            return None
        s = str(rating_str)
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*[wW]", s)
        if match:
            return float(match.group(1))
        frac_match = re.search(r"([0-9]+)/([0-9]+)\s*[wW]", s)
        if frac_match:
            return float(frac_match.group(1)) / float(frac_match.group(2))
        try:
            return float(s)
        except ValueError:
            return None

    @classmethod
    def parse_voltage_rating_v(cls, rating_str: Any) -> Optional[float]:
        if not rating_str:
            return None
        s = str(rating_str)
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*[vV]", s)
        if match:
            return float(match.group(1))
        try:
            return float(s)
        except ValueError:
            return None

    @classmethod
    def parse_current_rating_a(cls, rating_str: Any) -> Optional[float]:
        if not rating_str:
            return None
        s = str(rating_str)
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([mMuU]?)[aA]", s)
        if match:
            val = float(match.group(1))
            prefix = match.group(2).lower()
            if prefix == "m":
                val /= 1000.0
            elif prefix == "u":
                val /= 1e6
            return val
        try:
            return float(s)
        except ValueError:
            return None

    @classmethod
    def extract_requirements(
        cls,
        component: Union[Component, dict[str, Any]],
        footprint_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Extracts structured engineering requirements dict from Component OR dict.
        """
        if isinstance(component, dict):
            comp_type = component.get("component_type") or component.get("type") or ""
            val_raw = component.get("value")
            unit_raw = component.get("unit") or ""
            tol_raw = component.get("tolerance")
            rating_raw = component.get("rating")
            package_raw = component.get("package")
            pins_raw = component.get("pins")
            meta = component.get("metadata") or component.get("metadata_") or {}
        else:
            comp_type = getattr(component, "component_type", "") or ""
            val_raw = getattr(component, "value", None)
            unit_raw = getattr(component, "unit", "") or ""
            tol_raw = getattr(component, "tolerance", None)
            rating_raw = getattr(component, "rating", None)
            package_raw = getattr(component, "package", None)
            pins_raw = getattr(component, "pins", None)
            meta = getattr(component, "metadata_", None) or getattr(component, "metadata", None) or {}

        # Parse nominal value with prefix scaling
        nominal_val = None
        if val_raw is not None:
            try:
                num = float(val_raw)
                unit_str = str(unit_raw).strip()
                scale = 1.0
                if unit_str:
                    first_char = unit_str[0]
                    if first_char in cls.METRIC_PREFIXES and unit_str not in ("m", "min"):
                        scale = cls.METRIC_PREFIXES[first_char]
                    elif first_char == "m" and len(unit_str) > 1 and unit_str[1] not in ("m",):
                        scale = 1e-3
                nominal_val = num * scale
            except (ValueError, TypeError):
                nominal_val = val_raw

        tol_val = cls.parse_tolerance_percent(tol_raw)
        v_rat = cls.parse_voltage_rating_v(rating_raw)
        p_rat = cls.parse_power_rating_w(rating_raw)
        i_rat = cls.parse_current_rating_a(rating_raw)

        pkg_val = str(package_raw).strip() if package_raw else None
        fp_val = str(footprint_name).strip() if footprint_name else None

        pin_count = None
        if pins_raw and isinstance(pins_raw, list):
            pin_count = len(pins_raw)
        elif isinstance(pins_raw, int):
            pin_count = pins_raw

        reqs: dict[str, Any] = {
            "component_type": str(comp_type).upper(),
            "nominal_value": nominal_val,
            "unit": unit_raw,
            "tolerance": tol_val,
            "max_tolerance_percent": tol_val,
            "voltage_rating": v_rat,
            "min_voltage_rating_v": v_rat,
            "power_rating": p_rat,
            "min_power_rating_w": p_rat,
            "current_rating": i_rat,
            "min_current_rating_a": i_rat,
            "package": pkg_val,
            "footprint": fp_val,
            "pin_count": pin_count,
        }

        # Temperature range from metadata
        if isinstance(meta, dict):
            if "operating_temperature" in meta:
                reqs["temp_range_c"] = meta["operating_temperature"]
            elif "temp_min_c" in meta and "temp_max_c" in meta:
                reqs["temp_range_c"] = [meta["temp_min_c"], meta["temp_max_c"]]
            if "dielectric" in meta:
                reqs["dielectric"] = meta["dielectric"]

        return reqs
