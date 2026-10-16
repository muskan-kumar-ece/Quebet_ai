from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.db.provenance import EngineeringSource
from app.models.schemas.provenance import (
    AnalysisTraceabilityResponse,
    EvidenceTraceabilityResponse,
    FindingTraceabilityResponse,
    KnowledgeApplicabilityRequest,
    KnowledgeApplicabilityResponse,
    KnowledgeImpactResponse,
    KnowledgeRecordCreate,
    KnowledgeRecordResponse,
    KnowledgeSupersedeRequest,
    RequirementTraceabilityResponse,
    SourceCreate,
    SourceResponse,
    SourceSupersedeRequest,
)
from app.repositories.knowledge_repo import KnowledgeRepo
from app.repositories.source_repo import SourceRepo
from app.services.ai.verification.applicability_engine import KnowledgeApplicabilityEngine
from app.services.ai.verification.knowledge_impact_service import KnowledgeImpactService
from app.services.ai.verification.traceability_service import TraceabilityService

router = APIRouter(tags=["Engineering Knowledge & Traceability"])


# ============================================================================
# 1. SOURCES API
# ============================================================================

@router.post("/sources", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Registers an authoritative engineering reference document."""
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
async def get_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Retrieves an engineering reference source with tenant isolation."""
    repo = SourceRepo(db)
    source = await repo.get_source(source_id=source_id, tenant_id=current_user.tenant_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source {source_id} not found",
        )
    return {"data": SourceResponse.model_validate(source)}


@router.get("/sources/{source_id}/versions", response_model=dict[str, Any])
async def get_source_versions(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Lists the revision lineage and superseded versions for a source document."""
    repo = SourceRepo(db)
    source = await repo.get_source(source_id=source_id, tenant_id=current_user.tenant_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source {source_id} not found",
        )
    versions = await repo.list_versions(source_id=source_id, tenant_id=current_user.tenant_id)
    return {"data": [SourceResponse.model_validate(v) for v in versions]}


@router.post("/sources/{source_id}/supersede", response_model=dict[str, Any])
async def supersede_source(
    source_id: str,
    payload: SourceSupersedeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Marks an existing source as SUPERSEDED and creates a new linked version."""
    repo = SourceRepo(db)
    source = await repo.get_source(source_id=source_id, tenant_id=current_user.tenant_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source {source_id} not found",
        )
    new_source = await repo.supersede_source(
        old_source_id=source_id,
        new_source_data=payload.new_source.model_dump(),
        reason=payload.reason,
        tenant_id=current_user.tenant_id,
    )
    return {"data": SourceResponse.model_validate(new_source)}


# ============================================================================
# 2. KNOWLEDGE RECORDS API
# ============================================================================

@router.post("/knowledge", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_knowledge_record(
    payload: KnowledgeRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Records an atomic verified engineering fact or component rating."""
    repo = KnowledgeRepo(db)
    rec = await repo.create_knowledge_record(
        subject_identifier=payload.subject_identifier,
        parameter=payload.parameter,
        value=payload.value,
        unit=payload.unit,
        conditions=payload.conditions,
        valid_range=payload.valid_range,
        domain=payload.domain,
        subject_type=payload.subject_type,
        source_id=payload.source_id,
        classification=payload.classification,
        raw_value=payload.raw_value,
        normalized_value=payload.normalized_value,
        source_location=payload.source_location,
        is_conflicting=payload.is_conflicting,
        conflict_details=payload.conflict_details,
        status=payload.status,
        provenance=payload.provenance,
        tenant_id=current_user.tenant_id,
    )
    return {"data": KnowledgeRecordResponse.model_validate(rec)}


@router.get("/knowledge/{knowledge_id}", response_model=dict[str, Any])
async def get_knowledge_record(
    knowledge_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Retrieves a single engineering knowledge record."""
    repo = KnowledgeRepo(db)
    rec = await repo.get_knowledge_record(knowledge_id=knowledge_id, tenant_id=current_user.tenant_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge record {knowledge_id} not found",
        )
    return {"data": KnowledgeRecordResponse.model_validate(rec)}


@router.get("/knowledge/{knowledge_id}/provenance", response_model=dict[str, Any])
async def get_knowledge_provenance(
    knowledge_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Returns the provenance metadata and authoritative source supporting a knowledge record."""
    repo = KnowledgeRepo(db)
    rec = await repo.get_knowledge_record(knowledge_id=knowledge_id, tenant_id=current_user.tenant_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge record {knowledge_id} not found",
        )
    source_resp = SourceResponse.model_validate(rec.source) if rec.source else None
    return {
        "data": {
            "knowledge_id": rec.id,
            "subject_identifier": rec.subject_identifier,
            "parameter": rec.parameter,
            "value": rec.value,
            "unit": rec.unit,
            "status": rec.status,
            "provenance": rec.provenance,
            "conditions": rec.conditions,
            "source": source_resp,
        }
    }


@router.post("/knowledge/{knowledge_id}/supersede", response_model=dict[str, Any])
async def supersede_knowledge_record(
    knowledge_id: str,
    payload: KnowledgeSupersedeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Supersedes a knowledge record without deleting historical record."""
    repo = KnowledgeRepo(db)
    rec = await repo.get_knowledge_record(knowledge_id=knowledge_id, tenant_id=current_user.tenant_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge record {knowledge_id} not found",
        )
    new_rec = await repo.supersede_record(
        old_record_id=knowledge_id,
        new_data=payload.new_record.model_dump(),
        reason=payload.reason,
        tenant_id=current_user.tenant_id,
    )
    return {"data": KnowledgeRecordResponse.model_validate(new_rec)}


@router.post("/knowledge/{knowledge_id}/applicability", response_model=dict[str, Any])
async def check_knowledge_applicability(
    knowledge_id: str,
    payload: KnowledgeApplicabilityRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Evaluates whether this knowledge record applies to a given operating context."""
    repo = KnowledgeRepo(db)
    rec = await repo.get_knowledge_record(knowledge_id=knowledge_id, tenant_id=current_user.tenant_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge record {knowledge_id} not found",
        )

    res = KnowledgeApplicabilityEngine.evaluate(
        conditions=rec.conditions,
        context=payload.context,
    )
    return {
        "data": KnowledgeApplicabilityResponse(
            knowledge_id=rec.id,
            applicability=res["applicability"],
            reasons=res["reasons"],
            evaluated_conditions=res["evaluated_conditions"],
            missing_conditions=res["missing_conditions"],
        )
    }


# ============================================================================
# 3. TRACEABILITY GRAPH API
# ============================================================================

@router.get("/analyses/{analysis_id}/traceability", response_model=dict[str, Any])
async def get_analysis_traceability(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Returns the complete provenance chain for a deterministic circuit analysis."""
    service = TraceabilityService(db)
    try:
        data = await service.get_analysis_traceability(
            analysis_id=analysis_id,
            tenant_id=current_user.tenant_id,
        )
        return {
            "data": AnalysisTraceabilityResponse(
                analysis_id=data["analysis_id"],
                circuit_id=data["circuit_id"],
                circuit_revision=data["circuit_revision"],
                engine_versions=data["engine_versions"],
                rule_set_version=data["rule_set_version"],
                knowledge_snapshot_id=data["knowledge_snapshot_id"],
                input_values=data["input_values"],
                assumptions=data["assumptions"],
                calculation_methods=data["calculation_methods"],
                knowledge_records=[KnowledgeRecordResponse.model_validate(k) for k in data["knowledge_records"]],
                sources=[SourceResponse.model_validate(s) for s in data["sources"]],
                created_at=data["created_at"],
            )
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/findings/{finding_id}/traceability", response_model=dict[str, Any])
async def get_finding_traceability(
    finding_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Traces a rule finding back to the exact physical equations, component specs, and sources."""
    service = TraceabilityService(db)
    try:
        data = await service.get_finding_traceability(
            finding_id=finding_id,
            tenant_id=current_user.tenant_id,
        )
        return {
            "data": FindingTraceabilityResponse(
                finding_id=data["finding_id"],
                rule_id=data["rule_id"],
                analysis_id=data["analysis_id"],
                affected_components=data["affected_components"],
                affected_nets=data["affected_nets"],
                knowledge_records=[KnowledgeRecordResponse.model_validate(k) for k in data["knowledge_records"]],
                sources=[SourceResponse.model_validate(s) for s in data["sources"]],
                input_values=data["input_values"],
                calculation_result=data["calculation_result"],
            )
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/verification-requirements/{requirement_id}/traceability", response_model=dict[str, Any])
async def get_requirement_traceability(
    requirement_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Traces a verification requirement to its generating finding, knowledge records, and evidence."""
    service = TraceabilityService(db)
    try:
        data = await service.get_requirement_traceability(
            requirement_id=requirement_id,
            tenant_id=current_user.tenant_id,
        )
        return {
            "data": RequirementTraceabilityResponse(
                requirement_id=data["requirement_id"],
                requirement_code=data["requirement_code"],
                related_finding_id=data["related_finding_id"],
                related_rule_id=data["related_rule_id"],
                knowledge_records=[KnowledgeRecordResponse.model_validate(k) for k in data["knowledge_records"]],
                sources=[SourceResponse.model_validate(s) for s in data["sources"]],
                evidence_count=data["evidence_count"],
            )
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/evidence/{evidence_id}/traceability", response_model=dict[str, Any])
async def get_evidence_traceability(
    evidence_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Retrieves full calibration, instrument, document, and revision provenance for an evidence item."""
    service = TraceabilityService(db)
    try:
        data = await service.get_evidence_traceability(
            evidence_id=evidence_id,
            tenant_id=current_user.tenant_id,
        )
        return {
            "data": EvidenceTraceabilityResponse(
                evidence_id=data["evidence_id"],
                requirement_id=data["requirement_id"],
                evidence_type=data["evidence_type"],
                source=data["source"],
                source_id=data["source_id"],
                source_document=SourceResponse.model_validate(data["source_document"]) if data["source_document"] else None,
                instrument=data["instrument"],
                instrument_model=data["instrument_model"],
                instrument_serial=data["instrument_serial"],
                calibration_reference=data["calibration_reference"],
                calibration_status=data["calibration_status"],
                circuit_id=data["circuit_id"],
                circuit_revision=data["circuit_revision"],
                is_stale=data["is_stale"],
                status=data["status"],
            )
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ============================================================================
# 4. KNOWLEDGE IMPACT ANALYSIS
# ============================================================================

@router.get("/circuits/{circuit_id}/knowledge-impact", response_model=dict[str, Any])
async def get_circuit_knowledge_impact(
    circuit_id: str,
    knowledge_id: str = Query(..., description="ID of the knowledge record being checked"),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Evaluates the downstream blast radius of a knowledge record change on this circuit."""
    impact_service = KnowledgeImpactService(db)
    try:
        impact = await impact_service.evaluate_knowledge_impact(
            knowledge_id=knowledge_id,
            tenant_id=current_user.tenant_id,
        )
        return {"data": KnowledgeImpactResponse(**impact)}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
