"""
Canonical Cross-Domain Snapshot & Digest Engine for Phase 3 Wave 8.
Computes deterministic SHA-256 canonical integrity digests across multi-domain engineering states.
STRICT INVARIANT: PROVENANCE_AND_INTEGRITY_DIGEST != DIGITAL_SIGNATURE.
Canonical ordering and deterministic JSON formatting are mandatory.
"""
import hashlib
import json
from typing import Any, Optional


class CrossDomainSnapshotEngine:
    """
    Deterministic snapshot engine that captures structured cross-domain state and generates
    a 64-character SHA-256 hex digest for provenance and integrity tracking.
    """

    @staticmethod
    def serialize_domain_state(
        project_id: str,
        circuit: Any = None,
        board: Any = None,
        bom: Any = None,
        simulation_job: Any = None,
        dfm_analysis: Any = None,
        requirements: list[Any] | None = None,
        verifications: list[Any] | None = None,
        dfm_rules: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Builds a canonically sorted structured representation of the multi-domain engineering state.
        Ensures that independent changes across any of the 10 engineering domains directly mutate the digest.
        """
        # 1. Circuit domain (Electrical ratings, thermal limits, connectivity, power rails)
        circuit_data = None
        if circuit:
            components_summary = []
            for c in getattr(circuit, "components", []) or []:
                props = getattr(c, "properties", None) or getattr(c, "metadata_", None) or {}
                if not isinstance(props, dict):
                    props = {}
                norm_props = {}
                for k in ("operating_voltage", "voltage_rating", "abs_max_voltage", "power_dissipation_w", "r_theta_ja", "tj_max_c"):
                    if k in props and props[k] is not None:
                        norm_props[k] = float(props[k]) if isinstance(props[k], (int, float)) else str(props[k])

                components_summary.append({
                    "id": str(getattr(c, "id", "")),
                    "ref_des": str(getattr(c, "ref_des", "")).upper(),
                    "name": str(getattr(c, "name", "")),
                    "component_type": str(getattr(c, "component_type", "")),
                    "value": str(getattr(c, "value", "") or ""),
                    "parameters": norm_props,
                })
            components_summary.sort(key=lambda x: x["ref_des"])

            nets_summary = []
            for n in getattr(circuit, "nets", []) or []:
                nets_summary.append({
                    "id": str(getattr(n, "id", "")),
                    "name": str(getattr(n, "name", "")).upper(),
                })
            nets_summary.sort(key=lambda x: x["name"])

            # Schematic connectivity (Pin-to-Net bindings)
            connections_summary = []
            for conn in getattr(circuit, "connections", []) or []:
                connections_summary.append({
                    "component_id": str(getattr(conn, "component_id", "")),
                    "pin_number": str(getattr(conn, "pin_number", "")),
                    "net_id": str(getattr(conn, "net_id", "")),
                })
            connections_summary.sort(key=lambda x: (x["component_id"], x["pin_number"], x["net_id"]))

            c_props = getattr(circuit, "properties", {}) or {}
            if not isinstance(c_props, dict):
                c_props = {}
            rails_data = c_props.get("power_rails", {})

            circuit_data = {
                "id": str(getattr(circuit, "id", "")),
                "version": int(getattr(circuit, "version", 1)) if getattr(circuit, "version", None) is not None else None,
                "component_count": len(components_summary),
                "components": components_summary,
                "net_count": len(nets_summary),
                "nets": nets_summary,
                "connection_count": len(connections_summary),
                "connections": connections_summary,
                "power_rails": rails_data,
            }

        # 2. PCB domain (Geometry/routing, footprints, stackup, child integrity digest)
        board_data = None
        if board:
            footprints_summary = []
            for fp in getattr(board, "footprints", []) or []:
                footprints_summary.append({
                    "id": str(getattr(fp, "id", "")),
                    "ref_des": str(getattr(fp, "ref_des", "")).upper(),
                    "footprint_name": str(getattr(fp, "footprint_name", "")),
                    "pad_count": len(getattr(fp, "pads", []) or []),
                })
            footprints_summary.sort(key=lambda x: x["ref_des"])

            # PCB Stackup layers
            layers_summary = []
            for layer in getattr(board, "layers", []) or []:
                layers_summary.append({
                    "id": str(getattr(layer, "id", "")),
                    "name": str(getattr(layer, "name", "")),
                    "layer_type": str(getattr(layer, "layer_type", "")),
                    "layer_order": int(getattr(layer, "layer_order", 0) or 0),
                    "thickness_um": float(getattr(layer, "thickness_um", 0.0) or 0.0),
                    "copper_weight_oz": float(getattr(layer, "copper_weight_oz", 0.0) or 0.0),
                })
            layers_summary.sort(key=lambda x: x["layer_order"])

            # PCB Traces geometry & routing
            traces_summary = []
            for tr in getattr(board, "traces", []) or []:
                traces_summary.append({
                    "id": str(getattr(tr, "id", "")),
                    "net_id": str(getattr(tr, "net_id", "") or ""),
                    "layer_id": str(getattr(tr, "layer_id", "") or ""),
                    "width_mm": float(getattr(tr, "width_mm", 0.0) or 0.0),
                    "length_mm": float(getattr(tr, "length_mm", 0.0) or 0.0),
                })
            traces_summary.sort(key=lambda x: (x["id"], x["net_id"]))

            # PCB Vias
            vias_summary = []
            for v in getattr(board, "vias", []) or []:
                vias_summary.append({
                    "id": str(getattr(v, "id", "")),
                    "drill_size_mm": float(getattr(v, "drill_size_mm", 0.0) or 0.0),
                    "diameter_mm": float(getattr(v, "diameter_mm", 0.0) or 0.0),
                    "net_id": str(getattr(v, "net_id", "") or ""),
                })
            vias_summary.sort(key=lambda x: x["id"])

            board_data = {
                "id": str(getattr(board, "id", "")),
                "revision": int(getattr(board, "revision", getattr(board, "version", 1))),
                "integrity_digest": str(getattr(board, "integrity_digest", "") or ""),
                "footprint_count": len(footprints_summary),
                "footprints": footprints_summary,
                "layer_count": len(layers_summary),
                "layers": layers_summary,
                "trace_count": len(traces_summary),
                "traces": traces_summary,
                "via_count": len(vias_summary),
                "vias": vias_summary,
            }

        # 3. BOM domain (Procurement identity, package, quantity)
        bom_data = None
        if bom:
            lines_summary = []
            for line in getattr(bom, "lines", []) or []:
                lines_summary.append({
                    "id": str(getattr(line, "id", "")),
                    "ref_des": str(getattr(line, "reference_designator", "")).upper(),
                    "mpn": str(getattr(line, "manufacturer_part_number", "") or ""),
                    "package": str(getattr(line, "design_package", "") or getattr(line, "footprint_name", "") or ""),
                    "quantity": int(getattr(line, "quantity", 1) or 1),
                })
            lines_summary.sort(key=lambda x: x["ref_des"])

            bom_data = {
                "id": str(getattr(bom, "id", "")),
                "revision": int(getattr(bom, "revision", getattr(bom, "version", 1))),
                "line_count": len(lines_summary),
                "lines": lines_summary,
            }

        # 4. Simulation domain (Configuration, simulator, operating mode, circuit revision reference)
        sim_data = None
        if simulation_job:
            sim_data = {
                "id": str(getattr(simulation_job, "id", "")),
                "circuit_id": str(getattr(simulation_job, "circuit_id", "")),
                "circuit_version": getattr(simulation_job, "circuit_version", None),
                "status": str(getattr(simulation_job, "status", "")),
                "simulation_type": str(getattr(simulation_job, "simulation_type", "")),
                "simulator": str(getattr(simulation_job, "simulator", "")),
                "operating_mode": str(getattr(simulation_job, "operating_mode", "") or ""),
            }

        # 5. DFM domain (DFM rules configuration and board digest reference)
        dfm_data = None
        if dfm_analysis or dfm_rules:
            rules_cfg = {}
            if dfm_rules and isinstance(dfm_rules, dict):
                rules_cfg = {k: v for k, v in sorted(dfm_rules.items())}
            elif dfm_analysis and getattr(dfm_analysis, "rules_applied", None):
                ra = getattr(dfm_analysis, "rules_applied")
                if isinstance(ra, dict):
                    rules_cfg = {k: v for k, v in sorted(ra.items())}

            dfm_data = {
                "id": str(getattr(dfm_analysis, "id", "")) if dfm_analysis else "",
                "board_id": str(getattr(dfm_analysis, "board_id", "")) if dfm_analysis else "",
                "board_revision": int(getattr(dfm_analysis, "board_revision", 1)) if dfm_analysis else 1,
                "board_snapshot_digest": str(getattr(dfm_analysis, "provenance_digest", None) or getattr(dfm_analysis, "board_snapshot_digest", "") or "") if dfm_analysis else "",
                "status": str(getattr(dfm_analysis, "status", "")) if dfm_analysis else "",
                "rules_configuration": rules_cfg,
            }

        req_ids = sorted([str(getattr(r, "id", "")) for r in (requirements or []) if getattr(r, "id", None)])
        ver_ids = sorted([
            f"{getattr(v, 'id', '')}:rev_{getattr(v, 'circuit_revision', getattr(v, 'circuit_version', 1))}"
            for v in (verifications or []) if getattr(v, "id", None)
        ])

        # Canonical structure
        snapshot = {
            "project_id": str(project_id),
            "circuit": circuit_data,
            "board": board_data,
            "bom": bom_data,
            "simulation": sim_data,
            "dfm": dfm_data,
            "requirements": req_ids,
            "requirements_count": len(req_ids),
            "verifications": ver_ids,
            "verifications_count": len(ver_ids),
            "rule_registry_version": "WAVE_8_2026.1",
            "provenance_type": "PROVENANCE_AND_INTEGRITY_DIGEST",
        }

        return snapshot

    @staticmethod
    def compute_canonical_digest(data: dict[str, Any]) -> str:
        """
        Serializes dictionary into canonically formatted JSON (alphabetically sorted keys,
        compact separators) and returns its SHA-256 hex digest.
        """
        canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
