"""
Rule registry for Phase 3 Wave 7: Manufacturing / DFM & Assembly Intelligence.
Defines authoritative standard rulesets (Standard 2-Layer, Advanced 4-Layer, IPC Class 2),
individual rule definitions, and provenance digest computation.
"""
import hashlib
import json
from typing import Any
from app.models.db.dfm import ManufacturingRuleCategory


STANDARD_2LAYER_RULES: dict[str, Any] = {
    "MFG001": {
        "rule_id": "MFG001",
        "name": "Minimum Trace Width",
        "category": ManufacturingRuleCategory.FABRICATION.value,
        "description": "Enforces minimum manufacturable copper trace width to avoid acid pooling or etching open-circuits.",
        "severity": "ERROR",
        "parameters": {"min_trace_width_mm": 0.15},
        "standard_reference": "IPC-2221B Table 6-1 (Standard Fab Capability)",
    },
    "MFG002": {
        "rule_id": "MFG002",
        "name": "Minimum Copper Clearance",
        "category": ManufacturingRuleCategory.CLEARANCE.value,
        "description": "Enforces minimum clearance between traces, pads, and copper features on the same layer.",
        "severity": "ERROR",
        "parameters": {"min_clearance_mm": 0.15},
        "standard_reference": "IPC-2221B Table 6-1",
    },
    "MFG003": {
        "rule_id": "MFG003",
        "name": "Minimum Drill Diameter",
        "category": ManufacturingRuleCategory.DRILL_VIA.value,
        "description": "Enforces minimum mechanically drillable hole size to avoid drill bit breakage.",
        "severity": "ERROR",
        "parameters": {"min_drill_diameter_mm": 0.3},
        "standard_reference": "Mechanical Drill Capability Standard",
    },
    "MFG004": {
        "rule_id": "MFG004",
        "name": "Minimum Annular Ring",
        "category": ManufacturingRuleCategory.DRILL_VIA.value,
        "description": "Enforces minimum copper annular ring around plated through holes: (outer_diameter - drill) / 2.",
        "severity": "ERROR",
        "parameters": {"min_annular_ring_mm": 0.15},
        "standard_reference": "IPC-2221B Section 9.1.2 Class 2",
    },
    "MFG005": {
        "rule_id": "MFG005",
        "name": "Minimum Via-to-Via Clearance",
        "category": ManufacturingRuleCategory.DRILL_VIA.value,
        "description": "Enforces minimum hole-to-hole or via-to-via wall separation to avoid drill breakout or barrel cracking.",
        "severity": "WARNING",
        "parameters": {"min_via_to_via_mm": 0.5},
        "standard_reference": "IPC-A-600 Class 2",
    },
    "MFG006": {
        "rule_id": "MFG006",
        "name": "Board Edge Clearance",
        "category": ManufacturingRuleCategory.CLEARANCE.value,
        "description": "Enforces minimum clearance from copper elements and traces to route/v-cut board outline.",
        "severity": "ERROR",
        "parameters": {"min_edge_clearance_mm": 0.5},
        "standard_reference": "V-Scoring / Routing Edge Clearance Guideline",
    },
    "MFG007": {
        "rule_id": "MFG007",
        "name": "Minimum Solder Mask Sliver",
        "category": ManufacturingRuleCategory.SOLDER_MASK.value,
        "description": "Enforces minimum solder mask web/dam between adjacent SMD pads to prevent solder bridging.",
        "severity": "WARNING",
        "parameters": {"min_mask_sliver_mm": 0.10},
        "standard_reference": "IPC-7351B Solder Mask Guidelines",
    },
    "MFG008": {
        "rule_id": "MFG008",
        "name": "Silkscreen-to-Pad Clearance",
        "category": ManufacturingRuleCategory.SILKSCREEN.value,
        "description": "Prevents silkscreen ink from clipping onto solderable copper pads causing wetting failure.",
        "severity": "WARNING",
        "parameters": {"min_silkscreen_clearance_mm": 0.15},
        "standard_reference": "IPC-A-610 Class 2",
    },
    "MFG009": {
        "rule_id": "MFG009",
        "name": "Component-to-Component Placement Clearance",
        "category": ManufacturingRuleCategory.COMPONENT_PLACEMENT.value,
        "description": "Enforces physical bounding clearance between components for pick-and-place nozzle and reflow access.",
        "severity": "ERROR",
        "parameters": {"min_component_clearance_mm": 0.5},
        "standard_reference": "IPC-SM-782 Component Placement Rules",
    },
    "MFG010": {
        "rule_id": "MFG010",
        "name": "Component-to-Board-Edge Clearance",
        "category": ManufacturingRuleCategory.COMPONENT_PLACEMENT.value,
        "description": "Ensures components are set back from depaneling route tabs or rails to prevent cracking during breakout.",
        "severity": "WARNING",
        "parameters": {"min_edge_component_clearance_mm": 1.0},
        "standard_reference": "Depaneling Mechanical Clearance Standard",
    },
    "MFG011": {
        "rule_id": "MFG011",
        "name": "Pick-and-Place Centroid and Rotation Validity",
        "category": ManufacturingRuleCategory.ASSEMBLY.value,
        "description": "Verifies that components have defined centroid positions and standardized orientation.",
        "severity": "ERROR",
        "parameters": {"require_centroid": True, "valid_rotations": [0, 45, 90, 135, 180, 225, 270, 315, 360]},
        "standard_reference": "IPC-7351 Zero-Orientation Standard",
    },
    "MFG012": {
        "rule_id": "MFG012",
        "name": "SMT vs Through-Hole Soldering Consistency",
        "category": ManufacturingRuleCategory.ASSEMBLY.value,
        "description": "Verifies consistent assembly soldering process requirements (SMD pads vs drill requirements).",
        "severity": "WARNING",
        "parameters": {"require_drill_for_tht": True, "reject_drill_for_smd": True},
        "standard_reference": "IPC-A-610 Soldering Acceptability",
    },
    "MFG013": {
        "rule_id": "MFG013",
        "name": "Pin 1 and Polarity Indicator Presence",
        "category": ManufacturingRuleCategory.ASSEMBLY.value,
        "description": "Requires polarized packages (diodes, polarized capacitors, ICs) to have pin 1 or polarity markings.",
        "severity": "WARNING",
        "parameters": {"require_polarity_indication": True},
        "standard_reference": "IPC-7351 Polarity Marking Standard",
    },
    "MFG014": {
        "rule_id": "MFG014",
        "name": "BOM vs PCB Package Family Consistency",
        "category": ManufacturingRuleCategory.BOM_CONSISTENCY.value,
        "description": "Cross-checks BOM line package/case against placed PCB footprint package family.",
        "severity": "ERROR",
        "parameters": {"strict_package_match": True},
        "standard_reference": "Engineering Design-to-Procurement Traceability",
    },
    "MFG015": {
        "rule_id": "MFG015",
        "name": "BOM vs PCB Pad Count Consistency",
        "category": ManufacturingRuleCategory.BOM_CONSISTENCY.value,
        "description": "Verifies that physical footprint pad count corresponds with schematic component / BOM pin count.",
        "severity": "ERROR",
        "parameters": {"strict_pin_count_match": True},
        "standard_reference": "IPC-7351 Land Pattern Verification",
    },
    "MFG016": {
        "rule_id": "MFG016",
        "name": "Unconnected / Floating Active Pads Check",
        "category": ManufacturingRuleCategory.FABRICATION.value,
        "description": "Identifies IC pads missing net assignment that may represent manufacturing or schematic disconnects.",
        "severity": "WARNING",
        "parameters": {"flag_unassigned_pads": True},
        "standard_reference": "Electrical Continuity Pre-Fab Audit",
    },
}

