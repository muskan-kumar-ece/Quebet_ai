from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class IdentityState(str, Enum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"


class ParameterCategory(str, Enum):
    OPERATING_LIMIT = "OPERATING_LIMIT"
    ABSOLUTE_MAXIMUM = "ABSOLUTE_MAXIMUM"
    TYPICAL_VALUE = "TYPICAL_VALUE"
    MINIMUM = "MINIMUM"
    MAXIMUM = "MAXIMUM"
    PIN_DEFINITION = "PIN_DEFINITION"
    APPLICATION_CONSTRAINT = "APPLICATION_CONSTRAINT"
    REFERENCE_DESIGN = "REFERENCE_DESIGN"


class ApplicabilityCategory(str, Enum):
    APPLICABLE = "APPLICABLE"
    POTENTIALLY_APPLICABLE = "POTENTIALLY_APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"


class ComponentIdentityResolutionRequest(BaseModel):
    query: Optional[str] = None
    manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    package: Optional[str] = None


class ComponentIdentity(BaseModel):
    state: IdentityState
    manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    manufacturer_part_number: Optional[str] = None
    component_type: Optional[str] = None
    package: Optional[str] = None
    variant: Optional[str] = None
    document_identifier: Optional[str] = None
    revision: Optional[str] = None
    source_id: Optional[str] = None
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    ambiguity_reasons: list[str] = Field(default_factory=list)


class ComponentPin(BaseModel):
    pin_number: str
    pin_name: str
    pin_type: str = "PASSIVE"  # POWER_IN, POWER_OUT, GROUND, ANALOG_IN, ANALOG_OUT, DIGITAL_IO, PASSIVE
    electrical_role: Optional[str] = None  # VIN, VOUT, GND, EN, FB, SDA, SCL, TX, RX
    description: Optional[str] = None
    source_location: dict[str, Any] = Field(default_factory=dict)


class ComponentParameterItem(BaseModel):
    parameter: str
    category: str = ParameterCategory.TYPICAL_VALUE.value
    raw_value: str
    normalized_value: Optional[float] = None
    unit: Optional[str] = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    valid_range: Optional[dict[str, Any]] = None
    classification: str = "AUTHORITATIVE_SOURCE"
    source_id: Optional[str] = None
    source_revision: Optional[str] = None
    source_location: dict[str, Any] = Field(default_factory=dict)
    is_conflicting: bool = False
    conflict_details: dict[str, Any] = Field(default_factory=dict)


class ComponentConstraintItem(BaseModel):
    constraint_type: str  # CAPACITANCE, ESR, LAYOUT, PULL_UP, DECOUPLING
    description: str
    parameter: Optional[str] = None
    requirement_value: Optional[str] = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    source_location: dict[str, Any] = Field(default_factory=dict)


class ComponentReferenceDesignItem(BaseModel):
    title: str
    topology: str
    description: Optional[str] = None
    external_components: list[dict[str, Any]] = Field(default_factory=list)
    source_location: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ComponentProfileResponse(BaseModel):
    identity: ComponentIdentity
    pins: list[ComponentPin] = Field(default_factory=list)
    operating_ranges: list[ComponentParameterItem] = Field(default_factory=list)
    absolute_maximums: list[ComponentParameterItem] = Field(default_factory=list)
    electrical_characteristics: list[ComponentParameterItem] = Field(default_factory=list)
    thermal_characteristics: list[ComponentParameterItem] = Field(default_factory=list)
    application_constraints: list[ComponentConstraintItem] = Field(default_factory=list)
    reference_designs: list[ComponentReferenceDesignItem] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    provenance_chain: dict[str, Any] = Field(default_factory=dict)


class OperatingValidationRequest(BaseModel):
    parameter: str
    value: float
    unit: Optional[str] = None
    conditions: dict[str, Any] = Field(default_factory=dict)


class OperatingValidationResponse(BaseModel):
    parameter: str
    evaluated_value: float
    is_operating_valid: bool
    is_absolute_maximum_exceeded: bool
    status: str  # OPERATING_POINT_VALID, OPERATING_LIMIT_EXCEEDED, ABSOLUTE_MAXIMUM_EXCEEDED, PARAMETER_UNKNOWN
    operating_range: Optional[dict[str, Any]] = None
    absolute_maximum: Optional[dict[str, Any]] = None
    explanation: str


class ApplicabilityEvaluationRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


class ApplicabilityEvaluationResponse(BaseModel):
    part_number: str
    status: ApplicabilityCategory
    reasons: list[str] = Field(default_factory=list)
    evaluated_conditions: dict[str, Any] = Field(default_factory=dict)
    missing_conditions: list[str] = Field(default_factory=list)
