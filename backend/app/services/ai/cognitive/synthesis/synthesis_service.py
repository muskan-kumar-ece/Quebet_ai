from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.analysis import CircuitAnalysis
from app.models.db.assumption import Assumption
from app.models.db.circuit import Circuit
from app.models.db.cognitive import (
    ContextConflictCategory,
    ContextSnapshotStatus,
    EngineeringCognitiveContextSnapshot,
    EngineeringContextSnapshot,
    EngineeringDecisionBrief,
    EngineeringReflection,
    HistoricalOutcome,
    MemoryApplicability,
)
from app.models.db.component import Component
from app.models.db.connection import Connection
from app.models.db.decision import (
    EngineeringAssumption,
    EngineeringDecisionRecord,
    EngineeringRequirement,
)
from app.models.db.net import Net
from app.models.db.project import Project
from app.models.db.system import EngineeringSystem, EngineeringSystemRequirement
from app.models.db.verification import (
    EngineeringEvidence,
    EngineeringVerificationRequirement,
    EvidenceType,
    VerificationStatus,
)
from app.models.schemas.cognitive import (
    ContextSynthesisRequest,
    EngineeringContextConflict,
    MemoryRetrievalRequest,
)
from app.services.ai.cognitive.memory.retrieval_service import (
    EngineeringMemoryRetrievalService,
)
from app.services.ai.cognitive.reflection.contradiction_engine import (
    UnitNormalizer,
)
from app.services.ai.cognitive.synthesis.digest_service import ContextDigestService