ADVANCED_4LAYER_RULES: dict[str, Any] = {
    **STANDARD_2LAYER_RULES,
    "MFG001": {
        **STANDARD_2LAYER_RULES["MFG001"],
        "parameters": {"min_trace_width_mm": 0.10},  # 4 mil
        "standard_reference": "High-Density Interconnect / 4-Layer Fab Standard",
    },
    "MFG002": {
        **STANDARD_2LAYER_RULES["MFG002"],
        "parameters": {"min_clearance_mm": 0.10},  # 4 mil
        "standard_reference": "High-Density Interconnect / 4-Layer Fab Standard",
    },
    "MFG003": {
        **STANDARD_2LAYER_RULES["MFG003"],
        "parameters": {"min_drill_diameter_mm": 0.20},  # 0.2mm micro-drill
        "standard_reference": "Advanced Mechanical Drill Standard",
    },
    "MFG004": {
        **STANDARD_2LAYER_RULES["MFG004"],
        "parameters": {"min_annular_ring_mm": 0.125},  # 5 mil
        "standard_reference": "IPC-2221B Class 2/3 Multilayer",
    },
    "MFG005": {
        **STANDARD_2LAYER_RULES["MFG005"],
        "parameters": {"min_via_to_via_mm": 0.40},
        "standard_reference": "IPC-A-600 Multilayer Class 2",
    },
    "MFG006": {
        **STANDARD_2LAYER_RULES["MFG006"],
        "parameters": {"min_edge_clearance_mm": 0.30},
        "standard_reference": "Precision Edge Route Standard",
    },
    "MFG007": {
        **STANDARD_2LAYER_RULES["MFG007"],
        "parameters": {"min_mask_sliver_mm": 0.08},
        "standard_reference": "High-Resolution LPI Mask Standard",
    },
    "MFG009": {
        **STANDARD_2LAYER_RULES["MFG009"],
        "parameters": {"min_component_clearance_mm": 0.35},
        "standard_reference": "High Density SMT Placement Standard",
    },
}

