from typing import Any, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.analysis import CircuitAnalysis
from app.models.db.component import Component
from app.models.db.proposal import EngineeringProposal
from app.models.db.provenance import EngineeringKnowledgeRecord
from app.models.db.verification import EngineeringDesignReview, EngineeringVerificationRequirement


class KnowledgeImpactService:
    """
    Evaluates the downstream engineering blast radius when a Knowledge Record is changed or superseded.
    Identifies affected components, analyses, findings, verification requirements, design reviews, and proposals.
    Strictly preserves historical immutability: past analyses and reviews are NEVER mutated silently.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def evaluate_knowledge_impact(
        self,
        knowledge_id: str,
        tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        # 1. Fetch the knowledge record
        stmt = select(EngineeringKnowledgeRecord).where(EngineeringKnowledgeRecord.id == knowledge_id)
        if tenant_id:
            stmt = stmt.where(
                or_(
                    EngineeringKnowledgeRecord.tenant_id == tenant_id,
                    EngineeringKnowledgeRecord.tenant_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            raise ValueError(f"Knowledge record {knowledge_id} not found")

        subject = record.subject_identifier
        param = record.parameter

        # 2. Identify affected components in projects
        comp_stmt = select(Component).where(
            or_(
                Component.ref_des.ilike(f"%{subject}%"),
                Component.value.ilike(f"%{subject}%"),
                Component.part_number.ilike(f"%{subject}%"),
                Component.package.ilike(f"%{subject}%"),
            )
        )
        comp_res = await self.db.execute(comp_stmt)
        affected_comps = list(comp_res.scalars().all())
        affected_comp_ids = [c.id for c in affected_comps]
        affected_circuit_ids = list(set(c.circuit_id for c in affected_comps))

        # 3. Identify affected analyses referencing this subject/knowledge in calculations or findings
        affected_analyses: list[str] = []
        affected_findings: list[str] = []

        if affected_circuit_ids:
            ana_stmt = (
                select(CircuitAnalysis)
                .where(CircuitAnalysis.circuit_id.in_(affected_circuit_ids))
                .order_by(CircuitAnalysis.created_at.desc())
            )
            ana_res = await self.db.execute(ana_stmt)
            analyses = ana_res.scalars().all()

            for ana in analyses:
                is_affected = False
                for finding in (ana.findings or []):
                    # Check if finding relates to this subject or rule
                    rule_id = finding.get("rule_id", "")
                    comps = finding.get("affected_components", [])
                    k_ids = finding.get("knowledge_ids", [])
                    if knowledge_id in k_ids or any(c in affected_comp_ids for c in comps):
                        affected_findings.append(finding.get("id") or f"{ana.id}-{rule_id}")
                        is_affected = True

                if is_affected or any(
                    subject.lower() in str(calc).lower() for calc in (ana.calculations or [])
                ):
                    affected_analyses.append(ana.id)

        # 4. Identify affected verification requirements
        affected_requirements: list[str] = []
        if affected_findings:
            vr_stmt = select(EngineeringVerificationRequirement).where(
                EngineeringVerificationRequirement.related_finding_id.in_(affected_findings)
            )
            vr_res = await self.db.execute(vr_stmt)
            for req in vr_res.scalars().all():
                affected_requirements.append(req.id)

        # 5. Identify affected design reviews
        affected_reviews: list[str] = []
        if affected_analyses:
            dr_stmt = select(EngineeringDesignReview).where(
                EngineeringDesignReview.analysis_id.in_(affected_analyses)
            )
            dr_res = await self.db.execute(dr_stmt)
            for dr in dr_res.scalars().all():
                affected_reviews.append(dr.id)

        # 6. Identify affected proposals
        affected_proposals: list[str] = []
        if affected_circuit_ids:
            prop_stmt = select(EngineeringProposal).where(
                EngineeringProposal.circuit_id.in_(affected_circuit_ids),
                EngineeringProposal.status.in_(["PROPOSED", "IN_REVIEW"]),
            )
            prop_res = await self.db.execute(prop_stmt)
            for prop in prop_res.scalars().all():
                affected_proposals.append(prop.id)

        recommendation = (
            f"Knowledge record '{subject}.{param}' status is '{record.status}'. "
            f"{len(affected_analyses)} historical analyses depended on this parameter. "
            f"Historical records remain immutable. Recommend running fresh analysis on active circuits."
        )

        return {
            "knowledge_id": knowledge_id,
            "parameter": param,
            "subject_identifier": subject,
            "status": record.status,
            "affected_components": affected_comp_ids,
            "affected_analyses": list(set(affected_analyses)),
            "affected_findings": list(set(affected_findings)),
            "affected_verification_requirements": list(set(affected_requirements)),
            "affected_design_reviews": list(set(affected_reviews)),
            "affected_proposals": list(set(affected_proposals)),
            "recommendation": recommendation,
        }
