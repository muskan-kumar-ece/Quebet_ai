import math
from typing import Any
from app.models.db.circuit import Circuit
from app.models.db.pcb import EngineeringBoard
from app.models.schemas.pcb import PCBFinding


class PCBDecouplingEngine:
    """
    Decoupling placement intelligence engine.
    Connects schematic IC power/ground requirements to physical PCB placement proximity.
    Strict Invariant:
    If coordinates or component identities are missing, returns UNKNOWN (not PASS).
    Rule:
    - PCB014: Decoupling placement issue
    """

    DEFAULT_MAX_DECOUPLING_DIST_MM = 5.0  # 5 mm standard maximum proximity for high-frequency bypass

    @classmethod
    def evaluate(
        cls,
        circuit: Circuit,
        board: EngineeringBoard,
        max_distance_mm: float | None = None,
    ) -> list[PCBFinding]:
        findings: list[PCBFinding] = []
        limit_dist = max_distance_mm or cls.DEFAULT_MAX_DECOUPLING_DIST_MM

        footprints = getattr(board, "footprints", [])
        fp_by_ref = {fp.ref_des.upper(): fp for fp in footprints}

        # Identify ICs and capacitors from schematic
        schem_comps = getattr(circuit, "components", [])
        ics = [
            c for c in schem_comps
            if (getattr(c, "component_type", "") or "").upper() in ("IC", "MCU", "OPAMP", "REGULATOR")
            or (getattr(c, "ref_des", "") or "").upper().startswith("U")
        ]
        capacitors = [
            c for c in schem_comps
            if (getattr(c, "component_type", "") or "").upper().startswith("CAP")
            or (getattr(c, "ref_des", "") or "").upper().startswith("C")
        ]

        if not ics or not capacitors:
            return findings

        # Check decoupling requirements specified in metadata or inferred from power nets
        for ic in ics:
            ic_ref = (getattr(ic, "ref_des", "") or ic.id).upper()
            ic_fp = fp_by_ref.get(ic_ref)

            # Metadata decoupling requirements e.g. {"decoupling_caps": ["C1", "C2"], "max_distance_mm": 4.0}
            meta = ic.metadata_ if isinstance(ic.metadata_, dict) else {}
            req_caps = meta.get("decoupling_caps", [])
            req_limit = float(meta.get("max_distance_mm", limit_dist))

            if not req_caps:
                continue

            for cap_ref in req_caps:
                cap_ref_upper = str(cap_ref).upper()
                cap_fp = fp_by_ref.get(cap_ref_upper)

                if not ic_fp or not cap_fp:
                    findings.append(
                        PCBFinding(
                            rule_id="PCB014",
                            severity="WARNING",
                            category="DECOUPLING",
                            element_ref=f"{ic_ref} <-> {cap_ref_upper}",
                            status="UNKNOWN",
                            message=f"Decoupling placement for {ic_ref} and {cap_ref_upper} cannot be evaluated because physical footprint is missing.",
                        )
                    )
                    continue

                actual_dist = math.hypot(ic_fp.pos_x - cap_fp.pos_x, ic_fp.pos_y - cap_fp.pos_y)
                if actual_dist > req_limit:
                    findings.append(
                        PCBFinding(
                            rule_id="PCB014",
                            severity="WARNING",
                            category="DECOUPLING",
                            element_ref=f"{ic_ref} <-> {cap_ref_upper}",
                            actual_value=round(actual_dist, 2),
                            required_limit=req_limit,
                            unit="mm",
                            status="VIOLATED",
                            message=(
                                f"Decoupling capacitor {cap_ref_upper} is placed too far from IC {ic_ref}: "
                                f"{actual_dist:.2f} mm > maximum allowed {req_limit:.2f} mm."
                            ),
                        )
                    )

        return findings
