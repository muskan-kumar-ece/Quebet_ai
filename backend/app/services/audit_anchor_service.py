"""
Authoritative Audit Anchor Service for Phase 4D: External Audit Anchoring & Ledger Notarization.
Orchestrates:
- Deterministic logical checkpoint manifest construction.
- Monotonic per-project sequence range tracking.
- Row-level concurrency locking on Project during checkpoint creation.
- Out-of-transaction RFC 3161 network submission.
- Complete 10-stage CMS verification and durable token persistence.
- Idempotent retries reusing identical manifest and digest.
- Independent external retention mirroring (WORM).
- Offline re-verification of persisted tokens and underlying audit events.

STRICT INVARIANTS:
- AI ENGINEERING AUTHORITY = NONE
- AI DECISION AUTHORITY = NONE
- AUTONOMOUS MUTATION = DISABLED
- AUTONOMOUS APPROVAL = DISABLED
- AUTONOMOUS VERIFICATION = DISABLED
- UNKNOWN != SATISFIED
- HISTORICAL MEMORY != ENGINEERING TRUTH
- HISTORICAL VERIFICATION != CURRENT VERIFICATION
- AUDIT CHAIN VALIDITY != EXTERNAL ANCHOR VALIDITY
- TIMESTAMPED DIGEST != PROOF OF EVENT TRUTH
"""
from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional
import uuid

import httpx
from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import AUTHORIZED_HUMAN_ROLES, AuthenticatedUser
from app.models.db.audit_anchor import AnchorStatus, EngineeringAuditAnchor
from app.models.db.audit_ledger import EngineeringAuditEvent
from app.models.db.project import Project
from app.repositories.project_repo import project_repo
from app.services.audit_ledger_service import AuditLedgerService
from app.services.audit_retention_service import AuditRetentionService
from app.services.rfc3161_service import RFC3161Engine, RFC3161VerificationResult

logger = logging.getLogger(__name__)


