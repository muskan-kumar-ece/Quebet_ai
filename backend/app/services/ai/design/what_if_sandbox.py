import copy
import uuid
from typing import Any
from app.models.schemas.design import (
    CandidateProvenance,
    ConstraintResult,
    ConstraintStatus,
    EngineeringConstraint,
    EngineeringDesignAlternative,
    ProposedChange,
)
from app.services.ai.analysis.circuit_analysis_service import CircuitAnalysisService
from app.services.ai.design.constraint_engine import ConstraintEvaluationEngine


class SandboxedWhatIfSimulator:
    """
    Non-persistent in-memory circuit design simulation layer.
    Allows testing proposed candidate design modifications without mutating the user's real circuit.
    Runs deterministic analysis and constraint evaluations in < 500ms.
    Guarantees: Zero database mutations, zero schema changes, zero side-effects.
    """

    def __init__(self, analysis_service: CircuitAnalysisService | None = None):
        self.analysis_service = analysis_service or CircuitAnalysisService()
        self.constraint_engine = ConstraintEvaluationEngine()

    def simulate_candidate(
        self,
        base_circuit_dict: dict[str, Any],
        before_analysis: dict[str, Any],
        objective_id: str,
        title: str,
        description: str,
        proposed_changes: list[ProposedChange],
        constraints: list[EngineeringConstraint] | list[dict[str, Any]],
        provenance: list[str] | None = None,
        candidate_provenance_meta: dict[str, Any] | None = None,
        tradeoffs: list[str] | None = None,
        strategy: str = "GENERIC_MODIFICATION",
    ) -> EngineeringDesignAlternative:
        # 1. Deep clone in-memory circuit representation (NO DB MUTATION)
        sim_circuit = copy.deepcopy(base_circuit_dict)
        sim_components = sim_circuit.get("components", [])
        sim_nets = sim_circuit.get("nets", [])
        sim_connections = sim_circuit.get("connections", [])

        comp_by_id = {c["id"]: c for c in sim_components}
        comp_by_name = {c.get("name", "").upper(): c for c in sim_components}
        net_by_id = {n["id"]: n for n in sim_nets}
        net_by_name = {n.get("name", "").upper(): n for n in sim_nets}

        affected_components = set()
        affected_nets = set()
        engineering_effects_list = []

        # 2. Apply proposed changes in memory
        for change in proposed_changes:
            op = change.operation.upper()

            if op == "UPDATE_COMPONENT_VALUE":
                target = None
                if change.component_id and change.component_id in comp_by_id:
                    target = comp_by_id[change.component_id]
                elif change.ref_des and change.ref_des.upper() in comp_by_name:
                    target = comp_by_name[change.ref_des.upper()]

                if target:
                    old_v = target.get("value")
                    new_v = str(change.new_value)
                    target["value"] = new_v
                    affected_components.add(target.get("id"))
                    engineering_effects_list.append(f"Changed {target.get('name', 'component')} value from {old_v} to {new_v}.")

            elif op in ["UPDATE_COMPONENT_RATING", "UPDATE_COMPONENT_PARAMETER"]:
                target = None
                if change.component_id and change.component_id in comp_by_id:
                    target = comp_by_id[change.component_id]
                elif change.ref_des and change.ref_des.upper() in comp_by_name:
                    target = comp_by_name[change.ref_des.upper()]

                if target:
                    props = target.get("properties") or {}
                    field = change.field or "rating"
                    props[field] = str(change.new_value)
                    target["properties"] = props
                    if change.field in ["package", "footprint"]:
                        target["footprint"] = str(change.new_value)
                        target["package"] = str(change.new_value)
                    affected_components.add(target.get("id"))
                    engineering_effects_list.append(f"Updated {target.get('name')} {field} to {change.new_value}.")

            elif op == "REPLACE_COMPONENT":
                target = None
                if change.component_id and change.component_id in comp_by_id:
                    target = comp_by_id[change.component_id]
                elif change.ref_des and change.ref_des.upper() in comp_by_name:
                    target = comp_by_name[change.ref_des.upper()]

                if target:
                    old_name = target.get("name")
                    new_val = str(change.new_value or target.get("value"))
                    target["value"] = new_val
                    target["part_number"] = new_val
                    payload = change.payload or {}
                    if payload.get("package"):
                        target["footprint"] = payload.get("package")
                        target["package"] = payload.get("package")
                    if payload.get("properties"):
                        target["properties"] = payload.get("properties")
                    affected_components.add(target.get("id"))
                    engineering_effects_list.append(f"Replaced {old_name} with {new_val}.")

            elif op == "ADD_COMPONENT":
                payload = change.payload or {}
                new_id = change.component_id or f"sim-comp-{uuid.uuid4().hex[:8]}"
                ref_des = change.ref_des or payload.get("ref_des") or f"U_NEW_{len(sim_components)+1}"
                comp_type = change.component_type or payload.get("component_type", "generic")
                value = str(change.new_value or payload.get("value", ""))
                package = payload.get("package") or payload.get("footprint", "0805")

                new_comp = {
                    "id": new_id,
                    "circuit_id": sim_circuit.get("id", "sim-circ"),
                    "name": ref_des,
                    "ref_des": ref_des,
                    "component_type": comp_type,
                    "value": value,
                    "footprint": package,
                    "package": package,
                    "properties": payload.get("properties", {}),
                    "pins": payload.get("pins", [
                        {"id": f"p1-{new_id}", "name": "1", "number": "1"},
                        {"id": f"p2-{new_id}", "name": "2", "number": "2"},
                    ]),
                }
                sim_components.append(new_comp)
                comp_by_id[new_id] = new_comp
                comp_by_name[ref_des.upper()] = new_comp
                affected_components.add(new_id)
                engineering_effects_list.append(f"Added component {ref_des} ({value} {package}).")

            elif op == "REMOVE_COMPONENT":
                target_id = change.component_id
                if not target_id and change.ref_des and change.ref_des.upper() in comp_by_name:
                    target_id = comp_by_name[change.ref_des.upper()].get("id")

                if target_id and target_id in comp_by_id:
                    comp_name = comp_by_id[target_id].get("name")
                    sim_components[:] = [c for c in sim_components if c.get("id") != target_id]
                    sim_connections[:] = [conn for conn in sim_connections if conn.get("component_id") != target_id]
                    affected_components.add(target_id)
                    engineering_effects_list.append(f"Removed component {comp_name}.")

            elif op == "ADD_NET":
                net_name = change.net_name or (change.payload or {}).get("name")
                if net_name and net_name.upper() not in net_by_name:
                    n_id = f"sim-net-{uuid.uuid4().hex[:8]}"
                    new_net = {"id": n_id, "name": net_name}
                    sim_nets.append(new_net)
                    net_by_id[n_id] = new_net
                    net_by_name[net_name.upper()] = new_net
                    affected_nets.add(n_id)

            elif op == "ADD_CONNECTION":
                payload = change.payload or {}
                c_id = change.component_id or payload.get("component_id")
                if not c_id and change.ref_des and change.ref_des.upper() in comp_by_name:
                    c_id = comp_by_name[change.ref_des.upper()]["id"]

                n_name = change.net_name or payload.get("net_name")
                n_id = payload.get("net_id")
                if not n_id and n_name and n_name.upper() in net_by_name:
                    n_id = net_by_name[n_name.upper()]["id"]

                pin_num = change.pin_number or payload.get("pin_number", "1")
                if c_id and n_id:
                    sim_connections.append({
                        "id": f"sim-conn-{uuid.uuid4().hex[:8]}",
                        "component_id": c_id,
                        "net_id": n_id,
                        "pin_number": str(pin_num),
                    })
                    affected_components.add(c_id)
                    affected_nets.add(n_id)

        # 3. Deterministic Re-analysis in Sandbox
        after_analysis = self.analysis_service.analyze_circuit(sim_circuit)

        # 4. Evaluate Constraints
        constraint_results = self.constraint_engine.evaluate_constraints(
            constraints=constraints,
            circuit_dict=sim_circuit,
            analysis_data=after_analysis,
        )

        # 5. Finding Deltas (Resolved vs Introduced vs Remaining)
        before_findings = {f.get("rule_id"): f for f in before_analysis.get("findings", [])}
        after_findings = {f.get("rule_id"): f for f in after_analysis.get("findings", [])}

        findings_resolved = [f"{rid}: {before_findings[rid].get('title')}" for rid in before_findings if rid not in after_findings]
        findings_introduced = [f"{rid}: {after_findings[rid].get('title')}" for rid in after_findings if rid not in before_findings]
        remaining_findings = [f"{rid}: {after_findings[rid].get('title')}" for rid in after_findings if rid in before_findings]

        # 6. Constraint Status Summaries (Hard: PASS/FAIL/UNKNOWN; Soft: SATISFIED/NOT_SATISFIED/UNKNOWN)
        hard_results = [cr for cr in constraint_results if cr.hard_or_soft == "HARD"]
        soft_results = [cr for cr in constraint_results if cr.hard_or_soft == "SOFT"]

        if any(cr.status == ConstraintStatus.FAIL.value for cr in hard_results):
            hard_constraints_status = ConstraintStatus.FAIL.value
        elif any(cr.status == ConstraintStatus.UNKNOWN.value for cr in hard_results):
            hard_constraints_status = ConstraintStatus.UNKNOWN.value
        else:
            hard_constraints_status = ConstraintStatus.PASS.value

        soft_sat = sum(1 for cr in soft_results if cr.status == ConstraintStatus.SATISFIED.value)
        soft_not_sat = sum(1 for cr in soft_results if cr.status == ConstraintStatus.NOT_SATISFIED.value)
        soft_unk = sum(1 for cr in soft_results if cr.status == ConstraintStatus.UNKNOWN.value)
        soft_constraints_summary = {
            "satisfied": soft_sat,
            "not_satisfied": soft_not_sat,
            "unknown": soft_unk,
            "total": len(soft_results),
        }

        # 7. Quantitative Electrical and Structural Effects
        base_calcs = before_analysis.get("calculations", [])
        after_calcs = after_analysis.get("calculations", [])

        base_power = sum(
            c.get("result", {}).get("power_w", 0.0) or c.get("result", {}).get("power_dissipated_w", 0.0)
            for c in base_calcs
            if c.get("category") in ["OHMS_LAW", "REGULATOR", "POWER_DISSIPATION"]
        )
        after_power = sum(
            c.get("result", {}).get("power_w", 0.0) or c.get("result", {}).get("power_dissipated_w", 0.0)
            for c in after_calcs
            if c.get("category") in ["OHMS_LAW", "REGULATOR", "POWER_DISSIPATION"]
        )

        base_util = 0.0
        for c in base_calcs:
            if c.get("category") == "MARGIN":
                u = c.get("result", {}).get("utilization_pct", 0.0)
                if u > base_util:
                    base_util = u

        after_util = 0.0
        for c in after_calcs:
            if c.get("category") == "MARGIN":
                u = c.get("result", {}).get("utilization_pct", 0.0)
                if u > after_util:
                    after_util = u

        electrical_effects = {
            "base_power_w": round(base_power, 4) if base_power else None,
            "simulated_power_w": round(after_power, 4) if after_power else None,
            "power_delta_w": round(after_power - base_power, 4) if (base_power or after_power) else None,
            "worst_utilization_pct": round(after_util, 1),
            "worst_margin_pct": round(100.0 - after_util, 1) if after_util else None,
        }

        base_comps_count = len(base_circuit_dict.get("components", []))
        base_conns_count = len(base_circuit_dict.get("connections", []))
        structural_effects = {
            "component_count_delta": len(sim_components) - base_comps_count,
            "connection_count_delta": len(sim_connections) - base_conns_count,
            "affected_components": list(affected_components),
            "affected_nets": list(affected_nets),
        }

        # 8. Status & Confidence Determination (Confidence is strictly evidence quality, NEVER design ranking)
        has_critical = any(f.get("severity") == "CRITICAL" for f in after_analysis.get("findings", []))
        unknowns = after_analysis.get("unknowns", [])

        status = "VALIDATED"
        confidence = "HIGH"

        if has_critical or hard_constraints_status in [ConstraintStatus.FAIL.value, ConstraintStatus.UNKNOWN.value]:
            status = "BLOCKED"
            confidence = "LOW"
        elif unknowns:
            status = "PARTIAL"
            confidence = "MEDIUM" if len(unknowns) <= 2 else "LOW"

        # 9. Build Complete Candidate Provenance Chain
        alt_id = f"alt-{uuid.uuid4().hex[:8]}"
        meta = candidate_provenance_meta or {}
        candidate_provenance = CandidateProvenance(
            candidate_id=alt_id,
            trigger=meta.get("trigger", "RULE_ANALYSIS_FINDING"),
            generation_strategy=meta.get("strategy", strategy),
            source_finding=meta.get("source_finding"),
            affected_component=meta.get("affected_component"),
            affected_net=meta.get("affected_net"),
            old_value=meta.get("old_value"),
            new_value=meta.get("new_value"),
            old_component=meta.get("old_component"),
            new_component=meta.get("new_component"),
            rationale=description,
            knowledge_sources=provenance or ["CIRCUIT_PHYSICS_ENGINE", "ELECTRONICS_KB"],
            engineering_assumptions=after_analysis.get("assumptions", []),
            validation_analysis_id=after_analysis.get("id"),
            constraint_results=[cr.model_dump() for cr in constraint_results],
            finding_delta={
                "resolved": findings_resolved,
                "introduced": findings_introduced,
                "remaining": remaining_findings,
            },
            engineering_effects=electrical_effects,
            unknowns=unknowns,
            confidence=confidence,
        )

        return EngineeringDesignAlternative(
            alternative_id=alt_id,
            objective_id=objective_id,
            title=title,
            description=description,
            proposed_changes=proposed_changes,
            affected_components=list(affected_components),
            affected_nets=list(affected_nets),
            before_analysis_id=before_analysis.get("id"),
            after_analysis_id=None,
            after_analysis=after_analysis,
            engineering_effects=engineering_effects_list,
            findings_resolved=findings_resolved,
            findings_introduced=findings_introduced,
            remaining_findings=remaining_findings,
            hard_constraints_status=hard_constraints_status,
            soft_constraints_summary=soft_constraints_summary,
            constraint_results=constraint_results,
            electrical_effects=electrical_effects,
            structural_effects=structural_effects,
            cost="UNKNOWN",
            footprint="UNKNOWN",
            unknowns=unknowns,
            tradeoffs=tradeoffs or [],
            status=status,
            provenance=provenance or ["DETERMINISTIC_SANDBOX"],
            candidate_provenance=candidate_provenance.model_dump(),
            confidence=confidence,
        )
