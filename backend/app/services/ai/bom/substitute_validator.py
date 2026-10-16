"""
BOM Substitute Validator.

Validates and manages component substitution proposals.
Lifecycle:
  Proposal -> Engineering Compatibility Check -> Diff Preview -> Human Approval Gate -> Atomic Mutation.
Strict Invariants:
- AI CANNOT AUTONOMOUSLY SUBSTITUTE COMPONENTS (AI_UNAUTHORIZED_SUBSTITUTION 403).
- REJECTS STALE PROPOSALS (409 Conflict).
- ATOMIC BOM VERSION ADVANCEMENT.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, status

from app.core.dependencies import AuthenticatedUser
from app.models.db.bom import (
    BOMLineStatus,
    BOMSubstitutionProposal,
    ComponentPartCandidate,
    EngineeringBOM,
    EngineeringBOMLine,
    PartCompatibilityStatus,
)
from app.models.db.proposal import ProposalStatus
from app.services.ai.bom.compatibility_engine import BOMCompatibilityEngine


class BOMSubstituteValidator:
    """Validates component substitution proposals and enforces human approval boundary."""

    @classmethod
    def generate_substitution_diff(
        cls,
        line: EngineeringBOMLine,
        candidate: ComponentPartCandidate,
    ) -> Dict[str, Any]:
        """Generates deterministic side-by-side diff comparing original line and candidate."""
        reqs = getattr(line, "engineering_requirements", None) or getattr(line, "required_specifications", None) or {}
        cand_params = getattr(candidate, "parameters", None) or getattr(candidate, "specifications", None) or {}
        cand_pkg = getattr(candidate, "package", None)
        cand_mpn = getattr(candidate, "mpn", None)

        compat_status, evals = BOMCompatibilityEngine.evaluate(
            requirements=reqs,
            candidate_parameters=cand_params,
            candidate_package=cand_pkg,
            candidate_mpn=cand_mpn,
        )

        parameter_diffs: Dict[str, Any] = {}
        eval_list: List[Dict[str, Any]] = []
        for ev in evals:
            item = {
                "parameter": ev.parameter,
                "required": ev.required_value,
                "candidate": ev.actual_value,
                "status": ev.status,
                "message": ev.message,
            }
            parameter_diffs[ev.parameter] = item
            eval_list.append(item)

        orig_mpn = getattr(line, "manufacturer_part_number", None) or getattr(line, "active_mpn", None) or "UNSPECIFIED"
        orig_mfr = getattr(line, "manufacturer", None) or getattr(line, "active_manufacturer", None) or "GENERIC"
        ref_des = getattr(line, "reference_designator", None) or getattr(line, "ref_des", None) or ""

        return {
            "bom_line_id": str(line.id),
            "reference_designator": ref_des,
            "original_part": {
                "manufacturer": orig_mfr,
                "mpn": orig_mpn,
                "value": getattr(line, "design_value", None) or getattr(line, "nominal_value", None),
                "package": getattr(line, "design_package", None) or getattr(line, "package_footprint", None),
            },
            "proposed_part": {
                "manufacturer": candidate.manufacturer,
                "mpn": candidate.mpn,
                "package": candidate.package,
                "lifecycle": candidate.lifecycle_status,
                "availability": candidate.availability_status,
            },
            "engineering_compatibility_status": compat_status,
            "differences": parameter_diffs,
            "parameter_evaluations": eval_list,
            "is_technically_viable": compat_status != PartCompatibilityStatus.NOT_COMPATIBLE.value,
        }

    @classmethod
    def create_proposal(
        cls,
        bom: EngineeringBOM,
        line: EngineeringBOMLine,
        candidate: ComponentPartCandidate,
        proposed_by: str,
        justification: str,
    ) -> BOMSubstitutionProposal:
        """Constructs a BOMSubstitutionProposal with deterministic diff preview."""
        diff_data = cls.generate_substitution_diff(line, candidate)
        version = getattr(bom, "version", 1) or getattr(bom, "revision", 1) or 1
        circuit_version = getattr(bom, "circuit_version", 1) or 1

        proposal = BOMSubstitutionProposal(
            id=str(uuid.uuid4()),
            bom_id=str(bom.id),
            bom_line_id=str(line.id),
            base_bom_revision=version,
            circuit_version=circuit_version,
            tenant_id=bom.tenant_id,
            candidate_id=str(candidate.id),
            proposed_mpn=candidate.mpn,
            proposed_manufacturer=candidate.manufacturer,
            rationale=justification,
            diff_preview=diff_data,
            status=ProposalStatus.PROPOSED.value,
            created_by=proposed_by,
        )
        # Helper property for test assertions
        proposal.target_line_id = str(line.id)
        proposal.differences = diff_data.get("differences", {})
        return proposal

    @classmethod
    def validate_and_apply_approval(
        cls,
        proposal: BOMSubstitutionProposal,
        line: EngineeringBOMLine,
        bom: EngineeringBOM,
        candidate: ComponentPartCandidate,
        user: AuthenticatedUser,
    ) -> bool:
        """
        Enforces human approval boundary, checks for revision staleness,
        and atomically mutates BOM line and advances BOM version.
        """
        # 1. AI Actor Rejection
        actor_role = getattr(user, "role", "") or ""
        actor_id = getattr(user, "id", "") or ""
        norm_role = actor_role.lower()
        norm_id = actor_id.lower()

        if (
            norm_role in ("ai", "ai_agent", "service:ai", "model")
            or norm_id.startswith("ai-")
            or "agent" in norm_id
            or "bot" in norm_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AI_UNAUTHORIZED_SUBSTITUTION: AI actors are strictly prohibited from approving component substitutions. Explicit human engineering approval is required.",
            )

        # 2. Staleness Check
        current_bom_version = getattr(bom, "version", 1) or getattr(bom, "revision", 1) or 1
        if current_bom_version > proposal.base_bom_revision:
            proposal.status = ProposalStatus.STALE.value
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"STALE_BOM_REVISION: BOM revision has advanced from {proposal.base_bom_revision} to {current_bom_version}. Re-evaluation required.",
            )

        # 3. Apply Approval
        proposal.status = ProposalStatus.APPROVED.value
        proposal.approved_by = user.id
        proposal.applied_at = datetime.now(timezone.utc)

        # Update line attributes
        line.manufacturer = candidate.manufacturer
        line.manufacturer_part_number = candidate.mpn
        line.status = BOMLineStatus.SOURCED.value

        # Support alias attributes
        line.active_mpn = candidate.mpn
        line.active_manufacturer = candidate.manufacturer
        line.active_candidate_id = candidate.id

        # Update primary flags on candidates
        for cand in getattr(line, "candidates", []):
            cand.is_primary = (str(cand.id) == str(candidate.id))

        # Advance version/revision
        if hasattr(bom, "version"):
            bom.version += 1
        if hasattr(bom, "revision"):
            bom.revision = bom.version

        return True

    @classmethod
    def apply_substitution(
        cls,
        bom: EngineeringBOM,
        proposal: BOMSubstitutionProposal,
        line: EngineeringBOMLine,
        candidate: ComponentPartCandidate,
        actor_role: str,
        actor_id: str,
    ) -> bool:
        dummy_user = AuthenticatedUser(
            id=actor_id,
            email=f"{actor_id}@quebet.ai",
            role=actor_role,
            tenant_id=bom.tenant_id,
        )
        return cls.validate_and_apply_approval(
            proposal=proposal,
            line=line,
            bom=bom,
            candidate=candidate,
            user=dummy_user,
        )
