import re
from typing import Optional


MULTIPLIERS = {
    "f": 1e-15,
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


def parse_resistance(val: str | int | float | None) -> Optional[float]:
    """Parse resistance string to ohms (float). e.g., '10k', '4.7k', '220R', '1M', '0.5'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else None

    s = str(val).strip().replace("Ω", "").replace("ohm", "").replace("Ohm", "").replace("OHM", "")
    if not s:
        return None

    # Handle R as decimal point: 4R7 -> 4.7
    r_match = re.match(r"^(\d+)[rR](\d+)$", s)
    if r_match:
        return float(f"{r_match.group(1)}.{r_match.group(2)}")

    # Handle k as decimal point: 4k7 -> 4700
    k_match = re.match(r"^(\d+)[kK](\d+)$", s)
    if k_match:
        return float(f"{k_match.group(1)}.{k_match.group(2)}") * 1e3

    # Handle trailing R
    if s.endswith("R") or s.endswith("r"):
        s = s[:-1]

    # Standard multiplier regex
    m = re.match(r"^([0-9.]+)\s*([kKMm]?)$", s)
    if not m:
        try:
            return float(s)
        except ValueError:
            return None

    num = float(m.group(1))
    mult = MULTIPLIERS.get(m.group(2), 1.0)
    return num * mult


def parse_capacitance(val: str | int | float | None) -> Optional[float]:
    """Parse capacitance string to farads (float). e.g., '100nF', '0.1uF', '10uF', '22pF'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else None

    s = str(val).strip().replace("F", "").replace("f", "")
    if not s:
        return None

    # Handle u as decimal point: 4u7 -> 4.7uF
    u_match = re.match(r"^(\d+)[uUµ](\d+)$", s)
    if u_match:
        return float(f"{u_match.group(1)}.{u_match.group(2)}") * 1e-6

    # Handle n as decimal point: 4n7 -> 4.7nF
    n_match = re.match(r"^(\d+)[nN](\d+)$", s)
    if n_match:
        return float(f"{n_match.group(1)}.{n_match.group(2)}") * 1e-9

    # Handle p as decimal point: 4p7 -> 4.7pF
    p_match = re.match(r"^(\d+)[pP](\d+)$", s)
    if p_match:
        return float(f"{p_match.group(1)}.{p_match.group(2)}") * 1e-12

    m = re.match(r"^([0-9.]+)\s*([pnumµ]?)$", s)
    if not m:
        try:
            return float(s)
        except ValueError:
            return None

    num = float(m.group(1))
    mult = MULTIPLIERS.get(m.group(2), 1.0)
    return num * mult


def parse_voltage(val: str | int | float | None) -> Optional[float]:
    """Parse voltage string to volts (float). e.g., '3.3V', '5V', '3V3', '500mV'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s:
        return None

    # Handle V as decimal point: 3V3 -> 3.3, 1V8 -> 1.8
    v_match = re.match(r"^(\d+)[vV](\d+)$", s)
    if v_match:
        return float(f"{v_match.group(1)}.{v_match.group(2)}")

    s = s.replace("V", "").replace("v", "")
    m = re.match(r"^([0-9.]+)\s*([mku]?)$", s)
    if not m:
        try:
            return float(s)
        except ValueError:
            return None

    num = float(m.group(1))
    mult = MULTIPLIERS.get(m.group(2), 1.0)
    return num * mult


def parse_current(val: str | int | float | None) -> Optional[float]:
    """Parse current string to amperes (float). e.g., '500mA', '1.5A', '20mA', '10uA'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip().replace("A", "").replace("a", "")
    if not s:
        return None

    m = re.match(r"^([0-9.]+)\s*([mkuµ]?)$", s)
    if not m:
        try:
            return float(s)
        except ValueError:
            return None

    num = float(m.group(1))
    mult = MULTIPLIERS.get(m.group(2), 1.0)
    return num * mult


def parse_power(val: str | int | float | None) -> Optional[float]:
    """Parse power string to watts (float). e.g., '0.25W', '1/4W', '1/8W', '500mW'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else None

    s = str(val).strip().replace("W", "").replace("w", "")
    if not s:
        return None

    # Fractions like 1/4, 1/8, 1/2
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 2:
            try:
                return float(parts[0]) / float(parts[1])
            except (ValueError, ZeroDivisionError):
                return None

    m = re.match(r"^([0-9.]+)\s*([mku]?)$", s)
    if not m:
        try:
            return float(s)
        except ValueError:
            return None

    num = float(m.group(1))
    mult = MULTIPLIERS.get(m.group(2), 1.0)
    return num * mult


def format_engineering(val: float, unit: str, precision: int = 2) -> str:
    """Format float into readable engineering notation with SI prefix."""
    if val is None:
        return f"Unknown {unit}"
    if abs(val) < 1e-15:
        return f"0 {unit}"

    abs_val = abs(val)
    if abs_val >= 1e6:
        return f"{val / 1e6:.{precision}f} M{unit}"
    if abs_val >= 1e3:
        return f"{val / 1e3:.{precision}f} k{unit}"
    if abs_val >= 1.0:
        return f"{val:.{precision}f} {unit}"
    if abs_val >= 1e-3:
        return f"{val * 1e3:.{precision}f} m{unit}"
    if abs_val >= 1e-6:
        return f"{val * 1e6:.{precision}f} µ{unit}"
    if abs_val >= 1e-9:
        return f"{val * 1e9:.{precision}f} n{unit}"
    if abs_val >= 1e-12:
        return f"{val * 1e12:.{precision}f} p{unit}"

    return f"{val:.{precision}e} {unit}"


def parse_frequency(val: str | int | float | None) -> Optional[float]:
    """Parse frequency string to hertz (float). e.g., '10MHz', '100kHz', '1GHz', '50Hz'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else None

    s = str(val).strip().replace("Hz", "").replace("hz", "").replace("HZ", "")
    if not s:
        return None

    m = re.match(r"^([0-9.]+)\s*([kKMmGg]?)$", s)
    if not m:
        try:
            return float(s)
        except ValueError:
            return None

    num = float(m.group(1))
    suffix = m.group(2)
    mult = 1.0
    if suffix in ["k", "K"]:
        mult = 1e3
    elif suffix in ["M", "m"]:
        mult = 1e6
    elif suffix in ["G", "g"]:
        mult = 1e9
    return num * mult


def parse_inductance(val: str | int | float | None) -> Optional[float]:
    """Parse inductance string to henries (float). e.g., '10uH', '1mH', '100nH'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else None
    s = str(val).strip().replace("H", "").replace("h", "")
    if not s:
        return None
    u_match = re.match(r"^(\d+)[uUµ](\d+)$", s)
    if u_match:
        return float(f"{u_match.group(1)}.{u_match.group(2)}") * 1e-6
    n_match = re.match(r"^(\d+)[nN](\d+)$", s)
    if n_match:
        return float(f"{n_match.group(1)}.{n_match.group(2)}") * 1e-9
    m = re.match(r"^([0-9.]+)\s*([pnumµ]?)$", s)
    if not m:
        try:
            return float(s)
        except ValueError:
            return None
    num = float(m.group(1))
    mult = MULTIPLIERS.get(m.group(2), 1.0)
    return num * mult


from dataclasses import dataclass


@dataclass
class UnitNormalizedResult:
    is_valid: bool
    normalized_value: float | None
    unit: str | None = None


class UnitNormalizer:
    """Unified unit parser and normalizer for engineering quantities."""

    @staticmethod
    def parse(val: object) -> UnitNormalizedResult:
        if val is None:
            return UnitNormalizedResult(is_valid=False, normalized_value=None)
        if isinstance(val, (int, float)):
            return UnitNormalizedResult(is_valid=True, normalized_value=float(val))

        s = str(val).strip()
        if not s:
            return UnitNormalizedResult(is_valid=False, normalized_value=None)

        for parser in (
            parse_resistance,
            parse_voltage,
            parse_current,
            parse_capacitance,
            parse_inductance,
            parse_frequency,
            parse_power,
        ):
            res = parser(s)
            if res is not None:
                return UnitNormalizedResult(is_valid=True, normalized_value=res)

        try:
            return UnitNormalizedResult(is_valid=True, normalized_value=float(s))
        except ValueError:
            return UnitNormalizedResult(is_valid=False, normalized_value=None)

