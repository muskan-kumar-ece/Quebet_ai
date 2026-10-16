"""
BOM Cross-Domain Consistency Engine for Phase 3 Wave 8.
Evaluates Rules X003 (Schematic-BOM Sync), X004 (BOM-PCB Footprint), X005 (BOM-PCB Pad Count),
and X019 (Component Identity vs Selected Procurement Identity).
STRICT INVARIANTS:
- UNKNOWN != PASS
- PAD_COUNT_MATCH != PINOUT_MATCH and != ELECTRICAL_COMPATIBILITY
- PACKAGE_MATCH != FUNCTIONAL_COMPATIBILITY
- IDENTITY_MATCH != ELECTRICAL_COMPATIBILITY
- Zero synthetic scoring.
"""
import re
from typing import Any, Optional
from app.models.db.cross_domain import (
    CrossDomainSeverity,
    CrossDomainStatus,
    SourceClassification,
    ValidationDomain,
)
from app.models.schemas.cross_domain import CrossDomainFinding


class BOMCrossDomainConsistencyEngine:
    """
    Deterministic cross-domain consistency engine linking Schematic, PCB, and BOM procurement domains.
    """

    @staticmethod
    def evaluate(
        project_id: str,
        circuit: Optional[Any],
        board: Optional[Any],
        bom: Optional[Any],
        rules: dict[str, dict[str, Any]],
    ) -> list[CrossDomainFinding]:
        findings: list[CrossDomainFinding] = []

        rule_003 = rules.get("X003")
        rule_004 = rules.get("X004")
        rule_005 = rules.get("X005")
        rule_019 = rules.get("X019")

        # If BOM is missing entirely
        if not bom:
            for rule_id, domain_b, name, claim in [
                ("X003", ValidationDomain.SCHEMATIC, "Schematic-BOM Component Consistency", rule_003["engineering_claim"] if rule_003 else ""),
                ("X004", ValidationDomain.PCB, "BOM-to-PCB Footprint Consistency", rule_004["engineering_claim"] if rule_004 else ""),
                ("X005", ValidationDomain.PCB, "BOM-to-PCB Pad-Count Consistency", rule_005["engineering_claim"] if rule_005 else ""),
                ("X019", ValidationDomain.DATASHEET, "Component Identity vs Procurement Identity", rule_019["engineering_claim"] if rule_019 else ""),
            ]:
                r = rules.get(rule_id)
                if r:
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"{rule_id}_NO_BOM",
                            project_id=project_id,
                            domain_a=ValidationDomain.BOM,
                            domain_b=domain_b,
                            rule_id=rule_id,
                            status=CrossDomainStatus.UNKNOWN,
                            severity=CrossDomainSeverity.HIGH,
                            engineering_claim=claim,
                            explanation="Engineering Bill of Materials (BOM) is not configured or available. Cross-domain procurement consistency unknown.",
                            source_classification=SourceClassification.UNKNOWN,
                        )
                    )
            return findings

        bom_lines = getattr(bom, "lines", []) or []
        bom_by_ref: dict[str, Any] = {}
        for line in bom_lines:
            ref = str(getattr(line, "reference_designator", "")).strip().upper()
            if ref:
                bom_by_ref[ref] = line

        circuit_components = getattr(circuit, "components", []) or [] if circuit else []
        board_footprints = getattr(board, "footprints", []) or [] if board else []

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

        # --- Rule X003: Schematic-to-BOM Component Consistency ---
        if rule_003:
            if not circuit:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X003_NO_CIRCUIT",
                        project_id=project_id,
                        domain_a=ValidationDomain.SCHEMATIC,
                        domain_b=ValidationDomain.BOM,
                        rule_id="X003",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.HIGH,
                        engineering_claim=rule_003["engineering_claim"],
                        explanation="Schematic circuit model is missing. Schematic-to-BOM synchronization cannot be evaluated.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            else:
                missing_in_bom: list[str] = []
                for ref, c in circuit_by_ref.items():
                    if ref not in bom_by_ref:
                        missing_in_bom.append(ref)
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X003_UNLISTED_BOM_{c.id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.SCHEMATIC,
                                domain_b=ValidationDomain.BOM,
                                affected_entity_ids=[str(c.id)],
                                rule_id="X003",
                                status=CrossDomainStatus.FAIL,
                                severity=CrossDomainSeverity.HIGH,
                                engineering_claim=rule_003["engineering_claim"],
                                explanation=f"Schematic component {ref} ({getattr(c, 'name', '')}) is not listed in the project Bill of Materials.",
                                source_classification=SourceClassification.CALCULATED,
                            )
                        )

                unlisted_in_circuit: list[str] = []
                for ref, line in bom_by_ref.items():
                    if ref not in circuit_by_ref:
                        unlisted_in_circuit.append(ref)
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X003_EXTRA_BOM_LINE_{line.id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.SCHEMATIC,
                                domain_b=ValidationDomain.BOM,
                                affected_entity_ids=[str(line.id)],
                                rule_id="X003",
                                status=CrossDomainStatus.WARNING,
                                severity=CrossDomainSeverity.MEDIUM,
                                engineering_claim=rule_003["engineering_claim"],
                                explanation=f"BOM line for {ref} exists in BOM but does not correspond to an active schematic component.",
                                source_classification=SourceClassification.CALCULATED,
                            )
                        )

                if not missing_in_bom and len(circuit_by_ref) > 0:
                    findings.append(
                        CrossDomainFinding(
                            finding_id="X003_PASS_ALL",
                            project_id=project_id,
                            domain_a=ValidationDomain.SCHEMATIC,
                            domain_b=ValidationDomain.BOM,
                            rule_id="X003",
                            status=CrossDomainStatus.PASS,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_003["engineering_claim"],
                            explanation=f"All {len(circuit_by_ref)} schematic components are synchronized with BOM line items.",
                            source_classification=SourceClassification.CALCULATED,
                        )
                    )

        # --- Rule X004: BOM-to-PCB Footprint Consistency ---
        # --- Rule X005: BOM-to-PCB Pad-Count Consistency ---
        if not board:
            if rule_004:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X004_NO_BOARD",
                        project_id=project_id,
                        domain_a=ValidationDomain.BOM,
                        domain_b=ValidationDomain.PCB,
                        rule_id="X004",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.HIGH,
                        engineering_claim=rule_004["engineering_claim"],
                        explanation="PCB layout model is missing. BOM-to-PCB footprint geometry consistency cannot be evaluated.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            if rule_005:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X005_NO_BOARD",
                        project_id=project_id,
                        domain_a=ValidationDomain.BOM,
                        domain_b=ValidationDomain.PCB,
                        rule_id="X005",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.HIGH,
                        engineering_claim=rule_005["engineering_claim"],
                        explanation="PCB layout model is missing. BOM-to-PCB pad-count consistency cannot be evaluated.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
        else:
            mismatches_004 = 0
            matches_004 = 0
            mismatches_005 = 0
            matches_005 = 0

            for ref, fp in board_by_ref.items():
                line = bom_by_ref.get(ref)
                if not line:
                    continue

                fp_name = str(getattr(fp, "footprint_name", "")).strip().upper()
                bom_pkg = str(
                    getattr(line, "design_package", None)
                    or getattr(line, "footprint_name", None)
                    or getattr(line, "footprint_package", None)
                    or ""
                ).strip().upper()

                # Rule X004 evaluation
                if rule_004:
                    if not bom_pkg or not fp_name:
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X004_UNKNOWN_{fp.id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.BOM,
                                domain_b=ValidationDomain.PCB,
                                affected_entity_ids=[str(fp.id), str(line.id)],
                                rule_id="X004",
                                status=CrossDomainStatus.UNKNOWN,
                                severity=CrossDomainSeverity.MEDIUM,
                                engineering_claim=rule_004["engineering_claim"],
                                explanation=f"Component {ref} lacks package specification in BOM ('{bom_pkg}') or PCB ('{fp_name}'). (PACKAGE_MATCH != FUNCTIONAL_COMPATIBILITY).",
                                source_classification=SourceClassification.UNKNOWN,
                            )
                        )
                    else:
                        is_compat = BOMCrossDomainConsistencyEngine._packages_are_compatible(bom_pkg, fp_name)
                        if not is_compat:
                            mismatches_004 += 1
                            findings.append(
                                CrossDomainFinding(
                                    finding_id=f"X004_MISMATCH_{fp.id}",
                                    project_id=project_id,
                                    domain_a=ValidationDomain.BOM,
                                    domain_b=ValidationDomain.PCB,
                                    affected_entity_ids=[str(fp.id), str(line.id)],
                                    rule_id="X004",
                                    status=CrossDomainStatus.FAIL,
                                    severity=CrossDomainSeverity.HIGH,
                                    engineering_claim=rule_004["engineering_claim"],
                                    explanation=f"BOM package '{bom_pkg}' conflicts with PCB footprint package '{fp_name}' for {ref}. (PACKAGE_MATCH != FUNCTIONAL_COMPATIBILITY).",
                                    source_classification=SourceClassification.CALCULATED,
                                )
                            )
                        else:
                            matches_004 += 1

                # Rule X005 evaluation
                if rule_005:
                    pads = getattr(fp, "pads", []) or []
                    pad_count = len(pads)
                    inferred_pins = BOMCrossDomainConsistencyEngine._infer_pin_count(bom_pkg)

                    if inferred_pins is not None:
                        if inferred_pins != pad_count:
                            mismatches_005 += 1
                            findings.append(
                                CrossDomainFinding(
                                    finding_id=f"X005_PAD_MISMATCH_{fp.id}",
                                    project_id=project_id,
                                    domain_a=ValidationDomain.BOM,
                                    domain_b=ValidationDomain.PCB,
                                    affected_entity_ids=[str(fp.id), str(line.id)],
                                    rule_id="X005",
                                    status=CrossDomainStatus.FAIL,
                                    severity=CrossDomainSeverity.HIGH,
                                    engineering_claim=rule_005["engineering_claim"],
                                    explanation=f"Component {ref} package implies {inferred_pins} pins but PCB footprint has {pad_count} pads. (PAD_COUNT_MATCH != PINOUT_MATCH and != ELECTRICAL_COMPATIBILITY).",
                                    quantitative_values={"bom_pin_count": inferred_pins, "pcb_pad_count": pad_count},
                                    margin=float(pad_count - inferred_pins),
                                    source_classification=SourceClassification.CALCULATED,
                                )
                            )
                        else:
                            matches_005 += 1
                    else:
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X005_UNKNOWN_PINS_{fp.id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.BOM,
                                domain_b=ValidationDomain.PCB,
                                affected_entity_ids=[str(fp.id), str(line.id)],
                                rule_id="X005",
                                status=CrossDomainStatus.UNKNOWN,
                                severity=CrossDomainSeverity.INFO,
                                engineering_claim=rule_005["engineering_claim"],
                                explanation=f"BOM line for {ref} package '{bom_pkg}' does not define explicit pin count to compare against PCB pad count {pad_count}. (PAD_COUNT_MATCH != PINOUT_MATCH).",
                                source_classification=SourceClassification.UNKNOWN,
                            )
                        )

            if rule_004 and mismatches_004 == 0 and matches_004 > 0:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X004_PASS_ALL",
                        project_id=project_id,
                        domain_a=ValidationDomain.BOM,
                        domain_b=ValidationDomain.PCB,
                        rule_id="X004",
                        status=CrossDomainStatus.PASS,
                        severity=CrossDomainSeverity.INFO,
                        engineering_claim=rule_004["engineering_claim"],
                        explanation=f"All {matches_004} checked BOM packages match PCB footprint package geometries. (PACKAGE_MATCH != FUNCTIONAL_COMPATIBILITY).",
                        source_classification=SourceClassification.CALCULATED,
                    )
                )

            if rule_005 and mismatches_005 == 0 and matches_005 > 0:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X005_PASS_ALL",
                        project_id=project_id,
                        domain_a=ValidationDomain.BOM,
                        domain_b=ValidationDomain.PCB,
                        rule_id="X005",
                        status=CrossDomainStatus.PASS,
                        severity=CrossDomainSeverity.INFO,
                        engineering_claim=rule_005["engineering_claim"],
                        explanation=f"All {matches_005} checked BOM component pin counts match physical PCB pad counts. (PAD_COUNT_MATCH != PINOUT_MATCH and != ELECTRICAL_COMPATIBILITY).",
                        source_classification=SourceClassification.CALCULATED,
                    )
                )

        # --- Rule X019: Component Identity vs Selected Procurement Identity ---
        if rule_019:
            mismatches_019 = 0
            matches_019 = 0

            for ref, line in bom_by_ref.items():
                design_mpn = str(getattr(line, "manufacturer_part_number", "") or "").strip().upper()
                c_comp = circuit_by_ref.get(ref)
                c_mpn = str(getattr(c_comp, "mpn", "") or getattr(c_comp, "part_number", "") or "").strip().upper() if c_comp else ""

                if not design_mpn and not c_mpn:
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"X019_UNKNOWN_MPN_{line.id}",
                            project_id=project_id,
                            domain_a=ValidationDomain.BOM,
                            domain_b=ValidationDomain.DATASHEET,
                            affected_entity_ids=[str(line.id)],
                            rule_id="X019",
                            status=CrossDomainStatus.UNKNOWN,
                            severity=CrossDomainSeverity.MEDIUM,
                            engineering_claim=rule_019["engineering_claim"],
                            explanation=f"BOM line {ref} has no specified MPN. Procurement candidate identity correlation unknown. (IDENTITY_MATCH != ELECTRICAL_COMPATIBILITY).",
                            source_classification=SourceClassification.UNKNOWN,
                        )
                    )
                    continue

                # Check selected procurement candidate
                candidates = getattr(line, "candidates", []) or []
                selected_candidate = None
                for cand in candidates:
                    if getattr(cand, "is_selected", False):
                        selected_candidate = cand
                        break
                if not selected_candidate and candidates:
                    selected_candidate = candidates[0]

                if selected_candidate:
                    cand_mpn = str(getattr(selected_candidate, "mpn", "") or "").strip().upper()
                    base_mpn = design_mpn or c_mpn
                    if cand_mpn != base_mpn:
                        # Identity difference
                        mismatches_019 += 1
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X019_MPN_MISMATCH_{line.id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.BOM,
                                domain_b=ValidationDomain.DATASHEET,
                                affected_entity_ids=[str(line.id), str(selected_candidate.id)],
                                rule_id="X019",
                                status=CrossDomainStatus.WARNING,
                                severity=CrossDomainSeverity.HIGH,
                                engineering_claim=rule_019["engineering_claim"],
                                explanation=f"Component {ref} design MPN '{base_mpn}' differs from selected procurement MPN '{cand_mpn}'. (IDENTITY_MATCH != ELECTRICAL_COMPATIBILITY).",
                                source_classification=SourceClassification.CALCULATED,
                            )
                        )
                    else:
                        matches_019 += 1
                else:
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"X019_NO_CANDIDATE_{line.id}",
                            project_id=project_id,
                            domain_a=ValidationDomain.BOM,
                            domain_b=ValidationDomain.DATASHEET,
                            affected_entity_ids=[str(line.id)],
                            rule_id="X019",
                            status=CrossDomainStatus.UNKNOWN,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_019["engineering_claim"],
                            explanation=f"BOM line {ref} has no procurement candidate selected. Procurement identity correlation unknown.",
                            source_classification=SourceClassification.UNKNOWN,
                        )
                    )

            if mismatches_019 == 0 and matches_019 > 0:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X019_PASS_ALL",
                        project_id=project_id,
                        domain_a=ValidationDomain.BOM,
                        domain_b=ValidationDomain.DATASHEET,
                        rule_id="X019",
                        status=CrossDomainStatus.PASS,
                        severity=CrossDomainSeverity.INFO,
                        engineering_claim=rule_019["engineering_claim"],
                        explanation=f"All {matches_019} checked BOM lines have selected procurement candidates matching design MPN identity. (IDENTITY_MATCH != ELECTRICAL_COMPATIBILITY).",
                        source_classification=SourceClassification.CALCULATED,
                    )
                )

        return findings

    @staticmethod
    def _packages_are_compatible(pkg_a: str, pkg_b: str) -> bool:
        norm_a = re.sub(r"[-_\s]", "", pkg_a.upper())
        norm_b = re.sub(r"[-_\s]", "", pkg_b.upper())
        if norm_a == norm_b or norm_a in norm_b or norm_b in norm_a:
            return True
        return False

    @staticmethod
    def _infer_pin_count(package_str: str) -> Optional[int]:
        if not package_str:
            return None
        s = package_str.upper()
        m = re.search(r"(?:SOIC|SOP|SSOP|TSSOP|MSOP|DIP|QFN|QFP|LQFP|TQFP)[-_]?([0-9]{1,3})", s)
        if m:
            return int(m.group(1))
        if "SOT235" in s or "SOT-23-5" in s:
            return 5
        if "SOT236" in s or "SOT-23-6" in s:
            return 6
        if "SOT23" in s or "SOT-23" in s or "TO220" in s or "TO-220" in s:
            return 3
        if any(c in s for c in ("0201", "0402", "0603", "0805", "1206", "1210", "2010", "2512")):
            return 2
        return None
