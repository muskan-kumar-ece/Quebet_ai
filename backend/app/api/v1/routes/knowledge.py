from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.db.provenance import EngineeringKnowledgeRecord, EngineeringSource
from app.models.schemas.provenance import (
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
    KnowledgeRecordResponse,
    KnowledgeSearchItemResponse,
    KnowledgeSearchResponse,
    SourceCreate,
    SourceResponse,
)
from app.repositories.knowledge_repo import KnowledgeRepo
from app.repositories.source_repo import SourceRepo
from app.services.knowledge_service import (
    EngineeringKnowledgeIngestionService,
    EngineeringKnowledgeRetrievalService,
)

router = APIRouter(prefix="/knowledge", tags=["Engineering Knowledge & Source Intelligence"])


# ============================================================================
# 1. SOURCES ENDPOINTS
# ============================================================================

@router.post("/sources", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_knowledge_source(
    payload: SourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Registers an authoritative engineering reference document with deterministic SHA-256 integrity digest."""
    repo = SourceRepo(db)
    source = await repo.create_source(
        source_type=payload.source_type,
        title=payload.title,
        publisher=payload.publisher,
        document_identifier=payload.document_identifier,
        revision=payload.revision,
        version=payload.version,
        publication_date=payload.publication_date,
        effective_date=payload.effective_date,
        uri=payload.uri,
        document_hash=payload.document_hash,
        trust_level=payload.trust_level,
        status=payload.status,
        tenant_id=current_user.tenant_id,
        metadata=payload.metadata,
    )
    return {"data": SourceResponse.model_validate(source)}


@router.get("/sources/{source_id}", response_model=dict[str, Any])
async def get_knowledge_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Retrieves an engineering reference source with IDOR defense and tenant isolation."""
    repo = SourceRepo(db)
    source = await repo.get_source(source_id=source_id, tenant_id=current_user.tenant_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source {source_id} not found",
        )
    return {"data": SourceResponse.model_validate(source)}


@router.get("/sources/{source_id}/records", response_model=dict[str, Any])
async def get_source_records(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Retrieves all atomic engineering knowledge records derived from this source."""
    repo = SourceRepo(db)
    source = await repo.get_source(source_id=source_id, tenant_id=current_user.tenant_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source {source_id} not found",
        )

    stmt = (
        select(EngineeringKnowledgeRecord)
        .options(selectinload(EngineeringKnowledgeRecord.source))
        .where(
            EngineeringKnowledgeRecord.source_id == source_id,
            or_(
                EngineeringKnowledgeRecord.tenant_id == current_user.tenant_id,
                EngineeringKnowledgeRecord.tenant_id.is_(None),
            ),
        )
    )
    res = await db.execute(stmt)
    records = res.scalars().all()
    return {"data": [KnowledgeRecordResponse.model_validate(r) for r in records]}


# ============================================================================
# 2. INGESTION ENDPOINT
# ============================================================================

@router.post("/ingest", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def ingest_source_and_parameters(
    payload: KnowledgeIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """
    Ingests an engineering source document and its extracted parameters.
    Executes unit normalization, contradiction detection, and vector store indexing.
    """
    service = EngineeringKnowledgeIngestionService(db)
    source_dict = payload.source.model_dump()
    params_dict = [p.model_dump() for p in payload.parameters]

    result = await service.ingest_source(
        source_data=source_dict,
        parameters=params_dict,
        tenant_id=current_user.tenant_id,
    )

    source_resp = SourceResponse.model_validate(result["source"])
    records_resp = [KnowledgeRecordResponse.model_validate(r) for r in result["knowledge_records"]]

    return {
        "data": {
            "source": source_resp,
            "knowledge_records": records_resp,
            "superseded_source_id": result["superseded_source_id"],
        }
    }


# ============================================================================
# 3. KNOWLEDGE RETRIEVAL & SEARCH ENDPOINTS
# ============================================================================

@router.get("/search", response_model=dict[str, Any])
async def search_knowledge(
    q: Optional[str] = Query(None, description="Keyword search query"),
    subject_identifier: Optional[str] = Query(None, description="Component or subject identifier"),
    parameter: Optional[str] = Query(None, description="Parameter name"),
    classification: Optional[str] = Query(None, description="Classification filter"),
    domain: Optional[str] = Query(None, description="Engineering domain filter"),
    source_id: Optional[str] = Query(None, description="Source ID filter"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """
    Retrieves grounded engineering knowledge records, ordered strictly by authoritative precedence:
    CURRENT AUTHORITATIVE SOURCE > HISTORICAL MEMORY > AI GENERATED CONTEXT.
    """
    retrieval_service = EngineeringKnowledgeRetrievalService(db)
    items = await retrieval_service.search_knowledge(
        tenant_id=current_user.tenant_id,
        query=q,
        subject_identifier=subject_identifier,
        parameter=parameter,
        classification=classification,
        domain=domain,
        source_id=source_id,
        limit=limit,
    )

    formatted_items = []
    for item in items:
        rec_model = KnowledgeRecordResponse.model_validate(item["record"])
        src_model = SourceResponse.model_validate(item["source"]) if item["source"] else None
        formatted_items.append(
            KnowledgeSearchItemResponse(
                record=rec_model,
                source=src_model,
                provenance_chain=item["provenance_chain"],
            )
        )

    return {
        "data": KnowledgeSearchResponse(
            total=len(formatted_items),
            items=formatted_items,
        )
    }


from app.models.schemas.component_intelligence import (
    ApplicabilityEvaluationRequest,
    ComponentIdentityResolutionRequest,
    OperatingValidationRequest,
)
from app.services.component_intelligence_service import (
    EngineeringComponentIntelligenceService,
)


# ============================================================================
# 4. COMPONENT INTELLIGENCE ENDPOINTS (Phase 3 Wave 2)
# ============================================================================

@router.post("/components/resolve", response_model=dict[str, Any])
async def resolve_component_identity(
    payload: ComponentIdentityResolutionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Deterministically resolves component identity, distinguishing RESOLVED, AMBIGUOUS, UNKNOWN, CONFLICTING."""
    service = EngineeringComponentIntelligenceService(db)
    res = await service.resolve_identity(
        query=payload.query,
        manufacturer=payload.manufacturer,
        part_number=payload.part_number,
        package=payload.package,
        tenant_id=current_user.tenant_id,
    )
    return {"data": res.model_dump()}


@router.get("/components/{part_number}", response_model=dict[str, Any])
@router.get("/components/{part_number}/profile", response_model=dict[str, Any])
async def get_component_profile(
    part_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Retrieves full structured component profile: pins, operating ranges, absolute maximums, and constraints."""
    service = EngineeringComponentIntelligenceService(db)
    profile = await service.get_component_profile(part_number=part_number, tenant_id=current_user.tenant_id)
    return {"data": profile.model_dump()}


@router.get("/components/{part_number}/pins", response_model=dict[str, Any])
async def get_component_pins(
    part_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Retrieves documented pins and pin electrical roles for a component."""
    service = EngineeringComponentIntelligenceService(db)
    profile = await service.get_component_profile(part_number=part_number, tenant_id=current_user.tenant_id)
    return {"data": [p.model_dump() for p in profile.pins]}


@router.get("/components/{part_number}/parameters", response_model=dict[str, Any])
async def get_component_parameters(
    part_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Retrieves electrical characteristics and thermal parameters for a component."""
    service = EngineeringComponentIntelligenceService(db)
    profile = await service.get_component_profile(part_number=part_number, tenant_id=current_user.tenant_id)
    return {
        "data": {
            "electrical": [p.model_dump() for p in profile.electrical_characteristics],
            "thermal": [p.model_dump() for p in profile.thermal_characteristics],
        }
    }


@router.get("/components/{part_number}/limits", response_model=dict[str, Any])
async def get_component_limits(
    part_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """
    Retrieves operating limits and absolute maximum ratings.
    SAFETY INVARIANT: Operating limits and absolute maximum ratings are strictly separated.
    """
    service = EngineeringComponentIntelligenceService(db)
    profile = await service.get_component_profile(part_number=part_number, tenant_id=current_user.tenant_id)
    return {
        "data": {
            "operating_ranges": [p.model_dump() for p in profile.operating_ranges],
            "absolute_maximums": [p.model_dump() for p in profile.absolute_maximums],
        }
    }


@router.get("/components/{part_number}/references", response_model=dict[str, Any])
async def get_component_references(
    part_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Retrieves documented reference designs and application constraints."""
    service = EngineeringComponentIntelligenceService(db)
    profile = await service.get_component_profile(part_number=part_number, tenant_id=current_user.tenant_id)
    return {
        "data": {
            "application_constraints": [c.model_dump() for c in profile.application_constraints],
            "reference_designs": [r.model_dump() for r in profile.reference_designs],
        }
    }


@router.post("/components/{part_number}/validate-operating", response_model=dict[str, Any])
async def validate_component_operating_point(
    part_number: str,
    payload: OperatingValidationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """
    Validates whether an operating point satisfies recommended operating ranges.
    Prevents confusing Absolute Maximum with safe operating condition.
    """
    service = EngineeringComponentIntelligenceService(db)
    res = await service.validate_operating_point(
        part_number=part_number,
        parameter=payload.parameter,
        value=payload.value,
        unit=payload.unit,
        conditions=payload.conditions,
        tenant_id=current_user.tenant_id,
    )
    return {"data": res.model_dump()}


@router.post("/components/{part_number}/applicability", response_model=dict[str, Any])
async def evaluate_component_applicability(
    part_number: str,
    payload: ApplicabilityEvaluationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Evaluates categorical applicability of component specifications to an operating context."""
    service = EngineeringComponentIntelligenceService(db)
    res = await service.evaluate_applicability(
        part_number=part_number,
        context=payload.context,
        tenant_id=current_user.tenant_id,
    )
    return {"data": res}


# ============================================================================
# 5. KNOWLEDGE RECORD DETAIL (IDOR PROTECTED)
# ============================================================================

@router.get("/{knowledge_id}", response_model=dict[str, Any])
async def get_knowledge_record(
    knowledge_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Retrieves an atomic engineering knowledge record with IDOR defense and tenant isolation."""
    repo = KnowledgeRepo(db)
    rec = await repo.get_knowledge_record(knowledge_id=knowledge_id, tenant_id=current_user.tenant_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge record {knowledge_id} not found",
        )
    return {"data": KnowledgeRecordResponse.model_validate(rec)}
