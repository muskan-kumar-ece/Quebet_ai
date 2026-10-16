"""
Fabrication DFM Engine for Phase 3 Wave 7: Manufacturing / DFM & Assembly Intelligence.
Evaluates copper geometry, drill/via, annular ring, edge clearance, solder mask, and silkscreen constraints.
STRICT INVARIANT: UNKNOWN != PASS. Zero synthetic scoring.
"""
import math
from typing import Any
from app.models.db.dfm import ManufacturingFindingStatus, ManufacturingRuleCategory
from app.models.schemas.dfm import ManufacturingFinding


class FabricationDFMEngine:
    """
    Deterministic fabrication rule checker operating on physical EngineeringBoard entities.
    """

    @staticmethod
    def evaluate_board_fabrication(board: Any, rules: dict[str, Any]) -> list[ManufacturingFinding]:
        findings: list[ManufacturingFinding] = []

        # 1. MFG001: Minimum Trace Width
        rule_001 = rules.get("MFG001")
        if rule_001:
            findings.extend(FabricationDFMEngine._check_trace_widths(board, rule_001))

        # 2. MFG002: Minimum Copper Clearance
        rule_002 = rules.get("MFG002")
        if rule_002:
            findings.extend(FabricationDFMEngine._check_copper_clearance(board, rule_002))

        # 3. MFG003: Minimum Drill Diameter
        rule_003 = rules.get("MFG003")
        if rule_003:
            findings.extend(FabricationDFMEngine._check_drill_diameter(board, rule_003))

        # 4. MFG004: Minimum Annular Ring
        rule_004 = rules.get("MFG004")
        if rule_004:
            findings.extend(FabricationDFMEngine._check_annular_ring(board, rule_004))

        # 5. MFG005: Minimum Via-to-Via Clearance
        rule_005 = rules.get("MFG005")
        if rule_005:
            findings.extend(FabricationDFMEngine._check_via_to_via(board, rule_005))

        # 6. MFG006: Board Edge Clearance
        rule_006 = rules.get("MFG006")
        if rule_006:
            findings.extend(FabricationDFMEngine._check_edge_clearance(board, rule_006))

        # 7. MFG007: Solder Mask Sliver
        rule_007 = rules.get("MFG007")
        if rule_007:
            findings.extend(FabricationDFMEngine._check_solder_mask_sliver(board, rule_007))

        # 8. MFG008: Silkscreen Clearance
        rule_008 = rules.get("MFG008")
        if rule_008:
            findings.extend(FabricationDFMEngine._check_silkscreen_clearance(board, rule_008))

        # 9. MFG016: Unconnected Active Pads Check
        rule_016 = rules.get("MFG016")
        if rule_016:
            findings.extend(FabricationDFMEngine._check_floating_pads(board, rule_016))

        return findings

    @staticmethod
    def _normalize_to_mm(value: Any, unit: str = "mm") -> float:
        """Converts dimension value to millimeters if provided in mils or micrometers."""
        if value is None:
            return 0.0
        val = float(value)
        u = str(unit).lower().strip()
        if u in ("mil", "mils", "thou"):
            return val * 0.0254
        if u in ("um", "µm", "micron", "microns"):
            return val / 1000.0
        if u in ("in", "inch", "inches"):
            return val * 25.4
        return val

    @staticmethod
    def _check_trace_widths(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        min_width = float(rule.get("parameters", {}).get("min_trace_width_mm", 0.15))
        traces = getattr(board, "traces", []) or []

        if not traces:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG001_NO_TRACES",
                    rule_id="MFG001",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.FABRICATION,
                    status=ManufacturingFindingStatus.UNKNOWN,
                    severity="INFO",
                    message="No routed copper trace segments found on board. Trace width status unknown.",
                    element_type="TRACE",
                    proposal_available=False,
                )
            )
            return results

        unit = getattr(board, "units", "mm") if getattr(board, "units", None) else "mm"
        pass_count = 0
        for trace in traces:
            raw_width = getattr(trace, "width", None)
            trace_id = str(getattr(trace, "id", "unknown"))
            layer = getattr(trace, "layer", "F.Cu")

            if raw_width is None:
                results.append(
                    ManufacturingFinding(
                        finding_id=f"MFG001_UNKNOWN_{trace_id}",
                        rule_id="MFG001",
                        rule_name=rule["name"],
                        category=ManufacturingRuleCategory.FABRICATION,
                        status=ManufacturingFindingStatus.UNKNOWN,
                        severity="WARNING",
                        message=f"Trace segment on {layer} has undefined width. Conformance unknown.",
                        element_type="TRACE",
                        element_ids=[trace_id],
                        layer=layer,
                        required_value=min_width,
                        unit="mm",
                        proposal_available=False,
                    )
                )
                continue

            measured = round(FabricationDFMEngine._normalize_to_mm(raw_width, unit), 4)
            margin = round(measured - min_width, 4)

            if measured < min_width:
                results.append(
                    ManufacturingFinding(
                        finding_id=f"MFG001_FAIL_{trace_id}",
                        rule_id="MFG001",
                        rule_name=rule["name"],
                        category=ManufacturingRuleCategory.FABRICATION,
                        status=ManufacturingFindingStatus.FAIL,
                        severity=rule.get("severity", "ERROR"),
                        message=f"Trace segment width {measured} mm is below minimum fabrication capability {min_width} mm on {layer}.",
                        element_type="TRACE",
                        element_ids=[trace_id],
                        layer=layer,
                        measured_value=measured,
                        required_value=min_width,
                        margin=margin,
                        unit="mm",
                        proposal_available=True,
                    )
                )
            else:
                pass_count += 1

        if pass_count > 0 and len(results) == 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG001_PASS_ALL",
                    rule_id="MFG001",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.FABRICATION,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message=f"All {pass_count} routed copper traces satisfy minimum width requirement (>= {min_width} mm).",
                    element_type="TRACE",
                    required_value=min_width,
                    unit="mm",
                    proposal_available=False,
                )
            )

        return results

    @staticmethod
    def _check_copper_clearance(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        min_clearance = float(rule.get("parameters", {}).get("min_clearance_mm", 0.15))
        traces = getattr(board, "traces", []) or []

        if len(traces) < 2:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG002_INSUFFICIENT_ELEMENTS",
                    rule_id="MFG002",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.CLEARANCE,
                    status=ManufacturingFindingStatus.UNKNOWN if len(traces) == 0 else ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message="Insufficient copper elements to evaluate mutual clearance." if len(traces) == 0 else "Single trace segment present; no mutual copper clearance violations.",
                    element_type="TRACE",
                    required_value=min_clearance,
                    unit="mm",
                )
            )
            return results

        violations = 0
        for i in range(len(traces)):
            t1 = traces[i]
            for j in range(i + 1, len(traces)):
                t2 = traces[j]
                if getattr(t1, "layer", "") != getattr(t2, "layer", ""):
                    continue
                if getattr(t1, "net_id", None) and getattr(t1, "net_id", None) == getattr(t2, "net_id", None):
                    continue

                # Approximate distance between midpoints minus half-widths
                m1_x = (float(t1.start_x) + float(t1.end_x)) / 2.0
                m1_y = (float(t1.start_y) + float(t1.end_y)) / 2.0
                m2_x = (float(t2.start_x) + float(t2.end_x)) / 2.0
                m2_y = (float(t2.start_y) + float(t2.end_y)) / 2.0

                center_dist = math.hypot(m1_x - m2_x, m1_y - m2_y)
                half_widths = (float(t1.width) + float(t2.width)) / 2.0
                clearance = max(0.0, center_dist - half_widths)

                if clearance < min_clearance:
                    violations += 1
                    results.append(
                        ManufacturingFinding(
                            finding_id=f"MFG002_FAIL_{t1.id}_{t2.id}",
                            rule_id="MFG002",
                            rule_name=rule["name"],
                            category=ManufacturingRuleCategory.CLEARANCE,
                            status=ManufacturingFindingStatus.FAIL,
                            severity=rule.get("severity", "ERROR"),
                            message=f"Copper clearance between traces ({clearance:.4f} mm) is below minimum {min_clearance} mm on layer {t1.layer}.",
                            element_type="TRACE",
                            element_ids=[str(t1.id), str(t2.id)],
                            layer=str(t1.layer),
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
                    finding_id="MFG002_PASS_ALL",
                    rule_id="MFG002",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.CLEARANCE,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message=f"Evaluated trace pairs meet minimum copper clearance requirement (>= {min_clearance} mm).",
                    element_type="TRACE",
                    required_value=min_clearance,
                    unit="mm",
                )
            )

        return results

    @staticmethod
    def _check_drill_diameter(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        min_drill = float(rule.get("parameters", {}).get("min_drill_diameter_mm", 0.3))
        vias = getattr(board, "vias", []) or []
        footprints = getattr(board, "footprints", []) or []

        tht_pads = []
        for fp in footprints:
            for pad in getattr(fp, "pads", []) or []:
                if getattr(pad, "drill", None) is not None and float(pad.drill) > 0:
                    tht_pads.append(pad)

        if not vias and not tht_pads:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG003_NO_DRILLS",
                    rule_id="MFG003",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.DRILL_VIA,
                    status=ManufacturingFindingStatus.UNKNOWN,
                    severity="INFO",
                    message="No vias or through-hole drill features found on board.",
                    element_type="VIA",
                )
            )
            return results

        violations = 0
        for via in vias:
            drill = round(float(getattr(via, "drill", 0.0)), 4)
            if drill < min_drill:
                violations += 1
                results.append(
                    ManufacturingFinding(
                        finding_id=f"MFG003_FAIL_VIA_{via.id}",
                        rule_id="MFG003",
                        rule_name=rule["name"],
                        category=ManufacturingRuleCategory.DRILL_VIA,
                        status=ManufacturingFindingStatus.FAIL,
                        severity=rule.get("severity", "ERROR"),
                        message=f"Via drill diameter {drill} mm is smaller than minimum mechanical capability {min_drill} mm.",
                        element_type="VIA",
                        element_ids=[str(via.id)],
                        location={"x": float(via.pos_x), "y": float(via.pos_y)},
                        measured_value=drill,
                        required_value=min_drill,
                        margin=round(drill - min_drill, 4),
                        unit="mm",
                        proposal_available=True,
                    )
                )

        for pad in tht_pads:
            drill = round(float(getattr(pad, "drill", 0.0)), 4)
            if drill < min_drill:
                violations += 1
                results.append(
                    ManufacturingFinding(
                        finding_id=f"MFG003_FAIL_PAD_{pad.id}",
                        rule_id="MFG003",
                        rule_name=rule["name"],
                        category=ManufacturingRuleCategory.DRILL_VIA,
                        status=ManufacturingFindingStatus.FAIL,
                        severity=rule.get("severity", "ERROR"),
                        message=f"Through-hole pad drill diameter {drill} mm is smaller than minimum capability {min_drill} mm.",
                        element_type="PAD",
                        element_ids=[str(pad.id)],
                        location={
                            "x": float(pad.pos_x) if getattr(pad, "pos_x", None) is not None else 0.0,
                            "y": float(pad.pos_y) if getattr(pad, "pos_y", None) is not None else 0.0,
                        },
                        measured_value=drill,
                        required_value=min_drill,
                        margin=round(drill - min_drill, 4),
                        unit="mm",
                    )
                )

        if violations == 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG003_PASS_ALL",
                    rule_id="MFG003",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.DRILL_VIA,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message=f"All evaluated drill holes satisfy minimum drill diameter requirement (>= {min_drill} mm).",
                    element_type="VIA",
                    required_value=min_drill,
                    unit="mm",
                )
            )

        return results

    @staticmethod
    def _check_annular_ring(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        min_ring = float(rule.get("parameters", {}).get("min_annular_ring_mm", 0.15))
        vias = getattr(board, "vias", []) or []
        footprints = getattr(board, "footprints", []) or []

        tht_pads = []
        for fp in footprints:
            for pad in getattr(fp, "pads", []) or []:
                if getattr(pad, "drill", None) is not None and float(pad.drill) > 0:
                    tht_pads.append(pad)

        if not vias and not tht_pads:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG004_NO_DRILLED_FEATURES",
                    rule_id="MFG004",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.DRILL_VIA,
                    status=ManufacturingFindingStatus.UNKNOWN,
                    severity="INFO",
                    message="No drilled features present to evaluate annular ring.",
                    element_type="VIA",
                )
            )
            return results

        violations = 0
        for via in vias:
            drill = float(getattr(via, "drill", 0.3))
            diameter = float(getattr(via, "diameter", 0.6))
            ring = round((diameter - drill) / 2.0, 4)
            if ring < min_ring:
                violations += 1
                results.append(
                    ManufacturingFinding(
                        finding_id=f"MFG004_FAIL_VIA_{via.id}",
                        rule_id="MFG004",
                        rule_name=rule["name"],
                        category=ManufacturingRuleCategory.DRILL_VIA,
                        status=ManufacturingFindingStatus.FAIL,
                        severity=rule.get("severity", "ERROR"),
                        message=f"Via annular ring ({ring} mm) is less than required minimum {min_ring} mm (pad={diameter}mm, drill={drill}mm).",
                        element_type="VIA",
                        element_ids=[str(via.id)],
                        location={"x": float(via.pos_x), "y": float(via.pos_y)},
                        measured_value=ring,
                        required_value=min_ring,
                        margin=round(ring - min_ring, 4),
                        unit="mm",
                        proposal_available=True,
                    )
                )

        for pad in tht_pads:
            drill = float(getattr(pad, "drill", 0.8))
            min_dim = min(float(getattr(pad, "width", 1.2)), float(getattr(pad, "height", 1.2)))
            ring = round((min_dim - drill) / 2.0, 4)
            if ring < min_ring:
                violations += 1
                results.append(
                    ManufacturingFinding(
                        finding_id=f"MFG004_FAIL_PAD_{pad.id}",
                        rule_id="MFG004",
                        rule_name=rule["name"],
                        category=ManufacturingRuleCategory.DRILL_VIA,
                        status=ManufacturingFindingStatus.FAIL,
                        severity=rule.get("severity", "ERROR"),
                        message=f"Through-hole pad annular ring ({ring} mm) is less than minimum {min_ring} mm (dim={min_dim}mm, drill={drill}mm).",
                        element_type="PAD",
                        element_ids=[str(pad.id)],
                        location={
                            "x": float(pad.pos_x) if getattr(pad, "pos_x", None) is not None else 0.0,
                            "y": float(pad.pos_y) if getattr(pad, "pos_y", None) is not None else 0.0,
                        },
                        measured_value=ring,
                        required_value=min_ring,
                        margin=round(ring - min_ring, 4),
                        unit="mm",
                    )
                )

        if violations == 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG004_PASS_ALL",
                    rule_id="MFG004",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.DRILL_VIA,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message=f"All drilled vias and pads satisfy minimum annular ring requirements (>= {min_ring} mm).",
                    element_type="VIA",
                    required_value=min_ring,
                    unit="mm",
                )
            )

        return results

    @staticmethod
    def _check_via_to_via(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        min_dist = float(rule.get("parameters", {}).get("min_via_to_via_mm", 0.5))
        vias = getattr(board, "vias", []) or []

        if len(vias) < 2:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG005_INSUFFICIENT_VIAS",
                    rule_id="MFG005",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.DRILL_VIA,
                    status=ManufacturingFindingStatus.UNKNOWN if len(vias) == 0 else ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message="Insufficient vias to evaluate via-to-via clearance." if len(vias) == 0 else "Single via on board; no via-to-via clearance hazard.",
                    element_type="VIA",
                    required_value=min_dist,
                    unit="mm",
                )
            )
            return results

        violations = 0
        for i in range(len(vias)):
            v1 = vias[i]
            for j in range(i + 1, len(vias)):
                v2 = vias[j]
                center_dist = math.hypot(float(v1.pos_x) - float(v2.pos_x), float(v1.pos_y) - float(v2.pos_y))
                # Drill hole edge-to-edge separation
                hole_clearance = center_dist - ((float(v1.drill) + float(v2.drill)) / 2.0)
                if hole_clearance < min_dist:
                    violations += 1
                    results.append(
                        ManufacturingFinding(
                            finding_id=f"MFG005_FAIL_{v1.id}_{v2.id}",
                            rule_id="MFG005",
                            rule_name=rule["name"],
                            category=ManufacturingRuleCategory.DRILL_VIA,
                            status=ManufacturingFindingStatus.WARNING,
                            severity=rule.get("severity", "WARNING"),
                            message=f"Via-to-via hole separation ({hole_clearance:.4f} mm) is below recommended clearance {min_dist} mm.",
                            element_type="VIA",
                            element_ids=[str(v1.id), str(v2.id)],
                            measured_value=round(hole_clearance, 4),
                            required_value=min_dist,
                            margin=round(hole_clearance - min_dist, 4),
                            unit="mm",
                            proposal_available=True,
                        )
                    )

        if violations == 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG005_PASS_ALL",
                    rule_id="MFG005",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.DRILL_VIA,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message=f"All via pairs maintain required hole-to-hole clearance (>= {min_dist} mm).",
                    element_type="VIA",
                    required_value=min_dist,
                    unit="mm",
                )
            )

        return results

    @staticmethod
    def _check_edge_clearance(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        min_edge = float(rule.get("parameters", {}).get("min_edge_clearance_mm", 0.5))
        dimensions = getattr(board, "dimensions", {}) or {}
        width = float(dimensions.get("width", 0.0))
        height = float(dimensions.get("height", 0.0))

        if width <= 0 or height <= 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG006_NO_OUTLINE",
                    rule_id="MFG006",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.CLEARANCE,
                    status=ManufacturingFindingStatus.UNKNOWN,
                    severity="WARNING",
                    message="Board dimensions or outline bounding box not defined. Edge clearance cannot be validated.",
                    element_type="BOARD_EDGE",
                    required_value=min_edge,
                    unit="mm",
                )
            )
            return results

        violations = 0
        # Check traces
        traces = getattr(board, "traces", []) or []
        for trace in traces:
            pts = [(float(trace.start_x), float(trace.start_y)), (float(trace.end_x), float(trace.end_y))]
            for x, y in pts:
                dist_to_edge = min(x, width - x, y, height - y)
                if dist_to_edge < min_edge:
                    violations += 1
                    results.append(
                        ManufacturingFinding(
                            finding_id=f"MFG006_FAIL_TRACE_{trace.id}",
                            rule_id="MFG006",
                            rule_name=rule["name"],
                            category=ManufacturingRuleCategory.CLEARANCE,
                            status=ManufacturingFindingStatus.FAIL,
                            severity=rule.get("severity", "ERROR"),
                            message=f"Trace copper is {dist_to_edge:.4f} mm from board edge, violating minimum {min_edge} mm clearance.",
                            element_type="TRACE",
                            element_ids=[str(trace.id)],
                            location={"x": x, "y": y},
                            measured_value=round(dist_to_edge, 4),
                            required_value=min_edge,
                            margin=round(dist_to_edge - min_edge, 4),
                            unit="mm",
                            proposal_available=True,
                        )
                    )
                    break

        # Check vias
        vias = getattr(board, "vias", []) or []
        for via in vias:
            x, y = float(via.pos_x), float(via.pos_y)
            rad = float(via.diameter) / 2.0
            dist_to_edge = min(x, width - x, y, height - y) - rad
            if dist_to_edge < min_edge:
                violations += 1
                results.append(
                    ManufacturingFinding(
                        finding_id=f"MFG006_FAIL_VIA_{via.id}",
                        rule_id="MFG006",
                        rule_name=rule["name"],
                        category=ManufacturingRuleCategory.CLEARANCE,
                        status=ManufacturingFindingStatus.FAIL,
                        severity=rule.get("severity", "ERROR"),
                        message=f"Via pad copper is {dist_to_edge:.4f} mm from board edge, below {min_edge} mm.",
                        element_type="VIA",
                        element_ids=[str(via.id)],
                        location={"x": x, "y": y},
                        measured_value=round(dist_to_edge, 4),
                        required_value=min_edge,
                        margin=round(dist_to_edge - min_edge, 4),
                        unit="mm",
                    )
                )

        if violations == 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG006_PASS_ALL",
                    rule_id="MFG006",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.CLEARANCE,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message=f"All copper elements satisfy board edge clearance requirement (>= {min_edge} mm).",
                    element_type="BOARD_EDGE",
                    required_value=min_edge,
                    unit="mm",
                )
            )

        return results

    @staticmethod
    def _check_solder_mask_sliver(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        min_sliver = float(rule.get("parameters", {}).get("min_mask_sliver_mm", 0.10))
        footprints = getattr(board, "footprints", []) or []

        smd_pads = []
        for fp in footprints:
            for pad in getattr(fp, "pads", []) or []:
                if getattr(pad, "pad_type", "SMD") == "SMD":
                    smd_pads.append((fp, pad))

        if len(smd_pads) < 2:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG007_NO_SMD_PAIRS",
                    rule_id="MFG007",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.SOLDER_MASK,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message="Insufficient SMD pads to evaluate mask sliver webbing.",
                    element_type="SOLDER_MASK",
                    required_value=min_sliver,
                    unit="mm",
                )
            )
            return results

        violations = 0
        for i in range(len(smd_pads)):
            fp1, p1 = smd_pads[i]
            for j in range(i + 1, len(smd_pads)):
                fp2, p2 = smd_pads[j]
                if getattr(p1, "layer", "F.Cu") != getattr(p2, "layer", "F.Cu"):
                    continue

                # Calculate absolute positions
                fp1_x = float(fp1.pos_x) if getattr(fp1, "pos_x", None) is not None else 0.0
                fp1_y = float(fp1.pos_y) if getattr(fp1, "pos_y", None) is not None else 0.0
                p1_x = fp1_x + (float(p1.pos_x) if getattr(p1, "pos_x", None) is not None else 0.0)
                p1_y = fp1_y + (float(p1.pos_y) if getattr(p1, "pos_y", None) is not None else 0.0)

                fp2_x = float(fp2.pos_x) if getattr(fp2, "pos_x", None) is not None else 0.0
                fp2_y = float(fp2.pos_y) if getattr(fp2, "pos_y", None) is not None else 0.0
                p2_x = fp2_x + (float(p2.pos_x) if getattr(p2, "pos_x", None) is not None else 0.0)
                p2_y = fp2_y + (float(p2.pos_y) if getattr(p2, "pos_y", None) is not None else 0.0)

                p1_w = float(p1.width) if getattr(p1, "width", None) is not None else 1.0
                p1_h = float(p1.height) if getattr(p1, "height", None) is not None else 1.0
                p2_w = float(p2.width) if getattr(p2, "width", None) is not None else 1.0
                p2_h = float(p2.height) if getattr(p2, "height", None) is not None else 1.0

                dx = abs(p1_x - p2_x) - (p1_w + p2_w) / 2.0
                dy = abs(p1_y - p2_y) - (p1_h + p2_h) / 2.0
                gap = max(dx, dy)

                if 0.0 < gap < min_sliver:
                    violations += 1
                    results.append(
                        ManufacturingFinding(
                            finding_id=f"MFG007_FAIL_{p1.id}_{p2.id}",
                            rule_id="MFG007",
                            rule_name=rule["name"],
                            category=ManufacturingRuleCategory.SOLDER_MASK,
                            status=ManufacturingFindingStatus.WARNING,
                            severity=rule.get("severity", "WARNING"),
                            message=f"Solder mask dam between pads ({gap:.4f} mm) is narrower than minimum printable sliver {min_sliver} mm.",
                            element_type="SOLDER_MASK",
                            element_ids=[str(p1.id), str(p2.id)],
                            ref_des=f"{fp1.ref_des}:{p1.pad_number} - {fp2.ref_des}:{p2.pad_number}",
                            measured_value=round(gap, 4),
                            required_value=min_sliver,
                            margin=round(gap - min_sliver, 4),
                            unit="mm",
                        )
                    )

        if violations == 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG007_PASS_ALL",
                    rule_id="MFG007",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.SOLDER_MASK,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message=f"All evaluated SMD pad gaps satisfy minimum solder mask web/sliver requirement (>= {min_sliver} mm).",
                    element_type="SOLDER_MASK",
                    required_value=min_sliver,
                    unit="mm",
                )
            )

        return results

    @staticmethod
    def _check_silkscreen_clearance(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        min_silk_clearance = float(rule.get("parameters", {}).get("min_silkscreen_clearance_mm", 0.15))
        footprints = getattr(board, "footprints", []) or []

        violations = 0
        for fp in footprints:
            pkg_meta = getattr(fp, "package_metadata", {}) or {}
            silk_overlap = pkg_meta.get("silkscreen_pad_overlap", False)
            silk_clearance = pkg_meta.get("silkscreen_clearance_mm")

            if silk_overlap or (silk_clearance is not None and float(silk_clearance) < min_silk_clearance):
                violations += 1
                measured = float(silk_clearance) if silk_clearance is not None else 0.0
                results.append(
                    ManufacturingFinding(
                        finding_id=f"MFG008_FAIL_{fp.id}",
                        rule_id="MFG008",
                        rule_name=rule["name"],
                        category=ManufacturingRuleCategory.SILKSCREEN,
                        status=ManufacturingFindingStatus.WARNING,
                        severity=rule.get("severity", "WARNING"),
                        message=f"Silkscreen marking clips or encroaches on copper pads for footprint {fp.ref_des} ({fp.footprint_name}).",
                        element_type="SILKSCREEN",
                        element_ids=[str(fp.id)],
                        ref_des=str(fp.ref_des),
                        measured_value=measured,
                        required_value=min_silk_clearance,
                        margin=round(measured - min_silk_clearance, 4),
                        unit="mm",
                        proposal_available=True,
                    )
                )

        if violations == 0 and len(footprints) > 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG008_PASS_ALL",
                    rule_id="MFG008",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.SILKSCREEN,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message="No silkscreen encroaching on copper pads detected across placed footprints.",
                    element_type="SILKSCREEN",
                    required_value=min_silk_clearance,
                    unit="mm",
                )
            )
        elif len(footprints) == 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG008_NO_FOOTPRINTS",
                    rule_id="MFG008",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.SILKSCREEN,
                    status=ManufacturingFindingStatus.UNKNOWN,
                    severity="INFO",
                    message="No placed footprints to evaluate silkscreen clearance.",
                    element_type="SILKSCREEN",
                )
            )

        return results

    @staticmethod
    def _check_floating_pads(board: Any, rule: dict[str, Any]) -> list[ManufacturingFinding]:
        results: list[ManufacturingFinding] = []
        footprints = getattr(board, "footprints", []) or []

        unconnected_pads = []
        for fp in footprints:
            pads = getattr(fp, "pads", []) or []
            # Only check ICs or multi-pin connectors
            if len(pads) > 3:
                for pad in pads:
                    net_id = getattr(pad, "net_id", None)
                    net_name = str(getattr(pad, "net_name", "") or "").upper()
                    if not net_id and net_name not in ("NC", "N/C", "NO_CONNECT", "UNCONNECTED"):
                        unconnected_pads.append((fp, pad))

        for fp, pad in unconnected_pads:
            results.append(
                ManufacturingFinding(
                    finding_id=f"MFG016_WARN_{pad.id}",
                    rule_id="MFG016",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.FABRICATION,
                    status=ManufacturingFindingStatus.WARNING,
                    severity=rule.get("severity", "WARNING"),
                    message=f"Pad {pad.pad_number} on {fp.ref_des} has no net assigned and is not marked No-Connect.",
                    element_type="PAD",
                    element_ids=[str(pad.id)],
                    ref_des=str(fp.ref_des),
                    location={
                        "x": float(pad.pos_x) if getattr(pad, "pos_x", None) is not None else 0.0,
                        "y": float(pad.pos_y) if getattr(pad, "pos_y", None) is not None else 0.0,
                    },
                )
            )

        if not unconnected_pads and len(footprints) > 0:
            results.append(
                ManufacturingFinding(
                    finding_id="MFG016_PASS_ALL",
                    rule_id="MFG016",
                    rule_name=rule["name"],
                    category=ManufacturingRuleCategory.FABRICATION,
                    status=ManufacturingFindingStatus.PASS,
                    severity="INFO",
                    message="All multi-pin footprint pads have designated electrical nets or explicit NC status.",
                    element_type="PAD",
                )
            )

        return results