IPC_CLASS_2_RULES: dict[str, Any] = {
    **STANDARD_2LAYER_RULES,
    "MFG004": {
        **STANDARD_2LAYER_RULES["MFG004"],
        "parameters": {"min_annular_ring_mm": 0.15},
        "standard_reference": "IPC-6012 Class 2 Annular Ring Standard",
    },
    "MFG005": {
        **STANDARD_2LAYER_RULES["MFG005"],
        "parameters": {"min_via_to_via_mm": 0.45},
        "standard_reference": "IPC-6012 Class 2 Hole-to-Hole",
    },
}


def compute_ruleset_digest(rules: dict[str, Any]) -> str:
    """Computes deterministic SHA-256 digest of canonical ruleset JSON."""
    canonical_json = json.dumps(rules, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


DEFAULT_RULESETS = {
    "FAB_STANDARD_2LAYER": {
        "name": "Standard 2-Layer Fabrication & SMT Assembly",
        "source": "FAB_STANDARD_2LAYER",
        "source_revision": "REV_2026.1",
        "rules": STANDARD_2LAYER_RULES,
        "source_digest": compute_ruleset_digest(STANDARD_2LAYER_RULES),
        "is_default": True,
    },
    "FAB_ADVANCED_4LAYER": {
        "name": "Advanced 4-Layer High-Density Fabrication",
        "source": "FAB_ADVANCED_4LAYER",
        "source_revision": "REV_2026.1",
        "rules": ADVANCED_4LAYER_RULES,
        "source_digest": compute_ruleset_digest(ADVANCED_4LAYER_RULES),
        "is_default": False,
    },
    "IPC_CLASS_2": {
        "name": "IPC-2221 / IPC-6012 Referenced Class 2 Profile (IPC-DERIVED-RULESET)",
        "source": "IPC-DERIVED-RULESET",
        "source_revision": "REV_IPC_6012E_SUBSET",
        "rules": IPC_CLASS_2_RULES,
        "source_digest": compute_ruleset_digest(IPC_CLASS_2_RULES),
        "is_default": False,
    },
}
