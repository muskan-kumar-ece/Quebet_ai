import math
from typing import Any
from app.models.db.pcb import EngineeringBoard
from app.models.schemas.pcb import PCBFinding


class DisjointSet:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        if item not in self.parent:
            self.parent[item] = item
            return item
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, a: str, b: str) -> None:
        root_a = self.find(a)
        root_b = self.find(b)
        if root_a != root_b:
            self.parent[root_b] = root_a


class PCBConnectivityEngine:
    """
    Deterministic electrical connectivity analyzer for physical PCB layouts.
    Operates strictly on explicit topological intersections between pads, traces, and vias.
    Never infers connectivity from visual proximity.
    Rules:
    - PCB005: Unconnected pad (PAD_UNCONNECTED)
    - PCB006: Broken PCB net (NET_DISCONNECTED)
    - Short circuits (UNEXPECTED_CONNECTION)
    """

    TOLERANCE_MM = 0.05  # 50 um geometric contact tolerance

    @classmethod
    def get_pad_absolute_position(cls, fp_x: float, fp_y: float, pad_x: float, pad_y: float, rot_deg: float) -> tuple[float, float]:
        """Calculates pad absolute coordinates considering footprint rotation."""
        rad = math.radians(rot_deg)
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)
        # Rotate pad offset
        rx = pad_x * cos_r - pad_y * sin_r
        ry = pad_x * sin_r + pad_y * cos_r
        return fp_x + rx, fp_y + ry

    @classmethod
    def point_in_pad_bounds(
        cls,
        px: float,
        py: float,
        pad_center_x: float,
        pad_center_y: float,
        pad_w: float,
        pad_h: float,
        tolerance: float = 0.05,
    ) -> bool:
        """Checks if a point is within or on the boundary of a rectangular pad box."""
        half_w = (pad_w / 2.0) + tolerance
        half_h = (pad_h / 2.0) + tolerance
        return (pad_center_x - half_w <= px <= pad_center_x + half_w) and (
            pad_center_y - half_h <= py <= pad_center_y + half_h
        )

    @classmethod
    def points_touch(cls, x1: float, y1: float, x2: float, y2: float, tolerance: float = 0.05) -> bool:
        return math.hypot(x1 - x2, y1 - y2) <= tolerance

    @classmethod
    def analyze_connectivity(cls, board: EngineeringBoard) -> list[PCBFinding]:
        findings: list[PCBFinding] = []

        footprints = getattr(board, "footprints", [])
        traces = getattr(board, "traces", [])
        vias = getattr(board, "vias", [])

        # Collect all pads with absolute geometry and net info
        pads_by_net: dict[str, list[dict[str, Any]]] = {}
        all_pads: list[dict[str, Any]] = []

        for fp in footprints:
            fp_x = float(getattr(fp, "pos_x", 0.0) or 0.0)
            fp_y = float(getattr(fp, "pos_y", 0.0) or 0.0)
            fp_rot = float(getattr(fp, "rotation", 0.0) or 0.0)
            for pad in getattr(fp, "pads", []):
                p_x = float(getattr(pad, "pos_x", 0.0) or 0.0)
                p_y = float(getattr(pad, "pos_y", 0.0) or 0.0)
                abs_x, abs_y = cls.get_pad_absolute_position(
                    fp_x, fp_y, p_x, p_y, fp_rot
                )
                pad_info = {
                    "id": str(pad.id),
                    "ref": f"{fp.ref_des}.{pad.pad_number}",
                    "ref_des": fp.ref_des,
                    "pad_number": pad.pad_number,
                    "net_name": (pad.net_name or "").strip(),
                    "abs_x": abs_x,
                    "abs_y": abs_y,
                    "width": float(getattr(pad, "width", 1.0) or 1.0),
                    "height": float(getattr(pad, "height", 1.0) or 1.0),
                    "layer": pad.layer,
                }
                all_pads.append(pad_info)
                if pad_info["net_name"]:
                    net_key = pad_info["net_name"].upper()
                    pads_by_net.setdefault(net_key, []).append(pad_info)

        # Traces by net
        traces_by_net: dict[str, list[dict[str, Any]]] = {}
        for t in traces:
            net_name = (t.net_name or "").strip()
            t_info = {
                "id": str(t.id),
                "start_x": float(t.start_x),
                "start_y": float(t.start_y),
                "end_x": float(t.end_x),
                "end_y": float(t.end_y),
                "width": float(t.width),
                "layer": t.layer,
                "net_name": net_name,
            }
            if net_name:
                traces_by_net.setdefault(net_name.upper(), []).append(t_info)

        # Vias by net
        vias_by_net: dict[str, list[dict[str, Any]]] = {}
        for v in vias:
            net_name = (v.net_name or "").strip()
            v_info = {
                "id": str(v.id),
                "pos_x": float(v.pos_x),
                "pos_y": float(v.pos_y),
                "diameter": float(v.diameter),
                "start_layer": v.start_layer,
                "end_layer": v.end_layer,
                "net_name": net_name,
            }
            if net_name:
                vias_by_net.setdefault(net_name.upper(), []).append(v_info)

        # 1. Analyze each net for connectivity and broken paths
        all_nets = set(pads_by_net.keys()) | set(traces_by_net.keys())

        for net_name in sorted(all_nets):
            net_pads = pads_by_net.get(net_name, [])
            net_traces = traces_by_net.get(net_name, [])
            net_vias = vias_by_net.get(net_name, [])

            # Check for unconnected pads (PCB005)
            pad_connected_flag: dict[str, bool] = {p["id"]: False for p in net_pads}

            # Graph union find for net elements
            uf = DisjointSet()
            for p in net_pads:
                uf.find(f"PAD_{p['id']}")
            for t in net_traces:
                uf.find(f"TRACE_{t['id']}")
            for v in net_vias:
                uf.find(f"VIA_{v['id']}")

            # Connect traces with pads
            for p in net_pads:
                for t in net_traces:
                    # Pad touches start or end of trace on compatible layer
                    layer_match = (p["layer"] == "ALL_COPPER") or (p["layer"] == t["layer"])
                    if layer_match:
                        start_in = cls.point_in_pad_bounds(t["start_x"], t["start_y"], p["abs_x"], p["abs_y"], p["width"], p["height"])
                        end_in = cls.point_in_pad_bounds(t["end_x"], t["end_y"], p["abs_x"], p["abs_y"], p["width"], p["height"])
                        if start_in or end_in:
                            pad_connected_flag[p["id"]] = True
                            uf.union(f"PAD_{p['id']}", f"TRACE_{t['id']}")

                # Check vias directly on pad
                for v in net_vias:
                    via_in = cls.point_in_pad_bounds(v["pos_x"], v["pos_y"], p["abs_x"], p["abs_y"], p["width"], p["height"])
                    if via_in:
                        pad_connected_flag[p["id"]] = True
                        uf.union(f"PAD_{p['id']}", f"VIA_{v['id']}")

            # Connect traces with traces
            for i in range(len(net_traces)):
                t1 = net_traces[i]
                for j in range(i + 1, len(net_traces)):
                    t2 = net_traces[j]
                    if t1["layer"] == t2["layer"]:
                        # Check endpoint contacts
                        c1 = cls.points_touch(t1["start_x"], t1["start_y"], t2["start_x"], t2["start_y"])
                        c2 = cls.points_touch(t1["start_x"], t1["start_y"], t2["end_x"], t2["end_y"])
                        c3 = cls.points_touch(t1["end_x"], t1["end_y"], t2["start_x"], t2["start_y"])
                        c4 = cls.points_touch(t1["end_x"], t1["end_y"], t2["end_x"], t2["end_y"])
                        if c1 or c2 or c3 or c4:
                            uf.union(f"TRACE_{t1['id']}", f"TRACE_{t2['id']}")

            # Connect vias with traces
            for v in net_vias:
                for t in net_traces:
                    # Via connects if position touches trace endpoint
                    v_start = cls.points_touch(v["pos_x"], v["pos_y"], t["start_x"], t["start_y"], v["diameter"] / 2.0)
                    v_end = cls.points_touch(v["pos_x"], v["pos_y"], t["end_x"], t["end_y"], v["diameter"] / 2.0)
                    if v_start or v_end:
                        uf.union(f"VIA_{v['id']}", f"TRACE_{t['id']}")

            # Report unconnected pads (PCB005)
            # Only report if the net expects connections (len(net_pads) > 1 or traces exist)
            if len(net_pads) > 1 or len(net_traces) > 0:
                for p in net_pads:
                    if not pad_connected_flag[p["id"]]:
                        findings.append(
                            PCBFinding(
                                rule_id="PCB005",
                                severity="ERROR",
                                category="CONNECTIVITY",
                                element_ref=p["ref"],
                                actual_value="UNCONNECTED",
                                required_limit="ROUTED",
                                status="VIOLATED",
                                message=f"Pad {p['ref']} mapped to net '{net_name}' is completely unconnected.",
                            )
                        )

            # Check if net is broken into multiple disconnected components (PCB006)
            if len(net_pads) >= 2:
                pad_components = {uf.find(f"PAD_{p['id']}") for p in net_pads}
                if len(pad_components) > 1:
                    findings.append(
                        PCBFinding(
                            rule_id="PCB006",
                            severity="ERROR",
                            category="CONNECTIVITY",
                            element_ref=f"NET_{net_name}",
                            actual_value=f"{len(pad_components)} islands",
                            required_limit="1 continuous net",
                            status="VIOLATED",
                            message=f"Net '{net_name}' is broken into {len(pad_components)} disconnected subnets.",
                        )
                    )

        # 2. Short Circuit Detection (UNEXPECTED_CONNECTION between different nets)
        # Check trace-to-trace or trace-to-pad collision across different nets
        for i in range(len(traces)):
            t1 = traces[i]
            net1 = (t1.net_name or "").upper()
            if not net1:
                continue
            for j in range(i + 1, len(traces)):
                t2 = traces[j]
                net2 = (t2.net_name or "").upper()
                if not net2 or net1 == net2 or t1.layer != t2.layer:
                    continue
                # Check endpoint overlap
                if (
                    cls.points_touch(t1.start_x, t1.start_y, t2.start_x, t2.start_y)
                    or cls.points_touch(t1.start_x, t1.start_y, t2.end_x, t2.end_y)
                    or cls.points_touch(t1.end_x, t1.end_y, t2.start_x, t2.start_y)
                    or cls.points_touch(t1.end_x, t1.end_y, t2.end_x, t2.end_y)
                ):
                    findings.append(
                        PCBFinding(
                            rule_id="PCB006",
                            severity="ERROR",
                            category="CONNECTIVITY",
                            element_ref=f"SHORT_{net1}_{net2}",
                            actual_value="DIRECT_CONTACT",
                            required_limit="ISOLATED",
                            status="VIOLATED",
                            message=f"Short circuit detected between net '{net1}' and net '{net2}'.",
                        )
                    )

        return findings
