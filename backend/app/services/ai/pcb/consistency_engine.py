from typing import Any
from app.models.db.circuit import Circuit
from app.models.db.pcb import EngineeringBoard
from app.models.schemas.pcb import PCBFinding


class SchematicPCBConsistencyEngine:
    """
    Deterministic validator comparing schematic Circuit representation with physical EngineeringBoard.
    Rules:
    - PCB001: Component missing from PCB
    - PCB002: Component missing from schematic
    - PCB003: Footprint mismatch
    - PCB004: Pad-net mismatch
    - PCB012: Duplicate reference designator
    - PCB013: Invalid footprint binding
    """

    @classmethod
    def validate(
        cls,
        circuit: Circuit,
        board: EngineeringBoard,
    ) -> list[PCBFinding]:
        findings: list[PCBFinding] = []

        # 1. Map schematic components & nets
        schem_comp_by_id = {c.id: c for c in getattr(circuit, "components", [])}
        schem_comp_by_ref = {}
        for c in getattr(circuit, "components", []):
            ref = (getattr(c, "ref_des", None) or getattr(c, "designator", None) or "").upper()
            if ref:
                schem_comp_by_ref[ref] = c

        schem_net_by_id = {n.id: n.name for n in getattr(circuit, "nets", [])}

        # Build pin -> net mapping for schematic: (comp_id, pin_number) -> net_name
        schem_pin_nets: dict[tuple[str, str], str] = {}
        for conn in getattr(circuit, "connections", []):
            net_name = schem_net_by_id.get(conn.net_id, "")
            schem_pin_nets[(str(conn.component_id), str(conn.pin_number))] = net_name

        # 2. Inspect PCB footprints
        pcb_footprints = getattr(board, "footprints", [])
        pcb_refs_seen: dict[str, int] = {}
        matched_schem_comp_ids: set[str] = set()

        for fp in pcb_footprints:
            ref = fp.ref_des.upper()
            pcb_refs_seen[ref] = pcb_refs_seen.get(ref, 0) + 1

            # Check binding to schematic
            schem_comp = None
            if fp.component_id:
                schem_comp = schem_comp_by_id.get(fp.component_id)
                if not schem_comp:
                    findings.append(
                        PCBFinding(
                            rule_id="PCB013",
                            severity="ERROR",
                            category="SCHEMATIC_SYNC",
                            element_ref=ref,
                            actual_value=fp.component_id,
                            status="VIOLATED",
                            message=f"Footprint {ref} binds to non-existent schematic component_id '{fp.component_id}'.",
                        )
                    )
            elif ref in schem_comp_by_ref:
                schem_comp = schem_comp_by_ref[ref]

            if not schem_comp:
                # Component on PCB missing from schematic
                findings.append(
                    PCBFinding(
                        rule_id="PCB002",
                        severity="WARNING",
                        category="SCHEMATIC_SYNC",
                        element_ref=ref,
                        actual_value=ref,
                        status="VIOLATED",
                        message=f"PCB footprint {ref} ({fp.footprint_name}) has no corresponding schematic component.",
                    )
                )
            else:
                matched_schem_comp_ids.add(schem_comp.id)

                # Check footprint package mismatch if specified in schematic component metadata
                expected_fp = None
                if getattr(schem_comp, "metadata_", None) and isinstance(schem_comp.metadata_, dict):
                    expected_fp = schem_comp.metadata_.get("footprint") or schem_comp.metadata_.get("package")

                if expected_fp and expected_fp.upper() != fp.footprint_name.upper():
                    findings.append(
                        PCBFinding(
                            rule_id="PCB003",
                            severity="WARNING",
                            category="SCHEMATIC_SYNC",
                            element_ref=ref,
                            actual_value=fp.footprint_name,
                            required_limit=expected_fp,
                            status="VIOLATED",
                            message=f"Footprint package mismatch on {ref}: PCB has '{fp.footprint_name}', schematic expects '{expected_fp}'.",
                        )
                    )

                # Check pad-net consistency against schematic connections
                for pad in getattr(fp, "pads", []):
                    pad_num = str(pad.pad_number)
                    schem_net = schem_pin_nets.get((schem_comp.id, pad_num))
                    pcb_net = pad.net_name or ""

                    if schem_net and pcb_net and schem_net.upper() != pcb_net.upper():
                        findings.append(
                            PCBFinding(
                                rule_id="PCB004",
                                severity="ERROR",
                                category="SCHEMATIC_SYNC",
                                element_ref=f"{ref}.{pad_num}",
                                actual_value=pcb_net,
                                required_limit=schem_net,
                                status="VIOLATED",
                                message=f"Pad-net mismatch on {ref} pad {pad_num}: PCB is mapped to net '{pcb_net}', schematic connects to '{schem_net}'.",
                            )
                        )

        # 3. Check for duplicate reference designators on PCB (PCB012)
        for ref, count in pcb_refs_seen.items():
            if count > 1:
                findings.append(
                    PCBFinding(
                        rule_id="PCB012",
                        severity="ERROR",
                        category="SCHEMATIC_SYNC",
                        element_ref=ref,
                        actual_value=count,
                        required_limit=1,
                        status="VIOLATED",
                        message=f"Duplicate reference designator '{ref}' found {count} times on PCB.",
                    )
                )

        # 4. Check for schematic components missing from PCB (PCB001)
        for comp_id, comp in schem_comp_by_id.items():
            if comp_id not in matched_schem_comp_ids:
                ref = (getattr(comp, "ref_des", None) or getattr(comp, "designator", None) or comp_id).upper()
                comp_type = getattr(comp, "component_type", "") or ""
                findings.append(
                    PCBFinding(
                        rule_id="PCB001",
                        severity="ERROR",
                        category="SCHEMATIC_SYNC",
                        element_ref=ref,
                        status="VIOLATED",
                        message=f"Schematic component {ref} ({comp_type}) is missing from the physical PCB layout.",
                    )
                )

        return findings
