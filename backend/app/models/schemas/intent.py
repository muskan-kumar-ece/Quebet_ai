from typing import Any
from pydantic import BaseModel, Field


class MissingRequirement(BaseModel):
    """An explicit missing parameter that must not be hallucinated or blindly assumed."""

    field: str = Field(..., description="e.g. output_current, input_voltage_range")
    reason: str = Field(..., description="Why this field is required for component sizing or regulation")
    importance: str = Field(default="required", description="required | recommended | optional")


class EngineeringAssumptionItem(BaseModel):
    """An explicit assumption derived or proposed by the AI or defaults."""

    field: str = Field(..., description="e.g. ambient_temperature, operating_mode")
    value: str = Field(..., description="e.g. 25, continuous_conduction")
    unit: str | None = None
    source: str = Field(default="ai_inference", description="user | datasheet | knowledge_base | rule | ai_inference | default")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    rationale: str | None = None


class ProposedComponent(BaseModel):
    ref_des: str = Field(..., description="R1, C1, U1")
    component_type: str = Field(..., description="resistor, capacitor, linear_regulator, etc.")
    part_number: str | None = None
    value: str
    unit: str | None = None
    package: str | None = None
    description: str | None = None


class ProposedNet(BaseModel):
    name: str = Field(..., description="VCC_IN, VOUT_5V, GND")
    net_type: str = Field(default="signal", description="power | ground | signal | clock")


class ProposedConnection(BaseModel):
    from_ref_des: str
    from_pin: str
    to_net: str


class CircuitIntentRequest(BaseModel):
    prompt: str = Field(..., min_length=3, description="Natural language circuit specification")
    project_id: str | None = None
    user_preferences: dict[str, Any] = Field(default_factory=dict)


class CircuitIntent(BaseModel):
    """
    Intermediate typed representation produced from natural language intent.
    Never directly mutates the database until validated and confirmed.
    """

    summary: str
    topology: str | None = None  # e.g. "Linear LDO Regulator", "Buck Converter"
    input_voltage: str | None = None
    output_voltage: str | None = None
    output_current: str | None = None
    constraints: list[str] = Field(default_factory=list)
    missing_requirements: list[MissingRequirement] = Field(default_factory=list)
    assumptions: list[EngineeringAssumptionItem] = Field(default_factory=list)
    proposed_components: list[ProposedComponent] = Field(default_factory=list)
    proposed_nets: list[ProposedNet] = Field(default_factory=list)
    proposed_connections: list[ProposedConnection] = Field(default_factory=list)
    is_complete: bool = False
