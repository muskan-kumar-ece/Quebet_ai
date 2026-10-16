"""
BOM Snapshot & Canonical Integrity Service.

Provides deterministic canonical serialization and SHA-256 digest calculation
for Engineering BOM state to guarantee tamper-evidence, auditability, and provenance.
Zero AI scoring or synthetic heuristics.
"""

import hashlib
import json
from typing import Any, Dict, List
from app.models.db.bom import EngineeringBOM, EngineeringBOMLine, ComponentPartCandidate


class BOMSnapshotService:
    """Computes deterministic canonical snapshots and SHA-256 digests for EngineeringBOMs."""

    @staticmethod
    def _normalize_dict(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: BOMSnapshotService._normalize_dict(v) for k, v in sorted(obj.items())}
        elif isinstance(obj, list):
            return [BOMSnapshotService._normalize_dict(item) for item in obj]
        elif isinstance(obj, float):
            return round(obj, 6)
        return obj

    @staticmethod
    def generate_canonical_payload(bom: EngineeringBOM) -> Dict[str, Any]:
        """
        Builds a canonical dictionary representation of the BOM.
        Lines are canonically sorted by reference designator (`reference_designator`).
        Candidates under each line are sorted by `mpn`.
        Supply observations under each candidate are sorted by `supplier`.
        """
        lines_payload: List[Dict[str, Any]] = []

        # Sort lines canonically by reference_designator
        sorted_lines = sorted(
            bom.lines or [],
            key=lambda l: getattr(l, "reference_designator", None) or getattr(l, "ref_des", None) or "",
        )

        for line in sorted_lines:
            ref_des = getattr(line, "reference_designator", None) or getattr(line, "ref_des", None) or ""
            sorted_candidates = sorted(line.candidates or [], key=lambda c: c.mpn or "")
            candidates_payload: List[Dict[str, Any]] = []

            for cand in sorted_candidates:
                raw_sources = cand.supply_sources or []
                sorted_sources = sorted(raw_sources, key=lambda s: s.get("supplier", ""))

                cand_dict = {
                    "candidate_id": str(cand.id),
                    "mpn": cand.mpn,
                    "manufacturer": cand.manufacturer,
                    "lifecycle_status": cand.lifecycle_status,
                    "availability_status": cand.availability_status,
                    "compatibility_status": cand.compatibility_status,
                    "parameters": getattr(cand, "parameters", None) or getattr(cand, "specifications", None) or {},
                    "supply_sources": sorted_sources,
                }
                candidates_payload.append(cand_dict)

            line_dict = {
                "line_id": str(line.id),
                "reference_designator": ref_des,
                "quantity": line.quantity,
                "component_type": line.component_type,
                "design_value": getattr(line, "design_value", None) or getattr(line, "nominal_value", None),
                "design_package": getattr(line, "design_package", None) or getattr(line, "package_footprint", None),
                "engineering_requirements": getattr(line, "engineering_requirements", None) or getattr(line, "required_specifications", None) or {},
                "status": line.status,
                "manufacturer_part_number": getattr(line, "manufacturer_part_number", None) or getattr(line, "active_mpn", None),
                "manufacturer": getattr(line, "manufacturer", None) or getattr(line, "active_manufacturer", None),
                "candidates": candidates_payload,
            }
            lines_payload.append(line_dict)

        payload = {
            "bom_id": str(bom.id),
            "circuit_id": str(bom.circuit_id),
            "version": getattr(bom, "version", 1) or getattr(bom, "revision", 1) or 1,
            "status": bom.status,
            "total_lines": len(lines_payload),
            "lines": lines_payload,
        }

        return BOMSnapshotService._normalize_dict(payload)

    @classmethod
    def compute_bom_digest(cls, bom: EngineeringBOM) -> str:
        """
        Generates a SHA-256 hex digest for the canonical representation of the BOM.
        Ensures consistent formatting: UTF-8 encoding, sorted keys, compact separators.
        """
        canonical_data = cls.generate_canonical_payload(bom)
        serialized = json.dumps(canonical_data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def create_snapshot_record(cls, bom: EngineeringBOM) -> Dict[str, Any]:
        """Creates a complete snapshot dictionary matching BOMSnapshotResponse."""
        canonical_data = cls.generate_canonical_payload(bom)
        digest = cls.compute_bom_digest(bom)
        version = getattr(bom, "version", 1) or getattr(bom, "revision", 1) or 1
        circuit_version = getattr(bom, "circuit_version", 1) or 1
        return {
            "bom_id": str(bom.id),
            "bom_version": version,
            "circuit_id": str(bom.circuit_id),
            "circuit_version": circuit_version,
            "snapshot_digest": digest,
            "provenance_label": "PROVENANCE_AND_INTEGRITY_DIGEST",
            "content": canonical_data,
        }
