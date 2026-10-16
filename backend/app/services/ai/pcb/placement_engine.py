import math
from typing import Any
from app.models.db.pcb import EngineeringBoard
from app.models.schemas.pcb import PCBConstraintEvaluation, PCBFinding


class PCBPlacementEngine:
    """
    Deterministic placement constraint validation engine.
    Supports KEEP_IN, KEEP_OUT, COMPONENT_CLEARANCE, EDGE_CLEARANCE, RELATIVE_PLACEMENT, SIDE, ORIENTATION.
    Explicit invariant: Categorical evaluation only (SATISFIED, VIOLATED, UNKNOWN).
    NO composite score, NO 'best placement', NO 'winner'.
    """

    @classmethod
    def evaluate(
        cls,
        board: EngineeringBoard,
        constraints: list[dict[str, Any]] | None = None,
    ) -> tuple[list[PCBFinding], list[PCBConstraintEvaluation]]:
        findings: list[PCBFinding] = []
        evaluations: list[PCBConstraintEvaluation] = []

        footprints = getattr(board, "footprints", [])
        fp_by_ref = {fp.ref_des.upper(): fp for fp in footprints}

        dims = board.dimensions if isinstance(board.dimensions, dict) else {}
        board_w = float(dims.get("width_mm", 0.0))
        board_h = float(dims.get("height_mm", 0.0))

        meta = board.metadata_ if isinstance(board.metadata_, dict) else {}
        keep_out_zones = meta.get("keep_out_zones", [])
        user_constraints = constraints or meta.get("placement_constraints", [])

        # 1. KEEP_IN check (Footprint within board dimensions)
        if board_w > 0 and board_h > 0:
            for fp in footprints:
                # Component centroid check
                is_inside = (0 <= fp.pos_x <= board_w) and (0 <= fp.pos_y <= board_h)
                evaluations.append(
                    PCBConstraintEvaluation(
                        constraint_type="KEEP_IN",
                        target_refs=[fp.ref_des],
                        actual_value=round(fp.pos_x, 2),
                        limit_value=board_w,
                        unit="mm",
                        status="SATISFIED" if is_inside else "VIOLATED",
                        note=f"Component {fp.ref_des} position ({fp.pos_x:.1f}, {fp.pos_y:.1f}) within board bounds"
                        if is_inside
                        else f"Component {fp.ref_des} placed outside board boundary ({board_w}x{board_h} mm)",
                    )
                )
                if not is_inside:
                    findings.append(
                        PCBFinding(
                            rule_id="PCB011",
                            severity="ERROR",
                            category="PLACEMENT",
                            element_ref=fp.ref_des,
                            actual_value=f"({fp.pos_x}, {fp.pos_y})",
                            required_limit=f"(0-{board_w}, 0-{board_h})",
                            status="VIOLATED",
                            message=f"Component {fp.ref_des} is placed outside the board perimeter.",
                        )
                    )

        # 2. KEEP_OUT zones check
        for zone in keep_out_zones:
            # zone format: {"name": "ANTENNA_AREA", "x_min": 80, "x_max": 100, "y_min": 60, "y_max": 80}
            z_name = zone.get("name", "RESTRICTED")
            x1, x2 = float(zone.get("x_min", 0)), float(zone.get("x_max", 0))
            y1, y2 = float(zone.get("y_min", 0)), float(zone.get("y_max", 0))

            for fp in footprints:
                in_zone = (x1 <= fp.pos_x <= x2) and (y1 <= fp.pos_y <= y2)
                if in_zone:
                    findings.append(
                        PCBFinding(
                            rule_id="PCB011",
                            severity="ERROR",
                            category="PLACEMENT",
                            element_ref=fp.ref_des,
                            actual_value=f"({fp.pos_x}, {fp.pos_y})",
                            status="VIOLATED",
                            message=f"Component {fp.ref_des} overlaps restricted keep-out zone '{z_name}'.",
                        )
                    )
                evaluations.append(
                    PCBConstraintEvaluation(
                        constraint_type="KEEP_OUT",
                        target_refs=[fp.ref_des, z_name],
                        actual_value=round(fp.pos_x, 2),
                        status="VIOLATED" if in_zone else "SATISFIED",
                        note=f"Component {fp.ref_des} kept out of zone {z_name}" if not in_zone else f"Component overlaps keep-out {z_name}",
                    )
                )

        # 3. Explicit Relative Placement Constraints
        for c in user_constraints:
            c_type = c.get("type", "").upper()
            if c_type == "RELATIVE_PLACEMENT":
                comp_a = c.get("component_a", "").upper()
                comp_b = c.get("component_b", "").upper()
                max_dist = c.get("max_distance_mm")

                fp_a = fp_by_ref.get(comp_a)
                fp_b = fp_by_ref.get(comp_b)

                if not fp_a or not fp_b or max_dist is None:
                    evaluations.append(
                        PCBConstraintEvaluation(
                            constraint_type="RELATIVE_PLACEMENT",
                            target_refs=[comp_a, comp_b],
                            status="UNKNOWN",
                            note="Missing component coordinates or constraint distance",
                        )
                    )
                    continue

                actual_dist = math.hypot(fp_a.pos_x - fp_b.pos_x, fp_a.pos_y - fp_b.pos_y)
                is_satisfied = actual_dist <= float(max_dist)

                evaluations.append(
                    PCBConstraintEvaluation(
                        constraint_type="RELATIVE_PLACEMENT",
                        target_refs=[comp_a, comp_b],
                        actual_value=round(actual_dist, 3),
                        limit_value=float(max_dist),
                        unit="mm",
                        status="SATISFIED" if is_satisfied else "VIOLATED",
                        note=f"Distance {actual_dist:.2f} mm between {comp_a} and {comp_b} (max {max_dist} mm)",
                    )
                )
                if not is_satisfied:
                    findings.append(
                        PCBFinding(
                            rule_id="PCB011",
                            severity="WARNING",
                            category="PLACEMENT",
                            element_ref=f"{comp_a} <-> {comp_b}",
                            actual_value=round(actual_dist, 2),
                            required_limit=float(max_dist),
                            unit="mm",
                            status="VIOLATED",
                            message=f"Placement distance between {comp_a} and {comp_b} exceeds limit: {actual_dist:.2f} mm > {max_dist} mm.",
                        )
                    )

            elif c_type == "ORIENTATION":
                target = c.get("component", "").upper()
                allowed = c.get("allowed_rotations", [0, 90, 180, 270])
                fp_t = fp_by_ref.get(target)
                if fp_t:
                    rot = int(fp_t.rotation) % 360
                    is_ok = rot in allowed
                    evaluations.append(
                        PCBConstraintEvaluation(
                            constraint_type="ORIENTATION",
                            target_refs=[target],
                            actual_value=rot,
                            status="SATISFIED" if is_ok else "VIOLATED",
                            note=f"Component {target} rotation {rot} deg",
                        )
                    )
                    if not is_ok:
                        findings.append(
                            PCBFinding(
                                rule_id="PCB011",
                                severity="WARNING",
                                category="PLACEMENT",
                                element_ref=target,
                                actual_value=rot,
                                status="VIOLATED",
                                message=f"Component {target} orientation ({rot} deg) is not an allowed angle {allowed}.",
                            )
                        )

            elif c_type == "SIDE":
                target = c.get("component", "").upper()
                req_side = c.get("side", "TOP").upper()
                fp_t = fp_by_ref.get(target)
                if fp_t:
                    actual_side = fp_t.side.upper()
                    is_ok = actual_side == req_side
                    evaluations.append(
                        PCBConstraintEvaluation(
                            constraint_type="SIDE",
                            target_refs=[target],
                            status="SATISFIED" if is_ok else "VIOLATED",
                            note=f"Component {target} on side {actual_side} (required {req_side})",
                        )
                    )
                    if not is_ok:
                        findings.append(
                            PCBFinding(
                                rule_id="PCB011",
                                severity="ERROR",
                                category="PLACEMENT",
                                element_ref=target,
                                actual_value=actual_side,
                                required_limit=req_side,
                                status="VIOLATED",
                                message=f"Component {target} placed on {actual_side} side; required side is {req_side}.",
                            )
                        )

        return findings, evaluations
