"""
BOM Consistency DFM Engine for Phase 3 Wave 7: Manufacturing / DFM & Assembly Intelligence.
Evaluates physical PCB footprints against procurement BOM specifications.
Detects package family discrepancies and pin/pad count mismatches.
STRICT INVARIANT: UNKNOWN != PASS. Zero synthetic scoring.
"""
import re
from typing import Any, Optional
from app.models.db.dfm import ManufacturingFindingStatus, ManufacturingRuleCategory
from app.models.schemas.dfm import ManufacturingFinding


class BOMConsistencyDFMEngine:
    """
    Deterministic cross-verification engine between physical PCB footprints and EngineeringBOM lines.
    """

    @staticmethod
    def evaluate_bom_pcb_consistency(
        board: Any,
        bom: Optional[Any],
        rules: dict[str, Any],
    ) -> list[ManufacturingFinding]:
        findings: list[ManufacturingFinding] = []

        rule_014 = rules.get("MFG014")
        rule_015 = rules.get("MFG015")

        if not bom:
            if rule_014:
                findings.append(
                    ManufacturingFinding(
                        finding_id="MFG014_NO_BOM",
                        rule_id="MFG014",
                        rule_name=rule_014["name"],
                        category=ManufacturingRuleCategory.BOM_CONSISTENCY,
                        status=ManufacturingFindingStatus.UNKNOWN,
                        severity="WARNING",
                        message="No Bill of Materials (BOM) provided for board. Package consistency cannot be verified.",
                        element_type="BOM_LINE",
                    )
                )
            if rule_015:
                findings.append(
                    ManufacturingFinding(
                        finding_id="MFG015_NO_BOM",
                        rule_id="MFG015",
                        rule_name=rule_015["name"],
                        category=ManufacturingRuleCategory.BOM_CONSISTENCY,
                        status=ManufacturingFindingStatus.UNKNOWN,
                        severity="WARNING",
                        message="No Bill of Materials (BOM) provided for board. Pad/pin count consistency cannot be verified.",
                        element_type="BOM_LINE",
                    )
                )
            return findings

        # Index BOM lines by reference_designator
        bom_lines = getattr(bom, "lines", []) or []
        bom_by_ref: dict[str, Any] = {}
        for line in bom_lines:
            ref = str(getattr(line, "reference_designator", "")).strip().upper()
            if ref:
                bom_by_ref[ref] = line

        footprints = getattr(board, "footprints", []) or []
        if not footprints:
            if rule_014:
                findings.append(
                    ManufacturingFinding(
                        finding_id="MFG014_NO_FOOTPRINTS",
                        rule_id="MFG014",
                        rule_name=rule_014["name"],
                        category=ManufacturingRuleCategory.BOM_CONSISTENCY,
                        status=ManufacturingFindingStatus.UNKNOWN,
                        severity="INFO",
                        message="No footprints on board to verify against BOM.",
                        element_type="FOOTPRINT",
                    )
                )
            return findings

        mismatch_014 = 0
        pass_014 = 0
        mismatch_015 = 0
        pass_015 = 0

        for fp in footprints:
            ref = str(getattr(fp, "ref_des", "")).strip().upper()
            bom_line = bom_by_ref.get(ref)

            if not bom_line:
                # Placed footprint not found in BOM
                findings.append(
                    ManufacturingFinding(
                        finding_id=f"MFG014_UNLISTED_REF_{fp.id}",
                        rule_id="MFG014",
                        rule_name=rule_014["name"] if rule_014 else "BOM Package Consistency",
                        category=ManufacturingRuleCategory.BOM_CONSISTENCY,
                        status=ManufacturingFindingStatus.WARNING,
                        severity="WARNING",
                        message=f"Footprint {fp.ref_des} ({fp.footprint_name}) is placed on PCB but not listed in BOM.",
                        element_type="FOOTPRINT",
                        element_ids=[str(fp.id)],
                        ref_des=ref,
                    )
                )
                continue

            # --- Rule 014: Package Family Consistency ---
            if rule_014:
                fp_pkg = str(getattr(fp, "footprint_name", "")).strip()
                bom_pkg = (
                    getattr(bom_line, "design_package", None)
                    or getattr(bom_line, "footprint_name", None)
                    or getattr(bom_line, "footprint_package", None)
                    or ""
                )
                bom_pkg = str(bom_pkg).strip()

                if not bom_pkg:
                    # Check candidate package if available
                    candidates = getattr(bom_line, "candidates", []) or []
                    for c in candidates:
                        if getattr(c, "package_case", None):
                            bom_pkg = str(c.package_case).strip()
                            break

                if not bom_pkg:
                    findings.append(
                        ManufacturingFinding(
                            finding_id=f"MFG014_UNKNOWN_PKG_{fp.id}",
                            rule_id="MFG014",
                            rule_name=rule_014["name"],
                            category=ManufacturingRuleCategory.BOM_CONSISTENCY,
                            status=ManufacturingFindingStatus.UNKNOWN,
                            severity="WARNING",
                            message=f"BOM line for {ref} has no package specified. Cannot verify package match with PCB footprint '{fp_pkg}'.",
                            element_type="BOM_LINE",
                            element_ids=[str(fp.id), str(bom_line.id)],
                            ref_des=ref,
                        )
                    )
                elif not BOMConsistencyDFMEngine._packages_are_compatible(fp_pkg, bom_pkg):
                    mismatch_014 += 1
                    findings.append(
                        ManufacturingFinding(
                            finding_id=f"MFG014_MISMATCH_{fp.id}",
                            rule_id="MFG014",
                            rule_name=rule_014["name"],
                            category=ManufacturingRuleCategory.BOM_CONSISTENCY,
                            status=ManufacturingFindingStatus.FAIL,
                            severity="ERROR",
                            message=f"Package conflict for {ref}: PCB footprint is '{fp_pkg}' but BOM specifies '{bom_pkg}'. Assembly cannot proceed.",
                            element_type="FOOTPRINT",
                            element_ids=[str(fp.id), str(bom_line.id)],
                            ref_des=ref,
                            evidence={"pcb_package": fp_pkg, "bom_package": bom_pkg},
                            proposal_available=True,
                        )
                    )
                else:
                    pass_014 += 1

            # --- Rule 015: Pad Count Consistency ---
            if rule_015:
                pads = getattr(fp, "pads", []) or []
                actual_pad_count = len(pads)

                # Check expected pin count from BOM line engineering_requirements or metadata
                expected_pins = None
                line_meta = getattr(bom_line, "engineering_requirements", {}) or getattr(bom_line, "metadata_", {}) or {}
                if isinstance(line_meta, dict):
                    expected_pins = line_meta.get("pin_count") or line_meta.get("pins")

                if expected_pins is None:
                    # Infer pin count from standard package name if possible (e.g. SOIC-8 -> 8, SOT-23 -> 3, TO-220 -> 3)
                    expected_pins = BOMConsistencyDFMEngine._infer_pin_count(bom_pkg or str(getattr(bom_line, "footprint_package", "")))

                if expected_pins is not None:
                    if int(expected_pins) != actual_pad_count:
                        mismatch_015 += 1
                        findings.append(
                            ManufacturingFinding(
                                finding_id=f"MFG015_PAD_MISMATCH_{fp.id}",
                                rule_id="MFG015",
                                rule_name=rule_015["name"],
                                category=ManufacturingRuleCategory.BOM_CONSISTENCY,
                                status=ManufacturingFindingStatus.FAIL,
                                severity="ERROR",
                                message=f"Pin/pad count mismatch for {ref}: PCB footprint has {actual_pad_count} pads but BOM part specifies {expected_pins} pins.",
                                element_type="FOOTPRINT",
                                element_ids=[str(fp.id), str(bom_line.id)],
                                ref_des=ref,
                                measured_value=float(actual_pad_count),
                                required_value=float(expected_pins),
                                margin=float(actual_pad_count - expected_pins),
                                evidence={"pcb_pads": actual_pad_count, "bom_pins": expected_pins},
                                proposal_available=True,
                            )
                        )
                    else:
                        pass_015 += 1
                else:
                    findings.append(
                        ManufacturingFinding(
                            finding_id=f"MFG015_UNKNOWN_PINS_{fp.id}",
                            rule_id="MFG015",
                            rule_name=rule_015["name"],
                            category=ManufacturingRuleCategory.BOM_CONSISTENCY,
                            status=ManufacturingFindingStatus.UNKNOWN,
                            severity="INFO",
                            message=f"BOM line for {ref} does not specify explicit pin count. Pad count ({actual_pad_count}) verified as unconstrained.",
                            element_type="BOM_LINE",
                            ref_des=ref,
                        )
                    )

        if rule_014 and mismatch_014 == 0 and pass_014 > 0:
            findings.append(
                ManufacturingFinding(
                    finding_id="MFG014_PASS_ALL",
                    rule_id="MFG014",
                    rule_name=rule_014["name"],
                    category=ManufacturingRuleCategory.BOM_CONSISTENCY,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message=f"All {pass_014} BOM-linked PCB footprints match expected package families.",
                    element_type="BOM_LINE",
                )
            )

        if rule_015 and mismatch_015 == 0 and pass_015 > 0:
            findings.append(
                ManufacturingFinding(
                    finding_id="MFG015_PASS_ALL",
                    rule_id="MFG015",
                    rule_name=rule_015["name"],
                    category=ManufacturingRuleCategory.BOM_CONSISTENCY,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message=f"All {pass_015} BOM-linked footprints have matching physical pad counts (PAD_COUNT_MATCH != PINOUT_MATCH and != ELECTRICAL_COMPATIBILITY).",
                    element_type="BOM_LINE",
                )
            )

        return findings

    @staticmethod
    def _normalize_pkg_token(s: str) -> str:
        s = s.upper().replace("-", "").replace("_", "").replace(" ", "")
        # Remove common prefixes like 'R', 'C', 'L' for passives (e.g., R0805 -> 0805)
        m = re.match(r"^[RCL]([0-9]{4})$", s)
        if m:
            return m.group(1)
        return s

    @staticmethod
    def _packages_are_compatible(pkg_a: str, pkg_b: str) -> bool:
        if not pkg_a or not pkg_b:
            return False
        norm_a = BOMConsistencyDFMEngine._normalize_pkg_token(pkg_a)
        norm_b = BOMConsistencyDFMEngine._normalize_pkg_token(pkg_b)

        if norm_a == norm_b:
            return True

        # Check containment (e.g., "SOIC8" in "SOIC8EP" or "SOIC8" in "SOIC8_N")
        if norm_a in norm_b or norm_b in norm_a:
            return True

        return False

    @staticmethod
    def _infer_pin_count(package_str: str) -> Optional[int]:
        if not package_str:
            return None
        s = package_str.upper()
        # SOIC-8, DIP-14, QFN-32, LQFP-64, etc.
        m = re.search(r"(?:SOIC|SOP|SSOP|TSSOP|MSOP|DIP|QFN|QFP|LQFP|TQFP)[-_]?([0-9]{1,3})", s)
        if m:
            return int(m.group(1))
        # SOT-23 / SOT23
        if "SOT235" in s or "SOT-23-5" in s:
            return 5
        if "SOT236" in s or "SOT-23-6" in s:
            return 6
        if "SOT23" in s or "SOT-23" in s:
            return 3
        if "TO220" in s or "TO-220" in s or "TO92" in s or "TO-92" in s:
            return 3
        # Chip passives
        if any(code in s for code in ("0201", "0402", "0603", "0805", "1206", "1210", "2010", "2512")):
            return 2
        return None
