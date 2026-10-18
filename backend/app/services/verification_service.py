import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthenticatedUser
from app.models.db.circuit import Circuit
from app.models.db.verification import (
    DesignReviewStatus,
    EngineeringDesignReview,
    EngineeringEvidence,
    EngineeringReviewAuditEvent,
    EngineeringTestPoint,
    EngineeringVerificationRequirement,
    EvidenceStatus,
    VerificationStatus,
)
from app.models.schemas.verification import (
    DesignReviewResponse,
    EvidenceCreate,
    EvidenceResponse,
    FailureModeResponse,
    RequirementStatusUpdate,
    TestPointCreate,
    TestPointResponse,
    VerificationMatrixResponse,
    VerificationMatrixRow,
    VerificationRequirementResponse,
)
from app.repositories.analysis_repo import analysis_repo
from app.repositories.circuit_repo import circuit_repo
from app.repositories.project_repo import project_repo
from app.repositories.verification_repo import verification_repo
from app.services.ai.verification.failure_engine import failure_analysis_engine
from app.services.ai.verification.requirement_generator import verification_requirement_generator


class DesignReviewService:
    """
    Core service orchestrating Engineering Verification, Design Reviews, Failure Analysis,
    and Laboratory Test Points.
    """

    async def _verify_circuit_access(
        self,
        db: AsyncSession,
        circuit_id: str,
        current_user: AuthenticatedUser,
    ) -> Circuit:
        circuit = await circuit_repo.get_by_id(
            db=db,
            circuit_id=circuit_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")

        project = await project_repo.get_by_id(
            db=db,
            project_id=circuit.project_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated project not found")

        return circuit

    async def _verify_review_access(
        self,
        db: AsyncSession,
        review_id: str,
        current_user: AuthenticatedUser,
    ) -> EngineeringDesignReview:
        review = await verification_repo.get_review(db=db, review_id=review_id)
        if not review:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design review not found")

        if current_user.tenant_id:
            if review.tenant_id != current_user.tenant_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design review not found")
        else:
            if review.tenant_id is not None or review.created_by != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design review not found")

        return review

    async def create_or_generate_review(
        self,
        db: AsyncSession,
        circuit_id: str,
        current_user: AuthenticatedUser,
    ) -> DesignReviewResponse:
        circuit = await self._verify_circuit_access(db=db, circuit_id=circuit_id, current_user=current_user)

        # 1. Fetch latest deterministic analysis
        analysis = await analysis_repo.get_latest_for_circuit(
            db=db,
            circuit_id=circuit.id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not analysis:
            from app.services.analysis_service import analysis_service
            analysis_resp = await analysis_service.run_analysis(db=db, circuit_id=circuit.id, current_user=current_user)
            analysis = await analysis_repo.get_latest_for_circuit(
                db=db,
                circuit_id=circuit.id,
                tenant_id=current_user.tenant_id,
                owner_id=current_user.id,
            )
            if not analysis:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to run analysis for review")

        # Circuit dictionary for deterministic engines
        circuit_dict = {
            "id": circuit.id,
            "version": circuit.version,
            "components": [
                {
                    "id": c.id,
                    "ref_des": c.ref_des,
                    "name": c.ref_des,
                    "component_type": c.component_type,
                    "value": c.value,
                    "package": c.package,
                    "rating": c.rating,
                    "pins": c.pins,
                }
                for c in circuit.components
            ],
            "nets": [{"id": n.id, "name": n.name, "net_type": n.net_type} for n in circuit.nets],
            "connections": [
                {"id": conn.id, "component_id": conn.component_id, "net_id": conn.net_id, "pin_number": conn.pin_number}
                for conn in circuit.connections
            ],
        }

        analysis_data = {
            "id": analysis.id,
            "circuit_version": analysis.circuit_version,
            "findings": analysis.findings,
            "calculations": analysis.calculations,
            "unknowns": analysis.unknowns,
            "summary": analysis.graph_summary if hasattr(analysis, "graph_summary") else {},
        }

        review_id = str(uuid.uuid4())

        # 2. Derive Failure Modes
        failure_modes = failure_analysis_engine.analyze_circuit(
            circuit_dict=circuit_dict,
            analysis_data=analysis_data,
            review_id=review_id,
            tenant_id=current_user.tenant_id,
        )

        # 3. Generate Verification Requirements and Test Points
        requirements, test_points = verification_requirement_generator.generate(
            circuit_dict=circuit_dict,
            analysis_data=analysis_data,
            failure_modes=failure_modes,
            review_id=review_id,
            tenant_id=current_user.tenant_id,
        )

        # 4. Compute Initial Status
        critical_findings = [f for f in analysis.findings if f.get("severity") == "CRITICAL"]
        if critical_findings:
            initial_status = DesignReviewStatus.BLOCKED.value
        elif not requirements:
            initial_status = DesignReviewStatus.VERIFIED.value
        else:
            initial_status = DesignReviewStatus.VERIFICATION_REQUIRED.value

        review = EngineeringDesignReview(
            id=review_id,
            tenant_id=current_user.tenant_id,
            project_id=circuit.project_id,
            circuit_id=circuit.id,
            circuit_revision=circuit.version,
            analysis_id=analysis.id,
            status=initial_status,
            created_by=current_user.id,
            metadata_={},
            failure_modes=failure_modes,
            verification_requirements=requirements,
            test_points=test_points,
            audit_events=[
                EngineeringReviewAuditEvent(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    tenant_id=current_user.tenant_id,
                    actor_id=current_user.id,
                    event_type="REVIEW_CREATED",
                    object_id=review_id,
                    previous_state=None,
                    new_state=initial_status,
                    reason=f"Generated design review bound to circuit revision {circuit.version} and analysis {analysis.id}",
                )
            ],
        )

        saved = await verification_repo.create_review(db=db, review=review)
        return await self.get_review(db=db, review_id=saved.id, current_user=current_user)

    async def get_review(
        self,
        db: AsyncSession,
        review_id: str,
        current_user: AuthenticatedUser,
    ) -> DesignReviewResponse:
        review = await self._verify_review_access(db=db, review_id=review_id, current_user=current_user)
        circuit = await circuit_repo.get_by_id(db=db, circuit_id=review.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        current_circuit_revision = circuit.version if circuit else review.circuit_revision

        is_stale = review.circuit_revision != current_circuit_revision
        current_status = review.status
        if is_stale and current_status != DesignReviewStatus.STALE.value:
            current_status = DesignReviewStatus.STALE.value
            await verification_repo.update_review_status(db=db, review=review, status=current_status)

        # Calculate evidence summary counts
        evidence_summary: dict[str, int] = {}
        for req in review.verification_requirements:
            for ev in req.evidence_items:
                evidence_summary[ev.status] = evidence_summary.get(ev.status, 0) + 1

        # Check unresolved findings count from latest analysis
        analysis = await analysis_repo.get_by_id(
            db=db,
            analysis_id=review.analysis_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        unresolved_count = len(analysis.findings) if analysis else 0

        # Consolidate unknowns
        all_unknowns: set[str] = set()
        for fm in review.failure_modes:
            all_unknowns.update(fm.unknowns)
        for req in review.verification_requirements:
            all_unknowns.update(req.unknowns)

        return DesignReviewResponse(
            id=review.id,
            tenant_id=review.tenant_id,
            project_id=review.project_id,
            circuit_id=review.circuit_id,
            circuit_revision=review.circuit_revision,
            analysis_id=review.analysis_id,
            status=current_status,
            created_by=review.created_by,
            created_at=review.created_at,
            updated_at=review.updated_at,
            metadata_=review.metadata_,
            failure_modes=[FailureModeResponse.model_validate(fm) for fm in review.failure_modes],
            verification_requirements=[
                VerificationRequirementResponse.model_validate(req) for req in review.verification_requirements
            ],
            test_points=[TestPointResponse.model_validate(tp) for tp in review.test_points],
            evidence_summary=evidence_summary,
            unresolved_findings_count=unresolved_count,
            unknowns=sorted(list(all_unknowns)),
            is_stale=is_stale,
        )

    async def get_verification_matrix(
        self,
        db: AsyncSession,
        review_id: str,
        current_user: AuthenticatedUser,
    ) -> VerificationMatrixResponse:
        review_resp = await self.get_review(db=db, review_id=review_id, current_user=current_user)

        rows: list[VerificationMatrixRow] = []
        satisfied = in_prog = unknown_cnt = blocked = failed = not_app = 0

        for req in review_resp.verification_requirements:
            st = req.status
            if st == VerificationStatus.SATISFIED.value:
                satisfied += 1
            elif st == VerificationStatus.IN_PROGRESS.value:
                in_prog += 1
            elif st == VerificationStatus.UNKNOWN.value:
                unknown_cnt += 1
            elif st == VerificationStatus.BLOCKED.value:
                blocked += 1
            elif st == VerificationStatus.FAILED.value:
                failed += 1
            elif st == VerificationStatus.NOT_APPLICABLE.value:
                not_app += 1

            latest_ev = req.evidence_items[-1].description if req.evidence_items else None
            rows.append(
                VerificationMatrixRow(
                    requirement_id=req.id,
                    requirement_code=req.code,
                    title=req.title,
                    reason=req.reason,
                    method=req.method,
                    operating_condition=req.operating_condition,
                    evidence_count=len(req.evidence_items),
                    latest_evidence_summary=latest_ev,
                    status=st,
                    is_mandatory=req.is_mandatory,
                    unknowns=req.unknowns,
                    affected_components=req.affected_components,
                    affected_nets=req.affected_nets,
                )
            )

        return VerificationMatrixResponse(
            review_id=review_resp.id,
            circuit_id=review_resp.circuit_id,
            circuit_revision=review_resp.circuit_revision,
            status=review_resp.status,
            total_requirements=len(rows),
            satisfied_count=satisfied,
            in_progress_count=in_prog,
            unknown_count=unknown_cnt,
            blocked_count=blocked,
            failed_count=failed,
            not_applicable_count=not_app,
            is_stale=review_resp.is_stale,
            matrix=rows,
        )

    async def add_evidence(
        self,
        db: AsyncSession,
        requirement_id: str,
        evidence_in: EvidenceCreate,
        current_user: AuthenticatedUser,
    ) -> EvidenceResponse:
        requirement = await verification_repo.get_requirement(db=db, requirement_id=requirement_id)
        if not requirement:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification requirement not found")

        review = await self._verify_review_access(db=db, review_id=requirement.review_id, current_user=current_user)

        # Stale review rejection
        circuit = await circuit_repo.get_by_id(db=db, circuit_id=review.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if circuit and review.circuit_revision != circuit.version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "REVIEW_STALE",
                    "message": f"Cannot add evidence: Review revision {review.circuit_revision} is stale against circuit revision {circuit.version}.",
                    "review_revision": review.circuit_revision,
                    "current_circuit_revision": circuit.version,
                },
            )

        meta = evidence_in.metadata or {}
        cal_status = meta.get("calibration_status")
        if not cal_status:
            cal_status = "UNKNOWN" if evidence_in.evidence_type.value == "MEASUREMENT" else "NOT_APPLICABLE"

        evidence = EngineeringEvidence(
            id=str(uuid.uuid4()),
            verification_requirement_id=requirement.id,
            review_id=review.id,
            tenant_id=current_user.tenant_id,
            evidence_type=evidence_in.evidence_type.value,
            source=evidence_in.source,
            description=evidence_in.description,
            value=evidence_in.value,
            unit=evidence_in.unit,
            reference=evidence_in.reference,
            status=EvidenceStatus.VALID.value,
            confidence=evidence_in.confidence,
            provided_by=current_user.id,
            provided_at=datetime.now(timezone.utc),
            source_id=meta.get("source_id"),
            instrument=meta.get("instrument"),
            instrument_model=meta.get("instrument_model"),
            instrument_serial=meta.get("instrument_serial"),
            calibration_reference=meta.get("calibration_reference"),
            calibration_status=cal_status,
            measurement_timestamp=datetime.now(timezone.utc) if evidence_in.evidence_type.value == "MEASUREMENT" else None,
            circuit_id=review.circuit_id,
            circuit_revision=review.circuit_revision,
            analysis_id=review.analysis_id,
            is_stale=False,
            metadata_=meta,
        )

        saved = await verification_repo.add_evidence(db=db, evidence=evidence)
        resp = EvidenceResponse.model_validate(saved)

        # Audit event
        await verification_repo.add_audit_event(
            db=db,
            audit_event=EngineeringReviewAuditEvent(
                id=str(uuid.uuid4()),
                review_id=review.id,
                tenant_id=current_user.tenant_id,
                actor_id=current_user.id,
                event_type="EVIDENCE_ADDED",
                object_id=saved.id,
                previous_state=None,
                new_state=saved.status,
                reason=f"Added {evidence_in.evidence_type} evidence from source {evidence_in.source}",
            ),
        )

        # Auto-advance requirement state to IN_PROGRESS if NOT_STARTED
        if requirement.status in [VerificationStatus.NOT_STARTED.value, VerificationStatus.UNKNOWN.value]:
            await verification_repo.update_requirement_status(
                db=db,
                requirement=requirement,
                status=VerificationStatus.IN_PROGRESS.value,
            )

        await self._recompute_review_status(db=db, review=review)
        return resp

    async def update_requirement_status(
        self,
        db: AsyncSession,
        requirement_id: str,
        status_in: RequirementStatusUpdate,
        current_user: AuthenticatedUser,
    ) -> VerificationRequirementResponse:
        requirement = await verification_repo.get_requirement(db=db, requirement_id=requirement_id)
        if not requirement:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification requirement not found")

        review = await self._verify_review_access(db=db, review_id=requirement.review_id, current_user=current_user)

        # Stale review rejection
        circuit = await circuit_repo.get_by_id(db=db, circuit_id=review.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if circuit and review.circuit_revision != circuit.version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "REVIEW_STALE",
                    "message": f"Cannot update requirement: Review revision {review.circuit_revision} does not match current circuit revision {circuit.version}.",
                    "review_revision": review.circuit_revision,
                    "current_circuit_revision": circuit.version,
                },
            )

        new_status = status_in.status.value
        old_status = requirement.status

        # Invariant 1: NOT_APPLICABLE requires reason
        if new_status == VerificationStatus.NOT_APPLICABLE.value and not status_in.not_applicable_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid engineering rationale is required when marking a requirement NOT_APPLICABLE.",
            )

        # Invariant 2: Cannot mark SATISFIED if UNKNOWN remains or evidence is completely absent for calculation/measurement
        if new_status == VerificationStatus.SATISFIED.value:
            if requirement.unknowns:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot mark requirement SATISFIED while unresolved engineering unknowns exist: {requirement.unknowns}",
                )
            if not requirement.evidence_items and requirement.method in [
                "MEASUREMENT",
                "BENCH_TEST",
                "DATASHEET_REVIEW",
            ]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot mark requirement SATISFIED without verifiable evidence for method {requirement.method}.",
                )

        updated = await verification_repo.update_requirement_status(
            db=db,
            requirement=requirement,
            status=new_status,
            not_applicable_reason=status_in.not_applicable_reason,
        )

        # Audit event
        await verification_repo.add_audit_event(
            db=db,
            audit_event=EngineeringReviewAuditEvent(
                id=str(uuid.uuid4()),
                review_id=review.id,
                tenant_id=current_user.tenant_id,
                actor_id=current_user.id,
                event_type="REQUIREMENT_STATUS_CHANGED",
                object_id=requirement.id,
                previous_state=old_status,
                new_state=new_status,
                reason=status_in.reason or status_in.not_applicable_reason,
            ),
        )

        await self._recompute_review_status(db=db, review=review)
        # Reload requirement
        refreshed = await verification_repo.get_requirement(db=db, requirement_id=requirement.id)
        return VerificationRequirementResponse.model_validate(refreshed)

    async def add_test_point(
        self,
        db: AsyncSession,
        review_id: str,
        test_point_in: TestPointCreate,
        current_user: AuthenticatedUser,
    ) -> TestPointResponse:
        review = await self._verify_review_access(db=db, review_id=review_id, current_user=current_user)

        circuit = await circuit_repo.get_by_id(db=db, circuit_id=review.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if circuit and review.circuit_revision != circuit.version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "REVIEW_STALE", "message": "Cannot add test points to a stale review."},
            )

        test_point = EngineeringTestPoint(
            id=str(uuid.uuid4()),
            review_id=review.id,
            tenant_id=current_user.tenant_id,
            code=test_point_in.code,
            target_net=test_point_in.target_net,
            target_component=test_point_in.target_component,
            measurement=test_point_in.measurement,
            expected_basis=test_point_in.expected_basis,
            instrumentation=test_point_in.instrumentation,
            operating_condition=test_point_in.operating_condition.value,
            related_requirement_id=test_point_in.related_requirement_id,
            created_at=datetime.now(timezone.utc),
        )

        saved = await verification_repo.add_test_point(db=db, test_point=test_point)

        # Audit event
        await verification_repo.add_audit_event(
            db=db,
            audit_event=EngineeringReviewAuditEvent(
                id=str(uuid.uuid4()),
                review_id=review.id,
                tenant_id=current_user.tenant_id,
                actor_id=current_user.id,
                event_type="TEST_POINT_CREATED",
                object_id=saved.id,
                previous_state=None,
                new_state="CREATED",
                reason=f"Added test point {test_point_in.code} ({test_point_in.measurement})",
            ),
        )

        return TestPointResponse.model_validate(saved)

    async def _recompute_review_status(
        self,
        db: AsyncSession,
        review: EngineeringDesignReview,
    ) -> str:
        # Reload review with latest requirements
        full_review = await verification_repo.get_review(db=db, review_id=review.id)
        if not full_review:
            return review.status

        # Check critical findings
        analysis = await analysis_repo.get_by_id(
            db=db,
            analysis_id=full_review.analysis_id,
            tenant_id=full_review.tenant_id,
            allow_unscoped=True,
        )
        critical_unresolved = any(f.get("severity") == "CRITICAL" for f in (analysis.findings if analysis else []))

        mandatory_reqs = [r for r in full_review.verification_requirements if r.is_mandatory]
        any_failed_or_blocked = any(r.status in [VerificationStatus.FAILED.value, VerificationStatus.BLOCKED.value] for r in mandatory_reqs)
        any_unknown = any(r.status == VerificationStatus.UNKNOWN.value for r in mandatory_reqs)
        all_satisfied_or_na = all(
            r.status in [VerificationStatus.SATISFIED.value, VerificationStatus.NOT_APPLICABLE.value]
            for r in mandatory_reqs
        )
        any_satisfied = any(r.status == VerificationStatus.SATISFIED.value for r in mandatory_reqs)

        if critical_unresolved or any_failed_or_blocked:
            new_status = DesignReviewStatus.BLOCKED.value
        elif all_satisfied_or_na and not any_unknown:
            new_status = DesignReviewStatus.VERIFIED.value
        elif any_satisfied or any(r.status == VerificationStatus.IN_PROGRESS.value for r in mandatory_reqs):
            new_status = DesignReviewStatus.PARTIALLY_VERIFIED.value
        else:
            new_status = DesignReviewStatus.VERIFICATION_REQUIRED.value

        if new_status != full_review.status:
            await verification_repo.update_review_status(db=db, review=full_review, status=new_status)
            await verification_repo.add_audit_event(
                db=db,
                audit_event=EngineeringReviewAuditEvent(
                    id=str(uuid.uuid4()),
                    review_id=full_review.id,
                    tenant_id=full_review.tenant_id,
                    actor_id="SYSTEM",
                    event_type="REVIEW_STATUS_CHANGED",
                    object_id=full_review.id,
                    previous_state=full_review.status,
                    new_state=new_status,
                    reason="Recomputed review status from constituent requirement states",
                ),
            )

        return new_status


verification_service = DesignReviewService()
