"""
Pydantic schemas for Phase 3 Wave 10A: Engineering Audit Ledger Foundation.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class EngineeringAuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    tenant_id: Optional[str] = None
    sequence_number: int
    actor_id: str
    actor_role: str
    event_type: str
    entity_type: str
    entity_id: str
    entity_revision: Optional[int] = None
    payload: Dict[str, Any]
    payload_hash: str
    prev_event_hash: str
    event_hash: str
    created_at: datetime


class AuditLedgerListResponse(BaseModel):
    project_id: str
    total_events: int
    events: List[EngineeringAuditEventResponse]


class AuditChainVerificationResponse(BaseModel):
    project_id: str
    is_valid: bool
    events_verified: int
    status: str
    message: str
    head_hash: Optional[str] = None
    latest_sequence_number: Optional[int] = None
    error_code: Optional[str] = None
    event_index: Optional[int] = None
    event_id: Optional[str] = None
