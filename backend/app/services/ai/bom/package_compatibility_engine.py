"""
BOM Package & Footprint Compatibility Engine.

Evaluates physical package and footprint compatibility between component specifications
and PCB footprint constraints.
Strict Invariants:
- Never equates same pin count with package compatibility.
- Unknown package or footprint strictly remains UNKNOWN.
- Package compatibility is evaluated against standard EDA footprint families.
"""

import re
from typing import Optional, Tuple
from app.models.db.bom import ParameterEvaluationStatus


class BOMPackageCompatibilityEngine:
    """
    Evaluates physical package and footprint compatibility between component specifications and PCB footprint.
    Strict Invariant:
    Never equates same pin count with package compatibility.
    Unknown package or footprint remains UNKNOWN.
    """

    # Normalized package alias mappings
    PACKAGE_ALIASES: dict[str, set[str]] = {
        "0402": {"0402", "R_0402", "C_0402", "L_0402", "0402_METRIC", "1005", "R_0402_1005METRIC", "C_0402_1005METRIC"},
        "0603": {"0603", "R_0603", "C_0603", "L_0603", "0603_METRIC", "1608", "R_0603_1608METRIC", "C_0603_1608METRIC"},
        "0805": {"0805", "R_0805", "C_0805", "L_0805", "0805_METRIC", "2012", "R_0805_2012METRIC", "C_0805_2012METRIC"},
        "1206": {"1206", "R_1206", "C_1206", "L_1206", "1206_METRIC", "3216", "R_1206_3216METRIC", "C_1206_3216METRIC"},
        "TO-220": {"TO-220", "TO-220-3", "TO-220AB", "TO-220_VERTICAL", "TO-220-2"},
        "TO-263": {"TO-263", "D2PAK", "TO-263-3", "TO-263-5"},
        "SOT-23": {"SOT-23", "SOT-23-3", "SOT23", "TO-236AB"},
        "SOT-23-5": {"SOT-23-5", "SOT23-5", "TSOT-23-5"},
        "SOT-23-6": {"SOT-23-6", "SOT23-6"},
        "SOT-223": {"SOT-223", "SOT-223-3", "SOT223"},
        "SOIC-8": {"SOIC-8", "SOIC-8_3.9X4.9MM", "SO-8", "SO8"},
        "SOIC-14": {"SOIC-14", "SO-14", "SO14"},
        "SOIC-16": {"SOIC-16", "SO-16", "SO16"},
        "TSSOP-8": {"TSSOP-8", "MSOP-8"},
        "TSSOP-14": {"TSSOP-14"},
        "TSSOP-16": {"TSSOP-16"},
        "QFN-16": {"QFN-16", "QFN-16-1EP", "WQFN-16"},
        "QFN-20": {"QFN-20", "QFN-20-1EP", "WQFN-20"},
        "QFN-32": {"QFN-32", "VQFN-32"},
        "LQFP-32": {"LQFP-32", "TQFP-32"},
        "LQFP-48": {"LQFP-48", "TQFP-48"},
        "LQFP-64": {"LQFP-64", "TQFP-64"},
    }

    @classmethod
    def normalize_package_name(cls, name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        clean = name.strip().upper().replace("PACKAGE_", "").replace("FOOTPRINT_", "")
        clean = re.sub(r"[^A-Z0-9_\-\.]", "", clean)
        return clean

    @classmethod
    def get_package_family(cls, name: Optional[str]) -> Optional[str]:
        norm = cls.normalize_package_name(name)
        if not norm:
            return None
        for fam, aliases in cls.PACKAGE_ALIASES.items():
            norm_aliases = {cls.normalize_package_name(a) for a in aliases}
            if norm in norm_aliases:
                return fam
        # Regex matching for passive 2-terminal SMD packages
        m = re.search(r"(?:^|[_\-])(0402|0603|0805|1206)(?:[_\-]|$)", norm)
        if m:
            return m.group(1)
        return None

    @classmethod
    def evaluate_package_compatibility(
        cls,
        required_package: Optional[str],
        candidate_package: Optional[str],
        pcb_footprint: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Returns: (status, message)
        Statuses: SATISFIED, CONFLICT, UNKNOWN
        """
        if not required_package and not pcb_footprint:
            return ParameterEvaluationStatus.UNKNOWN.value, "No required package or PCB footprint specified"

        if not candidate_package:
            return ParameterEvaluationStatus.UNKNOWN.value, "Candidate part package is UNKNOWN"

        cand_norm = cls.normalize_package_name(candidate_package)
        req_norm = cls.normalize_package_name(required_package)
        fp_norm = cls.normalize_package_name(pcb_footprint)

        cand_fam = cls.get_package_family(candidate_package)
        req_fam = cls.get_package_family(required_package)
        fp_fam = cls.get_package_family(pcb_footprint)

        # 1. Compare against required package
        if req_norm:
            if cand_norm == req_norm:
                return ParameterEvaluationStatus.SATISFIED.value, f"Exact package match: {candidate_package}"

            if req_fam and cand_fam and req_fam == cand_fam:
                return (
                    ParameterEvaluationStatus.SATISFIED.value,
                    f"Compatible package family ({req_fam}): candidate '{candidate_package}' matches required '{required_package}'",
                )

            return (
                ParameterEvaluationStatus.CONFLICT.value,
                f"Package mismatch: candidate has '{candidate_package}', required design specifies '{required_package}'",
            )

        # 2. Compare against PCB footprint if required_package was missing
        if fp_norm:
            if cand_norm == fp_norm:
                return ParameterEvaluationStatus.SATISFIED.value, f"Matches PCB footprint: {pcb_footprint}"

            if fp_fam and cand_fam and fp_fam == cand_fam:
                return (
                    ParameterEvaluationStatus.SATISFIED.value,
                    f"Compatible with PCB footprint ({fp_fam}): candidate '{candidate_package}' matches footprint '{pcb_footprint}'",
                )

            return (
                ParameterEvaluationStatus.CONFLICT.value,
                f"Footprint mismatch: candidate '{candidate_package}' does not fit PCB footprint '{pcb_footprint}'",
            )

        return ParameterEvaluationStatus.UNKNOWN.value, "Package compatibility cannot be evaluated"

    @classmethod
    def are_packages_compatible(
        cls,
        pkg_req: Optional[str],
        pkg_cand: Optional[str],
        pins_req: Optional[int] = None,
        pins_cand: Optional[int] = None,
    ) -> bool:
        if pins_req is not None and pins_cand is not None and pins_req != pins_cand:
            return False
        status, _ = cls.evaluate_package_compatibility(pkg_req, pkg_cand)
        return status == ParameterEvaluationStatus.SATISFIED.value
