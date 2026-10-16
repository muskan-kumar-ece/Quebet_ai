import hashlib
import json
from typing import Any
from app.models.db.pcb import EngineeringBoard


class PCBSnapshotService:
    """
    Produces deterministic canonical snapshot and SHA-256 integrity digest of an EngineeringBoard.
    Terminology: PROVENANCE_AND_INTEGRITY_DIGEST.
    """

    @classmethod
    def generate_canonical_snapshot(cls, board: EngineeringBoard) -> dict[str, Any]:
        """
        Extracts and normalizes all physical PCB engineering data into a canonical structure.
        All collections are sorted deterministically.
        """
        # Layers
        layers = sorted(
            [
                {
                    "name": l.name,
                    "layer_type": l.layer_type,
                    "layer_order": l.layer_order,
                    "is_copper": bool(l.is_copper),
                    "thickness_um": float(l.thickness_um) if l.thickness_um is not None else None,
                    "dielectric_constant": float(l.dielectric_constant) if l.dielectric_constant is not None else None,
                    "copper_weight_oz": float(l.copper_weight_oz) if l.copper_weight_oz is not None else None,
                }
                for l in getattr(board, "layers", [])
            ],
            key=lambda x: x["layer_order"],
        )

        # Footprints & Pads
        footprints = []
        for fp in sorted(getattr(board, "footprints", []), key=lambda x: x.ref_des.upper()):
            pads = sorted(
                [
                    {
                        "pad_number": str(p.pad_number),
                        "pad_type": p.pad_type,
                        "pos_x": round(float(p.pos_x), 4),
                        "pos_y": round(float(p.pos_y), 4),
                        "width": round(float(p.width), 4),
                        "height": round(float(p.height), 4),
                        "drill": round(float(p.drill), 4) if p.drill is not None else None,
                        "shape": p.shape,
                        "layer": p.layer,
                        "net_name": p.net_name or "",
                    }
                    for p in getattr(fp, "pads", [])
                ],
                key=lambda x: str(x["pad_number"]).upper(),
            )
            footprints.append(
                {
                    "ref_des": fp.ref_des.upper(),
                    "component_id": str(fp.component_id) if fp.component_id else None,
                    "footprint_name": fp.footprint_name,
                    "pos_x": round(float(fp.pos_x or 0.0), 4),
                    "pos_y": round(float(fp.pos_y or 0.0), 4),
                    "rotation": round(float(fp.rotation or 0.0), 4),
                    "side": fp.side or "TOP",
                    "pads": pads,
                }
            )

        # Traces
        traces = sorted(
            [
                {
                    "start_x": round(float(t.start_x), 4),
                    "start_y": round(float(t.start_y), 4),
                    "end_x": round(float(t.end_x), 4),
                    "end_y": round(float(t.end_y), 4),
                    "width": round(float(t.width), 4),
                    "layer": t.layer,
                    "net_name": t.net_name or "",
                }
                for t in getattr(board, "traces", [])
            ],
            key=lambda x: (x["layer"], x["start_x"], x["start_y"], x["end_x"], x["end_y"], x["net_name"]),
        )

        # Vias
        vias = sorted(
            [
                {
                    "pos_x": round(float(v.pos_x), 4),
                    "pos_y": round(float(v.pos_y), 4),
                    "drill": round(float(v.drill), 4),
                    "diameter": round(float(v.diameter), 4),
                    "start_layer": v.start_layer,
                    "end_layer": v.end_layer,
                    "via_type": v.via_type,
                    "net_name": v.net_name or "",
                }
                for v in getattr(board, "vias", [])
            ],
            key=lambda x: (x["pos_x"], x["pos_y"], x["start_layer"], x["end_layer"], x["net_name"]),
        )

        dimensions = {
            "width_mm": float(board.dimensions.get("width_mm", 0.0)) if isinstance(board.dimensions, dict) else 0.0,
            "height_mm": float(board.dimensions.get("height_mm", 0.0)) if isinstance(board.dimensions, dict) else 0.0,
            "thickness_mm": float(board.dimensions.get("thickness_mm", 1.6)) if isinstance(board.dimensions, dict) else 1.6,
        }

        return {
            "board_id": str(board.id),
            "name": str(board.name),
            "version": int(board.version or 1),
            "circuit_id": str(board.circuit_id),
            "circuit_version": int(board.circuit_version or 1),
            "units": str(board.units),
            "dimensions": dimensions,
            "board_outline": board.board_outline or [],
            "layers": layers,
            "footprints": footprints,
            "traces": traces,
            "vias": vias,
        }

    @classmethod
    def compute_integrity_digest(cls, snapshot: dict[str, Any]) -> str:
        """
        Computes deterministic SHA-256 integrity digest over canonical JSON representation.
        """
        canonical_json = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
