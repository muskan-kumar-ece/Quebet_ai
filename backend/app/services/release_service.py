"""
Deterministic Release Gate Engine & Frozen Release Baselines Service.
Implements Phase 3 Wave 10C:
- Deterministic evaluation of Release Gates RG-01 through RG-09.
- Dynamic staleness detection and audit-chain cryptographic integrity check.
- Human-authorized immutable release baseline snapshot generation with canonical SHA-256 digest.
- Transactional coupling with Audit Ledger event RELEASE_BASELINE_CREATED.

STRICT INVARIANTS:
- AI ENGINEERING AUTHORITY = NONE
- AI DECISION AUTHORITY = NONE
- AUTONOMOUS MUTATION = DISABLED
- AUTONOMOUS APPROVAL = DISABLED
- AUTONOMOUS VERIFICATION = DISABLED
- UNKNOWN != SATISFIED
- CALCULATED != PHYSICALLY VERIFIED
- ZERO SYNTHETIC ENGINEERING SCORING
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import AuthenticatedUser
from app.models.db.audit_ledger import AuditEventType
from app.models.db.audit_anchor import AnchorStatus, EngineeringAuditAnchor
from app.models.db.bom import EngineeringBOM
from app.models.db.circuit import Circuit, CircuitValidationStatus
from app.models.db.cross_domain import (
    CrossDomainSeverity,
    CrossDomainStatus,
    CrossDomainValidationRecord,
    CrossDomainValidationStatus,
)
from app.models.db.decision import (
    DecisionStatus,
    EngineeringDecisionRecord,
    EngineeringRequirement,
    EngineeringUnknownDisposition,
    RequirementStatus,
    UnknownDispositionStatus,
)
from app.models.db.dfm import ManufacturingAnalysisRecord, ManufacturingAnalysisStatus
from app.models.db.pcb import BoardFootprint, BoardStatus, EngineeringBoard
from app.models.db.project import Project, ProjectType
from app.models.db.release import (
    EngineeringReleaseBaseline,
    EngineeringReleaseEvaluation,
    OverallReadinessState,
    ReleaseGateStatus,
)
from app.models.db.verification import (
    EngineeringDesignReview,
    EngineeringEvidence,
    EngineeringVerificationRequirement,
    EvidenceStatus,
    VerificationStatus,
)
from app.models.schemas.release import (
    ReleaseBaselineCreateRequest,
    ReleaseEvaluationRequest,
    ReleaseGateDetail,
)
from app.services.ai.pcb.drc_engine import PCBRuleEngine
from app.services.audit_ledger_service import AuditLedgerService


class ReleaseGateEngine:
    """
    Evaluator engine for gates RG-01 through RG-09.
    All evaluations are deterministic, failure-closed, and strictly bound to authoritative entities.
    """
    EVALUATOR_VERSION = "1.0.0"

    @staticmethod
    def evaluate_rg01(circuit: Optional[Circuit], eval_time: datetime) -> ReleaseGateDetail:
        """RG-01: Schematic Completeness & Validation"""
        if not circuit:
            return ReleaseGateDetail(
                gate_id="RG-01",
                name="Schematic Completeness & Validation",
                status=ReleaseGateStatus.BLOCKED,
                applicable_scope="SCHEMATIC",
                is_applicable=True,
                failure_reasons=["Circuit schematic not found for project."],
                missing_evidence=["Circuit entity"],
                evaluated_at=eval_time,
            )

        sources = [f"circuits.id:{circuit.id}"]
        evidence = [{"entity": "Circuit", "id": str(circuit.id), "version": circuit.version, "validation_status": circuit.validation_status}]

        if circuit.validation_status != CircuitValidationStatus.VALID.value:
            return ReleaseGateDetail(
                gate_id="RG-01",
                name="Schematic Completeness & Validation",
                status=ReleaseGateStatus.FAIL,
                applicable_scope="SCHEMATIC",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"Circuit validation status is '{circuit.validation_status}', required 'VALID'."],
                evaluated_at=eval_time,
            )

        if len(circuit.components) == 0:
            return ReleaseGateDetail(
                gate_id="RG-01",
                name="Schematic Completeness & Validation",
                status=ReleaseGateStatus.FAIL,
                applicable_scope="SCHEMATIC",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=["Circuit contains 0 components."],
                evaluated_at=eval_time,
            )

        return ReleaseGateDetail(
            gate_id="RG-01",
            name="Schematic Completeness & Validation",
            status=ReleaseGateStatus.PASS,
            applicable_scope="SCHEMATIC",
            is_applicable=True,
            authoritative_sources=sources,
            evidence_identifiers=evidence,
            evaluated_at=eval_time,
        )

    @staticmethod
    def evaluate_rg02(project: Project, circuit: Optional[Circuit], board: Optional[EngineeringBoard], eval_time: datetime) -> ReleaseGateDetail:
        """RG-02: PCB Layout & DRC Cleanliness"""
        if project.project_type == ProjectType.GENERAL.value and not board:
            return ReleaseGateDetail(
                gate_id="RG-02",
                name="PCB Layout & DRC Cleanliness",
                status=ReleaseGateStatus.NOT_APPLICABLE,
                applicable_scope="PCB",
                is_applicable=False,
                not_applicable_reason="Project type is GENERAL and contains no PCB board layout.",
                evaluated_at=eval_time,
            )

        if not board:
            return ReleaseGateDetail(
                gate_id="RG-02",
                name="PCB Layout & DRC Cleanliness",
                status=ReleaseGateStatus.BLOCKED,
                applicable_scope="PCB",
                is_applicable=True,
                failure_reasons=["Board layout not found for PCB project."],
                missing_evidence=["EngineeringBoard entity"],
                evaluated_at=eval_time,
            )

        sources = [f"engineering_boards.id:{board.id}"]
        evidence = [{"entity": "EngineeringBoard", "id": str(board.id), "version": board.version, "circuit_version": board.circuit_version, "status": board.status}]

        if circuit and board.circuit_version < circuit.version:
            return ReleaseGateDetail(
                gate_id="RG-02",
                name="PCB Layout & DRC Cleanliness",
                status=ReleaseGateStatus.STALE,
                applicable_scope="PCB",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"Board synchronized to circuit version {board.circuit_version}, but circuit is version {circuit.version}."],
                stale_reasons=["Circuit schematic mutated after PCB layout."],
                evaluated_at=eval_time,
            )

        if circuit:
            try:
                drc_result = PCBRuleEngine.run_drc(circuit=circuit, board=board)
                if not isinstance(drc_result, tuple) or len(drc_result) < 3:
                    return ReleaseGateDetail(
                        gate_id="RG-02",
                        name="PCB Layout & DRC Cleanliness",
                        status=ReleaseGateStatus.FAIL,
                        applicable_scope="PCB",
                        is_applicable=True,
                        authoritative_sources=sources,
                        evidence_identifiers=evidence,
                        failure_reasons=["PCB DRC execution returned malformed or incomplete output tuple."],
                        evaluated_at=eval_time,
                    )
                findings, _, metrics = drc_result
                if findings is None or not isinstance(findings, list):
                    return ReleaseGateDetail(
                        gate_id="RG-02",
                        name="PCB Layout & DRC Cleanliness",
                        status=ReleaseGateStatus.FAIL,
                        applicable_scope="PCB",
                        is_applicable=True,
                        authoritative_sources=sources,
                        evidence_identifiers=evidence,
                        failure_reasons=["PCB DRC findings output is invalid or missing."],
                        evaluated_at=eval_time,
                    )
                
                # Validate individual findings for structural integrity
                malformed_findings = [f for f in findings if f is None or not hasattr(f, "severity")]
                if malformed_findings:
                    return ReleaseGateDetail(
                        gate_id="RG-02",
                        name="PCB Layout & DRC Cleanliness",
                        status=ReleaseGateStatus.FAIL,
                        applicable_scope="PCB",
                        is_applicable=True,
                        authoritative_sources=sources,
                        evidence_identifiers=evidence,
                        failure_reasons=[f"PCB DRC returned {len(malformed_findings)} malformed or invalid finding entries."],
                        evaluated_at=eval_time,
                    )

                drc_failures = [f for f in findings if getattr(f, "severity", "") in ("FAIL", "CRITICAL", "ERROR")]
                if drc_failures:
                    return ReleaseGateDetail(
                        gate_id="RG-02",
                        name="PCB Layout & DRC Cleanliness",
                        status=ReleaseGateStatus.FAIL,
                        applicable_scope="PCB",
                        is_applicable=True,
                        authoritative_sources=sources,
                        evidence_identifiers=evidence,
                        failure_reasons=[f"PCB DRC reported {len(drc_failures)} critical/error findings."],
                        evaluated_at=eval_time,
                    )
            except Exception as e:
                return ReleaseGateDetail(
                    gate_id="RG-02",
                    name="PCB Layout & DRC Cleanliness",
                    status=ReleaseGateStatus.FAIL,
                    applicable_scope="PCB",
                    is_applicable=True,
                    authoritative_sources=sources,
                    evidence_identifiers=evidence,
                    failure_reasons=[f"PCB DRC execution failed with unexpected exception: {type(e).__name__}."],
                    evaluated_at=eval_time,
                )

        return ReleaseGateDetail(
            gate_id="RG-02",
            name="PCB Layout & DRC Cleanliness",
            status=ReleaseGateStatus.PASS,
            applicable_scope="PCB",
            is_applicable=True,
            authoritative_sources=sources,
            evidence_identifiers=evidence,
            evaluated_at=eval_time,
        )

    @staticmethod
    def evaluate_rg03(circuit: Optional[Circuit], bom: Optional[EngineeringBOM], eval_time: datetime) -> ReleaseGateDetail:
        """RG-03: BOM Procurement Resolution"""
        if not bom:
            return ReleaseGateDetail(
                gate_id="RG-03",
                name="BOM Procurement Resolution",
                status=ReleaseGateStatus.BLOCKED,
                applicable_scope="BOM",
                is_applicable=True,
                failure_reasons=["Bill of Materials (BOM) record not found for project."],
                missing_evidence=["EngineeringBOM entity"],
                evaluated_at=eval_time,
            )

        sources = [f"engineering_boms.id:{bom.id}"]
        evidence = [{"entity": "EngineeringBOM", "id": str(bom.id), "version": bom.version, "circuit_version": bom.circuit_version, "status": bom.status}]

        if circuit and bom.circuit_version < circuit.version:
            return ReleaseGateDetail(
                gate_id="RG-03",
                name="BOM Procurement Resolution",
                status=ReleaseGateStatus.STALE,
                applicable_scope="BOM",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"BOM synchronized to circuit version {bom.circuit_version}, but circuit is version {circuit.version}."],
                stale_reasons=["Circuit schematic mutated after BOM generation."],
                evaluated_at=eval_time,
            )

        unresolved_lines = [line for line in bom.lines if not getattr(line, "manufacturer_part_number", None)]
        if unresolved_lines:
            return ReleaseGateDetail(
                gate_id="RG-03",
                name="BOM Procurement Resolution",
                status=ReleaseGateStatus.FAIL,
                applicable_scope="BOM",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"BOM contains {len(unresolved_lines)} line items with unresolved MPN."],
                evaluated_at=eval_time,
            )

        return ReleaseGateDetail(
            gate_id="RG-03",
            name="BOM Procurement Resolution",
            status=ReleaseGateStatus.PASS,
            applicable_scope="BOM",
            is_applicable=True,
            authoritative_sources=sources,
            evidence_identifiers=evidence,
            evaluated_at=eval_time,
        )

    @staticmethod
    def evaluate_rg04(record: Optional[CrossDomainValidationRecord], eval_time: datetime) -> ReleaseGateDetail:
        """RG-04: Cross-Domain Multi-Physics Integrity"""
        if not record:
            return ReleaseGateDetail(
                gate_id="RG-04",
                name="Cross-Domain Multi-Physics Integrity",
                status=ReleaseGateStatus.UNKNOWN,
                applicable_scope="CROSS_DOMAIN",
                is_applicable=True,
                failure_reasons=["Cross-domain validation record not executed."],
                missing_evidence=["CrossDomainValidationRecord"],
                evaluated_at=eval_time,
            )

        sources = [f"cross_domain_validation_records.id:{record.id}"]
        evidence = [{"entity": "CrossDomainValidationRecord", "id": str(record.id), "status": record.validation_status, "is_stale": record.is_stale, "digest": record.snapshot_digest}]

        if record.is_stale:
            return ReleaseGateDetail(
                gate_id="RG-04",
                name="Cross-Domain Multi-Physics Integrity",
                status=ReleaseGateStatus.STALE,
                applicable_scope="CROSS_DOMAIN",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=["Cross-domain validation record snapshot is stale relative to current engineering state."],
                stale_reasons=record.staleness_reasons or ["Engineering state changed since cross-domain validation."],
                evaluated_at=eval_time,
            )

        critical_findings = [f for f in record.findings if f.get("severity") in ("CRITICAL", "HIGH") and f.get("status") == "FAIL"]
        if critical_findings:
            return ReleaseGateDetail(
                gate_id="RG-04",
                name="Cross-Domain Multi-Physics Integrity",
                status=ReleaseGateStatus.FAIL,
                applicable_scope="CROSS_DOMAIN",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"Cross-domain validation reported {len(critical_findings)} critical/high rule failures."],
                evaluated_at=eval_time,
            )

        return ReleaseGateDetail(
            gate_id="RG-04",
            name="Cross-Domain Multi-Physics Integrity",
            status=ReleaseGateStatus.PASS,
            applicable_scope="CROSS_DOMAIN",
            is_applicable=True,
            authoritative_sources=sources,
            evidence_identifiers=evidence,
            evaluated_at=eval_time,
        )

    @staticmethod
    def evaluate_rg05(project: Project, board: Optional[EngineeringBoard], dfm: Optional[ManufacturingAnalysisRecord], eval_time: datetime) -> ReleaseGateDetail:
        """RG-05: DFM Fabrication Clearance"""
        if project.project_type == ProjectType.GENERAL.value and not board:
            return ReleaseGateDetail(
                gate_id="RG-05",
                name="DFM Fabrication Clearance",
                status=ReleaseGateStatus.NOT_APPLICABLE,
                applicable_scope="DFM",
                is_applicable=False,
                not_applicable_reason="Project type is GENERAL without board fabrication requirement.",
                evaluated_at=eval_time,
            )

        if not dfm:
            return ReleaseGateDetail(
                gate_id="RG-05",
                name="DFM Fabrication Clearance",
                status=ReleaseGateStatus.BLOCKED,
                applicable_scope="DFM",
                is_applicable=True,
                failure_reasons=["DFM manufacturing analysis record not found."],
                missing_evidence=["ManufacturingAnalysisRecord"],
                evaluated_at=eval_time,
            )

        sources = [f"manufacturing_analysis_records.id:{dfm.id}"]
        evidence = [{"entity": "ManufacturingAnalysisRecord", "id": str(dfm.id), "status": dfm.status, "board_revision": dfm.board_revision}]

        if board and dfm.board_revision < board.version:
            return ReleaseGateDetail(
                gate_id="RG-05",
                name="DFM Fabrication Clearance",
                status=ReleaseGateStatus.STALE,
                applicable_scope="DFM",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"DFM analysis ran on board version {dfm.board_revision}, but current board is version {board.version}."],
                stale_reasons=["PCB board copper or outline modified after DFM analysis."],
                evaluated_at=eval_time,
            )

        if dfm.status != ManufacturingAnalysisStatus.COMPLETED.value:
            return ReleaseGateDetail(
                gate_id="RG-05",
                name="DFM Fabrication Clearance",
                status=ReleaseGateStatus.FAIL,
                applicable_scope="DFM",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"DFM analysis status is '{dfm.status}', required 'COMPLETED'."],
                evaluated_at=eval_time,
            )

        critical_findings = [f for f in dfm.findings if f.get("severity") in ("CRITICAL", "HIGH", "FAIL") and f.get("status") == "FAIL"]
        if critical_findings:
            return ReleaseGateDetail(
                gate_id="RG-05",
                name="DFM Fabrication Clearance",
                status=ReleaseGateStatus.FAIL,
                applicable_scope="DFM",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"DFM analysis reported {len(critical_findings)} fabrication clearance violations."],
                evaluated_at=eval_time,
            )

        return ReleaseGateDetail(
            gate_id="RG-05",
            name="DFM Fabrication Clearance",
            status=ReleaseGateStatus.PASS,
            applicable_scope="DFM",
            is_applicable=True,
            authoritative_sources=sources,
            evidence_identifiers=evidence,
            evaluated_at=eval_time,
        )

    @staticmethod
    def evaluate_rg06(requirements: List[EngineeringRequirement], eval_time: datetime) -> ReleaseGateDetail:
        """RG-06: Requirements Satisfaction Coverage"""
        if not requirements:
            return ReleaseGateDetail(
                gate_id="RG-06",
                name="Requirements Satisfaction Coverage",
                status=ReleaseGateStatus.UNKNOWN,
                applicable_scope="REQUIREMENTS",
                is_applicable=True,
                failure_reasons=["Zero formal engineering requirements defined for project (UNKNOWN != SATISFIED)."],
                missing_evidence=["EngineeringRequirement entities"],
                evaluated_at=eval_time,
            )

        sources = [f"engineering_requirements.count:{len(requirements)}"]
        evidence = [{"id": str(r.id), "key": r.requirement_key, "status": r.status, "category": r.category} for r in requirements]

        violated = [r for r in requirements if r.status == RequirementStatus.VIOLATED.value]
        if violated:
            return ReleaseGateDetail(
                gate_id="RG-06",
                name="Requirements Satisfaction Coverage",
                status=ReleaseGateStatus.FAIL,
                applicable_scope="REQUIREMENTS",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"{len(violated)} requirements are marked VIOLATED: {[r.requirement_key for r in violated]}."],
                evaluated_at=eval_time,
            )

        unsatisfied = [r for r in requirements if r.status not in (RequirementStatus.SATISFIED.value, RequirementStatus.SUPERSEDED.value)]
        if unsatisfied:
            return ReleaseGateDetail(
                gate_id="RG-06",
                name="Requirements Satisfaction Coverage",
                status=ReleaseGateStatus.BLOCKED,
                applicable_scope="REQUIREMENTS",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"{len(unsatisfied)} requirements not satisfied (UNKNOWN != SATISFIED): {[r.requirement_key for r in unsatisfied]}."],
                missing_evidence=[f"Verification evidence for requirement {r.requirement_key}" for r in unsatisfied],
                evaluated_at=eval_time,
            )

        return ReleaseGateDetail(
            gate_id="RG-06",
            name="Requirements Satisfaction Coverage",
            status=ReleaseGateStatus.PASS,
            applicable_scope="REQUIREMENTS",
            is_applicable=True,
            authoritative_sources=sources,
            evidence_identifiers=evidence,
            evaluated_at=eval_time,
        )

    @staticmethod
    def evaluate_rg07(circuit: Optional[Circuit], evidence_items: List[EngineeringEvidence], eval_time: datetime) -> ReleaseGateDetail:
        """RG-07: Physical Verification & Testing Evidence"""
        if not evidence_items:
            return ReleaseGateDetail(
                gate_id="RG-07",
                name="Physical Verification & Testing Evidence",
                status=ReleaseGateStatus.UNKNOWN,
                applicable_scope="VERIFICATION",
                is_applicable=True,
                failure_reasons=["Zero physical/test verification evidence items recorded (CALCULATED != PHYSICALLY VERIFIED)."],
                missing_evidence=["EngineeringEvidence records"],
                evaluated_at=eval_time,
            )

        sources = [f"engineering_evidence.count:{len(evidence_items)}"]
        evidence = [{"id": str(e.id), "status": e.status, "type": e.evidence_type, "rev": e.circuit_revision} for e in evidence_items]

        target_circuit_rev = circuit.version if circuit else 1

        stale_evidence = [e for e in evidence_items if e.circuit_revision is not None and e.circuit_revision < target_circuit_rev]
        if stale_evidence:
            return ReleaseGateDetail(
                gate_id="RG-07",
                name="Physical Verification & Testing Evidence",
                status=ReleaseGateStatus.STALE,
                applicable_scope="VERIFICATION",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"{len(stale_evidence)} evidence items correspond to historical revisions (HISTORICAL VERIFICATION != CURRENT VERIFICATION)."],
                stale_evidence=[str(e.id) for e in stale_evidence],
                evaluated_at=eval_time,
            )

        invalid_evidence = [e for e in evidence_items if e.status != EvidenceStatus.VALID.value]
        if invalid_evidence:
            return ReleaseGateDetail(
                gate_id="RG-07",
                name="Physical Verification & Testing Evidence",
                status=ReleaseGateStatus.FAIL,
                applicable_scope="VERIFICATION",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"{len(invalid_evidence)} evidence items have invalid/expired status."],
                evaluated_at=eval_time,
            )

        return ReleaseGateDetail(
            gate_id="RG-07",
            name="Physical Verification & Testing Evidence",
            status=ReleaseGateStatus.PASS,
            applicable_scope="VERIFICATION",
            is_applicable=True,
            authoritative_sources=sources,
            evidence_identifiers=evidence,
            evaluated_at=eval_time,
        )

    @staticmethod
    def evaluate_rg08(unknowns: List[EngineeringUnknownDisposition], decisions: List[EngineeringDecisionRecord], eval_time: datetime) -> ReleaseGateDetail:
        """RG-08: Engineering Unknown Dispositions"""
        sources = [f"engineering_unknown_dispositions.count:{len(unknowns)}"]
        evidence = [{"id": str(u.id), "key": u.unknown_key, "status": u.status, "actor": u.actor} for u in unknowns]

        open_unknowns = [u for u in unknowns if u.status != UnknownDispositionStatus.ACCEPTED.value]
        if open_unknowns:
            return ReleaseGateDetail(
                gate_id="RG-08",
                name="Engineering Unknown Dispositions",
                status=ReleaseGateStatus.BLOCKED,
                applicable_scope="DECISIONS",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"{len(open_unknowns)} unknowns are unresolved without human disposition (UNKNOWN != PASS)."],
                evaluated_at=eval_time,
            )

        return ReleaseGateDetail(
            gate_id="RG-08",
            name="Engineering Unknown Dispositions",
            status=ReleaseGateStatus.PASS,
            applicable_scope="DECISIONS",
            is_applicable=True,
            authoritative_sources=sources,
            evidence_identifiers=evidence,
            evaluated_at=eval_time,
        )

    AUTHORIZED_HUMAN_ROLES = {
        "ENGINEER",
        "LEAD_ENGINEER",
        "STAFF_ENGINEER",
        "PRINCIPAL_ENGINEER",
        "ADMIN",
        "SYSTEM:ADMIN",
        "SYSTEM_ADMIN",
    }

    @classmethod
    def is_authorized_human_role(cls, user: AuthenticatedUser) -> bool:
        """
        Validates whether user possesses an authoritative human engineering role.
        Enforces exact role matching and rejects all AI, synthetic, or ambiguous roles.
        """
        role = getattr(user, "role", "").strip().upper()
        if not role:
            return False
        # Categorically reject any AI identity
        if "AI" in role or "BOT" in role or "COPILOT" in role or role == "AI_AGENT":
            return False
        if getattr(user, "is_admin", False) and role in ("ADMIN", "SYSTEM:ADMIN", "SYSTEM_ADMIN"):
            return True
        return role in cls.AUTHORIZED_HUMAN_ROLES

    @staticmethod
    def evaluate_rg09(user: AuthenticatedUser, eval_time: datetime) -> ReleaseGateDetail:
        """RG-09: Human Release Authorization Check"""
        role = getattr(user, "role", "").strip().upper()
        is_admin = getattr(user, "is_admin", False)
        is_authorized = ReleaseGateEngine.is_authorized_human_role(user)

        sources = [f"users.id:{user.id}", f"users.role:{role}"]
        evidence = [{"user_id": str(user.id), "role": role, "is_admin": is_admin}]

        if not is_authorized:
            return ReleaseGateDetail(
                gate_id="RG-09",
                name="Human Release Authorization",
                status=ReleaseGateStatus.BLOCKED,
                applicable_scope="GOVERNANCE",
                is_applicable=True,
                authoritative_sources=sources,
                evidence_identifiers=evidence,
                failure_reasons=[f"Caller role '{role}' is not authorized to sign off releases (AI ENGINEERING AUTHORITY = NONE)."],
                evaluated_at=eval_time,
            )

        return ReleaseGateDetail(
            gate_id="RG-09",
            name="Human Release Authorization",
            status=ReleaseGateStatus.PASS,
            applicable_scope="GOVERNANCE",
            is_applicable=True,
            authoritative_sources=sources,
            evidence_identifiers=evidence,
            evaluated_at=eval_time,
        )


class ReleaseService:
    """
    Authoritative Release Service managing evaluations and immutable baselines.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditLedgerService(db)

    async def evaluate_release_readiness(
        self,
        project_id: str,
        user: AuthenticatedUser,
        request: Optional[ReleaseEvaluationRequest] = None,
    ) -> EngineeringReleaseEvaluation:
        proj_stmt = select(Project).where(Project.id == project_id)
        if user.tenant_id:
            proj_stmt = proj_stmt.where(Project.tenant_id == user.tenant_id)
        proj_res = await self.db.execute(proj_stmt)
        project = proj_res.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found or tenant access denied.",
            )

    async def _gather_authoritative_inputs(
        self,
        project_id: str,
        request: Optional[ReleaseEvaluationRequest] = None,
    ) -> Dict[str, Any]:
        """
        Loads all authoritative records across engineering domains that influence Release Gates RG-01 through RG-09.
        """
        # Circuit
        c_stmt = (
            select(Circuit)
            .where(Circuit.project_id == project_id)
            .options(
                selectinload(Circuit.components),
                selectinload(Circuit.nets),
                selectinload(Circuit.connections),
            )
            .order_by(desc(Circuit.created_at))
        )
        if request and request.circuit_id:
            c_stmt = c_stmt.where(Circuit.id == request.circuit_id)
        c_res = await self.db.execute(c_stmt)
        circuit = c_res.scalars().first()

        # Board
        b_stmt = (
            select(EngineeringBoard)
            .where(EngineeringBoard.project_id == project_id)
            .options(
                selectinload(EngineeringBoard.layers),
                selectinload(EngineeringBoard.footprints).selectinload(BoardFootprint.pads),
                selectinload(EngineeringBoard.traces),
                selectinload(EngineeringBoard.vias),
            )
            .order_by(desc(EngineeringBoard.created_at))
        )
        if request and request.board_id:
            b_stmt = b_stmt.where(EngineeringBoard.id == request.board_id)
        b_res = await self.db.execute(b_stmt)
        board = b_res.scalars().first()

        # BOM
        bom_stmt = (
            select(EngineeringBOM)
            .where(EngineeringBOM.project_id == project_id)
            .options(selectinload(EngineeringBOM.lines))
            .order_by(desc(EngineeringBOM.created_at))
        )
        if request and request.bom_id:
            bom_stmt = bom_stmt.where(EngineeringBOM.id == request.bom_id)
        bom_res = await self.db.execute(bom_stmt)
        bom = bom_res.scalars().first()

        # Cross-Domain validation record
        xd_stmt = (
            select(CrossDomainValidationRecord)
            .where(CrossDomainValidationRecord.project_id == project_id)
            .order_by(desc(CrossDomainValidationRecord.created_at))
        )
        xd_res = await self.db.execute(xd_stmt)
        xd_record = xd_res.scalars().first()

        # DFM Analysis
        dfm_record = None
        if board:
            dfm_stmt = (
                select(ManufacturingAnalysisRecord)
                .where(ManufacturingAnalysisRecord.board_id == board.id)
                .order_by(desc(ManufacturingAnalysisRecord.created_at))
            )
            dfm_res = await self.db.execute(dfm_stmt)
            dfm_record = dfm_res.scalars().first()
        elif circuit:
            dfm_stmt = (
                select(ManufacturingAnalysisRecord)
                .where(ManufacturingAnalysisRecord.circuit_id == circuit.id)
                .order_by(desc(ManufacturingAnalysisRecord.created_at))
            )
            dfm_res = await self.db.execute(dfm_stmt)
            dfm_record = dfm_res.scalars().first()

        # Requirements
        req_stmt = select(EngineeringRequirement).where(EngineeringRequirement.project_id == project_id).order_by(EngineeringRequirement.requirement_key)
        req_res = await self.db.execute(req_stmt)
        requirements = list(req_res.scalars().all())

        # Evidence
        try:
            ev_stmt = (
                select(EngineeringEvidence)
                .join(EngineeringDesignReview, EngineeringEvidence.review_id == EngineeringDesignReview.id)
                .where(EngineeringDesignReview.project_id == project_id)
                .order_by(EngineeringEvidence.id)
            )
            ev_res = await self.db.execute(ev_stmt)
            evidence_items = list(ev_res.scalars().all())
        except Exception:
            evidence_items = []
        if not evidence_items and circuit:
            ev_direct_stmt = select(EngineeringEvidence).where(EngineeringEvidence.circuit_id == circuit.id).order_by(EngineeringEvidence.id)
            ev_res = await self.db.execute(ev_direct_stmt)
            evidence_items = list(ev_res.scalars().all())

        # Unknowns & Decisions
        dec_stmt = select(EngineeringDecisionRecord).where(EngineeringDecisionRecord.project_id == project_id).order_by(EngineeringDecisionRecord.id)
        dec_res = await self.db.execute(dec_stmt)
        decisions = list(dec_res.scalars().all())

        dec_ids = [d.id for d in decisions]
        if dec_ids:
            unk_stmt = select(EngineeringUnknownDisposition).where(EngineeringUnknownDisposition.decision_id.in_(dec_ids)).order_by(EngineeringUnknownDisposition.id)
            unk_res = await self.db.execute(unk_stmt)
            unknowns = list(unk_res.scalars().all())
        else:
            unknowns = []

        return {
            "circuit": circuit,
            "board": board,
            "bom": bom,
            "xd_record": xd_record,
            "dfm_record": dfm_record,
            "requirements": requirements,
            "evidence_items": evidence_items,
            "decisions": decisions,
            "unknowns": unknowns,
        }

    @classmethod
    def compute_state_fingerprint(
        cls,
        project_id: str,
        inputs: Dict[str, Any],
        audit_head_hash: Optional[str],
        readiness: Optional[str] = None,
    ) -> str:
        """
        Computes a deterministic SHA-256 fingerprint capturing the full state of every authoritative
        input influencing Release Gates RG-01 through RG-09.
        """
        circuit = inputs.get("circuit")
        board = inputs.get("board")
        bom = inputs.get("bom")
        xd = inputs.get("xd_record")
        dfm = inputs.get("dfm_record")
        reqs = inputs.get("requirements") or []
        evs = inputs.get("evidence_items") or []
        unk = inputs.get("unknowns") or []

        circuit_repr = None
        if circuit:
            circuit_repr = {
                "id": str(circuit.id),
                "version": int(circuit.version),
                "validation_status": str(circuit.validation_status),
                "components_count": len(circuit.components),
                "nets_count": len(circuit.nets),
            }

        board_repr = None
        if board:
            board_repr = {
                "id": str(board.id),
                "version": int(board.version),
                "circuit_version": int(board.circuit_version) if board.circuit_version is not None else None,
                "status": str(board.status),
                "footprints_count": len(board.footprints),
                "traces_count": len(board.traces),
                "vias_count": len(board.vias),
            }

        bom_repr = None
        if bom:
            bom_repr = {
                "id": str(bom.id),
                "version": int(bom.version),
                "circuit_version": int(bom.circuit_version) if bom.circuit_version is not None else None,
                "status": str(bom.status),
                "lines_count": len(bom.lines),
                "lines_resolved": len([l for l in bom.lines if getattr(l, "manufacturer_part_number", None)]),
            }

        xd_repr = None
        if xd:
            xd_repr = {
                "id": str(xd.id),
                "status": str(xd.validation_status),
                "is_stale": bool(xd.is_stale),
                "snapshot_digest": str(xd.snapshot_digest),
                "findings_count": len(xd.findings) if isinstance(xd.findings, list) else 0,
            }

        dfm_repr = None
        if dfm:
            dfm_repr = {
                "id": str(dfm.id),
                "status": str(dfm.status),
                "board_revision": int(dfm.board_revision) if dfm.board_revision is not None else None,
                "findings_count": len(dfm.findings) if isinstance(dfm.findings, list) else 0,
            }

        reqs_repr = sorted([
            {"id": str(r.id), "key": str(r.requirement_key), "status": str(r.status)}
            for r in reqs
        ], key=lambda x: x["key"])

        evs_repr = sorted([
            {"id": str(e.id), "status": str(e.status), "rev": e.circuit_revision}
            for e in evs
        ], key=lambda x: x["id"])

        unk_repr = sorted([
            {"id": str(u.id), "key": str(u.unknown_key), "status": str(u.status)}
            for u in unk
        ], key=lambda x: x["key"])

        decs = inputs.get("decisions") or []
        decs_repr = sorted([
            {"id": str(d.id), "status": str(d.status), "rev": getattr(d, "revision", None)}
            for d in decs
        ], key=lambda x: x["id"])

        fingerprint_data = {
            "project_id": str(project_id),
            "circuit": circuit_repr,
            "board": board_repr,
            "bom": bom_repr,
            "cross_domain": xd_repr,
            "dfm": dfm_repr,
            "requirements": reqs_repr,
            "evidence": evs_repr,
            "decisions": decs_repr,
            "unknowns": unk_repr,
            "audit_head_hash": str(audit_head_hash) if audit_head_hash is not None else None,
            "readiness": str(readiness) if readiness is not None else None,
        }
        canonical_json = json.dumps(fingerprint_data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    async def evaluate_release_readiness(
        self,
        project_id: str,
        user: AuthenticatedUser,
        request: Optional[ReleaseEvaluationRequest] = None,
    ) -> EngineeringReleaseEvaluation:
        proj_stmt = select(Project).where(Project.id == project_id)
        if user.tenant_id:
            proj_stmt = proj_stmt.where(Project.tenant_id == user.tenant_id)
        proj_res = await self.db.execute(proj_stmt)
        project = proj_res.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found or tenant access denied.",
            )

        eval_time = datetime.now(timezone.utc)
        inputs = await self._gather_authoritative_inputs(project_id, request)

        circuit = inputs["circuit"]
        board = inputs["board"]
        bom = inputs["bom"]
        xd_record = inputs["xd_record"]
        dfm_record = inputs["dfm_record"]
        requirements = inputs["requirements"]
        evidence_items = inputs["evidence_items"]
        decisions = inputs["decisions"]
        unknowns = inputs["unknowns"]

        # Evaluate All 9 Gates
        g1 = ReleaseGateEngine.evaluate_rg01(circuit, eval_time)
        g2 = ReleaseGateEngine.evaluate_rg02(project, circuit, board, eval_time)
        g3 = ReleaseGateEngine.evaluate_rg03(circuit, bom, eval_time)
        g4 = ReleaseGateEngine.evaluate_rg04(xd_record, eval_time)
        g5 = ReleaseGateEngine.evaluate_rg05(project, board, dfm_record, eval_time)
        g6 = ReleaseGateEngine.evaluate_rg06(requirements, eval_time)
        g7 = ReleaseGateEngine.evaluate_rg07(circuit, evidence_items, eval_time)
        g8 = ReleaseGateEngine.evaluate_rg08(unknowns, decisions, eval_time)
        g9 = ReleaseGateEngine.evaluate_rg09(user, eval_time)

        gate_map = {
            "RG-01": g1, "RG-02": g2, "RG-03": g3,
            "RG-04": g4, "RG-05": g5, "RG-06": g6,
            "RG-07": g7, "RG-08": g8, "RG-09": g9,
        }

        # Audit Chain Verification
        expected_anchor = request.expected_audit_head_hash if request else None
        chain_verify = await self.audit_service.verify_chain(
            project_id=project_id,
            expected_head_hash=expected_anchor,
        )

        audit_verified = chain_verify.get("is_valid", False)
        audit_head_hash = chain_verify.get("head_hash")
        audit_seq = chain_verify.get("latest_sequence_number", 0)

        # Check if current audit head is anchored by a verified RFC 3161 anchor
        anchor_stmt = (
            select(EngineeringAuditAnchor)
            .where(
                EngineeringAuditAnchor.project_id == project_id,
                EngineeringAuditAnchor.to_sequence == audit_seq,
                EngineeringAuditAnchor.status == AnchorStatus.ANCHORED.value,
            )
            .limit(1)
        )
        anchor_res = await self.db.execute(anchor_stmt)
        verified_anchor = anchor_res.scalar_one_or_none()
        anchor_checked = (expected_anchor is not None) or (verified_anchor is not None)

        # Derive Overall Readiness State
        blocking = []
        missing = []
        stale = []

        for gid, g in gate_map.items():
            if g.failure_reasons:
                blocking.append({"gate_id": gid, "reasons": g.failure_reasons})
            if g.missing_evidence:
                missing.append({"gate_id": gid, "items": g.missing_evidence})
            if g.stale_reasons:
                stale.append({"gate_id": gid, "reasons": g.stale_reasons})

        statuses = [g.status for g in gate_map.values() if g.is_applicable]

        if not audit_verified:
            readiness = OverallReadinessState.BLOCKED.value
            blocking.append({"gate_id": "AUDIT_LEDGER", "reasons": ["Audit chain validation failed; tamper or discontinuity detected."]})
        elif any(s == ReleaseGateStatus.BLOCKED for s in statuses):
            readiness = OverallReadinessState.BLOCKED.value
        elif any(s == ReleaseGateStatus.STALE for s in statuses):
            readiness = OverallReadinessState.STALE.value
        elif any(s in (ReleaseGateStatus.FAIL, ReleaseGateStatus.UNKNOWN) for s in statuses):
            readiness = OverallReadinessState.NOT_READY.value
        elif all(s in (ReleaseGateStatus.PASS, ReleaseGateStatus.NOT_APPLICABLE) for s in statuses):
            readiness = OverallReadinessState.READY_FOR_RELEASE.value
        else:
            readiness = OverallReadinessState.NOT_READY.value

        state_fingerprint = self.compute_state_fingerprint(
            project_id=project_id,
            inputs=inputs,
            audit_head_hash=audit_head_hash,
            readiness=readiness,
        )

        evaluation = EngineeringReleaseEvaluation(
            id=str(uuid.uuid4()),
            project_id=project_id,
            tenant_id=user.tenant_id,
            evaluator_version=ReleaseGateEngine.EVALUATOR_VERSION,
            project_revision=circuit.version if circuit else 1,
            overall_readiness=readiness,
            is_stale=False,
            state_fingerprint=state_fingerprint,
            gate_results={gid: g.model_dump(mode="json") for gid, g in gate_map.items()},
            blocking_findings=blocking,
            missing_evidence=missing,
            stale_evidence=stale,
            audit_chain_verified=audit_verified,
            audit_chain_head_hash=audit_head_hash,
            audit_chain_sequence=audit_seq,
            audit_chain_trusted_anchor_checked=anchor_checked,
            evaluated_by_id=user.id,
            evaluated_at=eval_time,
        )

        self.db.add(evaluation)
        await self.db.commit()
        await self.db.refresh(evaluation)
        return evaluation

    async def check_is_stale(self, evaluation: EngineeringReleaseEvaluation) -> bool:
        """
        Dynamically verifies whether an evaluation has become stale due to:
        - Authoritative circuit revision change
        - Audit ledger advancement or mutation
        - Any authoritative engineering state change affecting RG-01 through RG-09
        """
        if evaluation.is_stale:
            return True

        project_id = evaluation.project_id
        current_inputs = await self._gather_authoritative_inputs(project_id)
        current_circuit = current_inputs.get("circuit")
        current_circuit_ver = current_circuit.version if current_circuit else 1

        if current_circuit_ver != evaluation.project_revision:
            return True

        current_chain_verify = await self.audit_service.verify_chain(project_id=project_id)
        current_audit_head = current_chain_verify.get("head_hash")

        if not current_chain_verify.get("is_valid", False):
            return True

        if current_audit_head != evaluation.audit_chain_head_hash:
            return True

        current_state_fingerprint = self.compute_state_fingerprint(
            project_id=project_id,
            inputs=current_inputs,
            audit_head_hash=current_audit_head,
            readiness=evaluation.overall_readiness,
        )

        return current_state_fingerprint != evaluation.state_fingerprint

    async def get_evaluation(
        self,
        evaluation_id: str,
        user: AuthenticatedUser,
    ) -> EngineeringReleaseEvaluation:
        stmt = select(EngineeringReleaseEvaluation).where(EngineeringReleaseEvaluation.id == evaluation_id)
        if user.tenant_id:
            stmt = stmt.where(EngineeringReleaseEvaluation.tenant_id == user.tenant_id)
        res = await self.db.execute(stmt)
        ev = res.scalar_one_or_none()
        if not ev:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Release evaluation {evaluation_id} not found or access denied.",
            )
        # Dynamically check staleness against live state
        if not ev.is_stale and await self.check_is_stale(ev):
            ev.is_stale = True
        return ev

    async def get_latest_evaluation(
        self,
        project_id: str,
        user: AuthenticatedUser,
    ) -> EngineeringReleaseEvaluation:
        stmt = (
            select(EngineeringReleaseEvaluation)
            .where(EngineeringReleaseEvaluation.project_id == project_id)
            .order_by(desc(EngineeringReleaseEvaluation.evaluated_at))
        )
        if user.tenant_id:
            stmt = stmt.where(EngineeringReleaseEvaluation.tenant_id == user.tenant_id)
        res = await self.db.execute(stmt)
        ev = res.scalars().first()
        if not ev:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No release evaluation found for project {project_id}.",
            )
        # Dynamically check staleness against live state
        if not ev.is_stale and await self.check_is_stale(ev):
            ev.is_stale = True
        return ev

    async def authorize_release_baseline(
        self,
        project_id: str,
        request: ReleaseBaselineCreateRequest,
        user: AuthenticatedUser,
    ) -> EngineeringReleaseBaseline:
        role = getattr(user, "role", "").strip().upper()
        if not ReleaseGateEngine.is_authorized_human_role(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Release authorization denied: AI or unauthorized actor role '{role}'. (AI ENGINEERING AUTHORITY = NONE).",
            )

        proj_stmt = (
            select(Project)
            .where(Project.id == project_id)
            .with_for_update()
        )
        if user.tenant_id:
            proj_stmt = proj_stmt.where(Project.tenant_id == user.tenant_id)
        proj_res = await self.db.execute(proj_stmt)
        project = proj_res.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found or tenant access denied.",
            )

        tag_stmt = select(EngineeringReleaseBaseline).where(
            EngineeringReleaseBaseline.project_id == project_id,
            EngineeringReleaseBaseline.release_tag == request.release_tag,
        )
        tag_res = await self.db.execute(tag_stmt)
        if tag_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Release tag '{request.release_tag}' already exists for project {project_id}.",
            )

        evaluation = await self.get_evaluation(request.evaluation_id, user)
        if evaluation.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Evaluation {request.evaluation_id} belongs to a different project.",
            )

        # Freshness Check: Re-gather authoritative inputs and recompute state fingerprint
        current_inputs = await self._gather_authoritative_inputs(project_id)
        current_circuit = current_inputs.get("circuit")
        current_circuit_ver = current_circuit.version if current_circuit else 1

        if current_circuit_ver != evaluation.project_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"RELEASE_EVALUATION_STALE: Circuit revision changed ({current_circuit_ver} != {evaluation.project_revision}). Re-evaluation required.",
            )

        # Audit Chain Freshness: Verify audit chain has not diverged or advanced past evaluation anchor
        current_chain_verify = await self.audit_service.verify_chain(project_id=project_id)
        current_audit_head = current_chain_verify.get("head_hash")

        if not current_chain_verify.get("is_valid", False):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="RELEASE_EVALUATION_STALE: Audit chain integrity verification failed.",
            )

        if current_audit_head != evaluation.audit_chain_head_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"RELEASE_EVALUATION_STALE: Audit ledger has advanced or mutated post-evaluation ({current_audit_head} != {evaluation.audit_chain_head_hash}). Re-evaluation required.",
            )

        current_state_fingerprint = self.compute_state_fingerprint(
            project_id=project_id,
            inputs=current_inputs,
            audit_head_hash=current_audit_head,
            readiness=evaluation.overall_readiness,
        )

        if current_state_fingerprint != evaluation.state_fingerprint:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="RELEASE_EVALUATION_STALE: Authoritative engineering state changed post-evaluation. Re-evaluation required.",
            )

        circuit = current_circuit

        if evaluation.overall_readiness != OverallReadinessState.READY_FOR_RELEASE.value:
            if not request.exceptions_approved:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot authorize release baseline: evaluation readiness is '{evaluation.overall_readiness}'. All required gates must PASS.",
                )

        circuit_digest = None
        if circuit:
            c_data = {"id": circuit.id, "version": circuit.version, "components": len(circuit.components), "nets": len(circuit.nets)}
            circuit_digest = hashlib.sha256(json.dumps(c_data, sort_keys=True).encode("utf-8")).hexdigest()

        board = current_inputs.get("board")
        board_digest = None
        if board:
            b_data = {"id": board.id, "version": board.version, "traces": len(board.traces), "footprints": len(board.footprints)}
            board_digest = hashlib.sha256(json.dumps(b_data, sort_keys=True).encode("utf-8")).hexdigest()

        bom = current_inputs.get("bom")
        bom_digest = None
        if bom:
            bm_data = {"id": bom.id, "version": bom.version, "lines": len(bom.lines)}
            bom_digest = hashlib.sha256(json.dumps(bm_data, sort_keys=True).encode("utf-8")).hexdigest()

        snapshot_manifest = {
            "release_tag": request.release_tag,
            "project_id": project_id,
            "evaluation_id": evaluation.id,
            "project_revision": evaluation.project_revision,
            "circuit_digest": circuit_digest,
            "board_digest": board_digest,
            "bom_digest": bom_digest,
            "gate_results": evaluation.gate_results,
            "audit_head_hash": evaluation.audit_chain_head_hash,
            "audit_sequence": evaluation.audit_chain_sequence,
            "authorized_by": user.id,
            "release_rationale": request.release_rationale,
            "exceptions_approved": request.exceptions_approved,
        }
        canonical_snapshot_digest = hashlib.sha256(
            json.dumps(snapshot_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        auth_time = datetime.now(timezone.utc)
        baseline = EngineeringReleaseBaseline(
            id=str(uuid.uuid4()),
            release_tag=request.release_tag,
            project_id=project_id,
            tenant_id=user.tenant_id,
            evaluation_id=evaluation.id,
            project_revision=evaluation.project_revision,
            circuit_id=circuit.id if circuit else None,
            circuit_version=circuit.version if circuit else None,
            circuit_digest=circuit_digest,
            board_id=board.id if board else None,
            board_version=board.version if board else None,
            board_digest=board_digest,
            bom_id=bom.id if bom else None,
            bom_version=bom.version if bom else None,
            bom_digest=bom_digest,
            audit_chain_head_hash=evaluation.audit_chain_head_hash or "GENESIS",
            audit_chain_sequence=evaluation.audit_chain_sequence or 0,
            audit_chain_trusted_anchor_checked=evaluation.audit_chain_trusted_anchor_checked,
            evaluation_snapshot=snapshot_manifest,
            canonical_snapshot_digest=canonical_snapshot_digest,
            authorized_by_id=user.id,
            authorized_by_role=role,
            authorized_at=auth_time,
            release_rationale=request.release_rationale,
            exceptions_approved=request.exceptions_approved,
        )

        try:
            self.db.add(baseline)
            await self.db.flush()

            # Stage RELEASE_BASELINE_CREATED audit event atomically
            await self.audit_service.record_event(
                project_id=project_id,
                actor_id=user.id,
                actor_role=role,
                event_type=AuditEventType.RELEASE_BASELINE_CREATED,
                entity_type="RELEASE_BASELINE",
                entity_id=baseline.id,
                entity_revision=evaluation.project_revision,
                payload={
                    "baseline_id": baseline.id,
                    "release_tag": baseline.release_tag,
                    "evaluation_id": evaluation.id,
                    "canonical_snapshot_digest": canonical_snapshot_digest,
                    "authorized_by": user.id,
                    "role": role,
                },
                tenant_id=user.tenant_id,
                commit=False,
            )

            await self.db.commit()
            await self.db.refresh(baseline)
            return baseline
        except Exception:
            await self.db.rollback()
            raise

    async def list_baselines(
        self,
        project_id: str,
        user: AuthenticatedUser,
    ) -> List[EngineeringReleaseBaseline]:
        stmt = (
            select(EngineeringReleaseBaseline)
            .where(EngineeringReleaseBaseline.project_id == project_id)
            .order_by(desc(EngineeringReleaseBaseline.authorized_at))
        )
        if user.tenant_id:
            stmt = stmt.where(EngineeringReleaseBaseline.tenant_id == user.tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_baseline(
        self,
        baseline_id: str,
        user: AuthenticatedUser,
    ) -> EngineeringReleaseBaseline:
        stmt = select(EngineeringReleaseBaseline).where(EngineeringReleaseBaseline.id == baseline_id)
        if user.tenant_id:
            stmt = stmt.where(EngineeringReleaseBaseline.tenant_id == user.tenant_id)
        res = await self.db.execute(stmt)
        b = res.scalar_one_or_none()
        if not b:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Release baseline {baseline_id} not found or access denied.",
            )
        return b
