from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db.verification import (
    EngineeringDesignReview,
    EngineeringEvidence,
    EngineeringFailureMode,
    EngineeringReviewAuditEvent,
    EngineeringTestPoint,
    EngineeringVerificationRequirement,
)


class VerificationRepository:
    """Repository for Design Reviews, Failure Modes, Verification Requirements, Evidence, and Test Points."""

    async def create_review(
        self,
        db: AsyncSession,
        review: EngineeringDesignReview,
    ) -> EngineeringDesignReview:
        db.add(review)
        await db.commit()
        await db.refresh(review)
        return review

    async def get_review(
        self,
        db: AsyncSession,
        review_id: str,
    ) -> EngineeringDesignReview | None:
        stmt = (
            select(EngineeringDesignReview)
            .where(
                EngineeringDesignReview.id == review_id,
                EngineeringDesignReview.deleted_at.is_(None),
            )
            .options(
                selectinload(EngineeringDesignReview.failure_modes),
                selectinload(EngineeringDesignReview.verification_requirements).selectinload(
                    EngineeringVerificationRequirement.evidence_items
                ),
                selectinload(EngineeringDesignReview.test_points),
                selectinload(EngineeringDesignReview.audit_events),
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_latest_review_for_circuit(
        self,
        db: AsyncSession,
        circuit_id: str,
    ) -> EngineeringDesignReview | None:
        stmt = (
            select(EngineeringDesignReview)
            .where(
                EngineeringDesignReview.circuit_id == circuit_id,
                EngineeringDesignReview.deleted_at.is_(None),
            )
            .order_by(EngineeringDesignReview.created_at.desc())
            .options(
                selectinload(EngineeringDesignReview.failure_modes),
                selectinload(EngineeringDesignReview.verification_requirements).selectinload(
                    EngineeringVerificationRequirement.evidence_items
                ),
                selectinload(EngineeringDesignReview.test_points),
                selectinload(EngineeringDesignReview.audit_events),
            )
        )
        res = await db.execute(stmt)
        return res.scalars().first()

    async def update_review_status(
        self,
        db: AsyncSession,
        review: EngineeringDesignReview,
        status: str,
    ) -> EngineeringDesignReview:
        review.status = status
        review.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(review)
        return review

    async def get_requirement(
        self,
        db: AsyncSession,
        requirement_id: str,
    ) -> EngineeringVerificationRequirement | None:
        stmt = (
            select(EngineeringVerificationRequirement)
            .where(EngineeringVerificationRequirement.id == requirement_id)
            .options(
                selectinload(EngineeringVerificationRequirement.evidence_items),
                selectinload(EngineeringVerificationRequirement.review),
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def update_requirement_status(
        self,
        db: AsyncSession,
        requirement: EngineeringVerificationRequirement,
        status: str,
        not_applicable_reason: str | None = None,
    ) -> EngineeringVerificationRequirement:
        requirement.status = status
        if not_applicable_reason is not None:
            requirement.not_applicable_reason = not_applicable_reason
        requirement.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(requirement)
        return requirement

    async def add_evidence(
        self,
        db: AsyncSession,
        evidence: EngineeringEvidence,
    ) -> EngineeringEvidence:
        db.add(evidence)
        await db.commit()
        await db.refresh(evidence)
        return evidence

    async def add_test_point(
        self,
        db: AsyncSession,
        test_point: EngineeringTestPoint,
    ) -> EngineeringTestPoint:
        db.add(test_point)
        await db.commit()
        await db.refresh(test_point)
        return test_point

    async def add_audit_event(
        self,
        db: AsyncSession,
        audit_event: EngineeringReviewAuditEvent,
    ) -> EngineeringReviewAuditEvent:
        db.add(audit_event)
        await db.commit()
        await db.refresh(audit_event)
        return audit_event

    async def get_audit_events(
        self,
        db: AsyncSession,
        review_id: str,
    ) -> list[EngineeringReviewAuditEvent]:
        stmt = (
            select(EngineeringReviewAuditEvent)
            .where(EngineeringReviewAuditEvent.review_id == review_id)
            .order_by(EngineeringReviewAuditEvent.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())


verification_repo = VerificationRepository()
