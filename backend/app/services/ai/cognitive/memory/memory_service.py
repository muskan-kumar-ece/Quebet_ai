from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.cognitive import (
    EngineeringDecisionBrief,
    EngineeringMemoryFeedback,
    EngineeringMemoryRecord,
    EngineeringReflection,
    HistoricalOutcome,
    MemoryFeedbackType,
    MemoryType,
)
from app.models.db.decision import (
    EngineeringDecisionRecord,
    EngineeringAssumption,
    EngineeringRequirement,
)
from app.models.db.verification import (
    EngineeringEvidence,
    EngineeringVerificationRequirement,
    EvidenceStatus,
    VerificationStatus,
)
from app.models.db.analysis import CircuitAnalysis
from app.models.db.assumption import Assumption

from app.models.schemas.cognitive import (
    EngineeringMemoryFeedbackResponse,
    EngineeringMemoryRecordResponse,
    MemoryFeedbackRequest,
    MemoryRecordCreateRequest,
)


class EngineeringMemoryService:
    """
    Manages creation, validation, and provenance enforcement for engineering memories.

    INVARIANTS:
    - HISTORICAL MEMORY != ENGINEERING TRUTH
    - A memory record without valid provenance must not enter the engineering memory store.
    - AI actors cannot fabricate memories without actual verified source records.
    - Multi-tenant isolation is strictly enforced.
    """

    SUPPORTED_SOURCE_ENTITIES = {
        "EngineeringDecisionRecord": EngineeringDecisionRecord,
        "EngineeringVerificationRequirement": EngineeringVerificationRequirement,
        "EngineeringEvidence": EngineeringEvidence,
        "CircuitAnalysis": CircuitAnalysis,
        "EngineeringAssumption": EngineeringAssumption,
        "Assumption": Assumption,
        "EngineeringRequirement": EngineeringRequirement,
        "EngineeringReflection": EngineeringReflection,
        "EngineeringDecisionBrief": EngineeringDecisionBrief,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_memory_record(
        self,
        tenant_id: str,
        request: MemoryRecordCreateRequest,
    ) -> EngineeringMemoryRecord:
        """
        Creates an EngineeringMemoryRecord after strictly verifying authoritative source provenance.
        """
        # 1. Validate entity type support
        model_cls = self.SUPPORTED_SOURCE_ENTITIES.get(request.source_entity_type)
        if not model_cls:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "INVALID_MEMORY_PROVENANCE",
                    "message": f"Unsupported source entity type '{request.source_entity_type}'. Memory must reference an authoritative engineering entity.",
                },
            )

        # 2. Verify source entity existence and tenant binding in the database
        query = select(model_cls).where(
            model_cls.id == request.source_entity_id,
            model_cls.tenant_id == tenant_id,
        )
        res = await self.db.execute(query)
        entity = res.scalar_one_or_none()

        if not entity:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "INVALID_MEMORY_PROVENANCE",
                    "message": f"Source entity {request.source_entity_type} with ID '{request.source_entity_id}' not found or belongs to another tenant.",
                },
            )

        # 3. Check for AI actor attempting to fabricate verification outcomes without valid verified status
        actor = (request.actor or "").lower()
        if actor in ["ai", "model", "llm", "copilot"]:
            if request.memory_type == MemoryType.VERIFICATION_LESSON.value and request.historical_outcome == HistoricalOutcome.VERIFIED_SUCCESS.value:
                # Must be backed by an actually verified requirement or evidence
                if request.source_entity_type == "EngineeringVerificationRequirement":
                    req_status = getattr(entity, "status", None)
                    if req_status != VerificationStatus.VERIFIED.value:
                        raise HTTPException(
                            status_code=422,
                            detail={
                                "error": "INVALID_MEMORY_PROVENANCE",
                                "message": "AI actor cannot assert verified historical outcome for unverified requirement.",
                            },
                        )
                elif request.source_entity_type == "EngineeringEvidence":
                    evi_status = getattr(entity, "status", None)
                    if evi_status != EvidenceStatus.VALIDATED.value:
                        raise HTTPException(
                            status_code=422,
                            detail={
                                "error": "INVALID_MEMORY_PROVENANCE",
                                "message": "AI actor cannot assert verified historical outcome for unvalidated evidence.",
                            },
                        )

        # 4. Create memory record
        memory_record = EngineeringMemoryRecord(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            project_id=request.project_id,
            system_id=request.system_id,
            circuit_id=request.circuit_id,
            memory_type=request.memory_type,
            source_entity_type=request.source_entity_type,
            source_entity_id=request.source_entity_id,
            engineering_domain=request.engineering_domain or "general",
            summary=request.summary,
            applicability_conditions=request.applicability_conditions or {},
            revision_context=request.revision_context or {},
            historical_outcome=request.historical_outcome,
            is_conflicting=False,
            conflict_details={},
        )
        self.db.add(memory_record)
        await self.db.commit()
        await self.db.refresh(memory_record)
        return memory_record

    async def get_memory_record(
        self,
        tenant_id: str,
        memory_id: str,
    ) -> EngineeringMemoryRecord:
        """
        Retrieves a memory record by ID with strict tenant isolation.
        """
        query = select(EngineeringMemoryRecord).where(
            EngineeringMemoryRecord.id == memory_id,
            EngineeringMemoryRecord.tenant_id == tenant_id,
        )
        res = await self.db.execute(query)
        record = res.scalar_one_or_none()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Engineering memory record '{memory_id}' not found.",
            )
        return record

    async def list_project_memories(
        self,
        tenant_id: str,
        project_id: str,
    ) -> List[EngineeringMemoryRecord]:
        """
        Lists all memories for a project within tenant.
        """
        query = (
            select(EngineeringMemoryRecord)
            .where(
                EngineeringMemoryRecord.tenant_id == tenant_id,
                EngineeringMemoryRecord.project_id == project_id,
            )
            .order_by(EngineeringMemoryRecord.created_at.desc())
        )
        res = await self.db.execute(query)
        return list(res.scalars().all())

    async def record_feedback(
        self,
        tenant_id: str,
        memory_id: str,
        request: MemoryFeedbackRequest,
    ) -> EngineeringMemoryFeedback:
        """
        Records human feedback on a surfaced historical memory.
        Updates retrieval preference without modifying the underlying authoritative source.
        """
        # Ensure memory exists in this tenant
        memory = await self.get_memory_record(tenant_id, memory_id)

        feedback = EngineeringMemoryFeedback(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            memory_id=memory.id,
            engineer_identity=request.engineer_identity or "Human Engineer",
            feedback_type=request.feedback_type,
            notes=request.notes,
        )
        self.db.add(feedback)
        await self.db.commit()
        await self.db.refresh(feedback)
        return feedback

    async def get_feedback_for_memory(
        self,
        tenant_id: str,
        memory_id: str,
    ) -> List[EngineeringMemoryFeedback]:
        """
        Retrieves feedback records for a memory.
        """
        query = (
            select(EngineeringMemoryFeedback)
            .where(
                EngineeringMemoryFeedback.tenant_id == tenant_id,
                EngineeringMemoryFeedback.memory_id == memory_id,
            )
            .order_by(EngineeringMemoryFeedback.created_at.desc())
        )
        res = await self.db.execute(query)
        return list(res.scalars().all())