class EngineeringContextSynthesisService:
    """
    Synthesizes a revision-bound, multi-tier engineering context snapshot.

    INVARIANTS:
    - STRUCTURED CONTEXT > AI EXPLANATION
    - CURRENT AUTHORITATIVE SOURCE > HISTORICAL MEMORY
    - CALCULATED != PHYSICALLY VERIFIED
    - HISTORICAL VERIFICATION != CURRENT VERIFICATION
    - UNKNOWN != SATISFIED
    - CONTEXT SNAPSHOT = REVISION-BOUND
    - ZERO SYNTHETIC SCORING
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def synthesize_context(
        self,
        tenant_id: str,
        request: ContextSynthesisRequest,
    ) -> EngineeringContextSnapshot:
        """
        Gathers authoritative records, deterministic analyses, requirements, assumptions,
        verification states, decision history, and historical memory into an immutable,
        canonical SHA-256 digest protected EngineeringContextSnapshot.
        """
        project_id = request.project_id
        circuit_id = request.circuit_id
        system_id = request.system_id

        # 1. Resolve project and current baseline revision
        p_query = select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
        p_res = await self.db.execute(p_query)
        project = p_res.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        base_revision = 1
        circuit: Optional[Circuit] = None
        system: Optional[EngineeringSystem] = None

        if circuit_id:
            c_query = select(Circuit).where(Circuit.id == circuit_id, Circuit.tenant_id == tenant_id)
            c_res = await self.db.execute(c_query)
            circuit = c_res.scalar_one_or_none()
            if circuit:
                base_revision = circuit.version
        elif system_id:
            s_query = select(EngineeringSystem).where(EngineeringSystem.id == system_id, EngineeringSystem.tenant_id == tenant_id)
            s_res = await self.db.execute(s_query)
            system = s_res.scalar_one_or_none()
            if system:
                base_revision = system.revision

        # 2. Collect current physical state (components, nets, connections)
        current_state: Dict[str, Any] = {
            "project_id": project_id,
            "project_name": project.name,
            "project_type": project.project_type,
            "base_revision": base_revision,
            "circuit_id": circuit_id,
            "system_id": system_id,
            "components": [],
            "nets": [],
            "connections": [],
        }

        components_list: List[Component] = []
        if circuit_id:
            comp_query = select(Component).where(Component.circuit_id == circuit_id)
            comp_res = await self.db.execute(comp_query)
            components_list = list(comp_res.scalars().all())
            current_state["components"] = [
                {
                    "id": c.id,
                    "name": c.ref_des,
                    "ref_des": c.ref_des,
                    "component_type": c.component_type,
                    "value": c.value,
                    "properties": c.metadata_ or {},
                }
                for c in components_list
            ]

            net_query = select(Net).where(Net.circuit_id == circuit_id)
            net_res = await self.db.execute(net_query)
            current_state["nets"] = [
                {"id": n.id, "name": n.name, "net_type": n.net_type}
                for n in net_res.scalars().all()
            ]

        # 3. Collect authoritative facts (datasheet values, physical constants, component properties)
        authoritative_facts: List[Dict[str, Any]] = []
        for c in components_list:
            props = dict(c.metadata_ or {})
            if c.value:
                props["value"] = c.value
            if c.rating:
                props["rating"] = c.rating
            for prop_key, prop_val in props.items():
                authoritative_facts.append({
                    "entity_type": "Component",
                    "entity_id": c.id,
                    "component_name": c.ref_des,
                    "ref_des": c.ref_des,
                    "property": prop_key,
                    "value": prop_val,
                    "origin": "AUTHORITATIVE_SPECIFICATION",
                })

        # 4. Collect deterministic results (CircuitAnalysis, calculations, margins)
        deterministic_results: List[Dict[str, Any]] = []
        findings: List[Dict[str, Any]] = []
        unknowns: List[Dict[str, Any]] = []

        if circuit_id:
            an_query = select(CircuitAnalysis).where(
                CircuitAnalysis.circuit_id == circuit_id,
                CircuitAnalysis.tenant_id == tenant_id,
            ).order_by(CircuitAnalysis.created_at.desc())
            an_res = await self.db.execute(an_query)
            analyses = list(an_res.scalars().all())

            for an in analyses:
                deterministic_results.append({
                    "analysis_id": an.id,
                    "analysis_type": "CIRCUIT_ANALYSIS",
                    "status": an.status,
                    "confidence": an.confidence,
                    "calculations": an.calculations or [],
                    "graph_summary": an.graph_summary or {},
                    "unknowns": an.unknowns or [],
                    "created_at": an.created_at.isoformat() if an.created_at else None,
                })
                if an.findings:
                    for f in an.findings:
                        findings.append({
                            "source_type": "CircuitAnalysis",
                            "source_id": an.id,
                            "finding": f,
                        })
                if an.unknowns:
                    for u in an.unknowns:
                        unknowns.append({
                            "source_type": "CircuitAnalysis",
                            "source_id": an.id,
                            "unknown": u,
                        })

        # 5. Collect assumptions
        assumptions: List[Dict[str, Any]] = []
        assump_query = select(Assumption).where(
            Assumption.circuit_id == circuit_id
        ) if circuit_id else None

        if assump_query is not None:
            assump_res = await self.db.execute(assump_query)
            for a in assump_res.scalars().all():
                assumptions.append({
                    "id": a.id,
                    "field": a.field,
                    "value": a.value,
                    "unit": a.unit,
                    "source": a.source,
                    "user_confirmed": a.user_confirmed,
                })

        # Also EngineeringAssumption (system-level)
        if system_id:
            eng_assump_query = select(EngineeringAssumption).where(
                EngineeringAssumption.system_id == system_id,
                EngineeringAssumption.tenant_id == tenant_id,
            )
            eng_assump_res = await self.db.execute(eng_assump_query)
            for ea in eng_assump_res.scalars().all():
                assumptions.append({
                    "id": ea.id,
                    "description": ea.description,
                    "value": ea.value,
                    "unit": ea.unit,
                    "basis": ea.basis,
                    "status": ea.status,
                    "impact": ea.impact,
                })


        # 6. Collect requirements & constraints (5 discrete states: SATISFIED, NOT_SATISFIED, UNKNOWN, NOT_EVALUATED, NOT_APPLICABLE)
        requirements: List[Dict[str, Any]] = []
        constraints: List[Dict[str, Any]] = []
        conflicts: List[Dict[str, Any]] = []

        req_query = select(EngineeringRequirement).where(
            EngineeringRequirement.project_id == project_id,
            EngineeringRequirement.tenant_id == tenant_id,
        )
        req_res = await self.db.execute(req_query)
        req_records = list(req_res.scalars().all())

        for req in req_records:
            # Check requirement condition against deterministic analysis
            req_state = "NOT_EVALUATED"
            req_expr = req.expression or {}
            target_prop = req_expr.get("property") or getattr(req, "target_property", None)
            max_val_str = req_expr.get("max_value") or getattr(req, "max_value", None)
            min_val_str = req_expr.get("min_value") or getattr(req, "min_value", None)

            matched_value = None
            if target_prop:
                p_norm = target_prop.lower().replace("-", "_").replace(" ", "_")
                # Look in calculations
                for an_res_item in deterministic_results:
                    for calc in an_res_item.get("calculations", []):
                        # Look in inputs
                        inp_dict = calc.get("inputs") or {}
                        for k, v in inp_dict.items():
                            k_norm = k.lower().replace("-", "_")
                            if p_norm == k_norm or p_norm in k_norm or k_norm in p_norm:
                                if v is not None and not isinstance(v, (dict, list)):
                                    unit = ""
                                    if k_norm.endswith("_v"): unit = "V"
                                    elif k_norm.endswith("_a"): unit = "A"
                                    elif k_norm.endswith("_ma"): unit = "mA"
                                    elif k_norm.endswith("_c"): unit = "C"
                                    elif k_norm.endswith("_w"): unit = "W"
                                    else: unit = calc.get("unit", "")
                                    matched_value = f"{v}{unit}"
                                    break
                        if matched_value:
                            break

                        # Look in result
                        res_dict = calc.get("result") or {}
                        for k, v in res_dict.items():
                            k_norm = k.lower().replace("-", "_")
                            if p_norm == k_norm or p_norm in k_norm or k_norm in p_norm:
                                if v is not None and not isinstance(v, (dict, list)):
                                    unit = ""
                                    if k_norm.endswith("_v"): unit = "V"
                                    elif k_norm.endswith("_a"): unit = "A"
                                    elif k_norm.endswith("_ma"): unit = "mA"
                                    elif k_norm.endswith("_c"): unit = "C"
                                    elif k_norm.endswith("_w"): unit = "W"
                                    else: unit = calc.get("unit", "")
                                    matched_value = f"{v}{unit}"
                                    break
                        if matched_value:
                            break
                    if matched_value:
                        break

                # Look in authoritative facts if not found
                if matched_value is None:
                    for fact in authoritative_facts:
                        f_prop = fact.get("property", "").lower().replace("-", "_")
                        if p_norm == f_prop or p_norm in f_prop or f_prop in p_norm:
                            val = fact.get("value")
                            if val is not None:
                                matched_value = str(val)
                                break

            if matched_value is None:
                req_state = "UNKNOWN"
                unknowns.append({
                    "category": "REQUIREMENT_PARAMETER_UNKNOWN",
                    "requirement_id": req.id,
                    "requirement_key": req.requirement_key,
                    "property": target_prop,
                    "description": f"Requirement '{req.title}' depends on parameter '{target_prop}' which has not been calculated or characterized.",
                })
            else:
                # Compare numerically
                parsed_act = UnitNormalizer.parse_value_unit(str(matched_value))
                if max_val_str and parsed_act:
                    parsed_max = UnitNormalizer.parse_value_unit(str(max_val_str))
                    if parsed_max and parsed_act[1] == parsed_max[1]:
                        if parsed_act[0] <= parsed_max[0]:
                            req_state = "SATISFIED"
                        else:
                            req_state = "NOT_SATISFIED"
                            # Record conflict between Requirement ceiling and Analysis result
                            conflicts.append({
                                "id": str(uuid.uuid4()),
                                "category": ContextConflictCategory.SPECIFICATION_CONFLICT.value,
                                "source_a_type": "EngineeringRequirement",
                                "source_a_id": req.id,
                                "source_b_type": "CircuitAnalysis",
                                "source_b_id": deterministic_results[0].get("analysis_id", "analysis") if deterministic_results else "analysis",
                                "description": f"Requirement '{req.requirement_key}' ceiling ({max_val_str}) violated by deterministic analysis value ({matched_value}).",
                                "requires_human_review": True,
                            })
                    else:
                        req_state = "NOT_EVALUATED"
                elif min_val_str and parsed_act:
                    parsed_min = UnitNormalizer.parse_value_unit(str(min_val_str))
                    if parsed_min and parsed_act[1] == parsed_min[1]:
                        if parsed_act[0] >= parsed_min[0]:
                            req_state = "SATISFIED"
                        else:
                            req_state = "NOT_SATISFIED"
                    else:
                        req_state = "NOT_EVALUATED"
                else:
                    req_state = "SATISFIED"

            requirements.append({
                "id": req.id,
                "requirement_key": req.requirement_key,
                "title": req.title,
                "category": req.category,
                "target_property": target_prop,
                "max_value": max_val_str,
                "min_value": min_val_str,
                "state": req_state,
            })

        # 7. Collect Evidence State (5 separate categories)
        evidence_state: Dict[str, List[Dict[str, Any]]] = {
            "PHYSICAL_EVIDENCE": [],
            "SIMULATION": [],
            "CALCULATION": [],
            "DATASHEET": [],
            "HISTORICAL_EVIDENCE": [],
        }

        evi_query = select(EngineeringEvidence).where(
            EngineeringEvidence.tenant_id == tenant_id,
        )
        evi_res = await self.db.execute(evi_query)
        evidence_records = list(evi_res.scalars().all())
        for ev in evidence_records:
            ev_dict = {
                "id": ev.id,
                "title": ev.description,
                "description": ev.description,
                "evidence_type": ev.evidence_type,
                "status": ev.status,
                "source_reference": ev.reference or ev.source,
            }
            if ev.evidence_type in evidence_state:
                evidence_state[ev.evidence_type].append(ev_dict)
            else:
                evidence_state["CALCULATION"].append(ev_dict)

        # 8. Collect Verification State (enforcing CALCULATED != PHYSICALLY VERIFIED)
        verification_state: Dict[str, Any] = {
            "requirements": [],
            "completed": [],
            "pending": [],
            "blocked": [],
        }

        verif_query = select(EngineeringVerificationRequirement).where(
            EngineeringVerificationRequirement.tenant_id == tenant_id,
        )
        verif_res = await self.db.execute(verif_query)
        for vr in verif_res.scalars().all():
            has_physical_evidence = any(
                getattr(ev, "requirement_id", None) == vr.id and ev.evidence_type in ["PHYSICAL_EVIDENCE", "LAB_TEST", "MEASUREMENT"]
                for ev in evidence_records
            )
            vr_status = vr.status
            if vr_status in [VerificationStatus.SATISFIED.value, "VERIFIED", VerificationStatus.IN_PROGRESS.value] and not has_physical_evidence:
                # If only calculation/simulation exists, verification status must be REQUIRED/PENDING
                vr_status = "PENDING"
            elif vr_status == VerificationStatus.NOT_STARTED.value:
                vr_status = "REQUIRED"

            vr_dict = {
                "id": vr.id,
                "title": vr.title,
                "code": vr.code,
                "verification_method": vr.method,
                "method": vr.method,
                "status": vr_status,
                "has_physical_evidence": has_physical_evidence,
            }
            verification_state["requirements"].append(vr_dict)
            if vr_status == "VERIFIED" and has_physical_evidence:
                verification_state["completed"].append(vr.id)
            else:
                verification_state["pending"].append(vr.id)

        # 9. Collect Decision History
        decision_history: List[Dict[str, Any]] = []
        dec_query = select(EngineeringDecisionRecord).where(
            EngineeringDecisionRecord.project_id == project_id,
            EngineeringDecisionRecord.tenant_id == tenant_id,
        ).order_by(EngineeringDecisionRecord.created_at.desc())
        dec_res = await self.db.execute(dec_query)
        for d in dec_res.scalars().all():
            decision_history.append({
                "id": d.id,
                "title": d.title,
                "decision_key": d.decision_key,
                "decision_type": d.decision_type,
                "status": d.status,
                "decided_by": d.decided_by,
                "rationale": d.rationale,
            })

        # 10. Collect Historical Memory from Wave 4
        historical_memory: List[Dict[str, Any]] = []
        if request.include_historical_memory:
            cur_params: Dict[str, Any] = {}
            for fact in authoritative_facts:
                if "property" in fact and "value" in fact:
                    cur_params[fact["property"]] = fact["value"]
            for comp in components_list:
                props = comp.metadata_ or {}
                for k, v in props.items():
                    cur_params[k] = v

            mem_service = EngineeringMemoryRetrievalService(self.db)
            ret_req = MemoryRetrievalRequest(
                project_id=project_id,
                system_id=system_id,
                circuit_id=circuit_id,
                engineering_domain=project.project_type,
                current_parameters=cur_params,
            )
            mem_res = await mem_service.retrieve_contextual_memories(tenant_id, ret_req)
            for m in mem_res.memories:
                mem_item = m.model_dump()
                historical_memory.append(mem_item)
                # Check for memory conflict
                if m.is_conflicting:
                    conflicts.append({
                        "id": str(uuid.uuid4()),
                        "category": ContextConflictCategory.MEMORY_CONFLICT.value,
                        "source_a_type": "AuthoritativeDatasheet",
                        "source_a_id": "current_specification",
                        "source_b_type": "EngineeringMemoryRecord",
                        "source_b_id": m.memory.id,
                        "description": f"Historical memory '{m.memory.summary}' conflicts with current authoritative source. Current source wins.",
                        "requires_human_review": True,
                    })

        # 11. Reflection State
        reflection_state: Dict[str, Any] = {
            "status": "NO_ADDITIONAL_WORK_REQUIRED",
            "findings": [],
        }
        ref_query = select(EngineeringReflection).where(
            EngineeringReflection.project_id == project_id,
            EngineeringReflection.tenant_id == tenant_id,
        ).order_by(EngineeringReflection.created_at.desc())
        ref_res = await self.db.execute(ref_query)
        latest_ref = ref_res.scalars().first()
        if latest_ref:
            reflection_state["status"] = latest_ref.status
            reflection_state["cycle"] = latest_ref.reflection_cycle
            reflection_state["has_contradictions"] = latest_ref.has_contradictions
            reflection_state["has_unresolved_unknowns"] = latest_ref.has_unresolved_unknowns
            reflection_state["has_evidence_gaps"] = latest_ref.has_evidence_gaps
            reflection_state["has_requirement_gaps"] = latest_ref.has_requirement_gaps
            reflection_state["has_verification_gaps"] = latest_ref.has_verification_gaps
            reflection_state["additional_work_required"] = latest_ref.additional_work_required

        # 12. Traceability State
        traceability_state: Dict[str, Any] = {
            "component_count": len(components_list),
            "requirement_count": len(requirements),
            "decision_count": len(decision_history),
            "evidence_count": sum(len(v) for v in evidence_state.values()),
            "conflict_count": len(conflicts),
        }

        # JSON-safe normalization to avoid non-serializable objects (e.g. datetime) in SQLite JSON columns
        current_state = json.loads(json.dumps(current_state, default=str))
        authoritative_facts = json.loads(json.dumps(authoritative_facts, default=str))
        deterministic_results = json.loads(json.dumps(deterministic_results, default=str))
        requirements = json.loads(json.dumps(requirements, default=str))
        constraints = json.loads(json.dumps(constraints, default=str))
        assumptions = json.loads(json.dumps(assumptions, default=str))
        findings = json.loads(json.dumps(findings, default=str))
        unknowns = json.loads(json.dumps(unknowns, default=str))
        evidence_state = json.loads(json.dumps(evidence_state, default=str))
        verification_state = json.loads(json.dumps(verification_state, default=str))
        decision_history = json.loads(json.dumps(decision_history, default=str))
        historical_memory = json.loads(json.dumps(historical_memory, default=str))
        traceability_state = json.loads(json.dumps(traceability_state, default=str))
        reflection_state = json.loads(json.dumps(reflection_state, default=str))
        conflicts = json.loads(json.dumps(conflicts, default=str))

        # 13. Assemble logical context and compute canonical digest
        logical_context: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "system_id": system_id,
            "circuit_id": circuit_id,
            "base_revision": base_revision,
            "current_state": current_state,
            "authoritative_facts": authoritative_facts,
            "deterministic_results": deterministic_results,
            "requirements": requirements,
            "constraints": constraints,
            "assumptions": assumptions,
            "findings": findings,
            "unknowns": unknowns,
            "evidence_state": evidence_state,
            "verification_state": verification_state,
            "decision_history": decision_history,
            "historical_memory": historical_memory,
            "traceability_state": traceability_state,
            "reflection_state": reflection_state,
            "conflicts": conflicts,
        }

        canonical_digest = ContextDigestService.calculate_canonical_digest(logical_context)

        # 14. Persist EngineeringContextSnapshot
        snapshot = EngineeringContextSnapshot(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            system_id=system_id,
            circuit_id=circuit_id,
            base_revision=base_revision,
            context_snapshot_id=None,
            status=ContextSnapshotStatus.CURRENT.value,
            canonical_digest=canonical_digest,
            current_state=current_state,
            authoritative_facts=authoritative_facts,
            deterministic_results=deterministic_results,
            requirements=requirements,
            constraints=constraints,
            assumptions=assumptions,
            findings=findings,
            unknowns=unknowns,
            evidence_state=evidence_state,
            verification_state=verification_state,
            decision_history=decision_history,
            historical_memory=historical_memory,
            traceability_state=traceability_state,
            reflection_state=reflection_state,
            conflicts=conflicts,
        )

        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        return snapshot

    async def get_context_snapshot(
        self,
        tenant_id: str,
        context_id: str,
    ) -> EngineeringContextSnapshot:
        """
        Retrieves an EngineeringContextSnapshot and dynamically evaluates freshness.
        If baseline revision has advanced, transitions status to STALE.
        """
        query = select(EngineeringContextSnapshot).where(
            EngineeringContextSnapshot.id == context_id,
            EngineeringContextSnapshot.tenant_id == tenant_id,
        )
        res = await self.db.execute(query)
        snapshot = res.scalar_one_or_none()
        if not snapshot:
            raise HTTPException(status_code=404, detail="Engineering context snapshot not found")

        # Dynamic Freshness Check: has circuit/system revision advanced?
        is_stale = False
        if snapshot.circuit_id:
            c_query = select(Circuit).where(Circuit.id == snapshot.circuit_id)
            c_res = await self.db.execute(c_query)
            circuit = c_res.scalar_one_or_none()
            if circuit and circuit.version > snapshot.base_revision:
                is_stale = True
        elif snapshot.system_id:
            s_query = select(EngineeringSystem).where(EngineeringSystem.id == snapshot.system_id)
            s_res = await self.db.execute(s_query)
            system = s_res.scalar_one_or_none()
            if system and system.revision > snapshot.base_revision:
                is_stale = True

        if is_stale and snapshot.status != ContextSnapshotStatus.STALE.value:
            snapshot.status = ContextSnapshotStatus.STALE.value
            await self.db.commit()
            await self.db.refresh(snapshot)

        return snapshot

    async def list_project_snapshots(
        self,
        tenant_id: str,
        project_id: str,
    ) -> List[EngineeringContextSnapshot]:
        """
        Lists all synthesized context snapshots for a project within tenant.
        """
        query = (
            select(EngineeringContextSnapshot)
            .where(
                EngineeringContextSnapshot.tenant_id == tenant_id,
                EngineeringContextSnapshot.project_id == project_id,
            )
            .order_by(EngineeringContextSnapshot.created_at.desc())
        )
        res = await self.db.execute(query)
        return list(res.scalars().all())
