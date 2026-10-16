from typing import Any
from app.models.db.pcb import BoardVia, EngineeringBoard, PCBProposalRecord
from app.models.db.proposal import ProposalStatus
from app.services.ai.pcb.snapshot import PCBSnapshotService


class PCBProposalEngine:
    """
    Manages human-gated layout proposals for EngineeringBoard.
    Lifecycle:
    AI Proposal -> Deterministic Validation -> Diff -> Human Approval -> Atomic Application.
    Strict Invariants:
    - AI proposals CANNOT autonomously mutate board state.
    - Application is rejected if base_revision is stale.
    - Application is rejected if status != APPROVED.
    """

    @classmethod
    def validate_proposal(
        cls,
        board: EngineeringBoard,
        operations: list[dict[str, Any]],
        base_revision: int,
    ) -> dict[str, Any]:
        """
        Validates proposed operations against board state and generates diff preview.
        """
        is_stale = board.version > base_revision
        diffs: list[dict[str, Any]] = []
        errors: list[str] = []

        if is_stale:
            errors.append(
                f"STALE_PROPOSAL: Board revision has advanced from {base_revision} to {board.version}."
            )

        fp_by_ref = {fp.ref_des.upper(): fp for fp in getattr(board, "footprints", [])}
        trace_by_id = {str(t.id): t for t in getattr(board, "traces", [])}

        for op in operations:
            op_type = op.get("op", "").lower()
            if op_type == "move_footprint":
                ref = str(op.get("ref_des", "")).upper()
                fp = fp_by_ref.get(ref)
                if not fp:
                    errors.append(f"Footprint {ref} not found on board")
                else:
                    new_x = float(op.get("pos_x", fp.pos_x))
                    new_y = float(op.get("pos_y", fp.pos_y))
                    new_rot = float(op.get("rotation", fp.rotation))
                    diffs.append(
                        {
                            "op": "move_footprint",
                            "target": ref,
                            "before": {"pos_x": fp.pos_x, "pos_y": fp.pos_y, "rotation": fp.rotation},
                            "after": {"pos_x": new_x, "pos_y": new_y, "rotation": new_rot},
                        }
                    )
            elif op_type == "change_trace_width":
                t_id = str(op.get("trace_id", ""))
                trace = trace_by_id.get(t_id)
                if not trace:
                    errors.append(f"Trace segment {t_id} not found on board")
                else:
                    new_w = float(op.get("width", trace.width))
                    diffs.append(
                        {
                            "op": "change_trace_width",
                            "target": t_id,
                            "before": {"width": trace.width},
                            "after": {"width": new_w},
                        }
                    )
            elif op_type == "add_via":
                diffs.append(
                    {
                        "op": "add_via",
                        "after": {
                            "pos_x": float(op.get("pos_x", 0.0)),
                            "pos_y": float(op.get("pos_y", 0.0)),
                            "drill": float(op.get("drill", 0.3)),
                            "diameter": float(op.get("diameter", 0.6)),
                            "net_name": op.get("net_name", ""),
                        },
                    }
                )
            else:
                errors.append(f"Unsupported proposal operation: {op_type}")

        return {
            "is_valid": len(errors) == 0,
            "is_stale": is_stale,
            "errors": errors,
            "diffs": diffs,
        }

    @classmethod
    def apply_proposal(
        cls,
        board: EngineeringBoard,
        proposal: PCBProposalRecord,
    ) -> bool:
        """
        Atomically applies approved proposal operations.
        Strictly requires human approval (status == APPROVED) and fresh base revision.
        """
        if proposal.status != ProposalStatus.APPROVED.value:
            raise ValueError(
                f"AUTONOMOUS_MUTATION_BLOCKED: Proposal {proposal.id} status is '{proposal.status}'. "
                "Explicit human approval is required before applying layout changes."
            )

        if board.version > proposal.base_revision:
            raise ValueError(
                f"STALE_PROPOSAL_REJECTED: Board version ({board.version}) > proposal base revision ({proposal.base_revision})."
            )

        fp_by_ref = {fp.ref_des.upper(): fp for fp in getattr(board, "footprints", [])}
        trace_by_id = {str(t.id): t for t in getattr(board, "traces", [])}

        for op in proposal.operations:
            op_type = op.get("op", "").lower()
            if op_type == "move_footprint":
                ref = str(op.get("ref_des", "")).upper()
                fp = fp_by_ref.get(ref)
                if fp:
                    if "pos_x" in op:
                        fp.pos_x = float(op["pos_x"])
                    if "pos_y" in op:
                        fp.pos_y = float(op["pos_y"])
                    if "rotation" in op:
                        fp.rotation = float(op["rotation"])

            elif op_type == "change_trace_width":
                t_id = str(op.get("trace_id", ""))
                trace = trace_by_id.get(t_id)
                if trace and "width" in op:
                    trace.width = float(op["width"])

            elif op_type == "add_via":
                import uuid
                new_via = BoardVia(
                    id=str(uuid.uuid4()),
                    board_id=board.id,
                    pos_x=float(op.get("pos_x", 0.0)),
                    pos_y=float(op.get("pos_y", 0.0)),
                    drill=float(op.get("drill", 0.3)),
                    diameter=float(op.get("diameter", 0.6)),
                    start_layer=op.get("start_layer", "F.Cu"),
                    end_layer=op.get("end_layer", "B.Cu"),
                    via_type=op.get("via_type", "THROUGH"),
                    net_name=op.get("net_name"),
                )
                board.vias.append(new_via)

        # Advance board version atomically
        board.version += 1
        # Recompute integrity digest
        snap = PCBSnapshotService.generate_canonical_snapshot(board)
        board.integrity_digest = PCBSnapshotService.compute_integrity_digest(snap)

        return True
