from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional, Set
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.circuit import Circuit
from app.models.db.system import EngineeringSystem
from app.models.db.cognitive import (
    EngineeringCognitiveWorkflow,
    EngineeringContextSnapshot,
    EngineeringDecisionBrief,
    EngineeringReflection,
    CognitiveWorkflowStatus,
    ContextSnapshotStatus,
)
from app.models.schemas.cognitive import (
    EngineeringExplanationRequest,
    EngineeringExplanationResponse,
    EvidenceChainNode,
    HumanActionItem,
    ExplanationCategory,
)


class EngineeringCognitiveExplanationService:
    """
    Phase 2 Wave 7: Engineering Cognitive Interaction & Explainability Service.
    Produces grounded, traceable, revision-bound, evidence-aware explanations
    from authoritative Phase 1 & Phase 2 engineering state.

    INVARIANTS:
    - STRUCTURED CONTEXT > AI EXPLANATION
    - CURRENT AUTHORITATIVE SOURCE > HISTORICAL MEMORY
    - CALCULATED != PHYSICALLY VERIFIED
    - UNKNOWN != SATISFIED
    - CONTEXT / WORKFLOW = REVISION-BOUND
    - ZERO SYNTHETIC SCORING (No composite score, best, winner, recommended, confidence %)
    - MODEL_INVALID_REFERENCE: Reject hallucinated or invented entity references
    - AI ENGINEERING AUTHORITY = NONE (Explanations are informational / advisory)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def explain_workflow(
        self,
        workflow_id: str,
        tenant_id: str,
        request: EngineeringExplanationRequest,
    ) -> EngineeringExplanationResponse:
        """
        Synthesizes a grounded explanation for an EngineeringCognitiveWorkflow.
        """
        wf_query = select(EngineeringCognitiveWorkflow).where(
            EngineeringCognitiveWorkflow.id == workflow_id,
            EngineeringCognitiveWorkflow.tenant_id == tenant_id,
        )
        wf_res = await self.db.execute(wf_query)
        workflow = wf_res.scalar_one_or_none()
        if not workflow:
            raise HTTPException(status_code=404, detail="Engineering cognitive workflow not found")

        # Dynamic Freshness Check on Workflow
        is_stale, stale_factors, current_rev = await self._check_revision_staleness(
            circuit_id=workflow.circuit_id,
            system_id=workflow.system_id,
            base_revision=workflow.base_revision,
            tenant_id=tenant_id,
        )
        if is_stale and workflow.status != CognitiveWorkflowStatus.STALE.value:
            workflow.status = CognitiveWorkflowStatus.STALE.value
            workflow.current_step = "STALE_REVISION"
            if stale_factors:
                workflow.blocking_reasons.extend(stale_factors)
            await self.db.commit()
            await self.db.refresh(workflow)

        # Load linked Context Snapshot
        snapshot: Optional[EngineeringContextSnapshot] = None
        target_context_id = workflow.synthesized_context_id or workflow.context_snapshot_id
        if target_context_id:
            snap_query = select(EngineeringContextSnapshot).where(
                EngineeringContextSnapshot.id == target_context_id,
                EngineeringContextSnapshot.tenant_id == tenant_id,
            )
            snap_res = await self.db.execute(snap_query)
            snapshot = snap_res.scalar_one_or_none()

        # Load linked Decision Brief
        brief: Optional[EngineeringDecisionBrief] = None
        if workflow.decision_brief_id:
            b_query = select(EngineeringDecisionBrief).where(
                EngineeringDecisionBrief.id == workflow.decision_brief_id,
                EngineeringDecisionBrief.tenant_id == tenant_id,
            )
            b_res = await self.db.execute(b_query)
            brief = b_res.scalar_one_or_none()

        # Load linked Reflection
        reflection: Optional[EngineeringReflection] = None
        if workflow.reflection_id:
            r_query = select(EngineeringReflection).where(
                EngineeringReflection.id == workflow.reflection_id,
                EngineeringReflection.tenant_id == tenant_id,
            )
            r_res = await self.db.execute(r_query)
            reflection = r_res.scalar_one_or_none()

        return self._generate_explanation(
            request=request,
            workflow=workflow,
            snapshot=snapshot,
            brief=brief,
            reflection=reflection,
            is_stale=is_stale,
            stale_factors=stale_factors,
            base_revision=workflow.base_revision,
            current_revision=current_rev,
        )

    async def explain_context(
        self,
        context_id: str,
        tenant_id: str,
        request: EngineeringExplanationRequest,
    ) -> EngineeringExplanationResponse:
        """
        Synthesizes a grounded explanation for an EngineeringContextSnapshot.
        """
        snap_query = select(EngineeringContextSnapshot).where(
            EngineeringContextSnapshot.id == context_id,
            EngineeringContextSnapshot.tenant_id == tenant_id,
        )
        snap_res = await self.db.execute(snap_query)
        snapshot = snap_res.scalar_one_or_none()
        if not snapshot:
            raise HTTPException(status_code=404, detail="Engineering context snapshot not found")

        is_stale, stale_factors, current_rev = await self._check_revision_staleness(
            circuit_id=snapshot.circuit_id,
            system_id=snapshot.system_id,
            base_revision=snapshot.base_revision,
            tenant_id=tenant_id,
        )
        if is_stale and snapshot.status != ContextSnapshotStatus.STALE.value:
            snapshot.status = ContextSnapshotStatus.STALE.value
            await self.db.commit()
            await self.db.refresh(snapshot)

        return self._generate_explanation(
            request=request,
            workflow=None,
            snapshot=snapshot,
            brief=None,
            reflection=None,
            is_stale=is_stale,
            stale_factors=stale_factors,
            base_revision=snapshot.base_revision,
            current_revision=current_rev,
        )

    async def _check_revision_staleness(
        self,
        circuit_id: Optional[str],
        system_id: Optional[str],
        base_revision: int,
        tenant_id: str,
    ) -> tuple[bool, List[str], int]:
        is_stale = False
        stale_factors: List[str] = []
        current_rev = base_revision

        if circuit_id:
            c_query = select(Circuit).where(Circuit.id == circuit_id, Circuit.tenant_id == tenant_id)
            c_res = await self.db.execute(c_query)
            c = c_res.scalar_one_or_none()
            if c:
                current_rev = c.version
                if c.version > base_revision:
                    is_stale = True
                    stale_factors.append(
                        f"Circuit '{c.name}' version advanced from {base_revision} to {c.version}."
                    )
        elif system_id:
            s_query = select(EngineeringSystem).where(EngineeringSystem.id == system_id, EngineeringSystem.tenant_id == tenant_id)
            s_res = await self.db.execute(s_query)
            s = s_res.scalar_one_or_none()
            if s:
                current_rev = s.revision
                if s.revision > base_revision:
                    is_stale = True
                    stale_factors.append(
                        f"System '{s.name}' revision advanced from {base_revision} to {s.revision}."
                    )

        return is_stale, stale_factors, current_rev

    def _collect_authorized_ids(
        self,
        workflow: Optional[EngineeringCognitiveWorkflow],
        snapshot: Optional[EngineeringContextSnapshot],
        brief: Optional[EngineeringDecisionBrief],
        reflection: Optional[EngineeringReflection],
    ) -> Set[str]:
        """
        Collects all authentic entity IDs within the current engineering context.
        Used to enforce the Grounding Contract and reject MODEL_INVALID_REFERENCE.
        """
        authorized: Set[str] = set()

        if workflow:
            authorized.add(workflow.id)
            authorized.add(workflow.project_id)
            if workflow.circuit_id:
                authorized.add(workflow.circuit_id)
            if workflow.system_id:
                authorized.add(workflow.system_id)
            if workflow.intent_packet_id:
                authorized.add(workflow.intent_packet_id)
            if workflow.plan_id:
                authorized.add(workflow.plan_id)
            if workflow.execution_id:
                authorized.add(workflow.execution_id)
            if workflow.reflection_id:
                authorized.add(workflow.reflection_id)
            if workflow.decision_brief_id:
                authorized.add(workflow.decision_brief_id)
            if workflow.synthesized_context_id:
                authorized.add(workflow.synthesized_context_id)

        if snapshot:
            authorized.add(snapshot.id)
            authorized.add(snapshot.project_id)
            if snapshot.circuit_id:
                authorized.add(snapshot.circuit_id)
            if snapshot.system_id:
                authorized.add(snapshot.system_id)

            # Current state (components, nets)
            for c in (snapshot.current_state or {}).get("components", []):
                if isinstance(c, dict):
                    if "id" in c:
                        authorized.add(c["id"])
                    if "ref_des" in c:
                        authorized.add(c["ref_des"])
            for n in (snapshot.current_state or {}).get("nets", []):
                if isinstance(n, dict):
                    if "id" in n:
                        authorized.add(n["id"])
                    if "name" in n:
                        authorized.add(n["name"])

            # Deterministic results & calculations
            for a in snapshot.deterministic_results or []:
                if isinstance(a, dict):
                    if "analysis_id" in a:
                        authorized.add(a["analysis_id"])
                    if "id" in a:
                        authorized.add(a["id"])
                    for calc in a.get("calculations", []):
                        if isinstance(calc, dict):
                            if "id" in calc:
                                authorized.add(calc["id"])
                            if "name" in calc:
                                authorized.add(calc["name"])

            # Requirements
            for r in snapshot.requirements or []:
                if isinstance(r, dict):
                    if "id" in r:
                        authorized.add(r["id"])
                    if "requirement_key" in r:
                        authorized.add(r["requirement_key"])
                    if "code" in r:
                        authorized.add(r["code"])

            # Constraints
            for cs in snapshot.constraints or []:
                if isinstance(cs, dict):
                    if "id" in cs:
                        authorized.add(cs["id"])
                    if "name" in cs:
                        authorized.add(cs["name"])

            # Assumptions
            for asm in snapshot.assumptions or []:
                if isinstance(asm, dict):
                    if "id" in asm:
                        authorized.add(asm["id"])
                    if "field" in asm:
                        authorized.add(asm["field"])

            # Findings
            for f in snapshot.findings or []:
                if isinstance(f, dict):
                    if "id" in f:
                        authorized.add(f["id"])
                    if "rule_id" in f:
                        authorized.add(f["rule_id"])

            # Verification state
            v_state = snapshot.verification_state or {}
            for vr in v_state.get("requirements", []):
                if isinstance(vr, dict):
                    if "id" in vr:
                        authorized.add(vr["id"])
                    if "title" in vr:
                        authorized.add(vr["title"])

            # Evidence state
            e_state = snapshot.evidence_state or {}
            for ev_list in e_state.values():
                if isinstance(ev_list, list):
                    for ev in ev_list:
                        if isinstance(ev, dict) and "id" in ev:
                            authorized.add(ev["id"])

            # Decisions
            for d in snapshot.decision_history or []:
                if isinstance(d, dict):
                    if "id" in d:
                        authorized.add(d["id"])
                    if "decision_key" in d:
                        authorized.add(d["decision_key"])

            # Historical memory
            for m in snapshot.historical_memory or []:
                if isinstance(m, dict):
                    inner_m = m.get("memory") or m
                    if isinstance(inner_m, dict) and "id" in inner_m:
                        authorized.add(inner_m["id"])
                    if "id" in m:
                        authorized.add(m["id"])

            # Conflicts
            for conf in snapshot.conflicts or []:
                if isinstance(conf, dict):
                    if "id" in conf:
                        authorized.add(conf["id"])
                    if "source_a_id" in conf:
                        authorized.add(conf["source_a_id"])
                    if "source_b_id" in conf:
                        authorized.add(conf["source_b_id"])

        if brief:
            authorized.add(brief.id)
            for alt in brief.alternatives_data or []:
                if isinstance(alt, dict) and "id" in alt:
                    authorized.add(alt["id"])
            for aid in brief.alternative_ids or []:
                authorized.add(aid)

        if reflection:
            authorized.add(reflection.id)
            for rf in getattr(reflection, "findings", []) or []:
                rf_id = getattr(rf, "id", None) or (rf.get("id") if isinstance(rf, dict) else None)
                if rf_id:
                    authorized.add(rf_id)

        return authorized

    def _generate_explanation(
        self,
        request: EngineeringExplanationRequest,
        workflow: Optional[EngineeringCognitiveWorkflow],
        snapshot: Optional[EngineeringContextSnapshot],
        brief: Optional[EngineeringDecisionBrief],
        reflection: Optional[EngineeringReflection],
        is_stale: bool,
        stale_factors: List[str],
        base_revision: int,
        current_revision: int,
    ) -> EngineeringExplanationResponse:
        """
        Core explanation generator enforcing all Wave 7 grounding and epistemic invariants.
        """
        # 1. Authoritative references set
        authorized_ids = self._collect_authorized_ids(workflow, snapshot, brief, reflection)

        # 2. Strict Grounding Contract: Verify asserted references
        for asserted_ref in (request.asserted_references or []):
            if asserted_ref not in authorized_ids:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "MODEL_INVALID_REFERENCE",
                        "message": f"Explanation referenced entity '{asserted_ref}' does not exist in authoritative engineering context.",
                    },
                )

        for focus_ref in (request.focus_areas or []):
            if focus_ref not in authorized_ids:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "MODEL_INVALID_REFERENCE",
                        "message": f"Explanation requested focus reference '{focus_ref}' does not exist in authoritative engineering context.",
                    },
                )

        # 3. Determine Category & Queries
        category = request.category or ExplanationCategory.WHY.value
        user_query = (request.user_query or "").strip().lower()

        # Map queries to categories if category is default
        if category == "WHY" and user_query:
            if "change" in user_query or "different" in user_query:
                category = ExplanationCategory.WHAT_CHANGED.value
            elif "unknown" in user_query or "missing parameter" in user_query:
                category = ExplanationCategory.WHAT_IS_UNKNOWN.value
            elif "support" in user_query or "evidence" in user_query:
                category = ExplanationCategory.WHAT_SUPPORTS_THIS.value
            elif "conflict" in user_query or "contradiction" in user_query:
                category = ExplanationCategory.WHAT_CONFLICTS.value
            elif "requirement" in user_query and "affect" in user_query:
                category = ExplanationCategory.WHAT_REQUIREMENTS_ARE_AFFECTED.value
            elif "verification" in user_query or "test" in user_query:
                category = ExplanationCategory.WHAT_REQUIRES_VERIFICATION.value
            elif "decision" in user_query or "tradeoff" in user_query:
                category = ExplanationCategory.WHAT_REQUIRES_HUMAN_DECISION.value
            elif "blocked" in user_query:
                category = ExplanationCategory.WHY_IS_THIS_BLOCKED.value
            elif "stale" in user_query:
                category = ExplanationCategory.WHY_IS_THIS_STALE.value

        evidence_refs: List[str] = []
        requirement_refs: List[str] = []
        finding_refs: List[str] = []
        assumption_refs: List[str] = []
        decision_refs: List[str] = []
        verification_refs: List[str] = []
        unknowns_list: List[str] = []
        evidence_chain: List[EvidenceChainNode] = []
        human_actions: List[HumanActionItem] = []
        changes_detected: List[Dict[str, Any]] = []
        traceable_refs: List[Dict[str, Any]] = []
        unreferenced_assertions: List[str] = []

        statement_lines: List[str] = []
        source_entity_type = request.target_entity_type
        source_entity_id = request.target_entity_id

        # Populate baseline traceable reference
        if workflow:
            traceable_refs.append({"type": "EngineeringCognitiveWorkflow", "id": workflow.id, "status": workflow.status})
        if snapshot:
            traceable_refs.append({"type": "EngineeringContextSnapshot", "id": snapshot.id, "base_revision": snapshot.base_revision})

        # --- CATEGORY DISPATCH ---

        if category == ExplanationCategory.WHY.value:
            statement_lines, evidence_chain = self._explain_why(
                snapshot=snapshot,
                workflow=workflow,
                reflection=reflection,
                target_entity_type=source_entity_type,
                target_entity_id=source_entity_id,
                requirement_refs=requirement_refs,
                finding_refs=finding_refs,
                evidence_refs=evidence_refs,
                verification_refs=verification_refs,
                traceable_refs=traceable_refs,
            )

        elif category == ExplanationCategory.WHY_IS_THIS_BLOCKED.value:
            statement_lines = self._explain_why_blocked(
                workflow=workflow,
                snapshot=snapshot,
                finding_refs=finding_refs,
                requirement_refs=requirement_refs,
                traceable_refs=traceable_refs,
            )

        elif category == ExplanationCategory.WHY_IS_THIS_STALE.value or (is_stale and category == ExplanationCategory.WHAT_CHANGED.value):
            statement_lines, changes_detected = self._explain_stale_and_changes(
                base_revision=base_revision,
                current_revision=current_revision,
                stale_factors=stale_factors,
                snapshot=snapshot,
                traceable_refs=traceable_refs,
            )

        elif category == ExplanationCategory.WHAT_CHANGED.value:
            statement_lines, changes_detected = self._explain_stale_and_changes(
                base_revision=base_revision,
                current_revision=current_revision,
                stale_factors=stale_factors,
                snapshot=snapshot,
                traceable_refs=traceable_refs,
            )

        elif category == ExplanationCategory.WHAT_IS_UNKNOWN.value:
            statement_lines, unknowns_list = self._explain_unknowns(
                snapshot=snapshot,
                reflection=reflection,
                traceable_refs=traceable_refs,
            )

        elif category == ExplanationCategory.WHAT_SUPPORTS_THIS.value or category == ExplanationCategory.WHAT_EVIDENCE_IS_MISSING.value:
            statement_lines, evidence_chain = self._explain_evidence_support(
                snapshot=snapshot,
                target_entity_id=source_entity_id,
                evidence_refs=evidence_refs,
                requirement_refs=requirement_refs,
                finding_refs=finding_refs,
                verification_refs=verification_refs,
                traceable_refs=traceable_refs,
            )

        elif category == ExplanationCategory.WHAT_CONFLICTS.value:
            statement_lines = self._explain_conflicts(
                snapshot=snapshot,
                traceable_refs=traceable_refs,
            )

        elif category == ExplanationCategory.WHAT_REQUIREMENTS_ARE_AFFECTED.value:
            statement_lines = self._explain_requirements(
                snapshot=snapshot,
                target_entity_id=source_entity_id,
                requirement_refs=requirement_refs,
                traceable_refs=traceable_refs,
            )

        elif category == ExplanationCategory.WHAT_REQUIRES_VERIFICATION.value:
            statement_lines = self._explain_verification(
                snapshot=snapshot,
                verification_refs=verification_refs,
                traceable_refs=traceable_refs,
            )

        elif category == ExplanationCategory.WHAT_REQUIRES_HUMAN_DECISION.value:
            statement_lines = self._explain_decision_brief(
                brief=brief,
                decision_refs=decision_refs,
                traceable_refs=traceable_refs,
            )

        else:
            statement_lines = [
                f"Engineering interrogation for category '{category}' completed against baseline revision {base_revision}."
            ]

        # Extract deterministic human actions across all categories
        human_actions = self._extract_human_actions(
            workflow=workflow,
            snapshot=snapshot,
            brief=brief,
            is_stale=is_stale,
        )

        # Check candidate statements for ungrounded claims
        for stmt in (request.candidate_statements or []):
            if not self._is_statement_grounded(stmt, authorized_ids):
                unreferenced_assertions.append(stmt)

        full_statement = " ".join(statement_lines)

        return EngineeringExplanationResponse(
            context_id=snapshot.id if snapshot else None,
            workflow_id=workflow.id if workflow else None,
            category=category,
            statement=full_statement,
            explanation=full_statement,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            base_revision=base_revision,
            is_stale=is_stale,
            stale_factors=stale_factors,
            evidence_refs=list(set(evidence_refs)),
            requirement_refs=list(set(requirement_refs)),
            finding_refs=list(set(finding_refs)),
            assumption_refs=list(set(assumption_refs)),
            decision_refs=list(set(decision_refs)),
            verification_refs=list(set(verification_refs)),
            unknowns=unknowns_list,
            evidence_chain=evidence_chain,
            human_actions=human_actions,
            changes_detected=changes_detected,
            origin="AI_GROUNDED_EXPLANATION",
            authority="INFORMATIONAL_ONLY",
            traceable_references=traceable_refs,
            unreferenced_assertions=unreferenced_assertions,
            created_at=datetime.now(timezone.utc),
        )

    def _explain_why(
        self,
        snapshot: Optional[EngineeringContextSnapshot],
        workflow: Optional[EngineeringCognitiveWorkflow],
        reflection: Optional[EngineeringReflection],
        target_entity_type: Optional[str],
        target_entity_id: Optional[str],
        requirement_refs: List[str],
        finding_refs: List[str],
        evidence_refs: List[str],
        verification_refs: List[str],
        traceable_refs: List[Dict[str, Any]],
    ) -> tuple[List[str], List[EvidenceChainNode]]:
        lines: List[str] = []
        chain: List[EvidenceChainNode] = []

        if not snapshot:
            lines.append("No active context snapshot available for root-cause interrogation.")
            return lines, chain

        # Case 1: Interrogating a specific Requirement
        target_req = None
        if target_entity_id:
            for r in snapshot.requirements or []:
                if isinstance(r, dict) and (r.get("id") == target_entity_id or r.get("requirement_key") == target_entity_id or r.get("code") == target_entity_id):
                    target_req = r
                    break

        if target_req:
            req_id = target_req.get("id", target_entity_id)
            req_key = target_req.get("requirement_key") or target_req.get("code") or "REQ"
            state = target_req.get("state", "UNKNOWN")
            requirement_refs.append(req_id)
            traceable_refs.append({"type": "EngineeringRequirement", "id": req_id, "state": state})

            lines.append(f"Requirement '{req_key}' is in evaluated state '{state}'.")

            # Check for failed calculations
            failed_calcs = []
            for a in snapshot.deterministic_results or []:
                if isinstance(a, dict):
                    for c in a.get("calculations", []):
                        if isinstance(c, dict) and c.get("status") == "FAIL":
                            failed_calcs.append(c)
                            calc_name = c.get("name", "Calculation")
                            chain.append(
                                EvidenceChainNode(
                                    step="CALCULATION",
                                    entity_type="DeterministicCalculation",
                                    entity_id=c.get("id", calc_name),
                                    description=f"Calculation '{calc_name}' resulted in failure: {c.get('result')}",
                                    is_calculation=True,
                                    is_physical=False,
                                )
                            )

            if failed_calcs:
                calc_names = ", ".join([c.get("name", "calc") for c in failed_calcs])
                lines.append(f"Root cause: Deterministic calculation evaluation failed on: {calc_names}.")

            # Check for pending physical verification
            v_reqs = (snapshot.verification_state or {}).get("requirements", [])
            pending_tests = [vr for vr in v_reqs if isinstance(vr, dict) and vr.get("status") in ["REQUIRED", "PENDING", "FAILED"]]
            if pending_tests:
                for vr in pending_tests:
                    vr_id = vr.get("id", "VR")
                    verification_refs.append(vr_id)
                    lines.append(f"Physical verification obligation pending: '{vr.get('title', vr_id)}' (Status: {vr.get('status')}).")
                    lines.append("Note: Deterministic calculation does NOT satisfy physical verification.")
                    chain.append(
                        EvidenceChainNode(
                            step="PHYSICAL_EVIDENCE",
                            entity_type="VerificationRequirement",
                            entity_id=vr_id,
                            description=f"Laboratory measurement requirement '{vr.get('title')}' remains unfulfilled.",
                            is_physical=True,
                            is_calculation=False,
                        )
                    )

            # Check for blocking findings
            crit_findings = [f for f in (snapshot.findings or []) if isinstance(f, dict) and f.get("severity") in ["CRITICAL", "BLOCKING", "ERROR"]]
            for f in crit_findings:
                f_id = f.get("id", "FINDING")
                finding_refs.append(f_id)
                lines.append(f"Contradicting finding flagged: {f.get('title', f_id)} - {f.get('description', '')}.")
                chain.append(
                    EvidenceChainNode(
                        step="FINDING",
                        entity_type="EngineeringFinding",
                        entity_id=f_id,
                        description=f.get("description", "Blocking engineering finding."),
                        is_physical=False,
                        is_calculation=False,
                    )
                )

            # Anchor chain conclusion
            chain.append(
                EvidenceChainNode(
                    step="CONCLUSION",
                    entity_type="RequirementEvaluation",
                    entity_id=req_id,
                    description=f"Requirement {req_key} remains unsatisfied due to above deterministic calculation and physical verification obligations.",
                    is_physical=False,
                    is_calculation=False,
                )
            )

        # Case 2: General Root-Cause interrogation (Workflow / Reflection)
        else:
            if workflow and workflow.blocking_reasons:
                lines.append(f"Workflow '{workflow.id}' execution is blocked by {len(workflow.blocking_reasons)} condition(s):")
                for reason in workflow.blocking_reasons:
                    lines.append(f"- {reason}")
            elif reflection and reflection.status != "SATISFIED":
                lines.append(f"Reflection cycle {reflection.reflection_cycle} flagged engineering gaps:")
                if reflection.has_contradictions:
                    lines.append("- Cross-source contradictions detected in engineering models.")
                if reflection.has_verification_gaps:
                    lines.append("- Physical verification requirements remain unverified in the laboratory.")
                if reflection.has_unresolved_unknowns:
                    lines.append("- Critical components possess uncharacterized unknown parameters.")
            else:
                lines.append("Deterministic analysis, requirements evaluation, and reflection indicate no unhandled engineering contradictions.")

        return lines, chain

    def _explain_why_blocked(
        self,
        workflow: Optional[EngineeringCognitiveWorkflow],
        snapshot: Optional[EngineeringContextSnapshot],
        finding_refs: List[str],
        requirement_refs: List[str],
        traceable_refs: List[Dict[str, Any]],
    ) -> List[str]:
        lines: List[str] = []
        if workflow and workflow.blocking_reasons:
            lines.append(f"Workflow '{workflow.id}' is blocked on step '{workflow.current_step}'.")
            for r in workflow.blocking_reasons:
                lines.append(f"- {r}")
        elif snapshot and snapshot.conflicts:
            lines.append(f"Context snapshot '{snapshot.id}' contains {len(snapshot.conflicts)} blocking contradiction(s):")
            for c in snapshot.conflicts:
                desc = c.get("description") if isinstance(c, dict) else getattr(c, "description", "")
                lines.append(f"- {desc}")
        else:
            lines.append("Workflow is not blocked by deterministic faults.")
        return lines

    def _explain_stale_and_changes(
        self,
        base_revision: int,
        current_revision: int,
        stale_factors: List[str],
        snapshot: Optional[EngineeringContextSnapshot],
        traceable_refs: List[Dict[str, Any]],
    ) -> tuple[List[str], List[Dict[str, Any]]]:
        lines: List[str] = []
        changes: List[Dict[str, Any]] = []

        if current_revision > base_revision:
            lines.append(
                f"STALE WARNING: Engineering state is STALE. Workflow was synthesized against baseline revision {base_revision}, but current design revision is {current_revision}."
            )
            for factor in stale_factors:
                lines.append(f"- {factor}")
                changes.append({
                    "change_type": "REVISION_ADVANCED",
                    "details": factor,
                    "base_revision": base_revision,
                    "current_revision": current_revision,
                })
            lines.append("Affected downstream deterministic calculations, verification matrices, and decision briefs must be re-executed.")
        else:
            lines.append(f"Engineering state is CURRENT. Base revision {base_revision} matches active system revision {current_revision}.")

        return lines, changes

    def _explain_unknowns(
        self,
        snapshot: Optional[EngineeringContextSnapshot],
        reflection: Optional[EngineeringReflection],
        traceable_refs: List[Dict[str, Any]],
    ) -> tuple[List[str], List[str]]:
        lines: List[str] = []
        unknowns: List[str] = []

        raw_unknowns = []
        if snapshot:
            raw_unknowns.extend(snapshot.unknowns or [])
        if reflection:
            for rf in getattr(reflection, "findings", []) or []:
                f_type = getattr(rf, "finding_type", None) or (rf.get("category") or rf.get("finding_type") if isinstance(rf, dict) else None)
                if f_type in ["UNKNOWN_PARAMETER", "UNKNOWN"]:
                    raw_unknowns.append(rf)

        if not raw_unknowns:
            lines.append("No uncharacterized parameters or unknowns flagged in active engineering context.")
            lines.append("EPISTEMIC INVARIANT: UNKNOWN != SATISFIED. Missing parameters are NOT inferred and carry ZERO confidence percentage.")
            return lines, unknowns

        lines.append(f"Detected {len(raw_unknowns)} unresolved engineering unknown(s):")
        lines.append("EPISTEMIC INVARIANT: UNKNOWN != SATISFIED. Missing parameters are NOT inferred and carry ZERO confidence percentage.")

        for item in raw_unknowns:
            if isinstance(item, dict):
                param = item.get("parameter") or item.get("field") or item.get("name") or "Unknown Parameter"
                comp = item.get("component") or item.get("target") or "Circuit Component"
                impact = item.get("impact") or "Blocks deterministic verification"
                unknown_entry = f"{comp} -> {param}: {impact}"
                unknowns.append(unknown_entry)
                lines.append(f"- {unknown_entry}")
            else:
                unknowns.append(str(item))
                lines.append(f"- {item}")

        lines.append("Resolution requires laboratory measurement or datasheet characterization by the human engineer.")
        return lines, unknowns

    def _explain_evidence_support(
        self,
        snapshot: Optional[EngineeringContextSnapshot],
        target_entity_id: Optional[str],
        evidence_refs: List[str],
        requirement_refs: List[str],
        finding_refs: List[str],
        verification_refs: List[str],
        traceable_refs: List[Dict[str, Any]],
    ) -> tuple[List[str], List[EvidenceChainNode]]:
        lines: List[str] = []
        chain: List[EvidenceChainNode] = []

        if not snapshot:
            lines.append("No active context snapshot to evaluate evidence chains.")
            return lines, chain

        lines.append("Evidence Chain Analysis:")
        lines.append("EPISTEMIC INVARIANT: Calculation ≠ Physical Evidence. Simulation models cannot close bench testing.")

        # Traverse deterministic results
        for a in snapshot.deterministic_results or []:
            if isinstance(a, dict):
                a_id = a.get("analysis_id", "ANALYSIS")
                for c in a.get("calculations", []):
                    if isinstance(c, dict):
                        calc_name = c.get("name", "Calculation")
                        c_id = c.get("id", calc_name)
                        evidence_refs.append(c_id)
                        chain.append(
                            EvidenceChainNode(
                                step="CALCULATION",
                                entity_type="DeterministicCalculation",
                                entity_id=c_id,
                                description=f"{calc_name}: {c.get('formula', '')} = {c.get('result', '')} {c.get('unit', '')}",
                                is_calculation=True,
                                is_physical=False,
                            )
                        )

        # Traverse physical evidence
        e_state = snapshot.evidence_state or {}
        for ev in e_state.get("PHYSICAL_EVIDENCE", []):
            if isinstance(ev, dict):
                ev_id = ev.get("id", "PE")
                evidence_refs.append(ev_id)
                chain.append(
                    EvidenceChainNode(
                        step="PHYSICAL_EVIDENCE",
                        entity_type="PhysicalMeasurement",
                        entity_id=ev_id,
                        description=ev.get("description", "Calibrated bench measurement."),
                        is_calculation=False,
                        is_physical=True,
                    )
                )

        if chain:
            lines.append(f"Grounded evidence chain compiled with {len(chain)} supporting node(s).")
        else:
            lines.append("No active calculation or physical evidence records linked in current context.")

        return lines, chain

    def _explain_conflicts(
        self,
        snapshot: Optional[EngineeringContextSnapshot],
        traceable_refs: List[Dict[str, Any]],
    ) -> List[str]:
        lines: List[str] = []
        if not snapshot or not snapshot.conflicts:
            lines.append("0 cross-source contradictions detected in active engineering baseline.")
            return lines

        lines.append(f"CRITICAL: {len(snapshot.conflicts)} cross-source contradiction(s) identified:")
        lines.append("EPISTEMIC INVARIANT: CURRENT AUTHORITATIVE SOURCE strictly supersedes HISTORICAL MEMORY.")

        for c in snapshot.conflicts:
            if isinstance(c, dict):
                c_id = c.get("id", "CONF")
                cat = c.get("category", "CONFLICT")
                desc = c.get("description", "")
                src_a = f"{c.get('source_a_type')}:{c.get('source_a_id')}"
                src_b = f"{c.get('source_b_type')}:{c.get('source_b_id')}"
                lines.append(f"- [{cat}] {desc} ({src_a} vs {src_b})")
                traceable_refs.append({"type": "EngineeringContextConflict", "id": c_id})

        return lines

    def _explain_requirements(
        self,
        snapshot: Optional[EngineeringContextSnapshot],
        target_entity_id: Optional[str],
        requirement_refs: List[str],
        traceable_refs: List[Dict[str, Any]],
    ) -> List[str]:
        lines: List[str] = []
        if not snapshot or not snapshot.requirements:
            lines.append("No formal requirements attached to active engineering context.")
            return lines

        lines.append(f"Requirement evaluation summary across {len(snapshot.requirements)} formal specification(s):")
        for r in snapshot.requirements:
            if isinstance(r, dict):
                r_id = r.get("id", "REQ")
                r_key = r.get("requirement_key") or r.get("code") or "REQ"
                state = r.get("state", "UNKNOWN")
                requirement_refs.append(r_id)
                lines.append(f"- Requirement {r_key} ({r.get('title', '')}): Status '{state}'.")
                traceable_refs.append({"type": "EngineeringRequirement", "id": r_id, "state": state})

        return lines

    def _explain_verification(
        self,
        snapshot: Optional[EngineeringContextSnapshot],
        verification_refs: List[str],
        traceable_refs: List[Dict[str, Any]],
    ) -> List[str]:
        lines: List[str] = []
        v_reqs = (snapshot.verification_state or {}).get("requirements", []) if snapshot else []

        if not v_reqs:
            lines.append("No active verification test obligations registered.")
            return lines

        lines.append(f"Verification obligations tracking {len(v_reqs)} test procedure(s):")
        lines.append("EPISTEMIC INVARIANT: Analytical calculation does NOT satisfy physical laboratory verification.")

        for vr in v_reqs:
            if isinstance(vr, dict):
                vr_id = vr.get("id", "VR")
                title = vr.get("title", vr_id)
                status_val = vr.get("status", "REQUIRED")
                method = vr.get("method") or "BENCH_MEASUREMENT"
                verification_refs.append(vr_id)
                lines.append(f"- [{method}] {title}: Status '{status_val}'.")
                traceable_refs.append({"type": "VerificationRequirement", "id": vr_id, "status": status_val})

        return lines

    def _explain_decision_brief(
        self,
        brief: Optional[EngineeringDecisionBrief],
        decision_refs: List[str],
        traceable_refs: List[Dict[str, Any]],
    ) -> List[str]:
        lines: List[str] = []
        if not brief:
            lines.append("No Engineering Decision Brief active in current workflow.")
            return lines

        decision_refs.append(brief.id)
        traceable_refs.append({"type": "EngineeringDecisionBrief", "id": brief.id, "status": brief.status})

        lines.append(f"Engineering Decision Brief: '{brief.question}'.")
        lines.append(f"Status: {brief.status}. Prepared {len(brief.alternatives_data or [])} candidate alternative(s).")
        lines.append("STRICT INVARIANT: Zero synthetic scoring. QUEBET does NOT recommend winners or compute composite scores.")

        for alt in brief.alternatives_data or []:
            if isinstance(alt, dict):
                alt_name = alt.get("title") or alt.get("id") or "Alternative"
                tradeoffs = alt.get("tradeoffs", [])
                lines.append(f"- Alternative '{alt_name}': {alt.get('description', '')}")
                if tradeoffs:
                    lines.append(f"  Tradeoffs: {', '.join(str(t) for t in tradeoffs)}")

        lines.append("Ratification authority belongs exclusively to the Human Engineer.")
        return lines

    def _extract_human_actions(
        self,
        workflow: Optional[EngineeringCognitiveWorkflow],
        snapshot: Optional[EngineeringContextSnapshot],
        brief: Optional[EngineeringDecisionBrief],
        is_stale: bool,
    ) -> List[HumanActionItem]:
        """
        Extracts a deterministic list of outstanding human engineering actions.
        Strictly zero synthetic scoring or intelligence ranking.
        """
        actions: List[HumanActionItem] = []

        if is_stale:
            actions.append(
                HumanActionItem(
                    action_type="WORKFLOW_REVALIDATION_REQUIRED",
                    title="Revalidate Stale Workflow",
                    description="Circuit or system baseline has advanced. Re-run analysis workflow against current revision.",
                    urgency="HIGH",
                )
            )

        if workflow:
            if workflow.current_step == "CLARIFICATION_REQUIRED":
                actions.append(
                    HumanActionItem(
                        action_type="CLARIFICATION_REQUIRED",
                        title="Provide Engineering Clarification",
                        description=f"Engineer clarification needed: {workflow.blocking_reasons[0] if workflow.blocking_reasons else 'Clarify ambiguous request.'}",
                        target_entity_type="EngineeringCognitiveWorkflow",
                        target_entity_id=workflow.id,
                        urgency="HIGH",
                    )
                )

        if brief and brief.status in ["PREPARED", "PENDING"]:
            actions.append(
                HumanActionItem(
                    action_type="DECISION_RATIFICATION",
                    title="Review and Ratify Decision Alternative",
                    description=f"Human engineer must evaluate alternatives for: '{brief.question}'.",
                    target_entity_type="EngineeringDecisionBrief",
                    target_entity_id=brief.id,
                    urgency="NORMAL",
                )
            )

        if snapshot:
            # Physical verification pending
            v_reqs = (snapshot.verification_state or {}).get("requirements", [])
            for vr in v_reqs:
                if isinstance(vr, dict) and vr.get("status") in ["REQUIRED", "PENDING"]:
                    actions.append(
                        HumanActionItem(
                            action_type="PHYSICAL_MEASUREMENT_REQUIRED",
                            title=f"Conduct Laboratory Test: {vr.get('title', 'Bench Test')}",
                            description=f"Physical test '{vr.get('title')}' is required. Simulation cannot fulfill physical verification.",
                            target_entity_type="VerificationRequirement",
                            target_entity_id=vr.get("id"),
                            urgency="NORMAL",
                        )
                    )

            # Blocking findings
            for f in snapshot.findings or []:
                if isinstance(f, dict) and f.get("severity") in ["CRITICAL", "BLOCKING"]:
                    actions.append(
                        HumanActionItem(
                            action_type="REVIEW_FINDING_CLOSURE_REQUIRED",
                            title=f"Resolve Blocking Finding: {f.get('title', 'Violation')}",
                            description=f.get("description", "Engineering constraint violation requires resolution or waiver."),
                            target_entity_type="EngineeringFinding",
                            target_entity_id=f.get("id"),
                            urgency="HIGH",
                        )
                    )

            # Uncharacterized parameters
            for unk in snapshot.unknowns or []:
                if isinstance(unk, dict):
                    actions.append(
                        HumanActionItem(
                            action_type="UNKNOWN_PARAMETER_RESOLUTION",
                            title=f"Characterize Missing Parameter: {unk.get('parameter', 'Unknown')}",
                            description=f"Provide datasheet parameter or measurement for {unk.get('component', 'component')}.",
                            urgency="NORMAL",
                        )
                    )

        return actions

    def _is_statement_grounded(self, statement: str, authorized_ids: Set[str]) -> bool:
        """
        Verifies whether an asserted statement is grounded or contains foreign/unsupported claims.
        """
        # If the statement explicitly mentions an entity ID formatted like an ID, ensure it exists
        words = statement.split()
        for w in words:
            clean_w = w.strip(".,;:()[]'\"")
            if any(prefix in clean_w for prefix in ["comp-", "circ-", "req-", "vr-", "dec-", "brief-", "wf-", "mem-", "snap-"]):
                if clean_w not in authorized_ids:
                    return False
        return True
