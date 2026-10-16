import re
from typing import Any, Optional
from app.services.ai.analysis.units import parse_voltage


class CircuitGraphAnalyzer:
    """
    Deterministic topological graph analyzer for circuit schematics.
    Constructs adjacency representations, identifies power/ground rails,
    detects floating pins, and segments voltage domains.
    """

    POWER_NAME_PATTERNS = [
        r"^(\+)?\d+(\.\d+)?[vV]$",  # +5V, 3.3V, 12V
        r"^VCC",
        r"^VDD",
        r"^VIN",
        r"^VBUS",
        r"^3V3",
        r"^5V",
        r"^1V8",
        r"^12V",
        r"^POWER",
    ]

    GROUND_NAME_PATTERNS = [
        r"^GND",
        r"^GROUND",
        r"^VSS",
        r"^0V",
        r"^AGND",
        r"^DGND",
    ]

    def __init__(
        self,
        components: list[dict[str, Any]],
        nets: list[dict[str, Any]],
        connections: list[dict[str, Any]],
    ):
        self.components = {c["id"]: c for c in components}
        self.nets = {n["id"]: n for n in nets}
        self.connections = connections

        # net_id -> list of pin connections
        self.net_pins: dict[str, list[dict[str, Any]]] = {n_id: [] for n_id in self.nets}
        # pin_id -> net_id
        self.pin_to_net: dict[str, str] = {}
        # component_id -> list of connected net_ids
        self.component_nets: dict[str, set[str]] = {c_id: set() for c_id in self.components}

        self._build_graph()

    def _build_graph(self) -> None:
        for conn in self.connections:
            net_id = conn.get("net_id")
            pin_id = conn.get("pin_id")
            comp_id = conn.get("component_id")

            if net_id and net_id in self.net_pins:
                self.net_pins[net_id].append(conn)
            if pin_id:
                self.pin_to_net[pin_id] = net_id
            if comp_id and comp_id in self.component_nets and net_id:
                self.component_nets[comp_id].add(net_id)

    def is_power_net(self, net_name: str) -> bool:
        name_clean = net_name.strip().upper()
        for pat in self.POWER_NAME_PATTERNS:
            if re.search(pat, name_clean):
                return True
        return False

    def is_ground_net(self, net_name: str) -> bool:
        name_clean = net_name.strip().upper()
        for pat in self.GROUND_NAME_PATTERNS:
            if re.search(pat, name_clean):
                return True
        return False

    def infer_net_voltage(self, net_name: str) -> Optional[float]:
        """Infer DC voltage from net name or explicit properties."""
        name_clean = net_name.strip()
        if self.is_ground_net(name_clean):
            return 0.0

        # Try parsing directly: +5V, 3.3V, 12V
        v = parse_voltage(name_clean)
        if v is not None:
            return v

        # Check known common names
        upper = name_clean.upper()
        if "3V3" in upper or "3.3" in upper:
            return 3.3
        if "5V" in upper or "VCC" in upper:
            return 5.0
        if "12V" in upper:
            return 12.0
        if "1V8" in upper:
            return 1.8

        return None

    def get_floating_pins(self) -> list[dict[str, Any]]:
        """Identify component pins that are not connected to any net or on single-pin nets."""
        floating = []
        for comp_id, comp in self.components.items():
            pins = comp.get("pins") or []
            for pin in pins:
                pin_id = pin.get("id")
                pin_name = pin.get("name", "PIN")
                pin_num = pin.get("number", "")

                # If pin has no connection in pin_to_net
                if pin_id not in self.pin_to_net:
                    floating.append({
                        "component_id": comp_id,
                        "component_name": comp.get("name"),
                        "pin_id": pin_id,
                        "pin_name": pin_name,
                        "pin_number": pin_num,
                        "reason": "Pin is not connected to any net",
                    })
                else:
                    net_id = self.pin_to_net[pin_id]
                    conns_on_net = self.net_pins.get(net_id, [])
                    if len(conns_on_net) <= 1:
                        floating.append({
                            "component_id": comp_id,
                            "component_name": comp.get("name"),
                            "pin_id": pin_id,
                            "pin_name": pin_name,
                            "pin_number": pin_num,
                            "net_id": net_id,
                            "reason": f"Net '{self.nets[net_id].get('name')}' has only 1 connection (stub net)",
                        })
        return floating

    def get_power_nets(self) -> list[dict[str, Any]]:
        res = []
        for net_id, net in self.nets.items():
            name = net.get("name", "")
            if self.is_power_net(name):
                voltage = self.infer_net_voltage(name)
                res.append({
                    "id": net_id,
                    "name": name,
                    "inferred_voltage": voltage,
                })
        return res

    def get_ground_nets(self) -> list[dict[str, Any]]:
        res = []
        for net_id, net in self.nets.items():
            name = net.get("name", "")
            if self.is_ground_net(name):
                res.append({
                    "id": net_id,
                    "name": name,
                })
        return res

    def count_subgraphs(self) -> int:
        """Count connected components using DFS over component-net bipartite graph."""
        visited_nodes: set[str] = set()
        count = 0

        all_nodes = list(self.components.keys()) + list(self.nets.keys())
        if not all_nodes:
            return 0

        # Build adjacency
        adj: dict[str, set[str]] = {n: set() for n in all_nodes}
        for conn in self.connections:
            c_id = conn.get("component_id")
            n_id = conn.get("net_id")
            if c_id in adj and n_id in adj:
                adj[c_id].add(n_id)
                adj[n_id].add(c_id)

        for node in all_nodes:
            if node not in visited_nodes:
                count += 1
                queue = [node]
                visited_nodes.add(node)
                while queue:
                    curr = queue.pop()
                    for neighbor in adj.get(curr, []):
                        if neighbor not in visited_nodes:
                            visited_nodes.add(neighbor)
                            queue.append(neighbor)

        return count

    def get_summary(self) -> dict[str, Any]:
        power_nets = self.get_power_nets()
        ground_nets = self.get_ground_nets()
        floating_pins = self.get_floating_pins()
        subgraphs = self.count_subgraphs()

        return {
            "total_components": len(self.components),
            "total_nets": len(self.nets),
            "total_connections": len(self.connections),
            "floating_pins": floating_pins,
            "power_nets": [p["name"] for p in power_nets],
            "ground_nets": [g["name"] for g in ground_nets],
            "isolated_subgraphs": subgraphs,
        }
