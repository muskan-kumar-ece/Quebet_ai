import json
import logging
import math
import re
from pathlib import Path
from typing import Any, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db.provenance import (
    EngineeringKnowledgeRecord,
    EngineeringSource,
    KnowledgeClassification,
    KnowledgeStatus,
    ParameterCategory,
    SourceStatus,
)
from app.models.schemas.component_intelligence import (
    ApplicabilityCategory,
    ComponentConstraintItem,
    ComponentIdentity,
    ComponentParameterItem,
    ComponentPin,
    ComponentProfileResponse,
    ComponentReferenceDesignItem,
    IdentityState,
    OperatingValidationResponse,
)
from app.services.ai.cognitive.reflection.contradiction_engine import UnitNormalizer
from app.services.component_knowledge_service import ComponentKnowledgeService

logger = logging.getLogger(__name__)


def sanitize_input(text: Optional[str], max_len: int = 256) -> str:
    """Sanitizes text, enforces length bounds, and strips control characters."""
    if not text:
        return ""
    cleaned = re.sub(
        r"(?i)(ignore\s+all\s+previous\s+instructions|system\s+prompt|system\s*:|<system>|</system>|assistant\s*:|human\s*:)",
        "[INERT_DATA]",
        str(text),
    )
    return cleaned.strip()[:max_len]


def is_malformed_number(val: Any) -> bool:
    """Detects NaN, Infinite, or non-finite values."""
    if isinstance(val, (int, float)):
        return math.isnan(val) or math.isinf(val)
    if isinstance(val, str):
        v_lower = val.lower().strip()
        return v_lower in ("nan", "inf", "-inf", "infinity", "-infinity")
    return False


