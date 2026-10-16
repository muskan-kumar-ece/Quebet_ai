import hashlib
import uuid
from typing import Any, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.provenance import EngineeringSource, SourceStatus, SourceTrustLevel


class SourceRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_source(
        self,
        source_type: str,
        title: str,
        publisher: str,
        document_identifier: str,
        revision: str = "Rev A",
        version: str = "1.0",
        publication_date: Optional[str] = None,
        effective_date: Optional[str] = None,
        uri: Optional[str] = None,
        document_hash: Optional[str] = None,
        trust_level: str = SourceTrustLevel.UNVERIFIED.value,
        status: str = SourceStatus.CURRENT.value,
        supersedes_source_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> EngineeringSource:
        # If document_hash not provided and document_identifier given, compute deterministic digest
        if not document_hash:
            digest_src = f"{document_identifier}:{revision}:{version}:{publisher}"
            document_hash = hashlib.sha256(digest_src.encode("utf-8")).hexdigest()

        source = EngineeringSource(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            source_type=source_type,
            title=title,
            publisher=publisher,
            document_identifier=document_identifier,
            revision=revision,
            version=version,
            publication_date=publication_date,
            effective_date=effective_date,
            uri=uri,
            document_hash=document_hash,
            trust_level=trust_level,
            status=status,
            supersedes_source_id=supersedes_source_id,
            metadata_=metadata or {},
        )
        self.db.add(source)
        await self.db.commit()
        await self.db.refresh(source)
        return source

    async def get_source(
        self,
        source_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSource]:
        stmt = select(EngineeringSource).where(EngineeringSource.id == source_id)
        if tenant_id:
            stmt = stmt.where(
                or_(
                    EngineeringSource.tenant_id == tenant_id,
                    EngineeringSource.tenant_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_identifier(
        self,
        document_identifier: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSource]:
        stmt = (
            select(EngineeringSource)
            .where(EngineeringSource.document_identifier == document_identifier)
            .order_by(EngineeringSource.created_at.desc())
        )
        if tenant_id:
            stmt = stmt.where(
                or_(
                    EngineeringSource.tenant_id == tenant_id,
                    EngineeringSource.tenant_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def list_sources(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EngineeringSource]:
        stmt = select(EngineeringSource).order_by(EngineeringSource.created_at.desc())
        if tenant_id:
            stmt = stmt.where(
                or_(
                    EngineeringSource.tenant_id == tenant_id,
                    EngineeringSource.tenant_id.is_(None),
                )
            )
        stmt = stmt.limit(limit).offset(offset)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def list_versions(
        self,
        source_id: str,
        tenant_id: Optional[str] = None,
    ) -> list[EngineeringSource]:
        """Finds all versions in the supersession lineage of a source."""
        base_source = await self.get_source(source_id, tenant_id=tenant_id)
        if not base_source:
            return []

        doc_id = base_source.document_identifier
        stmt = (
            select(EngineeringSource)
            .where(EngineeringSource.document_identifier == doc_id)
            .order_by(EngineeringSource.created_at.desc())
        )
        if tenant_id:
            stmt = stmt.where(
                or_(
                    EngineeringSource.tenant_id == tenant_id,
                    EngineeringSource.tenant_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def supersede_source(
        self,
        old_source_id: str,
        new_source_data: dict[str, Any],
        reason: str,
        tenant_id: Optional[str] = None,
    ) -> EngineeringSource:
        old_source = await self.get_source(old_source_id, tenant_id=tenant_id)
        if not old_source:
            raise ValueError(f"Source {old_source_id} not found")

        # Mark old source as superseded
        old_source.status = SourceStatus.SUPERSEDED.value
        old_meta = dict(old_source.metadata_ or {})
        old_meta["superseded_reason"] = reason
        old_source.metadata_ = old_meta

        # Create new source referencing old source
        new_data = dict(new_source_data)
        new_data["supersedes_source_id"] = old_source_id
        new_data["tenant_id"] = tenant_id

        meta = new_data.get("metadata") or {}
        meta["supersedes_reason"] = reason
        new_data["metadata"] = meta

        new_source = await self.create_source(**new_data)
        return new_source
