"""
Schematic <-> PCB Consistency Engine for Phase 3 Wave 8.
Evaluates Rules X001 (Connectivity Consistency) and X002 (Component Existence Consistency).
STRICT INVARIANT: UNKNOWN != PASS. Zero synthetic scoring.
"""
from typing import Any, Optional
from app.models.db.cross_domain import (
    CrossDomainSeverity,
    CrossDomainStatus,
    SourceClassification,
    ValidationDomain,
)
from app.models.schemas.cross_domain import CrossDomainFinding


class SchematicPCBConsistencyEngine:
    """
    Deterministic cross-domain checker between Schematic circuit model and PCB layout model.
    """

    @staticmethod
    def evaluate(
        project_id: str,
        circuit: Optional[Any],
        board: Optional[Any],
        rules: dict[str, dict[str, Any]],
    ) -> list[CrossDomainFinding]:
        findings: list[CrossDomainFinding] = []

        rule_001 = rules.get("X001")
        rule_002 = rules.get("X002")

        # Handle missing domain state
        if not circuit:
            if rule_001:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X001_NO_CIRCUIT",
                        project_id=project_id,
                        domain_a=ValidationDomain.SCHEMATIC,
                        domain_b=ValidationDomain.PCB,
                        rule_id="X001",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.HIGH,
                        engineering_claim=rule_001["engineering_claim"],
                        explanation="Schematic circuit model is missing or not provided. Net connectivity consistency cannot be evaluated.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            if rule_002:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X002_NO_CIRCUIT",
                        project_id=project_id,
                        domain_a=ValidationDomain.SCHEMATIC,
                        domain_b=ValidationDomain.PCB,
                        rule_id="X002",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.HIGH,
                        engineering_claim=rule_002["engineering_claim"],
                        explanation="Schematic circuit model is missing or not provided. Component placement coverage cannot be evaluated.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            return findings

        if not board:
            if rule_001:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X001_NO_BOARD",
                        project_id=project_id,
                        domain_a=ValidationDomain.SCHEMATIC,
                        domain_b=ValidationDomain.PCB,
                        rule_id="X001",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.HIGH,
                        engineering_claim=rule_001["engineering_claim"],
                        explanation="Physical PCB board model is missing or not provided. Net connectivity consistency cannot be evaluated.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            if rule_002:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X002_NO_BOARD",
                        project_id=project_id,
                        domain_a=ValidationDomain.SCHEMATIC,
                        domain_b=ValidationDomain.PCB,
                        rule_id="X002",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.HIGH,
                        engineering_claim=rule_002["engineering_claim"],
                        explanation="Physical PCB board model is missing or not provided. Component placement coverage cannot be evaluated.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            return findings

        circuit_components = getattr(circuit, "components", []) or []
        board_footprints = getattr(board, "footprints", []) or []

        circuit_by_ref: dict[str, Any] = {}
        for c in circuit_components:
            ref = str(getattr(c, "ref_des", "")).strip().upper()
            if ref:
                circuit_by_ref[ref] = c

        board_by_ref: dict[str, Any] = {}
        for fp in board_footprints:
            ref = str(getattr(fp, "ref_des", "")).strip().upper()
            if ref:
                board_by_ref[ref] = fp

        # --- Rule X002: Schematic-to-PCB Component Existence Consistency ---
        if rule_002:
            missing_on_board: list[str] = []
            for ref, c in circuit_by_ref.items():
                if ref not in board_by_ref:
                    missing_on_board.append(ref)
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"X002_MISSING_FP_{c.id}",
                            project_id=project_id,
                            domain_a=ValidationDomain.SCHEMATIC,
                            domain_b=ValidationDomain.PCB,
                            affected_entity_ids=[str(c.id)],
                            rule_id="X002",
                            status=CrossDomainStatus.FAIL,
                            severity=CrossDomainSeverity.CRITICAL,
                            engineering_claim=rule_002["engineering_claim"],
                            explanation=f"Schematic component {ref} ({getattr(c, 'name', '')}) has no corresponding footprint placed on PCB layout.",
                            source_classification=SourceClassification.CALCULATED,
                        )
                    )

            unmapped_on_pcb: list[str] = []
            for ref, fp in board_by_ref.items():
                if ref not in circuit_by_ref:
                    unmapped_on_pcb.append(ref)
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"X002_UNMAPPED_FP_{fp.id}",
                            project_id=project_id,
                            domain_a=ValidationDomain.SCHEMATIC,
                            domain_b=ValidationDomain.PCB,
                            affected_entity_ids=[str(fp.id)],
                            rule_id="X002",
                            status=CrossDomainStatus.WARNING,
                            severity=CrossDomainSeverity.MEDIUM,
                            engineering_claim=rule_002["engineering_claim"],
                            explanation=f"PCB footprint {ref} ({getattr(fp, 'footprint_name', '')}) exists on PCB but has no matching component in schematic.",
                            source_classification=SourceClassification.CALCULATED,
                        )
                    )

            if not missing_on_board and len(circuit_by_ref) > 0:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X002_PASS_ALL",
                        project_id=project_id,
                        domain_a=ValidationDomain.SCHEMATIC,
                        domain_b=ValidationDomain.PCB,
                        rule_id="X002",
                        status=CrossDomainStatus.PASS,
                        severity=CrossDomainSeverity.INFO,
                        engineering_claim=rule_002["engineering_claim"],
                        explanation=f"All {len(circuit_by_ref)} schematic components have matching physical footprints on PCB layout.",
                        source_classification=SourceClassification.CALCULATED,
                    )
                )

        # --- Rule X001: Schematic-to-PCB Connectivity Consistency ---
        if rule_001:
            circuit_nets = getattr(circuit, "nets", []) or []
            if not circuit_nets:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X001_NO_CIRCUIT_NETS",
                        project_id=project_id,
                        domain_a=ValidationDomain.SCHEMATIC,
                        domain_b=ValidationDomain.PCB,
                        rule_id="X001",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.MEDIUM,
                        engineering_claim=rule_001["engineering_claim"],
                        explanation="Schematic contains no defined electrical nets. Net connectivity consistency unknown.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            else:
                # Build net mappings
                circuit_net_names = {str(getattr(n, "name", "")).strip().upper() for n in circuit_nets if getattr(n, "name", None)}
                board_pads = []
                for fp in board_footprints:
                    board_pads.extend(getattr(fp, "pads", []) or [])
                
                board_net_names = {
                    str(getattr(p, "net_name", "")).strip().upper()
                    for p in board_pads
                    if getattr(p, "net_name", None) and str(getattr(p, "net_name", "")).strip()
                }

                net_mismatches = 0
                for c_net in circuit_nets:
                    c_name = str(getattr(c_net, "name", "")).strip().upper()
                    if c_name and c_name not in board_net_names:
                        net_mismatches += 1
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X001_NET_UNROUTED_{c_net.id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.SCHEMATIC,
                                domain_b=ValidationDomain.PCB,
                                affected_entity_ids=[str(c_net.id)],
                                rule_id="X001",
                                status=CrossDomainStatus.WARNING,
                                severity=CrossDomainSeverity.HIGH,
                                engineering_claim=rule_001["engineering_claim"],
                                explanation=f"Schematic electrical net '{c_name}' is not assigned to any physical pads or copper elements on PCB layout.",
                                source_classification=SourceClassification.CALCULATED,
                            )
                        )

                if net_mismatches == 0 and len(circuit_net_names) > 0:
                    findings.append(
                        CrossDomainFinding(
                            finding_id="X001_PASS_ALL",
                            project_id=project_id,
                            domain_a=ValidationDomain.SCHEMATIC,
                            domain_b=ValidationDomain.PCB,
                            rule_id="X001",
                            status=CrossDomainStatus.PASS,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_001["engineering_claim"],
                            explanation=f"All {len(circuit_net_names)} schematic electrical nets are recognized and mapped to PCB pad connectivity.",
                            source_classification=SourceClassification.CALCULATED,
                        )
                    )

        return findings
