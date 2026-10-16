"""
BOM Generator Service.

Generates an EngineeringBOM and EngineeringBOMLines deterministically from a Circuit
and optional EngineeringBoard. Separates Design Identity from Procurement Identity.
Zero synthetic scoring or heuristics.
"""

from typing import Any, Dict, List, Optional
import uuid
from app.models.db.bom import (
    EngineeringBOM,
    EngineeringBOMLine,
    ComponentPartCandidate,
    BOMStatus,
    BOMLineStatus,
    PartLifecycleStatus,
    PartAvailabilityStatus,
    PartCompatibilityStatus,
)
from app.models.db.circuit import Circuit
from app.services.ai.bom.requirement_extractor import BOMRequirementExtractor


class BOMGenerator:
    """Generates canonical EngineeringBOM from Circuit and optional EngineeringBoard."""

    @classmethod
    def generate_from_circuit(
        cls,
        circuit: Circuit,
        board: Optional[Any] = None,
        revision: int = 1,
    ) -> EngineeringBOM:
        """
        Builds an EngineeringBOM containing EngineeringBOMLines for each component in the circuit.
        Preserves design identity on the line and creates candidates for known manufacturer parts.
        """
        bom_id = str(uuid.uuid4())
        bom = EngineeringBOM(
            id=bom_id,
            project_id=circuit.project_id,
            circuit_id=circuit.id,
            circuit_version=getattr(circuit, "version", 1) or 1,
            board_id=board.id if board else None,
            board_version=getattr(board, "version", None) if board else None,
            tenant_id=circuit.tenant_id,
            name=f"BOM for {circuit.name or 'Circuit'}",
            version=revision,
            status=BOMStatus.DRAFT.value,
            created_by=getattr(circuit, "created_by", "system") or "system",
            metadata_={
                "generated_from_circuit_id": circuit.id,
                "circuit_name": circuit.name,
                "circuit_version": getattr(circuit, "version", 1),
                "board_id": board.id if board else None,
            },
        )

        board_footprint_map: Dict[str, str] = {}
        if board and hasattr(board, "footprints") and board.footprints:
            for fp in board.footprints:
                if getattr(fp, "ref_des", None) and getattr(fp, "package_name", None):
                    board_footprint_map[fp.ref_des.upper()] = fp.package_name

        components = getattr(circuit, "components", []) or []
        sorted_components = sorted(components, key=lambda c: getattr(c, "ref_des", "") or "")

        lines: List[EngineeringBOMLine] = []

        for comp in sorted_components:
            ref_des = getattr(comp, "ref_des", "") or ""
            comp_type = getattr(comp, "component_type", "") or "UNKNOWN"
            package = getattr(comp, "package", None) or board_footprint_map.get(ref_des.upper())

            comp_dict = {
                "ref_des": ref_des,
                "type": comp_type,
                "value": getattr(comp, "value", None),
                "unit": getattr(comp, "unit", None),
                "tolerance": getattr(comp, "tolerance", None),
                "rating": getattr(comp, "rating", None),
                "package": package,
                "pins": getattr(comp, "pins", None),
                "metadata": getattr(comp, "metadata_", None) or getattr(comp, "metadata", None) or {},
            }

            extracted_specs = BOMRequirementExtractor.extract_requirements(comp_dict)
            val_raw = comp_dict.get("value")
            unit_raw = comp_dict.get("unit") or ""
            nominal_val_str = f"{val_raw}{unit_raw}" if val_raw is not None else ""

            mpn = getattr(comp, "part_number", None)
            mfr = getattr(comp, "manufacturer", None)
            line_id = str(uuid.uuid4())

            line = EngineeringBOMLine(
                id=line_id,
                bom_id=bom_id,
                component_id=comp.id,
                reference_designator=ref_des,
                quantity=1,
                component_type=comp_type,
                design_value=nominal_val_str,
                design_package=package,
                design_tolerance=str(comp_dict.get("tolerance") or "") if comp_dict.get("tolerance") else None,
                design_rating=str(comp_dict.get("rating") or "") if comp_dict.get("rating") else None,
                footprint_name=package,
                engineering_requirements=extracted_specs,
                status=BOMLineStatus.UNMATCHED.value if not mpn else BOMLineStatus.SOURCED.value,
                manufacturer=mfr,
                manufacturer_part_number=mpn,
                provenance={"source": "CIRCUIT_COMPONENT", "component_id": comp.id},
            )

            if mpn:
                candidate = ComponentPartCandidate(
                    id=str(uuid.uuid4()),
                    bom_line_id=line_id,
                    manufacturer=mfr or "UNKNOWN",
                    mpn=mpn,
                    package=package,
                    lifecycle_status=PartLifecycleStatus.UNKNOWN.value,
                    availability_status=PartAvailabilityStatus.UNKNOWN.value,
                    compatibility_status=PartCompatibilityStatus.UNKNOWN.value,
                    parameters=extracted_specs,
                    supply_sources=[],
                    is_primary=True,
                    provenance={"source": "SCHEMATIC_ANNOTATION"},
                )
                line.candidates = [candidate]
            else:
                line.candidates = []

            lines.append(line)

        bom.lines = lines
        bom.total_lines = len(lines)
        return bom
