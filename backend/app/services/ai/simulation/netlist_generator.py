from dataclasses import dataclass, field
import hashlib
import re
from typing import Any
from app.models.db.circuit import Circuit
from app.models.db.simulation import SimulationType
from app.services.ai.analysis.units import UnitNormalizer
from app.services.ai.simulation.model_registry import SpiceModelRegistry


@dataclass
class NetlistValidationResult:
    """Validation report and generated SPICE netlist text."""
    is_valid: bool
    netlist: str
    netlist_digest: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    node_mapping: dict[str, str] = field(default_factory=dict)
    models_included: list[str] = field(default_factory=list)


class NetlistGenerator:
    """
    Deterministic SPICE Netlist Generator and Netlist Validator.
    Translates Circuit graph (components, nets, connections) into standard SPICE netlist.
    """

    @classmethod
    def sanitize_identifier(cls, name: str) -> str:
        """Sanitizes names into safe SPICE identifiers."""
        clean = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip())
        return clean or "NODE"

    @classmethod
    def is_ground_net(cls, net_name: str) -> bool:
        """Determines if a net represents electrical ground."""
        clean = net_name.strip().upper()
        return clean in ("0", "GND", "0V", "GROUND", "VSS", "EARTH")

    @classmethod
    def format_spice_value(cls, val_any: Any, default_unit: str = "") -> str:
        """Converts component value to standard SPICE string using UnitNormalizer."""
        if isinstance(val_any, (int, float)):
            return str(val_any)
        val_str = str(val_any).strip()
        parsed = UnitNormalizer.parse(val_str)
        if parsed.is_valid and parsed.normalized_value is not None:
            # Output plain float or scientific notation
            return f"{parsed.normalized_value:.6g}"
        return val_str

    @classmethod
    def generate(
        cls,
        circuit: Circuit,
        simulation_type: str = SimulationType.DC_OPERATING_POINT.value,
        config: dict[str, Any] | None = None,
    ) -> NetlistValidationResult:
        """
        Generates and validates a complete SPICE netlist from a Circuit model.
        """
        config = config or {}
        warnings: list[str] = []
        errors: list[str] = []

        from app.services.ai.simulation.simulator_base import (
            MAX_ELEMENT_COUNT,
            MAX_NETLIST_CHARS,
            MAX_NODE_COUNT,
        )

        # Resource limit verification
        if len(circuit.components) > MAX_ELEMENT_COUNT:
            errors.append(f"RESOURCE_LIMIT_EXCEEDED: Component count ({len(circuit.components)}) exceeds maximum allowed ({MAX_ELEMENT_COUNT})")
        if len(circuit.nets) > MAX_NODE_COUNT:
            errors.append(f"RESOURCE_LIMIT_EXCEEDED: Net count ({len(circuit.nets)}) exceeds maximum allowed ({MAX_NODE_COUNT})")

        # 1. Map nets to SPICE nodes
        # Node "0" is reserved for ground
        net_to_node: dict[str, str] = {}
        has_ground = False

        # Deterministic net sorting: ground nets first, then alphanumeric by name and id
        sorted_nets = sorted(
            circuit.nets,
            key=lambda n: (cls.is_ground_net(n.name) is False, (n.name or "").upper(), str(n.id))
        )

        # First pass: map ground nets
        for net in sorted_nets:
            net_name = net.name
            if cls.is_ground_net(net_name):
                net_to_node[net.id] = "0"
                net_to_node[net_name] = "0"
                has_ground = True

        # Second pass: map non-ground nets
        node_counter = 1
        for net in sorted_nets:
            if net.id not in net_to_node:
                safe_name = cls.sanitize_identifier(net.name)
                # Ensure no collision with "0"
                if safe_name == "0":
                    safe_name = f"N_{node_counter}"
                    node_counter += 1
                net_to_node[net.id] = safe_name
                net_to_node[net.name] = safe_name

        if not has_ground:
            # If no ground net explicitly defined, assign first net named GND or create virtual ground warning
            warnings.append("No explicit ground (GND/0V) net found; circuit may be singular without ground reference.")

        # 2. Build net connections for each component
        # Map: component_id -> list of (pin_number, node_name)
        comp_pin_nodes: dict[str, dict[str, str]] = {}
        for comp in circuit.components:
            comp_pin_nodes[comp.id] = {}

        # Sort connections deterministically by component_id, pin, net_id
        sorted_connections = sorted(
            circuit.connections,
            key=lambda c: (str(c.component_id), str(c.pin_number), str(c.net_id))
        )
        for conn in sorted_connections:
            comp_id = conn.component_id
            pin = str(conn.pin_number)
            net_id = conn.net_id
            node = net_to_node.get(net_id, cls.sanitize_identifier(str(net_id)))
            if comp_id in comp_pin_nodes:
                comp_pin_nodes[comp_id][pin] = node

        # 3. Generate SPICE elements
        netlist_lines: list[str] = []
        circuit_title = f"* QUEBET AI Netlist: {circuit.name} (Rev {circuit.version})"
        netlist_lines.append(circuit_title)
        netlist_lines.append(f"* Generated deterministically for simulation: {simulation_type}")
        netlist_lines.append("")

        models_needed: set[str] = set()
        element_refs: set[str] = set()

        # Sort components deterministically by designator/ref_des
        sorted_components = sorted(
            circuit.components,
            key=lambda c: ((getattr(c, "ref_des", None) or getattr(c, "designator", None) or str(c.id)).upper())
        )

        for comp in sorted_components:
            raw_ref = getattr(comp, "ref_des", None) or getattr(comp, "designator", None) or f"U_{comp.id[:6]}"
            ref = cls.sanitize_identifier(raw_ref).upper()
            if ref in element_refs:
                errors.append(f"Duplicate designator detected in circuit: {ref}")
            element_refs.add(ref)

            raw_type = getattr(comp, "component_type", None) or getattr(comp, "type", None) or ""
            comp_type = raw_type.upper()
            pins = comp_pin_nodes.get(comp.id, {})
            # Sort pins by pin number
            sorted_pins = sorted(pins.items(), key=lambda x: str(x[0]))
            connected_nodes = [node for _, node in sorted_pins]

            val_str = cls.format_spice_value(comp.value)

            # Determine SPICE element prefix
            if comp_type.startswith("RES") or ref.startswith("R"):
                if len(connected_nodes) < 2:
                    warnings.append(f"Resistor {ref} has fewer than 2 connected pins ({len(connected_nodes)})")
                    n1 = connected_nodes[0] if connected_nodes else "0"
                    n2 = "0"
                else:
                    n1, n2 = connected_nodes[0], connected_nodes[1]
                netlist_lines.append(f"{ref} {n1} {n2} {val_str or '1k'}")

            elif comp_type.startswith("CAP") or ref.startswith("C"):
                if len(connected_nodes) < 2:
                    warnings.append(f"Capacitor {ref} has fewer than 2 connected pins")
                    n1 = connected_nodes[0] if connected_nodes else "0"
                    n2 = "0"
                else:
                    n1, n2 = connected_nodes[0], connected_nodes[1]
                netlist_lines.append(f"{ref} {n1} {n2} {val_str or '1u'}")

            elif comp_type.startswith("IND") or ref.startswith("L"):
                if len(connected_nodes) < 2:
                    warnings.append(f"Inductor {ref} has fewer than 2 connected pins")
                    n1 = connected_nodes[0] if connected_nodes else "0"
                    n2 = "0"
                else:
                    n1, n2 = connected_nodes[0], connected_nodes[1]
                netlist_lines.append(f"{ref} {n1} {n2} {val_str or '1m'}")

            elif comp_type.startswith("VOLT") or comp_type.startswith("VSOURCE") or ref.startswith("V"):
                if len(connected_nodes) < 2:
                    n1 = connected_nodes[0] if connected_nodes else "N_VCC"
                    n2 = "0"
                else:
                    n1, n2 = connected_nodes[0], connected_nodes[1]
                netlist_lines.append(f"{ref} {n1} {n2} DC {val_str or '5'}")

            elif comp_type.startswith("CURR") or comp_type.startswith("ISOURCE") or ref.startswith("I"):
                if len(connected_nodes) < 2:
                    n1 = connected_nodes[0] if connected_nodes else "N_ICC"
                    n2 = "0"
                else:
                    n1, n2 = connected_nodes[0], connected_nodes[1]
                netlist_lines.append(f"{ref} {n1} {n2} DC {val_str or '1m'}")

            elif comp_type.startswith("DIO") or ref.startswith("D"):
                if len(connected_nodes) < 2:
                    warnings.append(f"Diode {ref} has fewer than 2 connected pins")
                    n1 = connected_nodes[0] if connected_nodes else "0"
                    n2 = "0"
                else:
                    n1, n2 = connected_nodes[0], connected_nodes[1]
                model_name = cls.sanitize_identifier(comp.part_number).upper() if comp.part_number else "1N4148"
                models_needed.add(model_name)
                netlist_lines.append(f"{ref} {n1} {n2} {model_name}")

            elif comp_type.startswith("TRANS") or ref.startswith("Q"):
                # BJT collector, base, emitter
                if len(connected_nodes) < 3:
                    warnings.append(f"Transistor {ref} has fewer than 3 connected pins")
                    nodes_padded = connected_nodes + ["0"] * (3 - len(connected_nodes))
                else:
                    nodes_padded = connected_nodes[:3]
                nc, nb, ne = nodes_padded[0], nodes_padded[1], nodes_padded[2]
                model_name = cls.sanitize_identifier(comp.part_number).upper() if comp.part_number else "2N2222"
                models_needed.add(model_name)
                netlist_lines.append(f"{ref} {nc} {nb} {ne} {model_name}")

            elif comp_type.startswith("MOS") or comp_type.startswith("NMOS") or comp_type.startswith("PMOS") or ref.startswith("M"):
                if len(connected_nodes) < 4:
                    warnings.append(f"MOSFET {ref} has fewer than 4 connected pins; bulk defaulted to source")
                    nodes_padded = connected_nodes + ["0"] * (4 - len(connected_nodes))
                else:
                    nodes_padded = connected_nodes[:4]
                nd, ng, ns, nb = nodes_padded[0], nodes_padded[1], nodes_padded[2], nodes_padded[3]
                model_name = cls.sanitize_identifier(comp.part_number).upper() if comp.part_number else "2N7000"
                models_needed.add(model_name)
                netlist_lines.append(f"{ref} {nd} {ng} {ns} {nb} {model_name}")

            elif (
                comp_type.startswith("IC")
                or comp_type.startswith("REG")
                or comp_type.startswith("OPAMP")
                or comp_type.startswith("MCU")
                or comp_type.startswith("SUB")
                or ref.startswith("X")
                or ref.startswith("U")
            ):
                # Generic subcircuit or multi-pin IC
                subckt_ref = f"X{ref}" if not ref.startswith("X") else ref
                node_str = " ".join(connected_nodes) if connected_nodes else "0"
                raw_sub = comp.part_number or comp.name or "SUBCKT_GENERIC"
                sub_name = cls.sanitize_identifier(raw_sub)
                netlist_lines.append(f"{subckt_ref} {node_str} {sub_name}")

            else:
                warnings.append(f"UNSUPPORTED_ELEMENT: Component {ref} of type '{comp_type}' cannot be directly modeled as a SPICE primitive")

        netlist_lines.append("")

        # 4. Append Models
        models_included: list[str] = []
        for model_name in sorted(models_needed):
            model_def = SpiceModelRegistry.get_model(model_name)
            if model_def:
                netlist_lines.append(f"* Model for {model_name}")
                netlist_lines.append(model_def)
                models_included.append(model_name)
            else:
                # Default generic diode or transistor if not in registry
                if model_name.startswith("D") or "DIO" in model_name:
                    netlist_lines.append(f".model {model_name} D")
                else:
                    netlist_lines.append(f".model {model_name} NPN")
                models_included.append(model_name)

        netlist_lines.append("")

        # 5. Append Simulation Directives
        if simulation_type == SimulationType.DC_OPERATING_POINT.value:
            netlist_lines.append(".op")
        elif simulation_type == SimulationType.DC_SWEEP.value:
            src = cls.sanitize_identifier(str(config.get("sweep_source", "V1")))
            vstart = float(config.get("start_voltage", 0.0))
            vstop = float(config.get("stop_voltage", 5.0))
            vstep = float(config.get("step_voltage", 0.1))
            netlist_lines.append(f".dc {src} {vstart} {vstop} {vstep}")
        elif simulation_type == SimulationType.AC_SMALL_SIGNAL.value:
            pts = int(config.get("points_per_decade", 10))
            fstart = float(config.get("start_freq", 1.0))
            fstop = float(config.get("stop_freq", 1000000.0))
            netlist_lines.append(f".ac dec {pts} {fstart} {fstop}")
        elif simulation_type == SimulationType.TRANSIENT.value:
            tstep = float(config.get("tstep", 1e-5))
            tstop = float(config.get("tstop", 0.01))
            netlist_lines.append(f".tran {tstep} {tstop}")

        netlist_lines.append(".end")
        netlist_lines.append("")

        full_netlist = "\n".join(netlist_lines)
        if len(full_netlist) > MAX_NETLIST_CHARS:
            errors.append(f"RESOURCE_LIMIT_EXCEEDED: Netlist size ({len(full_netlist)} chars) exceeds maximum allowed ({MAX_NETLIST_CHARS})")

        digest = hashlib.sha256(full_netlist.encode("utf-8")).hexdigest()
        is_valid = len(errors) == 0

        return NetlistValidationResult(
            is_valid=is_valid,
            netlist=full_netlist,
            netlist_digest=digest,
            warnings=warnings,
            errors=errors,
            node_mapping=net_to_node,
            models_included=models_included,
        )
