from typing import Any, Dict, List, Optional, Set
from fastapi import HTTPException, status

from app.models.db.cognitive import EngineeringContextSnapshot
from app.models.schemas.cognitive import (
    ContextExplainRequest,
    ContextExplanationResponse,
)


class EngineeringContextExplanationService:
    """
    Produces grounded, traceable human-readable explanations from an EngineeringContextSnapshot.

    INVARIANTS:
    - STRUCTURED CONTEXT > AI EXPLANATION
    - Every explanation assertion must be traceable to genuine context references.
    - AI hallucinated or foreign references must fail safely with MODEL_INVALID_REFERENCE.
    - ZERO SYNTHETIC SCORING.
    """

    @classmethod
    def explain_context(
        cls,
        snapshot: EngineeringContextSnapshot,
        request: ContextExplainRequest,
    ) -> ContextExplanationResponse:
        """
        Synthesizes a grounded explanation of the current engineering context and validates references.
        """
        # 1. Collect all authorized reference IDs present in the snapshot
        authorized_ids: Set[str] = set()

        if snapshot.project_id:
            authorized_ids.add(snapshot.project_id)
        if snapshot.circuit_id:
            authorized_ids.add(snapshot.circuit_id)
        if snapshot.system_id:
            authorized_ids.add(snapshot.system_id)

        # Components & Nets
        for c in (snapshot.current_state or {}).get("components", []):
            if isinstance(c, dict) and "id" in c:
                authorized_ids.add(c["id"])
        for n in (snapshot.current_state or {}).get("nets", []):
            if isinstance(n, dict) and "id" in n:
                authorized_ids.add(n["id"])

        # Analyses
        for a in snapshot.deterministic_results or []:
            if isinstance(a, dict) and "analysis_id" in a:
                authorized_ids.add(a["analysis_id"])

        # Requirements
        for r in snapshot.requirements or []:
            if isinstance(r, dict) and "id" in r:
                authorized_ids.add(r["id"])

        # Assumptions
        for assump in snapshot.assumptions or []:
            if isinstance(assump, dict) and "id" in assump:
                authorized_ids.add(assump["id"])

        # Decisions
        for d in snapshot.decision_history or []:
            if isinstance(d, dict) and "id" in d:
                authorized_ids.add(d["id"])

        # Verification requirements
        for vr in (snapshot.verification_state or {}).get("requirements", []):
            if isinstance(vr, dict) and "id" in vr:
                authorized_ids.add(vr["id"])

        # Memories
        for mem in snapshot.historical_memory or []:
            if isinstance(mem, dict):
                inner_mem = mem.get("memory") or {}
                if "id" in inner_mem:
                    authorized_ids.add(inner_mem["id"])

        # 2. Check focus areas / requested references for hallucination
        focus_areas = request.focus_areas or []
        for ref in focus_areas:
            if ref not in authorized_ids:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "MODEL_INVALID_REFERENCE",
                        "message": f"Explanation requested reference '{ref}' does not exist in the authoritative engineering context.",
                    },
                )

        # 3. Formulate structured, traceable overview
        num_components = len((snapshot.current_state or {}).get("components", []))
        num_requirements = len(snapshot.requirements or [])
        num_conflicts = len(snapshot.conflicts or [])
        num_unknowns = len(snapshot.unknowns or [])

        lines = [
            f"Engineering context synthesis for Project '{snapshot.project_id}' at baseline revision {snapshot.base_revision}.",
            f"Hardware topology contains {num_components} characterized components.",
            f"Requirement evaluation tracked across {num_requirements} formal specifications.",
        ]

        if num_conflicts > 0:
            lines.append(f"CRITICAL: {num_conflicts} engineering contradictions or conflicts detected requiring human resolution.")
        else:
            lines.append("No direct physical or specification conflicts detected in active baseline.")

        if num_unknowns > 0:
            lines.append(f"Notice: {num_unknowns} uncharacterized parameters or unknowns flagged requiring verification.")

        explanation_text = " ".join(lines)

        traceable_refs: List[Dict[str, Any]] = [
            {"type": "Project", "id": snapshot.project_id, "revision": snapshot.base_revision},
        ]
        if snapshot.circuit_id:
            traceable_refs.append({"type": "Circuit", "id": snapshot.circuit_id})
        for r in snapshot.requirements or []:
            if isinstance(r, dict) and "id" in r:
                traceable_refs.append({"type": "EngineeringRequirement", "id": r["id"], "state": r.get("state")})

        return ContextExplanationResponse(
            context_id=snapshot.id,
            explanation=explanation_text,
            origin="AI_GENERATED",
            authority="INFORMATIONAL_ONLY",
            traceable_references=traceable_refs,
            unreferenced_assertions=[],
        )