class AuditAnchorService:
    """
    Authoritative service managing RFC 3161 external timestamp anchors.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def _verify_human_engineer_authority(self, current_user: AuthenticatedUser) -> None:
        """Enforces that only authorized human engineering roles can request or notarize anchors."""
        role_norm = (getattr(current_user, "role", "") or "").strip().lower()
        if any(sub in role_norm for sub in ("ai", "bot", "copilot", "assistant", "agent", "autonomous")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Audit anchor authorization denied: AI agents possess no engineering authority. (AI ENGINEERING AUTHORITY = NONE)",
            )
        authorized_roles = {r.lower() for r in AUTHORIZED_HUMAN_ROLES}
        if role_norm not in authorized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Audit anchor authorization denied: role '{current_user.role}' is not an authorized human engineering role.",
            )

    async def _verify_project_access(self, project_id: str, current_user: AuthenticatedUser) -> Project:
        """Enforces project existence and strict multi-tenant / personal workspace scoping."""
        project = await project_repo.get_by_id(
            db=self.db,
            project_id=project_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied.",
            )
        return project

    async def get_latest_anchor(self, project_id: str) -> Optional[EngineeringAuditAnchor]:
        """Returns the most recent audit anchor for a project."""
        stmt = (
            select(EngineeringAuditAnchor)
            .where(EngineeringAuditAnchor.project_id == project_id)
            .order_by(desc(EngineeringAuditAnchor.checkpoint_sequence))
            .limit(1)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_anchors(
        self,
        project_id: str,
        current_user: AuthenticatedUser,
        limit: int = 50,
        offset: int = 0,
    ) -> List[EngineeringAuditAnchor]:
        """Retrieves chronological audit anchors for a project."""
        await self._verify_project_access(project_id, current_user)
        stmt = (
            select(EngineeringAuditAnchor)
            .where(EngineeringAuditAnchor.project_id == project_id)
            .order_by(EngineeringAuditAnchor.checkpoint_sequence.asc())
            .offset(offset)
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_anchor_by_id(
        self,
        project_id: str,
        anchor_id: str,
        current_user: AuthenticatedUser,
    ) -> EngineeringAuditAnchor:
        """Retrieves a specific anchor with tenant isolation."""
        await self._verify_project_access(project_id, current_user)
        stmt = (
            select(EngineeringAuditAnchor)
            .where(
                EngineeringAuditAnchor.id == anchor_id,
                EngineeringAuditAnchor.project_id == project_id,
            )
        )
        res = await self.db.execute(stmt)
        anchor = res.scalar_one_or_none()
        if not anchor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit anchor not found.",
            )
        return anchor

    async def request_anchor(
        self,
        project_id: str,
        current_user: AuthenticatedUser,
        tsa_url: Optional[str] = None,
        ca_cert_path: Optional[str] = None,
        force_retry: bool = False,
        allow_unverified_root_in_dev: bool = False,
    ) -> EngineeringAuditAnchor:
        """
        Creates, submits, and verifies an RFC 3161 external timestamp anchor for the project.
        - Uses row-level lock on Project during checkpoint manifest derivation.
        - Network call occurs outside transaction.
        - Idempotent retries reuse exact manifest and digest.
        """
        self._verify_human_engineer_authority(current_user)
        await self._verify_project_access(project_id, current_user)

        target_tsa_url = tsa_url or settings.TSA_SERVER_URL
        target_ca_path = ca_cert_path or settings.TSA_CA_CERT_PATH

        # 1. Acquire exclusive lock on Project row for concurrency safety
        proj_stmt = select(Project).where(Project.id == project_id).with_for_update()
        proj_res = await self.db.execute(proj_stmt)
        project = proj_res.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        # 2. Inspect latest event in audit ledger
        ev_stmt = (
            select(EngineeringAuditEvent)
            .where(EngineeringAuditEvent.project_id == project_id)
            .order_by(desc(EngineeringAuditEvent.sequence_number))
            .limit(1)
        )
        ev_res = await self.db.execute(ev_stmt)
        latest_event = ev_res.scalar_one_or_none()

        if not latest_event:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot anchor empty audit ledger. Project has zero recorded events.",
            )

        current_head_seq = latest_event.sequence_number
        current_head_hash = latest_event.event_hash

        # 3. Check existing anchors for project
        latest_anchor = await self.get_latest_anchor(project_id)

        anchor_row: Optional[EngineeringAuditAnchor] = None

        if latest_anchor:
            # If current head is already anchored
            if latest_anchor.to_sequence == current_head_seq:
                if latest_anchor.status == AnchorStatus.ANCHORED.value and not force_retry:
                    return latest_anchor
                if latest_anchor.status == AnchorStatus.PENDING.value and not force_retry:
                    return latest_anchor
                if latest_anchor.status == AnchorStatus.FAILED.value or force_retry:
                    # Idempotent retry: reuse the exact existing manifest, digest, and sequence
                    anchor_row = latest_anchor
                    anchor_row.status = AnchorStatus.PENDING.value
                    anchor_row.retry_count += 1
                    anchor_row.error_code = None
                    anchor_row.error_message = None

        if anchor_row is None:
            # New checkpoint range
            from_seq = (latest_anchor.to_sequence + 1) if latest_anchor else 1
            to_seq = current_head_seq

            if to_seq < from_seq:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No new audit events to anchor. Latest event sequence is {current_head_seq}.",
                )

            checkpoint_seq = (latest_anchor.checkpoint_sequence + 1) if latest_anchor else 1
            checkpoint_id = str(uuid.uuid4())
            nonce_int, nonce_hex = RFC3161Engine.generate_nonce()

            # Construct immutable logical Checkpoint Manifest
            manifest = {
                "canonicalization_algorithm": "QUEBET_CANONICAL_JSON_V1",
                "chain_head_hash": str(current_head_hash),
                "chain_id": f"ledger:project:{project_id}",
                "checkpoint_format_version": "1.0.0",
                "checkpoint_id": checkpoint_id,
                "checkpoint_sequence": int(checkpoint_seq),
                "digest_algorithm": "SHA-256",
                "event_count": int(to_seq - from_seq + 1),
                "from_sequence": int(from_seq),
                "logical_timestamp": datetime.now(timezone.utc).isoformat(),
                "project_id": str(project_id),
                "tenant_id": str(current_user.tenant_id) if current_user.tenant_id else None,
                "to_sequence": int(to_seq),
            }

            # Canonical serialization and digest
            checkpoint_digest = AuditLedgerService.compute_payload_hash(manifest)

            anchor_row = EngineeringAuditAnchor(
                id=checkpoint_id,
                project_id=project_id,
                tenant_id=current_user.tenant_id,
                checkpoint_sequence=checkpoint_seq,
                from_sequence=from_seq,
                to_sequence=to_seq,
                chain_head_hash=current_head_hash,
                checkpoint_manifest=manifest,
                checkpoint_digest=checkpoint_digest,
                nonce=nonce_hex,
                status=AnchorStatus.PENDING.value,
                tsa_url=target_tsa_url or "UNCONFIGURED",
                retry_count=0,
            )
            self.db.add(anchor_row)

        await self.db.commit()
        await self.db.refresh(anchor_row)

        # 4. Out-of-transaction TSA submission and verification
        if not target_tsa_url or target_tsa_url == "UNCONFIGURED":
            anchor_row.status = AnchorStatus.FAILED.value
            anchor_row.error_code = "TSA_NOT_CONFIGURED"
            anchor_row.error_message = (
                "No RFC 3161 TSA server URL configured. Set TSA_SERVER_URL in environment or pass explicit tsa_url."
            )
            await self.db.commit()
            await self.db.refresh(anchor_row)
            return anchor_row

        # Execute submission
        await self._submit_and_verify_tsa(
            anchor=anchor_row,
            tsa_url=target_tsa_url,
            ca_cert_path=target_ca_path,
            allow_unverified_root_in_dev=allow_unverified_root_in_dev,
        )

        return anchor_row

    async def _submit_and_verify_tsa(
        self,
        anchor: EngineeringAuditAnchor,
        tsa_url: str,
        ca_cert_path: Optional[str],
        allow_unverified_root_in_dev: bool = False,
    ) -> None:
        """
        Executes HTTP post to TSA, receives response, verifies token, and updates anchor record.
        """
        try:
            digest_bytes = bytes.fromhex(anchor.checkpoint_digest)
            nonce_int = int(anchor.nonce, 16)

            # Build DER request
            req_der = RFC3161Engine.create_timestamp_request(
                digest_bytes=digest_bytes,
                nonce=nonce_int,
                policy_oid=settings.TSA_POLICY_OID,
                cert_req=settings.TSA_REQUIRE_CERT_REQ,
            )

            # Transmit request
            headers = {"Content-Type": "application/timestamp-query"}
            async with httpx.AsyncClient(timeout=settings.TSA_TIMEOUT_SECONDS) as client:
                resp = await client.post(tsa_url, content=req_der, headers=headers)

            if resp.status_code != 200:
                anchor.status = AnchorStatus.FAILED.value
                anchor.error_code = f"HTTP_{resp.status_code}"
                anchor.error_message = f"TSA responded with non-200 HTTP status code {resp.status_code}."
                await self.db.commit()
                return

            # Parse ASN.1 response
            pki_status, fail_info, token_der = RFC3161Engine.parse_timestamp_response(resp.content)
            if pki_status not in (0, 1) or token_der is None:
                anchor.status = AnchorStatus.FAILED.value
                anchor.error_code = f"TSA_STATUS_{pki_status}"
                anchor.error_message = f"TSA rejected request: {fail_info or 'Status ' + str(pki_status)}"
                await self.db.commit()
                return

            # Complete 10-stage verification
            require_trusted = (settings.ENVIRONMENT == "production") and not allow_unverified_root_in_dev
            v_res = RFC3161Engine.verify_timestamp_token(
                token_der=token_der,
                expected_digest_bytes=digest_bytes,
                expected_nonce=nonce_int,
                ca_cert_path=ca_cert_path,
                required_policy_oid=settings.TSA_POLICY_OID,
                require_trusted_ca=require_trusted,
            )

            if not v_res.is_valid:
                anchor.status = AnchorStatus.VERIFICATION_FAILED.value
                anchor.error_code = v_res.failure_code or "VERIFICATION_FAILED"
                anchor.error_message = v_res.failure_message or "Cryptographic token verification failed."
                await self.db.commit()
                return

            # Successful verification: record evidence
            anchor.status = AnchorStatus.ANCHORED.value
            anchor.token_der = token_der
            anchor.token_hash = hashlib.sha256(token_der).hexdigest()
            anchor.tsa_timestamp = v_res.gen_time
            anchor.tsa_serial_number = v_res.serial_number
            anchor.tsa_policy_id = v_res.policy_oid
            anchor.anchored_at = datetime.now(timezone.utc)
            anchor.last_verified_at = datetime.now(timezone.utc)
            anchor.last_verification_status = "VERIFIED"
            anchor.error_code = None
            anchor.error_message = None

            # Attempt out-of-band immutable mirror
            mirrored, uri = await AuditRetentionService.mirror_anchor_out_of_band(
                project_id=anchor.project_id,
                tenant_id=anchor.tenant_id,
                checkpoint_sequence=anchor.checkpoint_sequence,
                checkpoint_manifest=anchor.checkpoint_manifest,
                token_der=token_der,
            )
            anchor.mirrored_to_external_store = mirrored
            anchor.external_store_uri = uri

            await self.db.commit()

        except httpx.TimeoutException:
            anchor.status = AnchorStatus.FAILED.value
            anchor.error_code = "NETWORK_TIMEOUT"
            anchor.error_message = f"TSA request timed out after {settings.TSA_TIMEOUT_SECONDS} seconds."
            await self.db.commit()
        except Exception as e:
            anchor.status = AnchorStatus.FAILED.value
            anchor.error_code = "SUBMISSION_EXCEPTION"
            anchor.error_message = str(e)
            await self.db.commit()

    async def verify_anchor(
        self,
        project_id: str,
        anchor_id: str,
        current_user: AuthenticatedUser,
        ca_cert_path: Optional[str] = None,
        check_underlying_events: bool = True,
        allow_unverified_root_in_dev: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes complete offline/online re-verification of a stored audit anchor:
        1. Manifest canonicalization & digest integrity check.
        2. RFC 3161 token signature, EKU, and CA chain re-verification.
        3. Underlying audit ledger continuity check over [from_sequence, to_sequence].
        """
        anchor = await self.get_anchor_by_id(project_id, anchor_id, current_user)

        target_ca_path = ca_cert_path or settings.TSA_CA_CERT_PATH
        manifest = anchor.checkpoint_manifest

        # 1. Manifest Digest Integrity
        recomputed_digest = AuditLedgerService.compute_payload_hash(manifest)
        if recomputed_digest != anchor.checkpoint_digest:
            anchor.last_verification_status = "TAMPERED_MANIFEST"
            anchor.last_verified_at = datetime.now(timezone.utc)
            await self.db.commit()
            return {
                "anchor_id": anchor.id,
                "is_valid": False,
                "status": "TAMPERED_MANIFEST",
                "failure_reason": f"Stored checkpoint digest '{anchor.checkpoint_digest}' does not match recomputed digest '{recomputed_digest}'.",
            }

        # 2. Token Cryptographic Verification
        if not anchor.token_der:
            return {
                "anchor_id": anchor.id,
                "is_valid": False,
                "status": anchor.status,
                "failure_reason": f"Anchor has no stored token (status: {anchor.status}).",
            }

        digest_bytes = bytes.fromhex(anchor.checkpoint_digest)
        nonce_int = int(anchor.nonce, 16)
        require_trusted = (settings.ENVIRONMENT == "production") and not allow_unverified_root_in_dev

        token_v = RFC3161Engine.verify_timestamp_token(
            token_der=anchor.token_der,
            expected_digest_bytes=digest_bytes,
            expected_nonce=nonce_int,
            ca_cert_path=target_ca_path,
            required_policy_oid=settings.TSA_POLICY_OID,
            require_trusted_ca=require_trusted,
        )

        if not token_v.is_valid:
            anchor.last_verification_status = token_v.failure_code
            anchor.last_verified_at = datetime.now(timezone.utc)
            await self.db.commit()
            return {
                "anchor_id": anchor.id,
                "is_valid": False,
                "status": token_v.status,
                "failure_reason": token_v.failure_message,
            }

        # 3. Underlying Audit Ledger Continuity Check
        events_valid = True
        ledger_message = "Audit events verified continuous."

        if check_underlying_events:
            ev_stmt = (
                select(EngineeringAuditEvent)
                .where(
                    EngineeringAuditEvent.project_id == project_id,
                    EngineeringAuditEvent.sequence_number >= anchor.from_sequence,
                    EngineeringAuditEvent.sequence_number <= anchor.to_sequence,
                )
                .order_by(EngineeringAuditEvent.sequence_number.asc())
            )
            ev_res = await self.db.execute(ev_stmt)
            events = list(ev_res.scalars().all())

            expected_count = anchor.to_sequence - anchor.from_sequence + 1
            if len(events) != expected_count:
                events_valid = False
                ledger_message = f"Sequence count mismatch: expected {expected_count} events in range [{anchor.from_sequence}..{anchor.to_sequence}], found {len(events)}."
            elif events[-1].event_hash != anchor.chain_head_hash:
                events_valid = False
                ledger_message = f"Audit chain head hash mismatch: event at sequence {anchor.to_sequence} has hash '{events[-1].event_hash}', anchor expects '{anchor.chain_head_hash}'."

        overall_valid = token_v.is_valid and events_valid
        anchor.last_verified_at = datetime.now(timezone.utc)
        anchor.last_verification_status = "VERIFIED" if overall_valid else "LEDGER_DISCONTINUITY"
        await self.db.commit()

        retention_info = AuditRetentionService.get_retention_capabilities()

        return {
            "anchor_id": anchor.id,
            "project_id": anchor.project_id,
            "checkpoint_sequence": anchor.checkpoint_sequence,
            "from_sequence": anchor.from_sequence,
            "to_sequence": anchor.to_sequence,
            "chain_head_hash": anchor.chain_head_hash,
            "checkpoint_digest": anchor.checkpoint_digest,
            "tsa_url": anchor.tsa_url,
            "tsa_timestamp": anchor.tsa_timestamp.isoformat() if anchor.tsa_timestamp else None,
            "tsa_serial_number": anchor.tsa_serial_number,
            "signer_subject": token_v.signer_subject,
            "ca_chain_trusted": token_v.ca_chain_trusted,
            "token_cryptographically_verified": token_v.is_valid,
            "underlying_events_continuous": events_valid,
            "is_valid": overall_valid,
            "status": "VERIFIED" if overall_valid else "LEDGER_DISCONTINUITY",
            "failure_reason": None if overall_valid else ledger_message,
            "retention": {
                "mirrored_to_external_store": anchor.mirrored_to_external_store,
                "external_store_uri": anchor.external_store_uri,
                **retention_info,
            },
        }
