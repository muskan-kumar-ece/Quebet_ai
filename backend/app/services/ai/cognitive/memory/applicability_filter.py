from typing import Any, Dict, List, Optional, Tuple
from app.models.db.cognitive import (
    EngineeringMemoryRecord,
    HistoricalOutcome,
    MemoryApplicability,
)


class EngineeringApplicabilityFilter:
    """
    Deterministic applicability classifier and conflict detector for historical memory.
    
    INVARIANTS:
    - HISTORICAL MEMORY != ENGINEERING TRUTH
    - CURRENT AUTHORITATIVE SOURCE > HISTORICAL MEMORY
    - HISTORICAL VERIFICATION != CURRENT VERIFICATION
    - ZERO SYNTHETIC SCORING
    """

    MANDATORY_WARNING = "Historical context — not current engineering verification."

    @classmethod
    def evaluate(
        cls,
        memory: EngineeringMemoryRecord,
        current_context: Dict[str, Any],
        has_negative_feedback: bool = False,
    ) -> Tuple[MemoryApplicability, str, str, bool, Dict[str, Any], List[str]]:
        """
        Deterministically evaluates applicability of a historical memory to the current context.

        Returns:
            Tuple of:
            - applicability (MemoryApplicability)
            - why_surfaced (str)
            - current_relevance (str)
            - is_conflicting (bool)
            - conflict_details (Dict)
            - warnings (List[str])
        """
        warnings = [cls.MANDATORY_WARNING]
        is_conflicting = False
        conflict_details: Dict[str, Any] = {}

        # 1. Human feedback override: if an engineer explicitly marked this memory NOT_APPLICABLE
        if has_negative_feedback:
            applicability = MemoryApplicability.NOT_APPLICABLE
            why_surfaced = "Surfaced from historical records; marked NOT_APPLICABLE by human engineer feedback."
            current_relevance = "Excluded from current guidance per recorded human engineer evaluation."
            return applicability, why_surfaced, current_relevance, is_conflicting, conflict_details, warnings

        # Extract current context dimensions
        cur_domain = current_context.get("engineering_domain")
        cur_comp_fam = current_context.get("component_family")
        cur_volt_dom = current_context.get("voltage_domain")
        cur_circuit_type = current_context.get("circuit_type")
        cur_params = current_context.get("current_parameters") or {}

        # Extract memory conditions
        mem_conds = memory.applicability_conditions or {}
        mem_domain = memory.engineering_domain or mem_conds.get("engineering_domain")
        mem_comp_fam = mem_conds.get("component_family")
        mem_volt_dom = mem_conds.get("voltage_domain")
        mem_circuit_type = mem_conds.get("circuit_type")

        # 2. Domain matching
        domain_mismatch = False
        if cur_domain and mem_domain:
            if cur_domain.lower() != "general" and mem_domain.lower() != "general":
                if cur_domain.lower() != mem_domain.lower():
                    domain_mismatch = True

        if domain_mismatch:
            applicability = MemoryApplicability.NOT_APPLICABLE
            why_surfaced = f"Domain mismatch: historical domain is '{mem_domain}' while current domain is '{cur_domain}'."
            current_relevance = "Not relevant to current operational or physical domain."
            return applicability, why_surfaced, current_relevance, is_conflicting, conflict_details, warnings

        # 3. Component family and operating domain evaluation
        comp_match = False
        if cur_comp_fam and mem_comp_fam:
            if cur_comp_fam.lower() in mem_comp_fam.lower() or mem_comp_fam.lower() in cur_comp_fam.lower():
                comp_match = True

        volt_match = False
        if cur_volt_dom and mem_volt_dom:
            if str(cur_volt_dom).lower() == str(mem_volt_dom).lower():
                volt_match = True

        circuit_match = False
        if cur_circuit_type and mem_circuit_type:
            if str(cur_circuit_type).lower() == str(mem_circuit_type).lower():
                circuit_match = True

        # 4. Conflict detection against current authoritative parameters
        # CURRENT AUTHORITATIVE SOURCE > HISTORICAL MEMORY
        mem_spec = mem_conds.get("component_specifications") or {}
        if cur_params and mem_spec:
            for param_key, cur_val in cur_params.items():
                if param_key in mem_spec:
                    mem_val = mem_spec[param_key]
                    if str(cur_val).strip() != str(mem_val).strip():
                        is_conflicting = True
                        conflict_details = {
                            "parameter": param_key,
                            "current_authoritative_value": cur_val,
                            "historical_memory_value": mem_val,
                            "authoritative_rule": "CURRENT AUTHORITATIVE SOURCE > HISTORICAL MEMORY",
                            "resolution": "Current authoritative specification overrides historical record without silent merge.",
                        }
                        warnings.append(
                            f"CONFLICT DETECTED on '{param_key}': Current authoritative value ({cur_val}) overrides historical record ({mem_val})."
                        )

        # 5. Verification non-satisfaction invariant
        # HISTORICAL VERIFICATION != CURRENT VERIFICATION
        if memory.historical_outcome == HistoricalOutcome.VERIFIED_SUCCESS.value:
            warnings.append(
                "Historical verification cannot close current verification obligations. Physical/lab verification remains REQUIRED for current design revision."
            )

        # 6. Categorical applicability determination
        if comp_match and (volt_match or circuit_match or (cur_domain and cur_domain.lower() == str(mem_domain).lower())):
            applicability = MemoryApplicability.APPLICABLE
            why_surfaced = f"Matching component family ({mem_comp_fam}) and matching operational domain ({cur_domain or mem_volt_dom})."
            current_relevance = f"Directly informs design parameters and historical trade-offs for {mem_comp_fam}."
        elif comp_match or volt_match or circuit_match:
            applicability = MemoryApplicability.POTENTIALLY_APPLICABLE
            surfaced_parts = []
            if comp_match:
                surfaced_parts.append(f"component family '{mem_comp_fam}'")
            if volt_match:
                surfaced_parts.append(f"voltage domain '{mem_volt_dom}'")
            if circuit_match:
                surfaced_parts.append(f"circuit type '{mem_circuit_type}'")
            why_surfaced = f"Partial context match on {', '.join(surfaced_parts)}."
            current_relevance = "Potentially relevant background experience; verify boundary conditions before relying on historical data."
        elif cur_domain and mem_domain and cur_domain.lower() == mem_domain.lower():
            applicability = MemoryApplicability.POTENTIALLY_APPLICABLE
            why_surfaced = f"Matching engineering domain '{mem_domain}'."
            current_relevance = "Provides historical domain context and prior design lessons."
        elif not mem_conds:
            applicability = MemoryApplicability.UNKNOWN
            why_surfaced = "Historical memory contains uncharacterized applicability conditions."
            current_relevance = "Applicability cannot be determined deterministically from available parameters."
        else:
            applicability = MemoryApplicability.POTENTIALLY_APPLICABLE
            why_surfaced = f"Surfaced from historical {memory.memory_type} records in domain '{mem_domain}'."
            current_relevance = "General engineering reference."

        return applicability, why_surfaced, current_relevance, is_conflicting, conflict_details, warnings
