import json
import re
from typing import Any, Dict, List, Optional
from app.models.db.cognitive import IntentType, IntentStatus
from app.models.schemas.cognitive import IntentPacketCreate


class IntentResolver:
    """
    Cognitive Intent Resolver for QUEBET AI.
    Transforms raw natural language engineering requests into structured IntentPackets.
    Strict JSON/Schema validation; does NOT hallucinate or silently invent missing engineering data.
    """

    @classmethod
    def resolve_intent(
        cls,
        raw_request: str,
        project_id: str,
        system_id: Optional[str] = None,
        circuit_id: Optional[str] = None,
        scope: str = "CIRCUIT",
        urgency: str = "NORMAL",
    ) -> IntentPacketCreate:
        req_lower = raw_request.lower()

        # 1. Classify Intent Type via controlled taxonomy
        intent_type = cls._classify_intent(req_lower, scope)
        goal = cls._extract_goal(raw_request, intent_type)

        # 2. Extract Entities (electrical parameters, component designators)
        entities = cls._extract_entities(req_lower)

        # 3. Extract Candidate Requirements & Constraints
        requirements = cls._extract_requirements(req_lower)
        constraints = cls._extract_constraints(req_lower)

        # 4. Extract Scenarios & Assumptions
        scenarios = cls._extract_scenarios(req_lower)
        assumptions = cls._extract_assumptions(req_lower)

        # 5. Identify Affected Objects
        affected_objects = cls._identify_affected_objects(req_lower, system_id, circuit_id)

        # 6. Detect Ambiguities & Missing Information
        ambiguities = cls._detect_ambiguities(req_lower)
        missing_info = cls._detect_missing_information(intent_type, entities, req_lower)

        # Context confidence (interpretation certainty, NOT engineering validity score)
        confidence = 0.95
        if ambiguities:
            confidence -= 0.3
        if missing_info:
            confidence -= 0.2
        confidence = max(0.2, min(1.0, confidence))

        return IntentPacketCreate(
            project_id=project_id,
            system_id=system_id,
            circuit_id=circuit_id,
            raw_request=raw_request,
            intent_type=intent_type.value,
            intent_subtype=cls._determine_subtype(intent_type, req_lower),
            goal=goal,
            requested_action=intent_type.value.lower(),
            entities=entities,
            requirements=requirements,
            constraints=constraints,
            assumptions=assumptions,
            scenarios=scenarios,
            affected_objects=affected_objects,
            urgency=urgency,
            scope=scope,
            context_confidence=confidence,
            ambiguities=ambiguities,
            missing_information=missing_info,
            source="USER_PROMPT",
        )

    @classmethod
    def _classify_intent(cls, text: str, default_scope: str) -> IntentType:
        # Review / Gating
        if any(w in text for w in ["review", "cdr", "pdr", "design review", "readiness"]):
            return IntentType.REVIEW_DESIGN
        # Verification / Testing
        if any(w in text for w in ["verification", "verify", "test point", "evidence", "plan verification"]):
            return IntentType.PLAN_VERIFICATION
        # Findings / Anomalies
        if any(w in text for w in ["finding", "rule violation", "investigate finding", "issue", "anomaly"]):
            return IntentType.INVESTIGATE_FINDING
        # Failure / Hazard
        if any(w in text for w in ["failure", "short circuit", "overvoltage", "fault", "propagation"]):
            return IntentType.INVESTIGATE_FAILURE
        # Compare
        if any(w in text for w in ["compare", "comparison", "tradeoff", "trade-off", "vs"]):
            return IntentType.COMPARE_ALTERNATIVES
        # Alternatives / Synthesis
        if any(w in text for w in ["alternative", "substitute", "explore", "replace", "what-if", "what if"]):
            return IntentType.EXPLORE_SYSTEM_ALTERNATIVES if "system" in text or default_scope == "SYSTEM" else IntentType.EXPLORE_DESIGN_ALTERNATIVES
        # Requirements / Constraints
        if any(w in text for w in ["requirement", "specification", "coverage"]):
            return IntentType.CHECK_REQUIREMENTS
        if any(w in text for w in ["constraint", "limit", "margin"]):
            return IntentType.CHECK_CONSTRAINTS
        # Traceability
        if any(w in text for w in ["trace", "provenance", "origin", "where did", "source"]):
            return IntentType.TRACE_ENGINEERING_FACT
        # Explanation
        if any(w in text for w in ["explain", "why", "interpret", "clarify"]):
            return IntentType.EXPLAIN_ENGINEERING_RESULT
        # System Analysis
        if any(w in text for w in ["system", "subsystem", "architecture", "power domain", "bus", "interface"]) or default_scope == "SYSTEM":
            return IntentType.ANALYZE_SYSTEM
        # Circuit Analysis
        if any(w in text for w in ["analyze", "analysis", "circuit", "schematic", "power", "thermal", "voltage", "current", "resistor"]):
            return IntentType.ANALYZE_CIRCUIT

        return IntentType.UNKNOWN

    @classmethod
    def _determine_subtype(cls, intent_type: IntentType, text: str) -> Optional[str]:
        if "thermal" in text:
            return "THERMAL"
        if "electrical" in text:
            return "ELECTRICAL"
        if "power" in text:
            return "POWER"
        if "interface" in text:
            return "INTERFACE"
        return None

    @classmethod
    def _extract_goal(cls, raw: str, intent_type: IntentType) -> str:
        clean = raw.strip()
        if len(clean) > 0:
            return clean
        return f"Perform {intent_type.value.lower().replace('_', ' ')}"

    @classmethod
    def _extract_entities(cls, text: str) -> List[Dict[str, Any]]:
        entities = []

        # Voltages
        volt_matches = re.finditer(r"(\d+(?:\.\d+)?)\s*(v|mv|kv)\b", text)
        for m in volt_matches:
            entities.append({
                "type": "VOLTAGE",
                "value": float(m.group(1)),
                "unit": m.group(2).upper(),
                "raw": m.group(0),
            })

        # Currents
        curr_matches = re.finditer(r"(\d+(?:\.\d+)?)\s*(a|ma|ua)\b", text)
        for m in curr_matches:
            entities.append({
                "type": "CURRENT",
                "value": float(m.group(1)),
                "unit": m.group(2).upper(),
                "raw": m.group(0),
            })

        # Temperatures
        temp_matches = re.finditer(r"(\d+(?:\.\d+)?)\s*(?:°\s*)?(c|degc)\b", text)
        for m in temp_matches:
            entities.append({
                "type": "TEMPERATURE",
                "value": float(m.group(1)),
                "unit": "C",
                "raw": m.group(0),
            })

        # Component References (R1, C2, U3, L4, Q1, D2)
        ref_matches = re.finditer(r"\b([rcluqd]\d+)\b", text)
        for m in ref_matches:
            entities.append({
                "type": "COMPONENT_REF",
                "ref_des": m.group(1).upper(),
                "raw": m.group(0),
            })

        return entities

    @classmethod
    def _extract_requirements(cls, text: str) -> List[Dict[str, Any]]:
        reqs = []
        if "must provide" in text or "shall provide" in text:
            m = re.search(r"(?:must|shall) provide (\d+(?:\.\d+)?\s*[vV])", text)
            if m:
                reqs.append({
                    "category": "ELECTRICAL",
                    "priority": "SHALL",
                    "statement": f"Output voltage shall be {m.group(1).upper()}",
                })
        return reqs

    @classmethod
    def _extract_constraints(cls, text: str) -> List[Dict[str, Any]]:
        constraints = []
        # Max temperature constraint
        temp_m = re.search(r"(?:below|less than|<|under)\s*(\d+(?:\.\d+)?)\s*(?:°\s*)?c", text)
        if temp_m:
            constraints.append({
                "parameter": "temperature",
                "operator": "<=",
                "threshold": float(temp_m.group(1)),
                "unit": "C",
            })
        return constraints

    @classmethod
    def _extract_scenarios(cls, text: str) -> List[Dict[str, Any]]:
        scenarios = []
        if "startup" in text:
            scenarios.append({"name": "startup", "condition": "system_startup"})
        if "full load" in text or "max load" in text:
            scenarios.append({"name": "full_load", "condition": "maximum_current"})
        return scenarios

    @classmethod
    def _extract_assumptions(cls, text: str) -> List[Dict[str, Any]]:
        assumptions = []
        if "ambient" in text or "assuming" in text:
            assumptions.append({
                "description": "Ambient operating temperature",
                "value": "25C",
                "basis": "Standard commercial lab environment",
            })
        return assumptions

    @classmethod
    def _identify_affected_objects(
        cls,
        text: str,
        system_id: Optional[str],
        circuit_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        objs = []
        if system_id:
            objs.append({"object_type": "system", "id": system_id})
        if circuit_id:
            objs.append({"object_type": "circuit", "id": circuit_id})

        # Components
        for m in re.finditer(r"\b([rcluqd]\d+)\b", text):
            objs.append({"object_type": "component", "ref_des": m.group(1).upper()})

        return objs

    @classmethod
    def _detect_ambiguities(cls, text: str) -> List[Dict[str, Any]]:
        ambiguities = []
        # Check generic mention of "the regulator" without specific ref_des
        if "the regulator" in text and not re.search(r"\bu\d+\b", text):
            ambiguities.append({
                "type": "MULTIPLE_MATCHES",
                "target": "regulator",
                "status": "CLARIFICATION_REQUIRED",
                "reason": "Request references 'the regulator' but does not specify component designator (e.g. U1, U2).",
                "action_required": "CLARIFICATION_REQUIRED",
            })
        return ambiguities

    @classmethod
    def _detect_missing_information(
        cls,
        intent: IntentType,
        entities: List[Dict[str, Any]],
        text: str,
    ) -> List[Dict[str, Any]]:
        missing = []
        if intent in [IntentType.ANALYZE_CIRCUIT, IntentType.EXPLORE_DESIGN_ALTERNATIVES]:
            has_voltage = any(e.get("type") == "VOLTAGE" for e in entities)
            has_current = any(e.get("type") == "CURRENT" for e in entities)

            if "regulator" in text or "converter" in text:
                if not has_voltage:
                    missing.append({
                        "parameter": "input_voltage",
                        "code": "INPUT_VOLTAGE_UNKNOWN",
                        "impact": "Required to calculate thermal dissipation and voltage breakdown margin.",
                    })
                if not has_current:
                    missing.append({
                        "parameter": "load_current",
                        "code": "LOAD_CURRENT_UNKNOWN",
                        "impact": "Required to evaluate current limits and thermal envelope.",
                    })

        return missing
