from typing import Any, Dict, List, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.cognitive import (
    EngineeringMemoryFeedback,
    EngineeringMemoryRecord,
    MemoryFeedbackType,
)
from app.models.schemas.cognitive import (
    EngineeringMemoryFeedbackResponse,
    EngineeringMemoryRecordResponse,
    MemoryRetrievalRequest,
    MemoryRetrievalResponse,
    SurfacedMemoryItemResponse,
)
from app.services.ai.cognitive.memory.applicability_filter import (
    EngineeringApplicabilityFilter,
)


class EngineeringMemoryRetrievalService:
    """
    Contextual memory retrieval service with deterministic applicability filtering.

    INVARIANTS:
    - HISTORICAL MEMORY != ENGINEERING TRUTH
    - CURRENT AUTHORITATIVE SOURCE > HISTORICAL MEMORY
    - HISTORICAL VERIFICATION != CURRENT VERIFICATION
    - ZERO SYNTHETIC SCORING (no score, no confidence_percentage, no relevance_percentage)
    - STRICT TENANT ISOLATION
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def retrieve_contextual_memories(
        self,
        tenant_id: str,
        request: MemoryRetrievalRequest,
    ) -> MemoryRetrievalResponse:
        """
        Retrieves historical engineering memories and evaluates applicability deterministically.
        """
        # 1. Fetch candidate memories strictly scoped to this tenant (capped to prevent unbounded candidate load)
        query = (
            select(EngineeringMemoryRecord)
            .where(EngineeringMemoryRecord.tenant_id == tenant_id)
            .order_by(EngineeringMemoryRecord.created_at.desc())
            .limit(200)
        )
        res = await self.db.execute(query)
        candidates = list(res.scalars().all())

        # 2. Fetch all negative feedbacks in tenant to account for engineer preferences
        fb_query = select(EngineeringMemoryFeedback).where(
            EngineeringMemoryFeedback.tenant_id == tenant_id,
            EngineeringMemoryFeedback.feedback_type.in_([
                MemoryFeedbackType.NOT_APPLICABLE.value,
                MemoryFeedbackType.NOT_RELEVANT.value,
                MemoryFeedbackType.INCORRECT_HISTORY.value,
            ]),
        )
        fb_res = await self.db.execute(fb_query)
        negative_feedbacks = {fb.memory_id for fb in fb_res.scalars().all()}

        # 3. Context dictionary for applicability filter
        current_context: Dict[str, Any] = {
            "engineering_domain": request.engineering_domain,
            "component_family": request.component_family,
            "voltage_domain": request.voltage_domain,
            "current_range": request.current_range,
            "temperature_range": request.temperature_range,
            "frequency_range": request.frequency_range,
            "circuit_type": request.circuit_type,
            "operating_mode": request.operating_mode,
            "current_parameters": request.current_parameters or {},
        }

        surfaced_items: List[SurfacedMemoryItemResponse] = []

        for mem in candidates:
            has_neg_fb = mem.id in negative_feedbacks

            # Run deterministic applicability evaluation
            (
                applicability,
                why_surfaced,
                current_relevance,
                is_conflicting,
                conflict_details,
                warnings,
            ) = EngineeringApplicabilityFilter.evaluate(
                memory=mem,
                current_context=current_context,
                has_negative_feedback=has_neg_fb,
            )

            # Build memory record response
            mem_resp = EngineeringMemoryRecordResponse(
                id=mem.id,
                tenant_id=mem.tenant_id,
                memory_type=mem.memory_type,
                source_entity_type=mem.source_entity_type,
                source_entity_id=mem.source_entity_id,
                project_id=mem.project_id,
                system_id=mem.system_id,
                circuit_id=mem.circuit_id,
                engineering_domain=mem.engineering_domain,
                summary=mem.summary,
                applicability_conditions=mem.applicability_conditions or {},
                revision_context=mem.revision_context or {},
                historical_outcome=mem.historical_outcome,
                is_conflicting=is_conflicting,
                conflict_details=conflict_details,
                created_at=mem.created_at,
                updated_at=mem.updated_at,
            )

            item = SurfacedMemoryItemResponse(
                memory=mem_resp,
                applicability=applicability.value,
                why_surfaced=why_surfaced,
                historical_outcome=mem.historical_outcome,
                current_relevance=current_relevance,
                is_conflicting=is_conflicting,
                conflict_details=conflict_details,
                warnings=warnings,
            )
            surfaced_items.append(item)

        # Order items deterministically: APPLICABLE first, then POTENTIALLY_APPLICABLE, UNKNOWN, NOT_APPLICABLE last
        order_map = {
            "APPLICABLE": 0,
            "POTENTIALLY_APPLICABLE": 1,
            "UNKNOWN": 2,
            "NOT_APPLICABLE": 3,
        }
        surfaced_items.sort(key=lambda x: (order_map.get(x.applicability, 4), -x.memory.created_at.timestamp()))

        limit = request.limit or 20
        surfaced_items = surfaced_items[:limit]

        return MemoryRetrievalResponse(
            project_id=request.project_id,
            total_surfaced=len(surfaced_items),
            memories=surfaced_items,
            retrieval_notes="Contextual historical memories retrieved and deterministically evaluated. Historical experience is advisory.",
        )