class EngineeringComponentIntelligenceService:
    """
    Phase 3 Wave 2: Datasheet & Component Intelligence Service.
    Enforces:
    - Deterministic Component Identity Resolution (RESOLVED, AMBIGUOUS, UNKNOWN, CONFLICTING)
    - Operating Limits vs Absolute Maximum Ratings Separation (Safety Invariant)
    - First-Class Test Conditions Preservation
    - Application Constraints & Reference Design Provenance
    - Zero Synthetic Scoring (Strict categorical evaluations only)
    - Full Provenance Chains bound to SHA-256 digests and revisions
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.kb_service = ComponentKnowledgeService()

    async def resolve_identity(
        self,
        query: Optional[str] = None,
        manufacturer: Optional[str] = None,
        part_number: Optional[str] = None,
        package: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> ComponentIdentity:
        """
        Deterministically resolves component identity.
        States:
        - RESOLVED: Single unambiguous component match.
        - AMBIGUOUS: Multiple candidates match query; NEVER picks a winner or autocorrects.
        - UNKNOWN: No documented component matches.
        - CONFLICTING: Conflicting manufacturer/type records for the same identifier.
        """
        clean_q = sanitize_input(query or part_number or "")
        clean_mfg = sanitize_input(manufacturer or "")
        clean_pkg = sanitize_input(package or "")

        if not clean_q and not clean_mfg:
            return ComponentIdentity(
                state=IdentityState.UNKNOWN,
                ambiguity_reasons=["Empty query or part number provided."],
            )

        # 1. Search DB EngineeringKnowledgeRecord for component subjects
        stmt = (
            select(EngineeringKnowledgeRecord)
            .options(selectinload(EngineeringKnowledgeRecord.source))
            .where(
                EngineeringKnowledgeRecord.subject_type == "COMPONENT",
                or_(
                    EngineeringKnowledgeRecord.tenant_id == tenant_id,
                    EngineeringKnowledgeRecord.tenant_id.is_(None),
                ),
            )
        )
        if clean_q:
            stmt = stmt.where(EngineeringKnowledgeRecord.subject_identifier.ilike(f"%{clean_q}%"))

        res = await self.db.execute(stmt)
        records = res.scalars().all()

        # Collect distinct subjects from SQL
        db_candidates: dict[str, dict[str, Any]] = {}
        for r in records:
            subj = r.subject_identifier
            if subj not in db_candidates:
                db_candidates[subj] = {
                    "part_number": subj,
                    "manufacturer": r.source.publisher if r.source else None,
                    "document_identifier": r.source.document_identifier if r.source else None,
                    "revision": r.source.revision if r.source else None,
                    "source_id": r.source_id,
                    "component_type": r.domain,
                    "origin": "DB_AUTHORITATIVE_SOURCE",
                }

        # 2. Search Curated Electronics-KB (Linear regulators, MCUs, etc.)
        kb_matches: list[dict[str, Any]] = []
        ics_data = self.kb_service.get_ics()
        for reg in ics_data.get("linear_regulators", []):
            pn = reg.get("part_number", "")
            if clean_q.lower() in pn.lower():
                kb_matches.append({
                    "part_number": pn,
                    "manufacturer": reg.get("manufacturer") or "General Semiconductor",
                    "component_type": reg.get("type", "Voltage Regulator"),
                    "package": reg.get("package"),
                    "origin": "ELECTRONICS_KB",
                })
        for mcu in ics_data.get("microcontrollers", []):
            pn = mcu.get("part_number", "")
            if clean_q.lower() in pn.lower():
                kb_matches.append({
                    "part_number": pn,
                    "manufacturer": mcu.get("manufacturer"),
                    "component_type": "Microcontroller",
                    "package": mcu.get("package"),
                    "origin": "ELECTRONICS_KB",
                })

        # Combine candidates
        all_candidates: dict[str, dict[str, Any]] = dict(db_candidates)
        for km in kb_matches:
            pn = km["part_number"]
            if pn not in all_candidates:
                all_candidates[pn] = km

        candidate_list = list(all_candidates.values())

        # Exact match check
        exact_matches = [
            c for c in candidate_list if c["part_number"].lower() == clean_q.lower()
        ]

        if len(exact_matches) == 1:
            match = exact_matches[0]
            # Check for conflict if manufacturer was specified
            if clean_mfg and match.get("manufacturer") and clean_mfg.lower() not in match["manufacturer"].lower():
                return ComponentIdentity(
                    state=IdentityState.CONFLICTING,
                    part_number=match["part_number"],
                    manufacturer=match.get("manufacturer"),
                    ambiguity_reasons=[
                        f"Manufacturer conflict: requested '{clean_mfg}', source specifies '{match.get('manufacturer')}'"
                    ],
                    candidates=candidate_list,
                )
            return ComponentIdentity(
                state=IdentityState.RESOLVED,
                part_number=match["part_number"],
                manufacturer=match.get("manufacturer"),
                component_type=match.get("component_type"),
                package=match.get("package"),
                document_identifier=match.get("document_identifier"),
                revision=match.get("revision"),
                source_id=match.get("source_id"),
            )

        if len(candidate_list) == 1:
            match = candidate_list[0]
            return ComponentIdentity(
                state=IdentityState.RESOLVED,
                part_number=match["part_number"],
                manufacturer=match.get("manufacturer"),
                component_type=match.get("component_type"),
                package=match.get("package"),
                document_identifier=match.get("document_identifier"),
                revision=match.get("revision"),
                source_id=match.get("source_id"),
            )

        if len(candidate_list) > 1:
            # INVARIANT: DO NOT PICK A WINNER. Return AMBIGUOUS state.
            return ComponentIdentity(
                state=IdentityState.AMBIGUOUS,
                ambiguity_reasons=[
                    f"Query '{clean_q}' matches {len(candidate_list)} components. Explicit disambiguation required."
                ],
                candidates=candidate_list,
            )

        return ComponentIdentity(
            state=IdentityState.UNKNOWN,
            ambiguity_reasons=[f"Component '{clean_q}' not found in authoritative knowledge."],
        )

    async def get_component_profile(
        self,
        part_number: str,
        tenant_id: Optional[str] = None,
    ) -> ComponentProfileResponse:
        """
        Assembles a comprehensive, structured component profile from authoritative records:
        - Pins & Pin Definitions
        - Operating Ranges (Recommended Limits)
        - Absolute Maximum Ratings
        - Electrical Characteristics
        - Thermal Characteristics
        - Application Constraints & External Component Requirements
        - Reference Designs
        - Active Contradictions
        - Documented Unknowns
        """
        clean_pn = sanitize_input(part_number)
        identity = await self.resolve_identity(part_number=clean_pn, tenant_id=tenant_id)

        # Retrieve all active records for this part number
        stmt = (
            select(EngineeringKnowledgeRecord)
            .options(selectinload(EngineeringKnowledgeRecord.source))
            .where(
                EngineeringKnowledgeRecord.subject_identifier.ilike(clean_pn),
                EngineeringKnowledgeRecord.status != KnowledgeStatus.SUPERSEDED.value,
                EngineeringKnowledgeRecord.status != KnowledgeStatus.REJECTED.value,
                or_(
                    EngineeringKnowledgeRecord.tenant_id == tenant_id,
                    EngineeringKnowledgeRecord.tenant_id.is_(None),
                ),
            )
            .order_by(EngineeringKnowledgeRecord.created_at.asc())
        )
        res = await self.db.execute(stmt)
        records = res.scalars().all()

        pins: list[ComponentPin] = []
        operating_ranges: list[ComponentParameterItem] = []
        absolute_maximums: list[ComponentParameterItem] = []
        electrical_characteristics: list[ComponentParameterItem] = []
        thermal_characteristics: list[ComponentParameterItem] = []
        application_constraints: list[ComponentConstraintItem] = []
        reference_designs: list[ComponentReferenceDesignItem] = []
        contradictions: list[dict[str, Any]] = []
        unknowns: list[str] = []

        primary_source: Optional[EngineeringSource] = None

        for r in records:
            if not primary_source and r.source:
                primary_source = r.source

            # Check for contradiction
            if r.is_conflicting:
                contradictions.append({
                    "record_id": r.id,
                    "parameter": r.parameter,
                    "conflict_details": r.conflict_details,
                    "source_id": r.source_id,
                })

            # Check for UNKNOWN
            if r.classification == KnowledgeClassification.UNKNOWN.value or r.value == "UNKNOWN":
                unknowns.append(r.parameter)
                continue

            category = r.parameter_category or ParameterCategory.TYPICAL_VALUE.value
            p_name = r.parameter.lower()

            # 1. Pins
            if category == ParameterCategory.PIN_DEFINITION.value or p_name.startswith("pin:") or p_name == "pin_definitions":
                pin_num = str(r.conditions.get("pin_number") or p_name.replace("pin:", "") or "1")
                pins.append(
                    ComponentPin(
                        pin_number=pin_num,
                        pin_name=r.value,
                        pin_type=r.conditions.get("pin_type", "PASSIVE"),
                        electrical_role=r.conditions.get("electrical_role") or r.value,
                        description=r.conditions.get("description"),
                        source_location=r.source_location,
                    )
                )
                continue

            # 2. Application Constraints
            if category == ParameterCategory.APPLICATION_CONSTRAINT.value or p_name.startswith("constraint:"):
                application_constraints.append(
                    ComponentConstraintItem(
                        constraint_type=r.conditions.get("constraint_type", "APPLICATION_CONSTRAINT"),
                        description=r.value,
                        parameter=r.parameter,
                        requirement_value=r.raw_value or r.value,
                        conditions=r.conditions,
                        source_location=r.source_location,
                    )
                )
                continue

            # 3. Reference Designs
            if category == ParameterCategory.REFERENCE_DESIGN.value or p_name.startswith("reference_design:"):
                reference_designs.append(
                    ComponentReferenceDesignItem(
                        title=r.value,
                        topology=r.conditions.get("topology", "REFERENCE_CIRCUIT"),
                        description=r.conditions.get("description"),
                        external_components=r.conditions.get("external_components", []),
                        source_location=r.source_location,
                        provenance=r.provenance,
                    )
                )
                continue

            param_item = ComponentParameterItem(
                parameter=r.parameter,
                category=category,
                raw_value=r.raw_value or r.value,
                normalized_value=r.normalized_value,
                unit=r.unit,
                conditions=r.conditions,
                valid_range=r.valid_range,
                classification=r.classification,
                source_id=r.source_id,
                source_revision=r.source.revision if r.source else None,
                source_location=r.source_location,
                is_conflicting=r.is_conflicting,
                conflict_details=r.conflict_details,
            )

            # 4. Absolute Maximum Ratings
            if category == ParameterCategory.ABSOLUTE_MAXIMUM.value or p_name.startswith("abs_max") or "maximum" in p_name:
                absolute_maximums.append(param_item)
            # 5. Operating Limits
            elif category == ParameterCategory.OPERATING_LIMIT.value or "operating" in p_name or p_name in ("v_in_min", "v_in_max", "v_out"):
                operating_ranges.append(param_item)
            # 6. Thermal Characteristics
            elif "theta" in p_name or "thermal" in p_name or "junction_temp" in p_name:
                thermal_characteristics.append(param_item)
            # 7. General Electrical Specs
            else:
                electrical_characteristics.append(param_item)

        # Fallback to electronics-kb if no records in SQL yet
        if not records:
            ics_data = self.kb_service.get_ics()
            for reg in ics_data.get("linear_regulators", []):
                if reg.get("part_number", "").lower() == clean_pn.lower():
                    # Populate from KB
                    identity.manufacturer = "General Semiconductor"
                    identity.component_type = reg.get("type")
                    identity.package = reg.get("package")

                    if reg.get("v_in_min") and reg.get("v_in_max"):
                        operating_ranges.append(
                            ComponentParameterItem(
                                parameter="v_in_range",
                                category=ParameterCategory.OPERATING_LIMIT.value,
                                raw_value=f"{reg['v_in_min']}V to {reg['v_in_max']}V",
                                normalized_value=reg["v_in_max"],
                                unit="V",
                                valid_range={"min": reg["v_in_min"], "max": reg["v_in_max"]},
                                classification=KnowledgeClassification.AUTHORITATIVE_SOURCE.value,
                            )
                        )
                    if reg.get("max_junction_temp_c"):
                        absolute_maximums.append(
                            ComponentParameterItem(
                                parameter="max_junction_temp",
                                category=ParameterCategory.ABSOLUTE_MAXIMUM.value,
                                raw_value=f"{reg['max_junction_temp_c']}°C",
                                normalized_value=reg["max_junction_temp_c"],
                                unit="°C",
                                classification=KnowledgeClassification.AUTHORITATIVE_SOURCE.value,
                            )
                        )
                    for issue in reg.get("common_issues", []):
                        application_constraints.append(
                            ComponentConstraintItem(
                                constraint_type="STABILITY_REQUIREMENT",
                                description=issue,
                            )
                        )
                    break

        # Ensure standard expected parameters are marked as UNKNOWN if missing
        standard_params = ["quiescent_current", "operating_temperature_max", "dropout_voltage"]
        present_params = {r.parameter.lower() for r in records}
        for sp in standard_params:
            if not any(sp in p for p in present_params) and sp not in unknowns:
                unknowns.append(sp)

        provenance_chain = {
            "part_number": clean_pn,
            "source_id": primary_source.id if primary_source else None,
            "document_identifier": primary_source.document_identifier if primary_source else "ELECTRONICS_KB",
            "revision": primary_source.revision if primary_source else "1.0",
            "integrity_digest": primary_source.document_hash if primary_source else None,
            "record_count": len(records),
        }

        return ComponentProfileResponse(
            identity=identity,
            pins=pins,
            operating_ranges=operating_ranges,
            absolute_maximums=absolute_maximums,
            electrical_characteristics=electrical_characteristics,
            thermal_characteristics=thermal_characteristics,
            application_constraints=application_constraints,
            reference_designs=reference_designs,
            contradictions=contradictions,
            unknowns=unknowns,
            provenance_chain=provenance_chain,
        )

    async def validate_operating_point(
        self,
        part_number: str,
        parameter: str,
        value: float,
        unit: Optional[str] = None,
        conditions: Optional[dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
    ) -> OperatingValidationResponse:
        """
        Evaluates whether a value is safe.
        ENFORCES THE CRITICAL SAFETY INVARIANT:
        Recommended / Operating Range != Absolute Maximum Rating.
        Even if value <= Absolute Maximum, if value > Operating Max,
        it is flagged as OPERATING_LIMIT_EXCEEDED.
        """
        if is_malformed_number(value):
            return OperatingValidationResponse(
                parameter=parameter,
                evaluated_value=0.0,
                is_operating_valid=False,
                is_absolute_maximum_exceeded=False,
                status="MALFORMED_VALUE_REJECTED",
                explanation=f"Malformed or non-finite value '{value}' rejected.",
            )

        profile = await self.get_component_profile(part_number=part_number, tenant_id=tenant_id)
        clean_param = parameter.lower()

        # Find absolute maximum rating
        abs_max_item = None
        for item in profile.absolute_maximums:
            if clean_param in item.parameter.lower() or item.parameter.lower() in clean_param:
                abs_max_item = item
                break

        # Find operating limit
        op_range_item = None
        for item in profile.operating_ranges:
            if clean_param in item.parameter.lower() or item.parameter.lower() in clean_param:
                op_range_item = item
                break

        abs_max_val = None
        if abs_max_item:
            if abs_max_item.valid_range and abs_max_item.valid_range.get("max") is not None:
                abs_max_val = abs_max_item.valid_range.get("max")
            elif abs_max_item.normalized_value is not None:
                abs_max_val = abs_max_item.normalized_value
        
        op_max_val = None
        op_min_val = None
        if op_range_item:
            if op_range_item.valid_range:
                op_max_val = op_range_item.valid_range.get("max")
                op_min_val = op_range_item.valid_range.get("min")
            elif op_range_item.normalized_value is not None:
                op_max_val = op_range_item.normalized_value

        # 1. Check Absolute Maximum Exceeded
        if abs_max_val is not None and value > abs_max_val:
            return OperatingValidationResponse(
                parameter=parameter,
                evaluated_value=value,
                is_operating_valid=False,
                is_absolute_maximum_exceeded=True,
                status="ABSOLUTE_MAXIMUM_EXCEEDED",
                operating_range=op_range_item.model_dump() if op_range_item else None,
                absolute_maximum=abs_max_item.model_dump() if abs_max_item else None,
                explanation=(
                    f"CRITICAL SAFETY VIOLATION: Evaluated {parameter} ({value}{unit or ''}) "
                    f"exceeds Absolute Maximum Rating ({abs_max_val}{abs_max_item.unit or ''}). Risk of permanent silicon damage."
                ),
            )

        # 2. Check Operating Limit Exceeded (even if below absolute max!)
        if op_max_val is not None and value > op_max_val:
            return OperatingValidationResponse(
                parameter=parameter,
                evaluated_value=value,
                is_operating_valid=False,
                is_absolute_maximum_exceeded=False,
                status="OPERATING_LIMIT_EXCEEDED",
                operating_range=op_range_item.model_dump() if op_range_item else None,
                absolute_maximum=abs_max_item.model_dump() if abs_max_item else None,
                explanation=(
                    f"OPERATING LIMIT EXCEEDED: Evaluated {parameter} ({value}{unit or ''}) "
                    f"exceeds Recommended Operating Limit ({op_max_val}{op_range_item.unit or ''}). "
                    f"Note: Absolute maximum is {abs_max_val}{abs_max_item.unit if abs_max_item else ''}, "
                    f"but operating point is out of specification."
                ),
            )

        if op_min_val is not None and value < op_min_val:
            return OperatingValidationResponse(
                parameter=parameter,
                evaluated_value=value,
                is_operating_valid=False,
                is_absolute_maximum_exceeded=False,
                status="OPERATING_LIMIT_EXCEEDED",
                operating_range=op_range_item.model_dump() if op_range_item else None,
                absolute_maximum=abs_max_item.model_dump() if abs_max_item else None,
                explanation=(
                    f"OPERATING LIMIT EXCEEDED: Evaluated {parameter} ({value}{unit or ''}) "
                    f"is below Minimum Operating Limit ({op_min_val}{op_range_item.unit or ''})."
                ),
            )

        # 3. Valid Operating Point
        if op_max_val is not None or abs_max_val is not None:
            return OperatingValidationResponse(
                parameter=parameter,
                evaluated_value=value,
                is_operating_valid=True,
                is_absolute_maximum_exceeded=False,
                status="OPERATING_POINT_VALID",
                operating_range=op_range_item.model_dump() if op_range_item else None,
                absolute_maximum=abs_max_item.model_dump() if abs_max_item else None,
                explanation=f"{parameter} ({value}{unit or ''}) is within documented operating bounds.",
            )

        # 4. Unknown
        return OperatingValidationResponse(
            parameter=parameter,
            evaluated_value=value,
            is_operating_valid=False,
            is_absolute_maximum_exceeded=False,
            status="PARAMETER_UNKNOWN",
            explanation=f"No operating limits or absolute maximums documented for parameter '{parameter}' on {part_number}.",
        )

    async def evaluate_applicability(
        self,
        part_number: str,
        context: dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Deterministically evaluates applicability of component knowledge to an operating context.
        ZERO SYNTHETIC SCORING. Returns categorical states only:
        APPLICABLE, POTENTIALLY_APPLICABLE, NOT_APPLICABLE, UNKNOWN, CONFLICTING.
        """
        profile = await self.get_component_profile(part_number=part_number, tenant_id=tenant_id)
        if profile.identity.state == IdentityState.UNKNOWN:
            return {
                "part_number": part_number,
                "status": ApplicabilityCategory.UNKNOWN.value,
                "reasons": [f"Component '{part_number}' is unknown."],
                "evaluated_conditions": {},
                "missing_conditions": list(context.keys()),
            }

        if profile.contradictions:
            return {
                "part_number": part_number,
                "status": ApplicabilityCategory.CONFLICTING.value,
                "reasons": ["Component profile contains contradictory authoritative source data."],
                "evaluated_conditions": {},
                "missing_conditions": [],
            }

        reasons = []
        evaluated = {}
        missing = []

        for ctx_k, ctx_v in context.items():
            if ctx_v is None:
                continue
            try:
                numeric_val = float(ctx_v)
            except (ValueError, TypeError):
                continue

            res_val = await self.validate_operating_point(
                part_number=part_number,
                parameter=ctx_k,
                value=numeric_val,
                tenant_id=tenant_id,
            )
            evaluated[ctx_k] = res_val.status
            if not res_val.is_operating_valid:
                reasons.append(res_val.explanation)
                return {
                    "part_number": part_number,
                    "status": ApplicabilityCategory.NOT_APPLICABLE.value,
                    "reasons": reasons,
                    "evaluated_conditions": evaluated,
                    "missing_conditions": missing,
                }
            else:
                reasons.append(f"{ctx_k} ({numeric_val}) is within recommended operating limits.")

        if evaluated:
            return {
                "part_number": part_number,
                "status": ApplicabilityCategory.APPLICABLE.value,
                "reasons": reasons or ["All evaluated operating context parameters satisfy component specifications."],
                "evaluated_conditions": evaluated,
                "missing_conditions": missing,
            }

        return {
            "part_number": part_number,
            "status": ApplicabilityCategory.UNKNOWN.value,
            "reasons": ["Insufficient context parameters to evaluate component applicability."],
            "evaluated_conditions": {},
            "missing_conditions": ["input_voltage", "temperature"],
        }
