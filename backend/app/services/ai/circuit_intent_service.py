import re
from app.models.schemas.intent import (
    CircuitIntent,
    EngineeringAssumptionItem,
    MissingRequirement,
    ProposedComponent,
    ProposedConnection,
    ProposedNet,
)


class CircuitIntentService:
    """
    Controlled AI interpretation boundary for translating natural language engineering requirements
    into typed CircuitIntent representations with missing parameter detection and assumption tracking.
    Never mutates the database directly.
    """

    async def interpret_intent(self, prompt: str) -> CircuitIntent:
        prompt_lower = prompt.lower()

        # 1. Deterministic Extraction via regex
        vin_match = re.search(r"(\d+(?:\.\d+)?)\s*v(?:olts?)?\s*(?:in(?:put)?|to)?", prompt_lower)
        vout_match = re.search(r"(?:to|out(?:put)?)\s*(\d+(?:\.\d+)?)\s*v(?:olts?)?", prompt_lower)
        curr_match = re.search(r"(\d+(?:\.\d+)?)\s*(m?a(?:mps?)?)\b", prompt_lower)

        vin = f"{vin_match.group(1)}V" if vin_match else None
        vout = f"{vout_match.group(1)}V" if vout_match else None
        current = f"{curr_match.group(1)}{curr_match.group(2).upper()}" if curr_match else None

        missing_reqs: list[MissingRequirement] = []
        assumptions: list[EngineeringAssumptionItem] = []
        proposed_components: list[ProposedComponent] = []
        proposed_nets: list[ProposedNet] = []
        proposed_connections: list[ProposedConnection] = []

        # 2. Missing Requirement Detection
        if not vin:
            missing_reqs.append(
                MissingRequirement(
                    field="input_voltage",
                    reason="Input voltage (Vin) is required to select regulator input breakdown voltage and calculate dissipation.",
                    importance="required",
                )
            )

        if not vout:
            missing_reqs.append(
                MissingRequirement(
                    field="output_voltage",
                    reason="Regulated target output voltage (Vout) is required to choose the regulator IC or feedback divider.",
                    importance="required",
                )
            )

        if not current:
            missing_reqs.append(
                MissingRequirement(
                    field="output_current",
                    reason="Maximum load current is required to compute power dissipation (Pd = (Vin - Vout) * Iload) and prevent thermal shutdown.",
                    importance="required",
                )
            )
        else:
            # Baseline assumptions when current is known
            assumptions.append(
                EngineeringAssumptionItem(
                    field="ambient_temperature",
                    value="25",
                    unit="C",
                    source="default",
                    confidence=0.95,
                    rationale="Standard nominal operating room temperature.",
                )
            )

        # 3. Topology & Component Synthesizer based on recognized parameters
        topology = None
        if vout == "5V" or (vout and "5" in vout):
            topology = "5V Linear Voltage Regulation"
            reg_part = "LM7805"
            reg_package = "TO-220"

            assumptions.append(
                EngineeringAssumptionItem(
                    field="regulator_ic",
                    value=reg_part,
                    source="knowledge_base",
                    confidence=0.9,
                    rationale="Industry standard 5V fixed regulator; supports up to 1.5A with heatsink.",
                )
            )

            proposed_components = [
                ProposedComponent(
                    ref_des="U1",
                    component_type="linear_regulator",
                    part_number=reg_part,
                    value="5V",
                    package=reg_package,
                    description="Fixed 5V 1.5A Linear Voltage Regulator",
                ),
                ProposedComponent(
                    ref_des="C1",
                    component_type="capacitor",
                    value="0.33uF",
                    unit="uF",
                    package="0805",
                    description="Input stability bypass capacitor per LM7805 datasheet",
                ),
                ProposedComponent(
                    ref_des="C2",
                    component_type="capacitor",
                    value="0.1uF",
                    unit="uF",
                    package="0603",
                    description="High-frequency output transient decoupling capacitor",
                ),
            ]

            proposed_nets = [
                ProposedNet(name="VCC_IN", net_type="power"),
                ProposedNet(name="VOUT_5V", net_type="power"),
                ProposedNet(name="GND", net_type="ground"),
            ]

            proposed_connections = [
                ProposedConnection(from_ref_des="U1", from_pin="1", to_net="VCC_IN"),
                ProposedConnection(from_ref_des="U1", from_pin="2", to_net="GND"),
                ProposedConnection(from_ref_des="U1", from_pin="3", to_net="VOUT_5V"),
                ProposedConnection(from_ref_des="C1", from_pin="1", to_net="VCC_IN"),
                ProposedConnection(from_ref_des="C1", from_pin="2", to_net="GND"),
                ProposedConnection(from_ref_des="C2", from_pin="1", to_net="VOUT_5V"),
                ProposedConnection(from_ref_des="C2", from_pin="2", to_net="GND"),
            ]

        elif vout == "3.3V" or (vout and "3.3" in vout):
            topology = "3.3V Low-Dropout (LDO) Regulation"
            reg_part = "AMS1117-3.3"
            reg_package = "SOT-223"

            assumptions.append(
                EngineeringAssumptionItem(
                    field="regulator_ic",
                    value=reg_part,
                    source="knowledge_base",
                    confidence=0.9,
                    rationale="Standard 3.3V 800mA LDO regulator; requires output cap with ESR > 0.1 ohm for stability.",
                )
            )

            proposed_components = [
                ProposedComponent(
                    ref_des="U1",
                    component_type="linear_regulator",
                    part_number=reg_part,
                    value="3.3V",
                    package=reg_package,
                    description="3.3V 800mA Low Dropout Voltage Regulator",
                ),
                ProposedComponent(
                    ref_des="C1",
                    component_type="capacitor",
                    value="10uF",
                    unit="uF",
                    package="0805",
                    description="Input bulk decoupling capacitor",
                ),
                ProposedComponent(
                    ref_des="C2",
                    component_type="capacitor",
                    value="10uF",
                    unit="uF",
                    package="0805",
                    description="Output stability capacitor with controlled ESR",
                ),
            ]

            proposed_nets = [
                ProposedNet(name="VCC_IN", net_type="power"),
                ProposedNet(name="VOUT_3V3", net_type="power"),
                ProposedNet(name="GND", net_type="ground"),
            ]

            proposed_connections = [
                ProposedConnection(from_ref_des="U1", from_pin="1", to_net="GND"),
                ProposedConnection(from_ref_des="U1", from_pin="2", to_net="VOUT_3V3"),
                ProposedConnection(from_ref_des="U1", from_pin="3", to_net="VCC_IN"),
                ProposedConnection(from_ref_des="C1", from_pin="1", to_net="VCC_IN"),
                ProposedConnection(from_ref_des="C1", from_pin="2", to_net="GND"),
                ProposedConnection(from_ref_des="C2", from_pin="1", to_net="VOUT_3V3"),
                ProposedConnection(from_ref_des="C2", from_pin="2", to_net="GND"),
            ]

        is_complete = len(missing_reqs) == 0 and len(proposed_components) > 0

        summary = f"Circuit interpretation for: '{prompt}'"
        if topology:
            summary += f" -> Identified topology: {topology}"

        return CircuitIntent(
            summary=summary,
            topology=topology,
            input_voltage=vin,
            output_voltage=vout,
            output_current=current,
            constraints=["Ripple < 50mV", "Decoupling within 5mm"] if topology else [],
            missing_requirements=missing_reqs,
            assumptions=assumptions,
            proposed_components=proposed_components,
            proposed_nets=proposed_nets,
            proposed_connections=proposed_connections,
            is_complete=is_complete,
        )


circuit_intent_service = CircuitIntentService()
