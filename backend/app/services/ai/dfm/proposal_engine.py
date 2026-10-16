"""
DFM Proposal Engine for Phase 3 Wave 7: Manufacturing / DFM & Assembly Intelligence.
Generates deterministic mutation proposals for DFM violations and enforces strict human approval boundaries.
STRICT INVARIANT: AI actors cannot approve or apply proposals (HTTP 403).
STRICT INVARIANT: Stale revision rejection (HTTP 409).
"""
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import HTTPException
from app.models.db.dfm import ManufacturingFindingStatus, ManufacturingProposalRecord
from app.models.db.proposal import ProposalStatus
from app.models.schemas.dfm import ManufacturingFinding, ManufacturingProposalCreate


class DFMProposalEngine:
    """
    Deterministic resolution proposal engine for DFM/DFA engineering findings.
    """

    @staticmethod
    def generate_proposals_for_findings(
        analysis_id: str,
        board: Any,
        findings: list[ManufacturingFinding],
    ) -> list[ManufacturingProposalCreate]:
        proposals: list[ManufacturingProposalCreate] = []

        for finding in findings:
            if not finding.proposal_available or finding.status not in (
                ManufacturingFindingStatus.FAIL,
                ManufacturingFindingStatus.WARNING,
            ):
                continue

            prop = DFMProposalEngine._create_proposal_for_finding(analysis_id, board, finding)
            if prop:
                proposals.append(prop)

        return proposals

    @staticmethod
    def _create_proposal_for_finding(
        analysis_id: str,
        board: Any,
        finding: ManufacturingFinding,
    ) -> Optional[ManufacturingProposalCreate]:
        rule_id = finding.rule_id

        # 1. Trace Width Violation
        if rule_id == "MFG001" and finding.element_ids:
            trace_id = finding.element_ids[0]
            required_w = finding.required_value or 0.15
            current_w = finding.measured_value or 0.10
            return ManufacturingProposalCreate(
                analysis_id=analysis_id,
                rule_id=rule_id,
                title=f"Widen copper trace {trace_id[:8]} to manufacturable width {required_w} mm",
                description=f"Increases trace segment width from {current_w} mm to {required_w} mm to satisfy minimum fabrication capability.",
                mutation_type="ADJUST_TRACE_WIDTH",
                proposed_mutations=[
                    {
                        "target_entity": "BoardTraceSegment",
                        "entity_id": trace_id,
                        "action": "UPDATE",
                        "fields": {"width": required_w},
                    }
                ],
                diff_preview={
                    "trace_id": trace_id,
                    "previous_width_mm": current_w,
                    "proposed_width_mm": required_w,
                    "delta_mm": round(required_w - current_w, 4),
                },
            )

        # 2. Drill Diameter Violation
        if rule_id == "MFG003" and finding.element_ids:
            via_id = finding.element_ids[0]
            required_drill = finding.required_value or 0.30
            current_drill = finding.measured_value or 0.20
            return ManufacturingProposalCreate(
                analysis_id=analysis_id,
                rule_id=rule_id,
                title=f"Enlarge via drill {via_id[:8]} to mechanical minimum {required_drill} mm",
                description=f"Enlarges drill from {current_drill} mm to {required_drill} mm and adjusts outer pad diameter to preserve annular ring.",
                mutation_type="ADJUST_DRILL_DIAMETER",
                proposed_mutations=[
                    {
                        "target_entity": "BoardVia",
                        "entity_id": via_id,
                        "action": "UPDATE",
                        "fields": {
                            "drill": required_drill,
                            "diameter": round(required_drill + 0.30, 4),
                        },
                    }
                ],
                diff_preview={
                    "via_id": via_id,
                    "previous_drill_mm": current_drill,
                    "proposed_drill_mm": required_drill,
                    "proposed_diameter_mm": round(required_drill + 0.30, 4),
                },
            )

        # 3. Annular Ring Violation
        if rule_id == "MFG004" and finding.element_ids:
            via_id = finding.element_ids[0]
            required_ring = finding.required_value or 0.15
            current_ring = finding.measured_value or 0.10
            # Calculate required diameter = drill + 2 * required_ring
            drill_val = 0.30
            for via in getattr(board, "vias", []) or []:
                if str(via.id) == via_id:
                    drill_val = float(via.drill)
                    break
            proposed_diam = round(drill_val + (2.0 * required_ring), 4)

            return ManufacturingProposalCreate(
                analysis_id=analysis_id,
                rule_id=rule_id,
                title=f"Expand via outer pad {via_id[:8]} to achieve {required_ring} mm annular ring",
                description=f"Expands outer pad diameter to {proposed_diam} mm to satisfy IPC-2221 Class 2 annular ring rule guideline.",
                mutation_type="ADJUST_ANNULAR_RING",
                proposed_mutations=[
                    {
                        "target_entity": "BoardVia",
                        "entity_id": via_id,
                        "action": "UPDATE",
                        "fields": {"diameter": proposed_diam},
                    }
                ],
                diff_preview={
                    "via_id": via_id,
                    "previous_annular_ring_mm": current_ring,
                    "proposed_annular_ring_mm": required_ring,
                    "proposed_outer_diameter_mm": proposed_diam,
                },
            )

        # 4. Component Placement Clearance Violation
        if rule_id == "MFG009" and len(finding.element_ids) >= 2:
            fp1_id, fp2_id = finding.element_ids[0], finding.element_ids[1]
            required_c = finding.required_value or 0.50
            current_c = finding.measured_value or 0.20
            shift_dist = round(required_c - current_c + 0.10, 4)

            return ManufacturingProposalCreate(
                analysis_id=analysis_id,
                rule_id=rule_id,
                title=f"Shift component {finding.ref_des or 'placement'} by {shift_dist} mm to clear assembly clearance",
                description=f"Nudges component {fp2_id[:8]} outward to eliminate pick-and-place collision risk.",
                mutation_type="SHIFT_COMPONENT",
                proposed_mutations=[
                    {
                        "target_entity": "BoardFootprint",
                        "entity_id": fp2_id,
                        "action": "UPDATE_OFFSET",
                        "fields": {"delta_x": shift_dist, "delta_y": 0.0},
                    }
                ],
                diff_preview={
                    "component_a_id": fp1_id,
                    "component_b_id": fp2_id,
                    "previous_clearance_mm": current_c,
                    "proposed_shift_mm": shift_dist,
                    "expected_clearance_mm": round(current_c + shift_dist, 4),
                },
            )

        # 5. Component Edge Clearance Violation
        if rule_id == "MFG010" and finding.element_ids:
            fp_id = finding.element_ids[0]
            required_edge = finding.required_value or 1.0
            current_edge = finding.measured_value or 0.4
            shift_in = round(required_edge - current_edge + 0.2, 4)

            return ManufacturingProposalCreate(
                analysis_id=analysis_id,
                rule_id=rule_id,
                title=f"Inset component {finding.ref_des or fp_id[:8]} inward from board edge",
                description=f"Moves component inward by {shift_in} mm to prevent cracking during depaneling.",
                mutation_type="INSET_COMPONENT_FROM_EDGE",
                proposed_mutations=[
                    {
                        "target_entity": "BoardFootprint",
                        "entity_id": fp_id,
                        "action": "UPDATE_OFFSET",
                        "fields": {"delta_x": shift_in, "delta_y": shift_in},
                    }
                ],
                diff_preview={
                    "footprint_id": fp_id,
                    "previous_edge_clearance_mm": current_edge,
                    "proposed_inward_shift_mm": shift_in,
                    "expected_edge_clearance_mm": round(current_edge + shift_in, 4),
                },
            )

        # 6. Silkscreen Overlap Violation
        if rule_id == "MFG008" and finding.element_ids:
            fp_id = finding.element_ids[0]
            return ManufacturingProposalCreate(
                analysis_id=analysis_id,
                rule_id=rule_id,
                title=f"Retract silkscreen clipping from pads on {finding.ref_des or fp_id[:8]}",
                description="Adjusts silkscreen bounding box clearance to eliminate solder wetting interference.",
                mutation_type="RETRACT_SILKSCREEN",
                proposed_mutations=[
                    {
                        "target_entity": "BoardFootprint",
                        "entity_id": fp_id,
                        "action": "UPDATE_METADATA",
                        "fields": {"silkscreen_pad_overlap": False, "silkscreen_clearance_mm": 0.20},
                    }
                ],
                diff_preview={
                    "footprint_id": fp_id,
                    "previous_overlap": True,
                    "proposed_overlap": False,
                    "proposed_clearance_mm": 0.20,
                },
            )

        # 7. Polarity Marking Missing
        if rule_id == "MFG013" and finding.element_ids:
            fp_id = finding.element_ids[0]
            return ManufacturingProposalCreate(
                analysis_id=analysis_id,
                rule_id=rule_id,
                title=f"Add Pin 1 / polarity alignment marker to {finding.ref_des or fp_id[:8]}",
                description="Adds silkscreen Pin 1 dot / polarity bar indicator to footprint.",
                mutation_type="ADD_POLARITY_MARKER",
                proposed_mutations=[
                    {
                        "target_entity": "BoardFootprint",
                        "entity_id": fp_id,
                        "action": "UPDATE_METADATA",
                        "fields": {"pin1_marked": True, "pin_1_dot": True},
                    }
                ],
                diff_preview={
                    "footprint_id": fp_id,
                    "previous_pin1_marked": False,
                    "proposed_pin1_marked": True,
                },
            )

        # 8. BOM Package Mismatch
        if rule_id == "MFG014" and finding.element_ids:
            fp_id = finding.element_ids[0]
            ev = finding.evidence or {}
            target_pkg = ev.get("bom_package")
            if target_pkg:
                return ManufacturingProposalCreate(
                    analysis_id=analysis_id,
                    rule_id=rule_id,
                    title=f"Align PCB footprint {finding.ref_des} to BOM package '{target_pkg}'",
                    description=f"Updates footprint definition to match procured part packaging ({target_pkg}).",
                    mutation_type="ALIGN_FOOTPRINT_PACKAGE",
                    proposed_mutations=[
                        {
                            "target_entity": "BoardFootprint",
                            "entity_id": fp_id,
                            "action": "UPDATE",
                            "fields": {"footprint_name": target_pkg},
                        }
                    ],
                    diff_preview={
                        "footprint_id": fp_id,
                        "previous_package": ev.get("pcb_package"),
                        "proposed_package": target_pkg,
                    },
                )

        return None

    @staticmethod
    def enforce_human_approval_gate(user: Any) -> None:
        """
        STRICT SECURITY & EPISTEMIC INVARIANT:
        AI actors, background agent bots, and synthetic automation MUST NEVER approve DFM proposals.
        """
        role = getattr(user, "role", None)
        user_id = str(getattr(user, "id", "") or "")

        if (
            role in ("ai", "service:ai", "model", "bot", "assistant")
            or user_id.startswith("ai-")
            or user_id.startswith("bot-")
            or user_id.startswith("svc-ai-")
        ):
            raise HTTPException(
                status_code=403,
                detail="AI_UNAUTHORIZED_PROPOSAL_APPROVAL: AI agents and automated services are strictly prohibited from approving or applying manufacturing/DFM proposals. Human sign-off is required.",
            )

        if role in ("viewer", "guest", "readonly", "read_only"):
            raise HTTPException(
                status_code=403,
                detail="UNAUTHORIZED_USER_ROLE: View-only or guest roles are not authorized to approve or apply manufacturing modifications.",
            )

    @staticmethod
    def apply_proposal_mutations(
        proposal: ManufacturingProposalRecord,
        board: Any,
        db: Any,
    ) -> None:
        """
        Applies proposed mutations atomically to the board, checking revision freshness.
        """
        current_rev = int(getattr(board, "version", 1))
        if proposal.board_revision != current_rev:
            raise HTTPException(
                status_code=409,
                detail=f"STALE_PROPOSAL_REVISION: Proposal was generated against board revision {proposal.board_revision}, but current revision is {current_rev}.",
            )

        mutations = proposal.proposed_mutations or []
        for mut in mutations:
            target_entity = mut.get("target_entity")
            entity_id = mut.get("entity_id")
            action = mut.get("action")
            fields = mut.get("fields", {})

            if target_entity == "BoardTraceSegment":
                for trace in getattr(board, "traces", []) or []:
                    if str(trace.id) == entity_id:
                        for k, v in fields.items():
                            setattr(trace, k, v)
                        break

            elif target_entity == "BoardVia":
                for via in getattr(board, "vias", []) or []:
                    if str(via.id) == entity_id:
                        for k, v in fields.items():
                            setattr(via, k, v)
                        break

            elif target_entity == "BoardFootprint":
                for fp in getattr(board, "footprints", []) or []:
                    if str(fp.id) == entity_id:
                        if action == "UPDATE_OFFSET":
                            fp.pos_x = float(fp.pos_x) + float(fields.get("delta_x", 0.0))
                            fp.pos_y = float(fp.pos_y) + float(fields.get("delta_y", 0.0))
                        elif action == "UPDATE_METADATA":
                            meta = dict(getattr(fp, "package_metadata", {}) or {})
                            meta.update(fields)
                            fp.package_metadata = meta
                        elif action == "UPDATE":
                            for k, v in fields.items():
                                setattr(fp, k, v)
                        break

        # Increment board version
        board.version = current_rev + 1
        db.add(board)
