"""
Pydantic schemas for Phase 4D: External Audit Anchoring & Ledger Notarization.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditAnchorRequest(BaseModel):
    tsa_url: Optional[str] = Field(default=None, description="Optional custom TSA URL override")
    ca_cert_path: Optional[str] = Field(default=None, description="Optional custom CA bundle path")
    force_retry: bool = Field(default=False, description="Retry last failed anchor if sequence unchanged")

    model_config = ConfigDict(from_attributes=True)


class AuditAnchorResponse(BaseModel):
    id: str
    project_id: str
    tenant_id: Optional[str] = None
    checkpoint_sequence: int
    from_sequence: int
    to_sequence: int
    chain_head_hash: str
    checkpoint_digest: str
    status: str
    tsa_url: str
    tsa_timestamp: Optional[datetime] = None
    tsa_serial_number: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    mirrored_to_external_store: bool = False
    external_store_uri: Optional[str] = None
    created_at: datetime
    anchored_at: Optional[datetime] = None
    last_verified_at: Optional[datetime] = None
    last_verification_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AuditAnchorListResponse(BaseModel):
    project_id: str
    total_anchors: int
    anchors: List[AuditAnchorResponse]

    model_config = ConfigDict(from_attributes=True)


class AuditAnchorVerificationResponse(BaseModel):
    anchor_id: str
    project_id: str
    checkpoint_sequence: int
    from_sequence: int
    to_sequence: int
    chain_head_hash: str
    checkpoint_digest: str
    tsa_url: str
    tsa_timestamp: Optional[str] = None
    tsa_serial_number: Optional[str] = None
    signer_subject: Optional[str] = None
    ca_chain_trusted: bool
    token_cryptographically_verified: bool
    underlying_events_continuous: bool
    is_valid: bool
    status: str
    failure_reason: Optional[str] = None
    retention: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
