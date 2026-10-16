import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.circuit import Circuit
from app.models.db.system import EngineeringSystem
from app.models.db.verification import (
    EngineeringDesignReview,
    EngineeringVerificationRequirement,
    EngineeringEvidence,
    EngineeringReviewAuditEvent,
    VerificationStatus,
    EvidenceStatus,
    DesignReviewStatus,
)
from app.models.db.cognitive import (
    EngineeringCognitiveWorkflow,
    CognitiveWorkflowStatus,
)
from app.models.schemas.cognitive import (
    EvidenceRegisterRequest,
    VerificationCloseRequest,
    VerificationWorkspaceObligation,
    VerificationWorkspaceSummary,
    VerificationWorkspaceResponse,
    EvidenceSufficiencyStatus,
)
from app.services.verification_service import verification_service
from app.core.dependencies import AuthenticatedUser


class EngineeringVerificationWorkspaceService:
    """
    Phase 2 Wave 8: Engineering Evidence & Verification Workspace Service.
    Enforces absolute epistemic invariants:
    - CALCULATED != PHYSICALLY VERIFIED
    - ANALYSIS != PHYSICAL EVIDENCE
    - UNKNOWN != SATISFIED
    - EVIDENCE_EXISTENCE != EVIDENCE_SUFFICIENCY
    - HISTORICAL_VERIFICATION != CURRENT_VERIFICATION
    - AI_VERIFICATION_AUTHORITY = NONE
    - AUTONOMOUS_VERIFICATION_CLOSURE = DISABLED
    - ZERO SYNTHETIC SCORING
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_workflow_verification_workspace(
        self,
        workflow_id: str,
        tenant_id: str,
    ) -> VerificationWorkspaceResponse:
        """
        Synthesizes a unified verification workspace for an active cognitive workflow.
        """
        wf_query = select(EngineeringCognitiveWorkflow).where(
            EngineeringCognitiveWorkflow.id == workflow_id,
            EngineeringCognitiveWorkflow.tenant_id == tenant_id,
        )
        wf_res = await self.db.execute(wf_query)
        workflow = wf_res.scalar_one_or_none()
        if not workflow:
            raise HTTPException(status_code=404, detail="Engineering cognitive workflow not found")

        # 1. Freshness evaluation
        is_stale, stale_factors, current_rev = await self._check_revision_staleness(
            circuit_id=workflow.circuit_id,
            system_id=workflow.system_id,
            base_revision=workflow.base_revision,
            tenant_id=tenant_id,
        )

        # 2. Locate or generate Design Review
        review: Optional[EngineeringDesignReview] = None
        if workflow.circuit_id:
            rev_query = (
                select(EngineeringDesignReview)
                .where(
                    EngineeringDesignReview.circuit_id == workflow.circuit_id,
                    EngineeringDesignReview.tenant_id == tenant_id,
                )
                .order_by(EngineeringDesignReview.circuit_revision.desc())
            )
            rev_res = await self.db.execute(rev_query)
            review = rev_res.scalars().first()

            if not review:
                # Generate deterministic design review
                user_stub = AuthenticatedUser(
                    id="system-orchestrator",
                    email="orchestrator@quebet.internal",
                    role="engineer",
                    tenant_id=tenant_id,
                )
                review = await verification_service.create_or_generate_review(
                    db=self.db,
                    circuit_id=workflow.circuit_id,
                    current_user=user_stub,
                )

        # 3. Build obligations list
        obligations: List[VerificationWorkspaceObligation] = []
        if review:
            # Refresh relationship items
            vr_query = (
                select(EngineeringVerificationRequirement)
                .where(EngineeringVerificationRequirement.review_id == review.id)
                .order_by(EngineeringVerificationRequirement.code)
            )
            vr_res = await self.db.execute(vr_query)
            vr_items = list(vr_res.scalars().all())

            for vr in vr_items:
                # Fetch attached evidence
                evi_query = (
                    select(EngineeringEvidence)
                    .where(EngineeringEvidence.verification_requirement_id == vr.id)
                    .order_by(EngineeringEvidence.provided_at.desc())
                )
                evi_res = await self.db.execute(evi_query)
                evidences = list(evi_res.scalars().all())

                obligation = self._evaluate_obligation_sufficiency(
                    vr=vr,
                    evidences=evidences,
                    current_circuit_rev=current_rev,
                    is_system_stale=is_stale,
                )
                obligations.append(obligation)

        # 4. Synthesize Summary (strictly zero synthetic scoring)
        verified_count = sum(1 for o in obligations if o.status == VerificationStatus.SATISFIED.value)
        pending_count = sum(1 for o in obligations if o.status in [VerificationStatus.NOT_STARTED.value, VerificationStatus.IN_PROGRESS.value])
        blocked_count = sum(1 for o in obligations if o.status == VerificationStatus.BLOCKED.value)
        stale_count = sum(1 for o in obligations if o.is_stale)
        missing_count = sum(1 for o in obligations if o.sufficiency == EvidenceSufficiencyStatus.MISSING.value)
        insufficient_count = sum(1 for o in obligations if o.sufficiency == EvidenceSufficiencyStatus.INSUFFICIENT.value)
        physical_pending = sum(1 for o in obligations if o.is_physical_required and not o.has_physical_evidence)
        unknowns_count = sum(1 for o in obligations if o.status == VerificationStatus.UNKNOWN.value)

        human_actions: List[str] = []
        if is_stale:
            human_actions.append("Revalidate stale verification matrix against current design revision.")
        if physical_pending > 0:
            human_actions.append(f"Execute {physical_pending} mandatory laboratory bench measurement(s).")
        if missing_count > 0:
            human_actions.append(f"Upload and bind supporting evidence for {missing_count} obligation(s).")
        if verified_count < len(obligations) and pending_count > 0:
            human_actions.append("Conduct formal human verification review and ratification.")

        summary = VerificationWorkspaceSummary(
            total_obligations=len(obligations),
            verified_count=verified_count,
            pending_count=pending_count,
            blocked_count=blocked_count,
            stale_count=stale_count,
            missing_evidence_count=missing_count,
            insufficient_evidence_count=insufficient_count,
            physical_tests_pending=physical_pending,
            unresolved_unknowns_count=unknowns_count,
            outstanding_human_actions=human_actions,
        )

        # 5. Integrity Digest
        digest_content = f"{workflow.id}:{current_rev}:{len(obligations)}:{verified_count}:{pending_count}:{blocked_count}"
        integrity_digest = hashlib.sha256(digest_content.encode("utf-8")).hexdigest()

        return VerificationWorkspaceResponse(
            workspace_id=f"ws-{workflow.id[:8]}",
            workflow_id=workflow.id,
            review_id=review.id if review else None,
            project_id=workflow.project_id,
            circuit_id=workflow.circuit_id,
            system_id=workflow.system_id,
            base_revision=workflow.base_revision,
            is_stale=is_stale,
            stale_factors=stale_factors,
            obligations=obligations,
            summary=summary,
            provenance_integrity_digest=integrity_digest,
            created_at=datetime.now(timezone.utc),
        )

    async def get_verification_obligation(
        self,
        verification_id: str,
        tenant_id: str,
    ) -> VerificationWorkspaceObligation:
        vr_query = select(EngineeringVerificationRequirement).where(
            EngineeringVerificationRequirement.id == verification_id,
            EngineeringVerificationRequirement.tenant_id == tenant_id,
        )
        vr_res = await self.db.execute(vr_query)
        vr = vr_res.scalar_one_or_none()
        if not vr:
            raise HTTPException(status_code=404, detail="Verification requirement not found")

        # Load review for revision info
        rev_query = select(EngineeringDesignReview).where(EngineeringDesignReview.id == vr.review_id)
        rev_res = await self.db.execute(rev_query)
        review = rev_res.scalar_one_or_none()

        current_circuit_rev = review.circuit_revision if review else 1
        is_stale_detected = False
        if review and review.circuit_id:
            c_query = select(Circuit.version).where(Circuit.id == review.circuit_id)
            c_res = await self.db.execute(c_query)
            latest_version = c_res.scalar_one_or_none()
            if latest_version is not None and latest_version > (review.circuit_revision or 1):
                current_circuit_rev = latest_version
                is_stale_detected = True

        evi_query = select(EngineeringEvidence).where(
            EngineeringEvidence.verification_requirement_id == vr.id
        ).order_by(EngineeringEvidence.provided_at.desc())
        evi_res = await self.db.execute(evi_query)
        evidences = list(evi_res.scalars().all())

        return self._evaluate_obligation_sufficiency(
            vr=vr,
            evidences=evidences,
            current_circuit_rev=current_circuit_rev,
            is_system_stale=is_stale_detected,
        )

    async def attach_evidence(
        self,
        verification_id: str,
        request: EvidenceRegisterRequest,
        tenant_id: str,
        actor: str,
    ) -> Dict[str, Any]:
        """
        Attaches traceable evidence to a verification obligation with entity reference validation.
        """
        vr_query = select(EngineeringVerificationRequirement).where(
            EngineeringVerificationRequirement.id == verification_id,
            EngineeringVerificationRequirement.tenant_id == tenant_id,
        )
        vr_res = await self.db.execute(vr_query)
        vr = vr_res.scalar_one_or_none()
        if not vr:
            raise HTTPException(status_code=404, detail="Verification requirement not found")

        rev_query = select(EngineeringDesignReview).where(EngineeringDesignReview.id == vr.review_id)
        rev_res = await self.db.execute(rev_query)
        review = rev_res.scalar_one_or_none()

        # 1. Grounding Contract: Validate bound entity reference if specified
        if request.bound_entity_id:
            await self._validate_bound_entity(request.bound_entity_type, request.bound_entity_id, tenant_id)

        # 2. Epistemic boundary: distinguish physical vs calculation
        is_physical = request.is_physical
        if request.evidence_type in ["MEASUREMENT", "LAB_OBSERVATION", "TEST_REPORT"]:
            is_physical = True
        elif request.evidence_type in ["CALCULATION", "SIMULATION_REPORT"]:
            is_physical = False

        # 3. Create evidence record
        evidence = EngineeringEvidence(
            verification_requirement_id=vr.id,
            review_id=vr.review_id,
            tenant_id=tenant_id,
            evidence_type=request.evidence_type,
            source=request.source,
            description=request.description,
            value=request.value,
            unit=request.unit,
            reference=request.reference,
            provided_by=actor,
            status=EvidenceStatus.VALID.value,
            circuit_id=review.circuit_id if review else None,
            circuit_revision=review.circuit_revision if review else 1,
            instrument=request.instrument,
            instrument_model=request.instrument_model,
            instrument_serial=request.instrument_serial,
            calibration_reference=request.calibration_reference,
            calibration_status=request.calibration_status or "CALIBRATED",
            is_stale=False,
            metadata_={
                **request.metadata,
                "is_physical": is_physical,
                "bound_entity_type": request.bound_entity_type,
                "bound_entity_id": request.bound_entity_id,
            },
        )
        self.db.add(evidence)

        # If requirement was NOT_STARTED, move to IN_PROGRESS
        if vr.status == VerificationStatus.NOT_STARTED.value:
            vr.status = VerificationStatus.IN_PROGRESS.value

        await self.db.commit()
        await self.db.refresh(evidence)

        # Compute provenance digest
        digest_data = f"{evidence.id}:{evidence.evidence_type}:{evidence.source}:{evidence.provided_by}:{evidence.circuit_revision}"
        evidence_digest = hashlib.sha256(digest_data.encode("utf-8")).hexdigest()

        return {
            "evidence_id": evidence.id,
            "verification_requirement_id": vr.id,
            "evidence_type": evidence.evidence_type,
            "is_physical": is_physical,
            "source": evidence.source,
            "description": evidence.description,
            "provenance_integrity_digest": evidence_digest,
            "cryptographic_hash": evidence_digest,
            "provided_by": actor,
            "provided_at": evidence.provided_at.isoformat(),
        }

    async def review_verification(
        self,
        verification_id: str,
        tenant_id: str,
        actor: str,
    ) -> Dict[str, Any]:
        """
        Prepares a verification summary and gap audit without altering authoritative verification status.
        """
        obligation = await self.get_verification_obligation(verification_id, tenant_id)
        gaps: List[str] = []
        if obligation.is_physical_required and not obligation.has_physical_evidence:
            gaps.append("Physical laboratory measurement is required. Simulation models cannot close bench verification.")
        if obligation.sufficiency == EvidenceSufficiencyStatus.MISSING.value:
            gaps.append("No supporting engineering evidence attached.")
        if obligation.is_stale:
            gaps.append("Attached evidence is from a superseded circuit revision.")

        return {
            "verification_requirement_id": obligation.verification_requirement_id,
            "code": obligation.code,
            "title": obligation.title,
            "current_status": obligation.status,
            "sufficiency": obligation.sufficiency,
            "is_physical_required": obligation.is_physical_required,
            "evidence_count": len(obligation.attached_evidence_items),
            "remaining_gaps": gaps,
            "authority": "INFORMATIONAL_ONLY",
            "reviewed_by": actor,
        }

    async def close_verification(
        self,
        verification_id: str,
        request: VerificationCloseRequest,
        tenant_id: str,
        actor: str,
    ) -> Dict[str, Any]:
        """
        Executes human-gated verification closure.
        Strictly rejects autonomous AI closure attempts, missing physical evidence, and stale revisions.
        """
        # 1. AI Gate Policy: AUTONOMOUS_VERIFICATION_CLOSURE = DISABLED
        actor_check = (request.actor or actor).lower()
        if (
            actor_check.startswith("ai-")
            or "model" in actor_check
            or "agent" in actor_check
            or "bot" in actor_check
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "AI_UNAUTHORIZED_VERIFICATION_CLOSURE",
                    "message": "AI verification authority is NONE. Verification closure must be performed by a human engineer.",
                },
            )

        vr_query = select(EngineeringVerificationRequirement).where(
            EngineeringVerificationRequirement.id == verification_id,
            EngineeringVerificationRequirement.tenant_id == tenant_id,
        )
        vr_res = await self.db.execute(vr_query)
        vr = vr_res.scalar_one_or_none()
        if not vr:
            raise HTTPException(status_code=404, detail="Verification requirement not found")

        rev_query = select(EngineeringDesignReview).where(EngineeringDesignReview.id == vr.review_id)
        rev_res = await self.db.execute(rev_query)
        review = rev_res.scalar_one_or_none()

        # 2. Check Revision Freshness
        if review and review.circuit_id:
            c_query = select(Circuit).where(Circuit.id == review.circuit_id)
            c_res = await self.db.execute(c_query)
            circuit = c_res.scalar_one_or_none()
            if circuit and circuit.version > review.circuit_revision:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "VERIFICATION_STALE_REVISION",
                        "message": f"Circuit revision has advanced from {review.circuit_revision} to {circuit.version}. Cannot close stale verification.",
                    },
                )

        if request.current_revision is not None and review and request.current_revision != review.circuit_revision:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "VERIFICATION_STALE_REVISION",
                    "message": f"Requested revision {request.current_revision} does not match active review revision {review.circuit_revision}.",
                },
            )

        # 3. Check Evidence Sufficiency & Physical Requirements
        evi_query = select(EngineeringEvidence).where(
            EngineeringEvidence.verification_requirement_id == vr.id
        )
        evi_res = await self.db.execute(evi_query)
        evidences = list(evi_res.scalars().all())

        previous_status = vr.status
        if request.decision == "VERIFIED":
            if not evidences:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "EVIDENCE_MISSING",
                        "message": f"Cannot verify obligation '{vr.code}' without supporting evidence.",
                    },
                )

            # Check if physical test required
            is_physical_req = vr.method in ["BENCH_TEST", "MEASUREMENT", "LAB_OBSERVATION"] or "thermal" in vr.title.lower()
            has_physical = any(
                e.evidence_type in ["MEASUREMENT", "LAB_OBSERVATION", "TEST_REPORT"]
                or (e.metadata_ or {}).get("is_physical") is True
                for e in evidences
            )

            if is_physical_req and not has_physical:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "PHYSICAL_MEASUREMENT_MISSING",
                        "message": "Physical laboratory measurement required. Simulation or calculation cannot close physical verification obligations.",
                    },
                )

            # Check stale evidence
            if any(e.is_stale for e in evidences):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "EVIDENCE_STALE",
                        "message": "Attached evidence was flagged as stale and cannot satisfy current verification.",
                    },
                )

            vr.status = VerificationStatus.SATISFIED.value

        elif request.decision == "WAIVED":
            if not request.waiver_reason and not request.rationale:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "WAIVER_JUSTIFICATION_REQUIRED",
                        "message": "Verification waiver requires mandatory human engineering rationale.",
                    },
                )
            vr.status = VerificationStatus.NOT_APPLICABLE.value
            vr.not_applicable_reason = request.waiver_reason or request.rationale

        elif request.decision == "FAILED":
            vr.status = VerificationStatus.FAILED.value

        # 4. Record Human Audit Event
        effective_actor = request.actor or actor
        audit_event = EngineeringReviewAuditEvent(
            id=str(uuid.uuid4()),
            review_id=vr.review_id,
            tenant_id=tenant_id,
            actor_id=effective_actor,
            event_type="VERIFICATION_STATUS_UPDATED",
            object_id=vr.id,
            previous_state=previous_status,
            new_state=vr.status,
            reason=request.rationale,
        )
        self.db.add(audit_event)

        await self.db.commit()
        await self.db.refresh(vr)

        return {
            "verification_requirement_id": vr.id,
            "code": vr.code,
            "status": vr.status,
            "decision": request.decision,
            "closed_by": effective_actor,
            "audit_event_id": audit_event.id,
            "waiver_reason": vr.not_applicable_reason,
            "rationale": request.rationale,
            "closed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _evaluate_obligation_sufficiency(
        self,
        vr: EngineeringVerificationRequirement,
        evidences: List[EngineeringEvidence],
        current_circuit_rev: int,
        is_system_stale: bool,
    ) -> VerificationWorkspaceObligation:
        is_physical_req = vr.method in ["BENCH_TEST", "MEASUREMENT", "LAB_OBSERVATION"] or "thermal" in vr.title.lower()
        has_physical = any(
            e.evidence_type in ["MEASUREMENT", "LAB_OBSERVATION", "TEST_REPORT"]
            or (e.metadata_ or {}).get("is_physical") is True
            for e in evidences
        )

        stale_reasons: List[str] = []
        is_obligation_stale = is_system_stale
        if is_system_stale:
            stale_reasons.append("Design baseline revision has advanced.")

        for e in evidences:
            if e.circuit_revision is not None and e.circuit_revision < current_circuit_rev:
                is_obligation_stale = True
                stale_reasons.append(f"Evidence '{e.source}' is bound to revision {e.circuit_revision} (current is {current_circuit_rev}).")
            if e.is_stale:
                is_obligation_stale = True
                stale_reasons.append(f"Evidence '{e.source}' marked as STALE.")

        # Determine Sufficiency Status
        if not evidences:
            sufficiency = EvidenceSufficiencyStatus.MISSING.value
        elif is_physical_req and not has_physical:
            sufficiency = EvidenceSufficiencyStatus.INSUFFICIENT.value
        elif is_obligation_stale:
            sufficiency = EvidenceSufficiencyStatus.INSUFFICIENT.value
        else:
            sufficiency = EvidenceSufficiencyStatus.SUFFICIENT.value

        human_action: Optional[str] = None
        if vr.status == VerificationStatus.SATISFIED.value:
            human_action = None
        elif is_obligation_stale:
            human_action = "Revalidate evidence against current revision."
        elif is_physical_req and not has_physical:
            human_action = "Conduct laboratory bench measurement."
        elif sufficiency == EvidenceSufficiencyStatus.MISSING.value:
            human_action = "Attach required verification evidence."
        elif sufficiency == EvidenceSufficiencyStatus.SUFFICIENT.value:
            human_action = "Review evidence and ratify verification closure."

        evidence_dicts = [
            {
                "id": e.id,
                "evidence_type": e.evidence_type,
                "source": e.source,
                "description": e.description,
                "value": e.value,
                "unit": e.unit,
                "is_physical": (e.metadata_ or {}).get("is_physical", False) or e.evidence_type in ["MEASUREMENT", "LAB_OBSERVATION", "TEST_REPORT"],
                "is_stale": e.is_stale or (e.circuit_revision is not None and e.circuit_revision < current_circuit_rev),
                "circuit_revision": e.circuit_revision,
                "provided_by": e.provided_by,
                "provided_at": e.provided_at.isoformat(),
            }
            for e in evidences
        ]

        return VerificationWorkspaceObligation(
            verification_requirement_id=vr.id,
            code=vr.code,
            title=vr.title,
            reason=vr.reason,
            method=vr.method,
            operating_condition=vr.operating_condition,
            is_mandatory=vr.is_mandatory,
            status=vr.status,
            related_finding_id=vr.related_finding_id,
            required_evidence_types=list(vr.required_evidence or []),
            attached_evidence_items=evidence_dicts,
            sufficiency=sufficiency,
            is_physical_required=is_physical_req,
            has_physical_evidence=has_physical,
            is_stale=is_obligation_stale,
            stale_reasons=list(set(stale_reasons)),
            human_action_required=human_action,
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
                    stale_factors.append(f"Circuit version advanced from {base_revision} to {c.version}.")
        elif system_id:
            s_query = select(EngineeringSystem).where(EngineeringSystem.id == system_id, EngineeringSystem.tenant_id == tenant_id)
            s_res = await self.db.execute(s_query)
            s = s_res.scalar_one_or_none()
            if s:
                current_rev = s.revision
                if s.revision > base_revision:
                    is_stale = True
                    stale_factors.append(f"System revision advanced from {base_revision} to {s.revision}.")

        return is_stale, stale_factors, current_rev

    async def _validate_bound_entity(self, entity_type: Optional[str], entity_id: str, tenant_id: str) -> None:
        """
        Ensures entity being bound actually exists in the tenant workspace.
        """
        # Check Circuit
        c_query = select(Circuit).where(Circuit.id == entity_id, Circuit.tenant_id == tenant_id)
        if (await self.db.execute(c_query)).scalar_one_or_none():
            return
        # Check System
        s_query = select(EngineeringSystem).where(EngineeringSystem.id == entity_id, EngineeringSystem.tenant_id == tenant_id)
        if (await self.db.execute(s_query)).scalar_one_or_none():
            return
        # Check Verification Requirement
        vr_query = select(EngineeringVerificationRequirement).where(
            EngineeringVerificationRequirement.id == entity_id,
            EngineeringVerificationRequirement.tenant_id == tenant_id,
        )
        if (await self.db.execute(vr_query)).scalar_one_or_none():
            return

        raise HTTPException(
            status_code=422,
            detail={
                "error": "MODEL_INVALID_REFERENCE",
                "message": f"Bound entity '{entity_id}' of type '{entity_type}' does not exist in authoritative context.",
            },
        )
