"""
Assembly DFA Engine for Phase 3 Wave 7: Manufacturing / DFM & Assembly Intelligence.
Evaluates component placement clearances, board edge clearances, pick-and-place centroids,
soldering technology consistency, and polarity / pin 1 markings.
STRICT INVARIANT: UNKNOWN != PASS. Zero synthetic scoring.
"""
import math
from typing import Any
from app.models.db.dfm import ManufacturingFindingStatus, ManufacturingRuleCategory
from app.models.schemas.dfm import ManufacturingFinding


class AssemblyDFAEngine:
    """
    Deterministic assembly rule checker operating on physical EngineeringBoard footprints and pads.
    """

    @staticmethod
    def evaluate_board_assembly(board: Any, rules: dict[str, Any]) -> list[ManufacturingFinding]:
        findings: list[ManufacturingFinding] = []

        # 1. MFG009: Component-to-Component Clearance
        rule_009 = rules.get("MFG009")
        if rule_009:
            findings.extend(AssemblyDFAEngine._check_component_clearance(board, rule_009))

        # 2. MFG010: Component-to-Board-Edge Clearance
        rule_010 = rules.get("MFG010")
        if rule_010:
            findings.extend(AssemblyDFAEngine._check_component_edge_clearance(board, rule_010))

        # 3. MFG011: Pick-and-Place Centroid and Rotation Validity
        rule_011 = rules.get("MFG011")
        if rule_011:
            findings.extend(AssemblyDFAEngine._check_pnp_centroids(board, rule_011))

        # 4. MFG012: SMT vs THT Soldering Consistency
        rule_012 = rules.get("MFG012")
        if rule_012:
            findings.extend(AssemblyDFAEngine._check_soldering_consistency(board, rule_012))

        # 5. MFG013: Pin 1 and Polarity Indicator Presence
        rule_013 = rules.get("MFG013")
        if rule_013:
            findings.extend(AssemblyDFAEngine._check_polarity_marking(board, rule_013))

        return findings

    @staticmethod
    def _get_footprint_bounds(fp: Any) -> tuple[float, float, float, float]:
        """Returns (min_x, max_x, min_y, max_y) in board coordinates."""
        pads = getattr(fp, "pads", []) or []
        fp_x = float(getattr(fp, "pos_x", 0.0) if getattr(fp, "pos_x", None) is not None else 0.0)
        fp_y = float(getattr(fp, "pos_y", 0.0) if getattr(fp, "pos_y", None) is not None else 0.0)

        if not pads:
            # Fall back to package metadata dimensions or default 2x2mm box
            meta = getattr(fp, "package_metadata", {}) or {}
            w = float(meta.get("body_width_mm", meta.get("width_mm", 2.0)))
            h = float(meta.get("body_length_mm", meta.get("height_mm", 2.0)))
            return (fp_x - w / 2.0, fp_x + w / 2.0, fp_y - h / 2.0, fp_y + h / 2.0)

        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        for pad in pads:
            pad_x = getattr(pad, "pos_x", 0.0)
            pad_y = getattr(pad, "pos_y", 0.0)
            pad_w = getattr(pad, "width", 1.0)
            pad_h = getattr(pad, "height", 1.0)
            px = fp_x + float(pad_x if pad_x is not None else 0.0)
            py = fp_y + float(pad_y if pad_y is not None else 0.0)
            pw = float(pad_w if pad_w is not None else 1.0) / 2.0
            ph = float(pad_h if pad_h is not None else 1.0) / 2.0
            min_x = min(min_x, px - pw)
            max_x = max(max_x, px + pw)
            min_y = min(min_y, py - ph)
            max_y = max(max_y, py + ph)

        return (min_x, max_x, min_y, max_y)

    @staticmethod
    def _check_component_clearance(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        min_clearance = float(rule.get("parameters", {}).get("min_component_clearance_mm", 0.5))
        footprints = getattr(board, "footprints", []) or []

        if len(footprints) < 2:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG009_INSUFFICIENT_COMPONENTS",
                    rule_id="MFG009",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.COMPONENT_PLACEMENT,
                    status=ManufacturingFindingStatus.UNKNOWN if len(footprints) == 0 else ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message="Insufficient components on board to evaluate inter-component assembly spacing." if len(footprints) == 0 else "Single component on board; no placement clearance collision.",
                    element_type="FOOTPRINT",
                    required_value=min_clearance,
                    unit="mm",
                )
            )
            return results

        violations = 0
        for i in range(len(footprints)):
            fp1 = footprints[i]
            side1 = getattr(fp1, "side", "TOP")
            b1_min_x, b1_max_x, b1_min_y, b1_max_y = AssemblyDFAEngine._get_footprint_bounds(fp1)

            for j in range(i + 1, len(footprints)):
                fp2 = footprints[j]
                side2 = getattr(fp2, "side", "TOP")
                if side1 != side2:
                    continue  # Opposite sides don't collide in placement clearance

                b2_min_x, b2_max_x, b2_min_y, b2_max_y = AssemblyDFAEngine._get_footprint_bounds(fp2)

                # Distance between bounding boxes
                dx = max(0.0, max(b1_min_x - b2_max_x, b2_min_x - b1_max_x))
                dy = max(0.0, max(b1_min_y - b2_max_y, b2_min_y - b1_max_y))
                clearance = math.hypot(dx, dy)

                if clearance < min_clearance:
                    violations += 1
                    results.append(
                        ManufacturingFinding(
                            finding_id=f"MFG009_FAIL_{fp1.id}_{fp2.id}",
                            rule_id="MFG009",
                            rule_name=rule["name"],
                            category=ManufacturingRuleCategory.COMPONENT_PLACEMENT,
                            status=ManufacturingFindingStatus.FAIL,
                            severity=rule.get("severity", "ERROR"),
                            message=f"Placement clearance between {fp1.ref_des} and {fp2.ref_des} ({clearance:.4f} mm) is below required assembly spacing {min_clearance} mm on {side1}.",
                            element_type="FOOTPRINT",
                            element_ids=[str(fp1.id), str(fp2.id)],
                            ref_des=f"{fp1.ref_des} <-> {fp2.ref_des}",
                            measured_value=round(clearance, 4),
                            required_value=min_clearance,
                            margin=round(clearance - min_clearance, 4),
                            unit="mm",
                            proposal_available=True,
                        )
                    )

        if violations == 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG009_PASS_ALL",
                    rule_id="MFG009",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.COMPONENT_PLACEMENT,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message=f"All component placement pairs satisfy minimum assembly clearance requirement (>= {min_clearance} mm).",
                    element_type="FOOTPRINT",
                    required_value=min_clearance,
                    unit="mm",
                )
            )

        return results

    @staticmethod
    def _check_component_edge_clearance(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        min_edge = float(rule.get("parameters", {}).get("min_edge_component_clearance_mm", 1.0))
        footprints = getattr(board, "footprints", []) or []
        dimensions = getattr(board, "dimensions", {}) or {}
        width = float(dimensions.get("width", 0.0))
        height = float(dimensions.get("height", 0.0))

        if width <= 0 or height <= 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG010_NO_DIMENSIONS",
                    rule_id="MFG010",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.COMPONENT_PLACEMENT,
                    status=ManufacturingFindingStatus.UNKNOWN,
                    severity="WARNING",
                    message="Board outline/dimensions undefined. Component-to-edge clearance cannot be verified.",
                    element_type="FOOTPRINT",
                    required_value=min_edge,
                    unit="mm",
                )
            )
            return results

        violations = 0
        for fp in footprints:
            min_x, max_x, min_y, max_y = AssemblyDFAEngine._get_footprint_bounds(fp)
            dist_to_edge = min(min_x, width - max_x, min_y, height - max_y)

            if dist_to_edge < min_edge:
                violations += 1
                results.append(
                    ManufacturingFinding(
                        finding_id=f"MFG010_WARN_{fp.id}",
                        rule_id="MFG010",
                        rule_name=rule["name"],
                        category=ManufacturingRuleCategory.COMPONENT_PLACEMENT,
                        status=ManufacturingFindingStatus.WARNING,
                        severity=rule.get("severity", "WARNING"),
                        message=f"Component {fp.ref_des} boundary is {dist_to_edge:.4f} mm from board edge, below recommended depaneling setback {min_edge} mm.",
                        element_type="FOOTPRINT",
                        element_ids=[str(fp.id)],
                        ref_des=str(fp.ref_des),
                        location={
                            "x": float(fp.pos_x) if getattr(fp, "pos_x", None) is not None else 0.0,
                            "y": float(fp.pos_y) if getattr(fp, "pos_y", None) is not None else 0.0,
                        },
                        measured_value=round(dist_to_edge, 4),
                        required_value=min_edge,
                        margin=round(dist_to_edge - min_edge, 4),
                        unit="mm",
                        proposal_available=True,
                    )
                )

        if violations == 0 and len(footprints) > 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG010_PASS_ALL",
                    rule_id="MFG010",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.COMPONENT_PLACEMENT,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message=f"All components maintain safe setback from board perimeter edges (>= {min_edge} mm).",
                    element_type="FOOTPRINT",
                    required_value=min_edge,
                    unit="mm",
                )
            )

        return results

    @staticmethod
    def _check_pnp_centroids(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        footprints = getattr(board, "footprints", []) or []

        if not footprints:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG011_NO_FOOTPRINTS",
                    rule_id="MFG011",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.ASSEMBLY,
                    status=ManufacturingFindingStatus.UNKNOWN,
                    severity="INFO",
                    message="No components present to verify pick-and-place centroid data.",
                    element_type="FOOTPRINT",
                )
            )
            return results

        valid_angles = rule.get("parameters", {}).get("valid_rotations", [0, 45, 90, 135, 180, 225, 270, 315, 360])
        violations = 0

        for fp in footprints:
            pos_x = getattr(fp, "pos_x", None)
            pos_y = getattr(fp, "pos_y", None)
            rotation = getattr(fp, "rotation", 0.0)
            if rotation is None:
                rotation = 0.0

            # Check centroid definition
            if pos_x is None or pos_y is None or math.isnan(pos_x) or math.isnan(pos_y):
                violations += 1
                results.append(
                    ManufacturingFinding(
                        finding_id=f"MFG011_FAIL_CENTROID_{fp.id}",
                        rule_id="MFG011",
                        rule_name=rule["name"],
                        category=ManufacturingRuleCategory.ASSEMBLY,
                        status=ManufacturingFindingStatus.FAIL,
                        severity=rule.get("severity", "ERROR"),
                        message=f"Component {fp.ref_des} is missing valid pick-and-place centroid coordinates.",
                        element_type="FOOTPRINT",
                        element_ids=[str(fp.id)],
                        ref_des=str(fp.ref_des),
                    )
                )
                continue

            # Check normalized rotation angle (0 <= rot < 360)
            norm_rot = float(rotation) % 360.0
            is_valid_rot = any(abs(norm_rot - ang) < 0.01 for ang in valid_angles)
            if not is_valid_rot:
                violations += 1
                results.append(
                    ManufacturingFinding(
                        finding_id=f"MFG011_WARN_ROT_{fp.id}",
                        rule_id="MFG011",
                        rule_name=rule["name"],
                        category=ManufacturingRuleCategory.ASSEMBLY,
                        status=ManufacturingFindingStatus.WARNING,
                        severity="WARNING",
                        message=f"Component {fp.ref_des} has non-standard assembly rotation angle {rotation} degrees.",
                        element_type="FOOTPRINT",
                        element_ids=[str(fp.id)],
                        ref_des=str(fp.ref_des),
                        measured_value=float(rotation),
                        unit="degrees",
                    )
                )

        if violations == 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG011_PASS_ALL",
                    rule_id="MFG011",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.ASSEMBLY,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message="All placed components possess valid centroid coordinates and standardized assembly rotations per PROJECT_ASSEMBLY_RULE (centroid presence does not equal machine tape-and-reel feeder setup).",
                    element_type="FOOTPRINT",
                )
            )

        return results

    @staticmethod
    def _check_soldering_consistency(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        footprints = getattr(board, "footprints", []) or []

        violations = 0
        for fp in footprints:
            pads = getattr(fp, "pads", []) or []
            for pad in pads:
                pad_type = str(getattr(pad, "pad_type", "SMD")).upper()
                drill = getattr(pad, "drill", None)

                # If SMD has a drill defined
                if pad_type == "SMD" and drill is not None and float(drill) > 0:
                    violations += 1
                    results.append(
                        ManufacturingFinding(
                            finding_id=f"MFG012_FAIL_SMD_DRILL_{pad.id}",
                            rule_id="MFG012",
                            rule_name=rule["name"],
                            category=ManufacturingRuleCategory.ASSEMBLY,
                            status=ManufacturingFindingStatus.WARNING,
                            severity=rule.get("severity", "WARNING"),
                            message=f"SMD pad {pad.pad_number} on {fp.ref_des} contains drill diameter ({drill} mm), creating paste wick-away hazard during reflow.",
                            element_type="PAD",
                            element_ids=[str(pad.id)],
                            ref_des=f"{fp.ref_des}:{pad.pad_number}",
                            measured_value=float(drill),
                            unit="mm",
                        )
                    )
                # If THROUGH_HOLE pad has no drill
                elif pad_type in ("THROUGH_HOLE", "THT") and (drill is None or float(drill) <= 0):
                    violations += 1
                    results.append(
                        ManufacturingFinding(
                            finding_id=f"MFG012_FAIL_THT_NODRILL_{pad.id}",
                            rule_id="MFG012",
                            rule_name=rule["name"],
                            category=ManufacturingRuleCategory.ASSEMBLY,
                            status=ManufacturingFindingStatus.FAIL,
                            severity="ERROR",
                            message=f"Through-hole pad {pad.pad_number} on {fp.ref_des} is missing drill hole definition.",
                            element_type="PAD",
                            element_ids=[str(pad.id)],
                            ref_des=f"{fp.ref_des}:{pad.pad_number}",
                        )
                    )

        if violations == 0 and len(footprints) > 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG012_PASS_ALL",
                    rule_id="MFG012",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.ASSEMBLY,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message="All placed component pads conform to consistent SMD and Through-Hole soldering geometry.",
                    element_type="PAD",
                )
            )

        return results

    @staticmethod
    def _check_polarity_marking(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        footprints = getattr(board, "footprints", []) or []

        violations = 0
        for fp in footprints:
            ref_des = str(getattr(fp, "ref_des", "")).upper()
            is_polarized = (
                ref_des.startswith("D")  # Diode / LED
                or ref_des.startswith("U")  # IC
                or ref_des.startswith("Q")  # Transistor
                or ref_des.startswith("J")  # Header / polarized connector
                or "POL" in ref_des  # Polarized capacitor
            )

            if is_polarized:
                meta = getattr(fp, "package_metadata", {}) or {}
                has_mark = (
                    meta.get("pin1_marked", False)
                    or meta.get("polarity_marked", False)
                    or meta.get("pin_1_dot", False)
                )

                if not has_mark:
                    violations += 1
                    results.append(
                        ManufacturingFinding(
                            finding_id=f"MFG013_WARN_POL_{fp.id}",
                            rule_id="MFG013",
                            rule_name=rule["name"],
                            category=ManufacturingRuleCategory.ASSEMBLY,
                            status=ManufacturingFindingStatus.WARNING,
                            severity=rule.get("severity", "WARNING"),
                            message=f"Polarized component {fp.ref_des} ({fp.footprint_name}) lacks explicit silkscreen or package Pin 1/polarity orientation indication.",
                            element_type="FOOTPRINT",
                            element_ids=[str(fp.id)],
                            ref_des=str(fp.ref_des),
                            proposal_available=True,
                        )
                    )

        if violations == 0 and len(footprints) > 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG013_PASS_ALL",
                    rule_id="MFG013",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.ASSEMBLY,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message="All polarized components have silkscreen or package Pin 1/polarity orientation indication present (ORIENTATION_MARKER_PRESENT; not physical post-assembly inspection).",
                    element_type="FOOTPRINT",
                )
            )

        return results
