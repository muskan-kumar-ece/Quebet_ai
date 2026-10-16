import hashlib
import json
import uuid
from typing import Any, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.db.provenance import (
    EngineeringKnowledgeRecord,
    EngineeringKnowledgeSnapshot,
    KnowledgeClassification,
    KnowledgeStatus,
)


class KnowledgeRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_knowledge_record(
        self,
        subject_identifier: str,
        parameter: str,
        value: str,
        unit: Optional[str] = None,
        classification: str = KnowledgeClassification.AUTHORITATIVE_SOURCE.value,
        parameter_category: Optional[str] = None,
        raw_value: Optional[str] = None,
        normalized_value: Optional[float] = None,
        source_location: Optional[dict[str, Any]] = None,
        is_conflicting: bool = False,
        conflict_details: Optional[dict[str, Any]] = None,
        conditions: Optional[dict[str, Any]] = None,
        valid_range: Optional[dict[str, Any]] = None,
        domain: str = "SEMICONDUCTOR",
        subject_type: str = "COMPONENT",
        source_id: Optional[str] = None,
        status: str = KnowledgeStatus.VERIFIED.value,
        provenance: Optional[dict[str, Any]] = None,
        supersedes_knowledge_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> EngineeringKnowledgeRecord:
        record = EngineeringKnowledgeRecord(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            source_id=source_id,
            domain=domain,
            subject_type=subject_type,
            subject_identifier=subject_identifier,
            parameter=parameter,
            value=str(value),
            unit=unit,
            classification=classification,
            parameter_category=parameter_category,
            raw_value=raw_value,
            normalized_value=normalized_value,
            source_location=source_location or {},
            is_conflicting=is_conflicting,
            conflict_details=conflict_details or {},
            conditions=conditions or {},
            valid_range=valid_range,
            status=status,
            provenance=provenance or {},
            supersedes_knowledge_id=supersedes_knowledge_id,
        )
        self.db.add(record)
        await self.db.commit()
        saved = await self.get_knowledge_record(record.id, tenant_id=tenant_id)
        return saved or record

    async def get_knowledge_record(
        self,
        knowledge_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringKnowledgeRecord]:
        stmt = (
            select(EngineeringKnowledgeRecord)
            .options(selectinload(EngineeringKnowledgeRecord.source))
            .where(EngineeringKnowledgeRecord.id == knowledge_id)
        )
        if tenant_id:
            stmt = stmt.where(
                or_(
                    EngineeringKnowledgeRecord.tenant_id == tenant_id,
                    EngineeringKnowledgeRecord.tenant_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_records(
        self,
        subject_identifier: Optional[str] = None,
        parameter: Optional[str] = None,
        status: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[EngineeringKnowledgeRecord]:
        stmt = (
            select(EngineeringKnowledgeRecord)
            .options(selectinload(EngineeringKnowledgeRecord.source))
            .order_by(EngineeringKnowledgeRecord.created_at.desc())
        )
        if subject_identifier:
            stmt = stmt.where(EngineeringKnowledgeRecord.subject_identifier == subject_identifier)
        if parameter:
            stmt = stmt.where(EngineeringKnowledgeRecord.parameter == parameter)
        if status:
            stmt = stmt.where(EngineeringKnowledgeRecord.status == status)
        if tenant_id:
            stmt = stmt.where(
                or_(
                    EngineeringKnowledgeRecord.tenant_id == tenant_id,
                    EngineeringKnowledgeRecord.tenant_id.is_(None),
                )
            )
        stmt = stmt.limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def supersede_record(
        self,
        old_record_id: str,
        new_data: dict[str, Any],
        reason: str,
        tenant_id: Optional[str] = None,
    ) -> EngineeringKnowledgeRecord:
        old_record = await self.get_knowledge_record(old_record_id, tenant_id=tenant_id)
        if not old_record:
            raise ValueError(f"Knowledge record {old_record_id} not found")

        # Invalidate/supersede old record without deleting
        old_record.status = KnowledgeStatus.SUPERSEDED.value
        old_prov = dict(old_record.provenance or {})
        old_prov["superseded_reason"] = reason
        old_record.provenance = old_prov

        # Create new record linking back
        data = dict(new_data)
        data["supersedes_knowledge_id"] = old_record_id
        data["tenant_id"] = tenant_id

        prov = data.get("provenance") or {}
        prov["supersedes_reason"] = reason
        data["provenance"] = prov

        new_rec = await self.create_knowledge_record(**data)
        return new_rec

    async def create_or_get_snapshot(
        self,
        record_ids: list[str],
        tenant_id: Optional[str] = None,
    ) -> EngineeringKnowledgeSnapshot:
        """Computes a deterministic hash over sorted record IDs and returns or creates an immutable snapshot."""
        sorted_ids = sorted(record_ids)
        digest = hashlib.sha256(json.dumps(sorted_ids).encode("utf-8")).hexdigest()

        stmt = select(EngineeringKnowledgeSnapshot).where(
            EngineeringKnowledgeSnapshot.snapshot_hash == digest
        )
        if tenant_id:
            stmt = stmt.where(
                or_(
                    EngineeringKnowledgeSnapshot.tenant_id == tenant_id,
                    EngineeringKnowledgeSnapshot.tenant_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        existing = res.scalars().first()
        if existing:
            return existing

        snapshot = EngineeringKnowledgeSnapshot(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            snapshot_hash=digest,
            knowledge_record_ids=sorted_ids,
            metadata_={"record_count": len(sorted_ids)},
        )
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        return snapshot

    async def get_snapshot(
        self,
        snapshot_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringKnowledgeSnapshot]:
        stmt = select(EngineeringKnowledgeSnapshot).where(EngineeringKnowledgeSnapshot.id == snapshot_id)
        if tenant_id:
            stmt = stmt.where(
                or_(
                    EngineeringKnowledgeSnapshot.tenant_id == tenant_id,
                    EngineeringKnowledgeSnapshot.tenant_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()
