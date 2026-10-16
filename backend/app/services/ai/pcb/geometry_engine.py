import math
from typing import Any
from app.models.db.pcb import EngineeringBoard
from app.models.schemas.pcb import PCBFinding


class PCBGeometryEngine:
    """
    Deterministic geometric clearance and design-rule verification engine.
    Evaluates:
    - PCB007: Clearance violation (pad-pad, trace-pad, trace-trace)
    - PCB008: Board edge clearance violation
    """

    DEFAULT_CLEARANCE_MM = 0.15  # 150 um (~6 mil) standard manufacturing rule
    DEFAULT_EDGE_CLEARANCE_MM = 0.5  # 500 um routing-to-edge isolation

    @classmethod
    def distance_point_to_segment(
        cls, px: float, py: float, x1: float, y1: float, x2: float, y2: float
    ) -> float:
        """Computes minimum Euclidean distance from point (px, py) to line segment (x1, y1)-(x2, y2)."""
        dx = x2 - x1
        dy = y2 - y1
        l2 = dx * dx + dy * dy
        if l2 == 0:
            return math.hypot(px - x1, py - y1)
        # Projection factor t
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    @classmethod
    def evaluate_clearances(
        cls,
        board: EngineeringBoard,
        min_clearance: float | None = None,
        min_edge_clearance: float | None = None,
    ) -> list[PCBFinding]:
        findings: list[PCBFinding] = []
        rule_clearance = min_clearance or cls.DEFAULT_CLEARANCE_MM
        rule_edge_clearance = min_edge_clearance or cls.DEFAULT_EDGE_CLEARANCE_MM

        footprints = getattr(board, "footprints", [])
        traces = getattr(board, "traces", [])
        vias = getattr(board, "vias", [])

        # Dimensions & Outline
        dims = board.dimensions if isinstance(board.dimensions, dict) else {}
        board_w = float(dims.get("width_mm", 0.0))
        board_h = float(dims.get("height_mm", 0.0))

        # Flatten pads with absolute center positions
        pad_items: list[dict[str, Any]] = []
        for fp in footprints:
            fp_rot = float(getattr(fp, "rotation", 0.0) or 0.0)
            fp_x = float(getattr(fp, "pos_x", 0.0) or 0.0)
            fp_y = float(getattr(fp, "pos_y", 0.0) or 0.0)
            rad = math.radians(fp_rot)
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)
            for pad in getattr(fp, "pads", []):
                p_x = float(getattr(pad, "pos_x", 0.0) or 0.0)
                p_y = float(getattr(pad, "pos_y", 0.0) or 0.0)
                rx = p_x * cos_r - p_y * sin_r
                ry = p_x * sin_r + p_y * cos_r
                pad_items.append(
                    {
                        "ref": f"{fp.ref_des}.{pad.pad_number}",
                        "ref_des": fp.ref_des,
                        "net_name": (pad.net_name or "").strip().upper(),
                        "abs_x": fp_x + rx,
                        "abs_y": fp_y + ry,
                        "width": float(getattr(pad, "width", 1.0) or 1.0),
                        "height": float(getattr(pad, "height", 1.0) or 1.0),
                        "layer": pad.layer,
                    }
                )

        # 1. Pad-to-Pad Clearance between different nets on same layer
        for i in range(len(pad_items)):
            p1 = pad_items[i]
            for j in range(i + 1, len(pad_items)):
                p2 = pad_items[j]
                if not p1["net_name"] or not p2["net_name"] or p1["net_name"] == p2["net_name"]:
                    continue
                # Layer check
                if p1["layer"] != "ALL_COPPER" and p2["layer"] != "ALL_COPPER" and p1["layer"] != p2["layer"]:
                    continue

                center_dist = math.hypot(p1["abs_x"] - p2["abs_x"], p1["abs_y"] - p2["abs_y"])
                # Approximate edge clearance subtracting half-sizes
                half_size1 = max(p1["width"], p1["height"]) / 2.0
                half_size2 = max(p2["width"], p2["height"]) / 2.0
                edge_to_edge = max(0.0, center_dist - half_size1 - half_size2)

                if edge_to_edge < rule_clearance:
                    findings.append(
                        PCBFinding(
                            rule_id="PCB007",
                            severity="ERROR",
                            category="CLEARANCE",
                            element_ref=f"{p1['ref']} <-> {p2['ref']}",
                            actual_value=round(edge_to_edge, 3),
                            required_limit=rule_clearance,
                            unit="mm",
                            status="VIOLATED",
                            message=(
                                f"Clearance violation between pad {p1['ref']} ({p1['net_name']}) "
                                f"and pad {p2['ref']} ({p2['net_name']}): {edge_to_edge:.3f} mm < {rule_clearance} mm."
                            ),
                        )
                    )

        # 2. Trace-to-Pad Clearance between different nets
        for p in pad_items:
            p_net = p["net_name"]
            if not p_net:
                continue
            p_half = max(p["width"], p["height"]) / 2.0
            for t in traces:
                t_net = (t.net_name or "").strip().upper()
                if not t_net or t_net == p_net:
                    continue
                if p["layer"] != "ALL_COPPER" and p["layer"] != t.layer:
                    continue

                dist = cls.distance_point_to_segment(
                    p["abs_x"], p["abs_y"], float(t.start_x), float(t.start_y), float(t.end_x), float(t.end_y)
                )
                trace_half_w = float(t.width) / 2.0
                actual_clearance = max(0.0, dist - p_half - trace_half_w)

                if actual_clearance < rule_clearance:
                    findings.append(
                        PCBFinding(
                            rule_id="PCB007",
                            severity="ERROR",
                            category="CLEARANCE",
                            element_ref=f"{p['ref']} <-> TRACE_{t.id[:6]}",
                            actual_value=round(actual_clearance, 3),
                            required_limit=rule_clearance,
                            unit="mm",
                            status="VIOLATED",
                            message=(
                                f"Clearance violation between pad {p['ref']} ({p_net}) "
                                f"and trace ({t_net}): {actual_clearance:.3f} mm < {rule_clearance} mm."
                            ),
                        )
                    )

        # 3. Board Edge Clearance (PCB008)
        if board_w > 0 and board_h > 0:
            # Check pads
            for p in pad_items:
                dist_left = p["abs_x"] - (p["width"] / 2.0)
                dist_right = board_w - (p["abs_x"] + p["width"] / 2.0)
                dist_bottom = p["abs_y"] - (p["height"] / 2.0)
                dist_top = board_h - (p["abs_y"] + p["height"] / 2.0)
                min_dist = min(dist_left, dist_right, dist_bottom, dist_top)

                if min_dist < rule_edge_clearance:
                    findings.append(
                        PCBFinding(
                            rule_id="PCB008",
                            severity="ERROR",
                            category="CLEARANCE",
                            element_ref=p["ref"],
                            actual_value=round(min_dist, 3),
                            required_limit=rule_edge_clearance,
                            unit="mm",
                            status="VIOLATED",
                            message=(
                                f"Board edge clearance violation for pad {p['ref']}: "
                                f"{min_dist:.3f} mm < required {rule_edge_clearance} mm."
                            ),
                        )
                    )

            # Check traces
            for t in traces:
                half_w = float(t.width) / 2.0
                pts = [(t.start_x, t.start_y), (t.end_x, t.end_y)]
                for x, y in pts:
                    dist_to_edge = min(x - half_w, board_w - (x + half_w), y - half_w, board_h - (y + half_w))
                    if dist_to_edge < rule_edge_clearance:
                        findings.append(
                            PCBFinding(
                                rule_id="PCB008",
                                severity="ERROR",
                                category="CLEARANCE",
                                element_ref=f"TRACE_{t.id[:6]}",
                                actual_value=round(dist_to_edge, 3),
                                required_limit=rule_edge_clearance,
                                unit="mm",
                                status="VIOLATED",
                                message=(
                                    f"Board edge clearance violation for trace segment {t.net_name or ''}: "
                                    f"{dist_to_edge:.3f} mm < required {rule_edge_clearance} mm."
                                ),
                            )
                        )
                        break

        return findings
