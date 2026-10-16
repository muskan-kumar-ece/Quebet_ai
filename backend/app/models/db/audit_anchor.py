"""
Database models for Phase 4D: External Audit Anchoring & Ledger Notarization.
Persists immutable checkpoint manifests, RFC 3161 timestamp tokens, and verification status.

STRICT INVARIANTS:
- AI ENGINEERING AUTHORITY = NONE
- AI DECISION AUTHORITY = NONE
- AUTONOMOUS MUTATION = DISABLED
- AUTONOMOUS APPROVAL = DISABLED
- AUTONOMOUS VERIFICATION = DISABLED
- HISTORICAL MEMORY != ENGINEERING TRUTH
- HISTORICAL VERIFICATION != CURRENT VERIFICATION
- AUDIT CHAIN VALIDITY != EXTERNAL ANCHOR VALIDITY
- TIMESTAMPED DIGEST != PROOF OF EVENT TRUTH
- UNKNOWN != SATISFIED
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, AuditTimestampMixin, UUIDMixin


class AnchorStatus(str, Enum):
    PENDING = "PENDING"
    ANCHORED = "ANCHORED"
    FAILED = "FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"


class EngineeringAuditAnchor(Base, UUIDMixin, AuditTimestampMixin):
    """
    Durable record of an external RFC 3161 cryptographic timestamp anchor
    binding a specific sequence range of an engineering audit ledger.
    """
    __tablename__ = "engineering_audit_anchors"

    # Multi-tenant and project scoping (RESTRICT deletion to preserve permanent audit trail)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    # Monotonic checkpoint counter per project (1, 2, 3...)
    checkpoint_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Covered audit ledger sequence range
    from_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    to_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chain_head_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Immutable Checkpoint Manifest & Digest
    checkpoint_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    checkpoint_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # 128-bit Cryptographic Nonce (hex string)
    nonce: Mapped[str] = mapped_column(String(32), nullable=False)

    # Lifecycle State: PENDING, ANCHORED, FAILED, VERIFICATION_FAILED
    status: Mapped[str] = mapped_column(String(32), default=AnchorStatus.PENDING.value, index=True, nullable=False)

    # TSA Authority & Metadata
    tsa_url: Mapped[str] = mapped_column(String(255), nullable=False)
    tsa_policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tsa_serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tsa_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Raw Verified RFC 3161 Token
    token_der: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Operational Diagnostic Fields
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Independent Retention Mirror Metadata
    mirrored_to_external_store: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    external_store_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Lifecycle Timestamps
    anchored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verification_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Relationships
    project = relationship("Project")

    # Unique Constraints
    __table_args__ = (
        UniqueConstraint("project_id", "checkpoint_sequence", name="uq_anchor_project_sequence"),
        UniqueConstraint("project_id", "to_sequence", name="uq_anchor_project_to_seq"),
    )
