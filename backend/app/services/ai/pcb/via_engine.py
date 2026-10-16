import math
from typing import Any
from app.models.db.pcb import EngineeringBoard
from app.models.schemas.pcb import PCBFinding


class PCBViaEngine:
    """
    Deterministic via constraint and annular ring validation engine.
    Rule:
    - PCB010: Via constraint violation (drill too small, insufficient annular ring, via-via clearance)
    """

    MIN_DRILL_MM = 0.2  # 200 um minimum mechanical drill
    MIN_ANNULAR_RING_MM = 0.125  # 125 um minimum annular ring width

    @classmethod
    def evaluate(
        cls,
        board: EngineeringBoard,
        min_drill_mm: float | None = None,
        min_annular_ring_mm: float | None = None,
    ) -> list[PCBFinding]:
        findings: list[PCBFinding] = []
        limit_drill = min_drill_mm or cls.MIN_DRILL_MM
        limit_ring = min_annular_ring_mm or cls.MIN_ANNULAR_RING_MM

        vias = getattr(board, "vias", [])

        for v in vias:
            via_ref = f"VIA_{v.id[:6]}"
            drill = float(v.drill)
            diam = float(v.diameter)

            # 1. Minimum drill check
            if drill < limit_drill:
                findings.append(
                    PCBFinding(
                        rule_id="PCB010",
                        severity="ERROR",
                        category="CLEARANCE",
                        element_ref=via_ref,
                        actual_value=drill,
                        required_limit=limit_drill,
                        unit="mm",
                        status="VIOLATED",
                        message=f"Via drill diameter {drill:.3f} mm is below manufacturing minimum {limit_drill:.3f} mm.",
                    )
                )

            # 2. Annular ring check: ring = (diameter - drill) / 2
            actual_ring = (diam - drill) / 2.0
            if actual_ring < limit_ring:
                findings.append(
                    PCBFinding(
                        rule_id="PCB010",
                        severity="ERROR",
                        category="CLEARANCE",
                        element_ref=via_ref,
                        actual_value=round(actual_ring, 3),
                        required_limit=limit_ring,
                        unit="mm",
                        status="VIOLATED",
                        message=(
                            f"Via annular ring {actual_ring:.3f} mm is below required minimum {limit_ring:.3f} mm "
                            f"(diameter={diam}mm, drill={drill}mm)."
                        ),
                    )
                )

        # 3. Via-to-Via clearance
        for i in range(len(vias)):
            v1 = vias[i]
            for j in range(i + 1, len(vias)):
                v2 = vias[j]
                net1 = (v1.net_name or "").strip().upper()
                net2 = (v2.net_name or "").strip().upper()
                if net1 and net2 and net1 == net2:
                    continue  # Same net vias can touch/stitch

                center_dist = math.hypot(float(v1.pos_x) - float(v2.pos_x), float(v1.pos_y) - float(v2.pos_y))
                edge_dist = center_dist - (float(v1.diameter) / 2.0) - (float(v2.diameter) / 2.0)
                if edge_dist < 0.2:  # 200 um minimum via clearance
                    findings.append(
                        PCBFinding(
                            rule_id="PCB010",
                            severity="ERROR",
                            category="CLEARANCE",
                            element_ref=f"VIA_{v1.id[:6]} <-> VIA_{v2.id[:6]}",
                            actual_value=round(edge_dist, 3),
                            required_limit=0.2,
                            unit="mm",
                            status="VIOLATED",
                            message=f"Via-to-via clearance violation between {net1 or 'VIA1'} and {net2 or 'VIA2'}: {edge_dist:.3f} mm < 0.2 mm.",
                        )
                    )

        return findings
