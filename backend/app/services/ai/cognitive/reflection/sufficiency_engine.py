from typing import Any, Dict, List, Optional
from app.models.db.cognitive import (
    ReasoningFindingType,
    ReasoningFindingSeverity,
    ReflectionStatus,
)
from app.services.ai.cognitive.reflection.contradiction_engine import EngineeringContradictionEngine
from app.services.ai.cognitive.reflection.unknown_service import UnknownAnalysisService
from app.services.ai.cognitive.reflection.requirement_reflection import RequirementReflectionService
from app.services.ai.cognitive.reflection.verification_reflection import VerificationReflectionService
from app.services.ai.cognitive.reflection.evidence_sufficiency import EvidenceSufficiencyEngine


class ResultSufficiencyEngine:
    """
    Central reflection evaluator synthesizing deterministic contradiction, unknown,
    requirement, verification, and evidence analyses into an auditable reflection record.
    Strictly prohibits synthetic or composite scores.
    """

    @classmethod
    def evaluate(
        cls,
        execution_results: List[Dict[str, Any]],
        execution_findings: List[Dict[str, Any]],
        execution_unknowns: List[Dict[str, Any]],
        requirements: List[Dict[str, Any]],
        assumptions: List[Dict[str, Any]],
        verification_impacts: List[Dict[str, Any]],
        traceability_records: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
        context_payload: Optional[Dict[str, Any]] = None,
        base_revision: int = 1,
    ) -> Dict[str, Any]:
        all_findings: List[Dict[str, Any]] = []

        # 1. Contradictions
        contradictions = EngineeringContradictionEngine.check_contradictions(
            execution_results=execution_results,
            requirements=requirements,
            assumptions=assumptions,
            context_payload=context_payload,
        )
        all_findings.extend(contradictions)

        # 2. Unknowns & missing parameters
        unknowns = UnknownAnalysisService.analyze_unknowns(
            execution_unknowns=execution_unknowns,
            context_payload=context_payload,
        )
        all_findings.extend(unknowns)

        # 3. Requirements evaluation (4-state: SATISFIED, NOT_SATISFIED, UNKNOWN, NOT_EVALUATED)
        req_findings = RequirementReflectionService.evaluate_requirements(
            requirements=requirements,
            execution_results=execution_results,
            traceability_records=traceability_records,
        )
        all_findings.extend(req_findings)

        # 4. Verification obligations & invariants
        verif_findings = VerificationReflectionService.audit_verification(
            verification_impacts=verification_impacts,
            requirements=requirements,
        )
        all_findings.extend(verif_findings)

        # 5. Evidence sufficiency & calibration
        ev_findings = EvidenceSufficiencyEngine.evaluate_evidence(
            evidence_items=evidence_items,
            current_revision=base_revision,
        )
        all_findings.extend(ev_findings)

        # Deduplicate findings by title and affected_entity_id
        dedup_findings: List[Dict[str, Any]] = []
        seen = set()
        for f in all_findings:
            key = f"{f['finding_type']}:{f['title']}:{f.get('affected_entity_id')}"
            if key not in seen:
                seen.add(key)
                dedup_findings.append(f)

        # Compute Discrete Status Booleans
        has_contradictions = any(
            f["finding_type"] in (ReasoningFindingType.CONTRADICTORY_RESULT.value, ReasoningFindingType.ASSUMPTION_CONFLICT.value)
            for f in dedup_findings
        )
        has_unresolved_unknowns = any(
            f["finding_type"] in (ReasoningFindingType.UNRESOLVED_UNKNOWN.value, ReasoningFindingType.MISSING_INFORMATION.value)
            for f in dedup_findings
        )
        has_evidence_gaps = any(
            f["finding_type"] == ReasoningFindingType.INSUFFICIENT_EVIDENCE.value
            for f in dedup_findings
        )
        has_requirement_gaps = any(
            f["finding_type"] in (ReasoningFindingType.REQUIREMENT_GAP.value, ReasoningFindingType.TRACEABILITY_GAP.value)
            for f in dedup_findings
        )
        has_verification_gaps = any(
            f["finding_type"] == ReasoningFindingType.VERIFICATION_GAP.value
            for f in dedup_findings
        )

        has_critical = any(f["severity"] == ReasoningFindingSeverity.CRITICAL.value for f in dedup_findings)

        additional_work_required = bool(has_contradictions or has_unresolved_unknowns or has_requirement_gaps or has_verification_gaps or has_critical)

        # Synthesize Proposed Follow-up Tasks (Read-Only)
        proposed_tasks = []
        cap_to_findings: Dict[str, List[Dict[str, Any]]] = {}
        for f in dedup_findings:
            cap = f.get("follow_up_capability")
            if cap:
                cap_to_findings.setdefault(cap, []).append(f)

        order_idx = 0
        for cap, matched_findings in cap_to_findings.items():
            order_idx += 1
            targets = [
                {"type": f["affected_entity_type"], "id": f["affected_entity_id"]}
                for f in matched_findings if f.get("affected_entity_id")
            ]
            proposed_tasks.append({
                "task_type": cap,
                "description": f"Resolve {len(matched_findings)} finding(s): {matched_findings[0]['title']}",
                "target_objects": targets,
                "required_capabilities": [cap],
                "required_inputs": {
                    "finding_titles": [f["title"] for f in matched_findings],
                    "entity_ids": [f["affected_entity_id"] for f in matched_findings if f.get("affected_entity_id")],
                },
                "expected_outputs": ["resolved_data", "updated_evidence"],
                "order_index": order_idx,
            })

        # Formulate Discrete Factual Summary
        summary_lines = [
            f"Cognitive Reflection evaluated {len(execution_results)} execution result(s) against authoritative engineering baselines.",
            f"Findings detected: {len(dedup_findings)} discrete finding(s) ({sum(1 for f in dedup_findings if f['severity'] == ReasoningFindingSeverity.CRITICAL.value)} CRITICAL, {sum(1 for f in dedup_findings if f['severity'] == ReasoningFindingSeverity.WARNING.value)} WARNING).",
        ]
        if has_contradictions:
            summary_lines.append(f"• Contradictions: Operating point or absolute maximum rating limits violated.")
        if has_unresolved_unknowns:
            summary_lines.append(f"• Unknowns: Uncharacterized parameters require datasheet lookup or measurement.")
        if has_requirement_gaps:
            summary_lines.append(f"• Requirement Gaps: Requirements unverified or marked NOT_SATISFIED (UNKNOWN != SATISFIED).")
        if has_verification_gaps:
            summary_lines.append(f"• Verification Gaps: Physical verification obligations pending (CALCULATED != PHYSICALLY VERIFIED).")
        if has_evidence_gaps:
            summary_lines.append(f"• Evidence Gaps: Stale revision or uncalibrated instrumentation records detected.")

        if additional_work_required:
            summary_lines.append(f"Conclusion: ADDITIONAL_WORK_REQUIRED. {len(proposed_tasks)} follow-up task(s) proposed.")
        else:
            summary_lines.append("Conclusion: COMPLETE. No unresolved contradictions or gaps detected in this cycle.")

        summary = "\n".join(summary_lines)

        status = ReflectionStatus.ADDITIONAL_WORK_REQUIRED.value if additional_work_required else ReflectionStatus.COMPLETE.value

        return {
            "status": status,
            "has_contradictions": has_contradictions,
            "has_unresolved_unknowns": has_unresolved_unknowns,
            "has_evidence_gaps": has_evidence_gaps,
            "has_requirement_gaps": has_requirement_gaps,
            "has_verification_gaps": has_verification_gaps,
            "additional_work_required": additional_work_required,
            "findings": dedup_findings,
            "proposed_follow_up_tasks": proposed_tasks,
            "summary": summary,
        }
