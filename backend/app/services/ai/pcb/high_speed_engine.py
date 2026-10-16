import math
from typing import Any
from app.models.db.pcb import EngineeringBoard
from app.models.schemas.pcb import PCBFinding


class PCBHighSpeedEngine:
    """
    High-Speed and Differential Pair constraint verification engine.
    Calculates trace lengths and verifies intra-pair length skew.
    Strict Epistemic Invariant:
    Geometric length matching does NOT verify signal integrity, impedance, or EMI compliance.
    Rule:
    - PCB015: Differential pair constraint violation
    """

    DEFAULT_MAX_SKEW_MM = 0.5  # 500 um length mismatch tolerance

    @classmethod
    def compute_net_trace_length(cls, traces: list[Any], net_name: str) -> float:
        """Computes total routed copper trace length for a given net."""
        clean_name = net_name.strip().upper()
        total_len = 0.0
        for t in traces:
            if (t.net_name or "").strip().upper() == clean_name:
                dx = float(t.end_x) - float(t.start_x)
                dy = float(t.end_y) - float(t.start_y)
                total_len += math.hypot(dx, dy)
        return total_len

    @classmethod
    def evaluate(
        cls,
        board: EngineeringBoard,
        diff_pairs: list[dict[str, Any]] | None = None,
    ) -> list[PCBFinding]:
        findings: list[PCBFinding] = []
        traces = getattr(board, "traces", [])

        meta = board.metadata_ if isinstance(board.metadata_, dict) else {}
        pairs_config = diff_pairs or meta.get("differential_pairs", [])

        for pair in pairs_config:
            pos_net = str(pair.get("pos_net", "")).strip().upper()
            neg_net = str(pair.get("neg_net", "")).strip().upper()
            max_skew = float(pair.get("max_skew_mm", cls.DEFAULT_MAX_SKEW_MM))

            if not pos_net or not neg_net:
                continue

            len_pos = cls.compute_net_trace_length(traces, pos_net)
            len_neg = cls.compute_net_trace_length(traces, neg_net)

            # If neither has traces yet, report info
            if len_pos == 0.0 and len_neg == 0.0:
                continue

            skew = abs(len_pos - len_neg)
            if skew > max_skew:
                findings.append(
                    PCBFinding(
                        rule_id="PCB015",
                        severity="WARNING",
                        category="HIGH_SPEED",
                        element_ref=f"{pos_net} / {neg_net}",
                        actual_value=round(skew, 3),
                        required_limit=max_skew,
                        unit="mm",
                        status="VIOLATED",
                        message=(
                            f"Differential pair length skew between '{pos_net}' ({len_pos:.2f}mm) "
                            f"and '{neg_net}' ({len_neg:.2f}mm) is {skew:.3f} mm, exceeding allowed {max_skew} mm."
                        ),
                    )
                )

        return findings
