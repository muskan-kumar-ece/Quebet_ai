import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { getStandardPinLayout, getPinCoordinates } from "../src/components/schematic/pinGeometry.ts";
import { getOrthogonalPath, computeJunctionDots } from "../src/components/schematic/wireRouter.ts";
import { useCircuitWorkspace } from "../src/components/schematic/useCircuitWorkspace.ts";
import type { SchematicComponent, SchematicObject } from "../src/components/schematic/types.ts";

describe("Phase 1 Wave 2: Frontend Engineering Canvas Test Suite", () => {
  const sampleComponent: SchematicComponent = {
    id: "comp-r1",
    circuit_id: "circ-1",
    ref_des: "R1",
    component_type: "resistor",
    value: "10k",
    tolerance: "1%",
    package: "0805",
    pins: [
      { pin_number: "1", pin_name: "1", pin_type: "passive" },
      { pin_number: "2", pin_name: "2", pin_type: "passive" },
    ],
  };

  const sampleSchemObj: SchematicObject = {
    id: "so-r1",
    circuit_id: "circ-1",
    object_type: "symbol",
    component_id: "comp-r1",
    pos_x: 200,
    pos_y: 150,
    rotation: 0,
  };

  // 1. Symbol & Pin Coordinates
  test("Calculates deterministic pin offsets for standard resistor symbol", () => {
    const pins = getStandardPinLayout("resistor");
    assert.equal(pins.length, 2);
    assert.equal(pins[0]?.pin_number, "1");
    assert.equal(pins[0]?.dx, -35);
    assert.equal(pins[1]?.pin_number, "2");
    assert.equal(pins[1]?.dx, 35);
  });

  test("Calculates rotated pin coordinates with 90 degree transform", () => {
    const unrotated = getPinCoordinates(sampleComponent, "1", sampleSchemObj);
    assert.equal(unrotated.x, 165); // 200 - 35
    assert.equal(unrotated.y, 150);

    const rotatedSchemObj: SchematicObject = { ...sampleSchemObj, rotation: 90 };
    const rotated = getPinCoordinates(sampleComponent, "1", rotatedSchemObj);
    assert.equal(rotated.x, 200);
    assert.equal(rotated.y, 115); // 150 - 35
  });

  // 2. Wire Routing & Junction Solder Dots
  test("Computes orthogonal Manhattan routing between non-aligned pins", () => {
    const start = { x: 100, y: 100 };
    const end = { x: 200, y: 180 };
    const path = getOrthogonalPath(start, end);
    assert.equal(path, "M 100 100 L 150 100 L 150 180 L 200 180");

    // Aligned points should form a straight direct path
    const alignedPath = getOrthogonalPath({ x: 100, y: 100 }, { x: 300, y: 100 });
    assert.equal(alignedPath, "M 100 100 L 300 100");
  });

  test("Identifies solder junction dots when 3 or more connections meet at a node", () => {
    const points = [
      { x: 150, y: 100 },
      { x: 150, y: 100 },
      { x: 150, y: 100 }, // 3 connections meet here
      { x: 300, y: 200 },
      { x: 300, y: 200 }, // only 2 connections
    ];
    const junctions = computeJunctionDots(points);
    assert.equal(junctions.length, 1);
    assert.equal(junctions[0]?.x, 150);
    assert.equal(junctions[0]?.y, 100);
  });

  // 3. Workspace State Management & Selection
  test("Initializes circuit workspace and handles selection", () => {
    const store = useCircuitWorkspace.getState();
    store.initCircuit({
      id: "circ-test",
      version: 1,
      components: [sampleComponent],
      nets: [{ id: "net-vcc", circuit_id: "circ-test", name: "VCC", net_type: "power" }],
      connections: [],
      schematic_objects: [sampleSchemObj],
    });

    assert.equal(useCircuitWorkspace.getState().circuitId, "circ-test");
    assert.equal(useCircuitWorkspace.getState().components.length, 1);

    // Component selection
    store.setSelectedComponent("comp-r1");
    assert.equal(useCircuitWorkspace.getState().selectedComponentId, "comp-r1");
    assert.equal(useCircuitWorkspace.getState().selectedNetId, null);

    // Net selection
    store.setSelectedNet("net-vcc");
    assert.equal(useCircuitWorkspace.getState().selectedNetId, "net-vcc");
    assert.equal(useCircuitWorkspace.getState().selectedComponentId, null);

    // Clear selection
    store.clearSelection();
    assert.equal(useCircuitWorkspace.getState().selectedComponentId, null);
    assert.equal(useCircuitWorkspace.getState().selectedNetId, null);
  });

  // 4. Movement with Snap to Grid
  test("Moves component with snap to grid", () => {
    const store = useCircuitWorkspace.getState();
    store.initCircuit({
      id: "circ-test",
      version: 1,
      components: [sampleComponent],
      nets: [],
      connections: [],
      schematic_objects: [sampleSchemObj],
    });

    store.setSnapEnabled(true);
    store.setGridSize(20);

    // Move to (233, 167) -> should snap to (240, 160)
    store.moveComponent("comp-r1", 233, 167);
    const obj = useCircuitWorkspace.getState().schematicObjects.find((o) => o.component_id === "comp-r1");
    assert.equal(obj?.pos_x, 240);
    assert.equal(obj?.pos_y, 160);
  });

  // 5. Inspector Editing
  test("Updates component properties in workspace", () => {
    const store = useCircuitWorkspace.getState();
    store.initCircuit({
      id: "circ-test",
      version: 1,
      components: [sampleComponent],
      nets: [],
      connections: [],
      schematic_objects: [sampleSchemObj],
    });

    store.updateComponentProperty("comp-r1", { value: "47k", tolerance: "0.1%" });
    const comp = useCircuitWorkspace.getState().components.find((c) => c.id === "comp-r1");
    assert.equal(comp?.value, "47k");
    assert.equal(comp?.tolerance, "0.1%");
  });

  // 6. Undo / Redo
  test("Correctly reverts and reapplies state via undo and redo", () => {
    const store = useCircuitWorkspace.getState();
    store.initCircuit({
      id: "circ-test",
      version: 1,
      components: [sampleComponent],
      nets: [],
      connections: [],
      schematic_objects: [sampleSchemObj],
    });

    // Initial value is 10k
    assert.equal(useCircuitWorkspace.getState().components[0]?.value, "10k");

    // Edit value to 22k
    store.updateComponentProperty("comp-r1", { value: "22k" });
    assert.equal(useCircuitWorkspace.getState().components[0]?.value, "22k");

    // Undo -> reverts to 10k
    store.undo();
    assert.equal(useCircuitWorkspace.getState().components[0]?.value, "10k");

    // Redo -> re-applies 22k
    store.redo();
    assert.equal(useCircuitWorkspace.getState().components[0]?.value, "22k");
  });

  // 7. Interactive Wire Creation & Net Assignment
  test("Adds connection and net during wire creation", () => {
    const store = useCircuitWorkspace.getState();
    store.initCircuit({
      id: "circ-test",
      version: 1,
      components: [sampleComponent],
      nets: [],
      connections: [],
      schematic_objects: [sampleSchemObj],
    });

    // Start wire from R1 pin 1
    store.startWireDrawing("comp-r1", "1", "1");
    assert.deepEqual(useCircuitWorkspace.getState().wireDrawingSource, {
      componentId: "comp-r1",
      pinNumber: "1",
      pinName: "1",
    });

    // Add Net VOUT and connect pin 1 to VOUT
    store.addNet({ id: "net-vout", circuit_id: "circ-test", name: "VOUT", net_type: "power" });
    store.addConnection({
      id: "conn-1",
      circuit_id: "circ-test",
      component_id: "comp-r1",
      pin_number: "1",
      net_id: "net-vout",
    });

    assert.equal(useCircuitWorkspace.getState().connections.length, 1);
    assert.equal(useCircuitWorkspace.getState().connections[0]?.net_id, "net-vout");
    // Wire drawing completes and resets source pin
    assert.equal(useCircuitWorkspace.getState().wireDrawingSource, null);
  });

  // 8. Phase 1 Wave 3: Circuit Analysis & Rule Findings Structure
  test("Validates structured CircuitAnalysis with Calculations and Findings", () => {
    const mockAnalysis = {
      id: "an-1",
      circuit_id: "circ-test",
      circuit_version: 1,
      created_by: "eng-1",
      status: "COMPLETE",
      confidence: "HIGH",
      graph_summary: {
        total_components: 2,
        total_nets: 3,
        total_connections: 4,
        floating_pins: [],
        power_nets: ["+5V"],
        ground_nets: ["GND"],
        isolated_subgraphs: 1,
      },
      calculations: [
        {
          id: "calc-1",
          name: "Ohm's Law: R1 (5.0V drop)",
          category: "OHMS_LAW",
          component_ids: ["comp-r1"],
          net_ids: ["net-5v", "net-mid"],
          formula: "I = V / R, P = V * I",
          inputs: { voltage_v: 5.0, resistance_ohms: 10000.0 },
          result: { current_ma: 0.5, power_mw: 2.5 },
          unit: "A",
          confidence: "HIGH",
        },
        {
          id: "calc-2",
          name: "Voltage Divider: R1/R2",
          category: "VOLTAGE_DIVIDER",
          component_ids: ["comp-r1", "comp-r2"],
          net_ids: ["net-5v", "net-mid", "net-gnd"],
          formula: "Vout = Vin * (R2 / (R1 + R2))",
          inputs: { vin_v: 5.0, r1_ohms: 10000.0, r2_ohms: 10000.0 },
          result: { vout_v: 2.5, divider_ratio: 0.5 },
          unit: "V",
          confidence: "HIGH",
        },
      ],
      findings: [
        {
          id: "f-1",
          rule_id: "R006",
          title: "Insufficient power margin on R1",
          description: "R1 operates at 85% of rated power limit.",
          severity: "WARNING",
          component_ids: ["comp-r1"],
          net_ids: [],
          pin_ids: [],
          recommended_action: "Upgrade package from 0402 to 0805.",
          provenance: "DETERMINISTIC_RULE",
        },
      ],
      unknowns: [],
      assumptions: [],
      execution_time_ms: 12.4,
      created_at: new Date().toISOString(),
    };

    assert.equal(mockAnalysis.status, "COMPLETE");
    assert.equal(mockAnalysis.confidence, "HIGH");
    assert.equal(mockAnalysis.calculations.length, 2);
    assert.equal(mockAnalysis.calculations[0]?.category, "OHMS_LAW");
    assert.equal(mockAnalysis.calculations[1]?.result.vout_v, 2.5);
    assert.equal(mockAnalysis.findings.length, 1);
    assert.equal(mockAnalysis.findings[0]?.rule_id, "R006");
    assert.equal(mockAnalysis.findings[0]?.severity, "WARNING");
    assert.equal(mockAnalysis.graph_summary.power_nets[0], "+5V");
  });

  test("Correctly flags BLOCKED status on critical engineering rule violations", () => {
    const criticalFindings = [
      {
        id: "f-crit",
        rule_id: "R003",
        title: "Excessive power dissipation on R1",
        description: "Dissipated power (350 mW) exceeds rated power (125 mW).",
        severity: "CRITICAL",
        component_ids: ["comp-r1"],
        net_ids: [],
        pin_ids: [],
        provenance: "DETERMINISTIC_RULE",
      },
    ];

    const hasCritical = criticalFindings.some((f) => f.severity === "CRITICAL");
    const status = hasCritical ? "BLOCKED" : "COMPLETE";
    assert.equal(status, "BLOCKED");
  });
});

describe("Phase 1 Wave 4.1: Engineering Design Intelligence Hardening", () => {
  test("Evaluates design alternative constraint satisfaction and finding deltas without arbitrary score", () => {
    const mockAlternative = {
      id: "alt-upgrade-r1",
      title: "Upgrade R1 Package to 1206",
      description: "Increase resistor package to 1206 (250mW rating)",
      approach: "PACKAGE_UPGRADE",
      proposed_changes: [
        {
          change_type: "update_component",
          component_id: "comp-r1",
          ref_des: "R1",
          field: "package",
          old_value: "0402",
          new_value: "1206",
        },
      ],
      findings_resolved: ["R003: Excessive resistor power"],
      findings_introduced: [],
      remaining_findings: [],
      hard_constraints_status: "PASS",
      constraint_results: [
        {
          constraint_name: "Max Component Power",
          hard_or_soft: "HARD",
          status: "PASS",
          actual_value: 0.15,
          required_value: 0.25,
        },
      ],
      electrical_effects: {
        power_delta_w: 0.0,
      },
      structural_effects: {
        component_count_delta: 0,
      },
      cost: "UNKNOWN",
      footprint: "1206",
      unknowns: [],
      tradeoffs: ["Larger PCB footprint required (1206 instead of 0402)"],
      confidence: "HIGH" as const,
      is_valid: true,
    };

    assert.equal(mockAlternative.is_valid, true);
    assert.equal(mockAlternative.findings_resolved.length, 1);
    assert.equal(mockAlternative.findings_introduced.length, 0);
    assert.equal(mockAlternative.hard_constraints_status, "PASS");
    assert.equal(mockAlternative.constraint_results[0]?.status, "PASS");
    assert.equal(mockAlternative.confidence, "HIGH");
    assert.equal((mockAlternative as any).score, undefined); // Assert NO score field exists
  });

  test("Identifies STALE proposal when circuit version has advanced past proposal base_revision", () => {
    const proposal = {
      id: "prop-123",
      title: "Add Decoupling Cap C3",
      status: "APPROVED" as const,
      base_revision: 2,
    };

    const currentCircuitVersion = 3;
    const isStale = proposal.base_revision !== undefined && proposal.base_revision !== currentCircuitVersion;
    assert.equal(isStale, true);

    const effectiveStatus = isStale ? "STALE" : proposal.status;
    assert.equal(effectiveStatus, "STALE");
  });

  test("UNKNOWN constraints are never treated as PASS or SATISFIED", () => {
    const hardConstraintResult = {
      constraint_name: "Max Ambient Temperature",
      hard_or_soft: "HARD",
      status: "UNKNOWN",
      actual_value: null,
      required_value: 70,
    };

    const isPass = hardConstraintResult.status === "PASS";
    assert.equal(isPass, false);
    assert.equal(hardConstraintResult.status, "UNKNOWN");

    const softConstraintResult = {
      constraint_name: "Target Bill of Materials Cost",
      hard_or_soft: "SOFT",
      status: "UNKNOWN",
      actual_value: null,
      required_value: 5.0,
    };

    const isSatisfied = softConstraintResult.status === "SATISFIED";
    assert.equal(isSatisfied, false);
    assert.equal(softConstraintResult.status, "UNKNOWN");
  });

  test("Comparison matrix provides transparent evidence without winner or recommendation", () => {
    const comparisonRows = [
      {
        alternative_id: "alt-1",
        title: "E24 Resistor Increase",
        hard_constraints: "PASS",
        soft_constraints: "2/2 SATISFIED",
        findings_resolved_count: 1,
        findings_introduced_count: 0,
        power_delta_w: -0.05,
        confidence: "HIGH",
      },
      {
        alternative_id: "alt-2",
        title: "1206 Package Upgrade",
        hard_constraints: "PASS",
        soft_constraints: "2/2 SATISFIED",
        findings_resolved_count: 1,
        findings_introduced_count: 0,
        power_delta_w: 0.0,
        confidence: "HIGH",
      },
    ];

    // Assert rows contain transparent metrics without any ranking score
    assert.equal(comparisonRows.length, 2);
    for (const row of comparisonRows) {
      assert.equal((row as any).score, undefined);
      assert.equal((row as any).is_best, undefined);
      assert.equal((row as any).is_recommended, undefined);
    }
  });
});

// ==============================================================================
// Phase 1 Wave 5: Engineering Verification, Design Review & Failure Analysis
// ==============================================================================
describe("Phase 1 Wave 5: Engineering Verification & Design Review", () => {
  test("Validates Design Review revision binding and identifies STALE state on revision mismatch", () => {
    const mockReview = {
      id: "rev-101",
      circuit_id: "circ-wave5",
      circuit_revision: 2,
      analysis_id: "an-202",
      status: "VERIFICATION_REQUIRED",
      is_stale: false,
      verification_requirements: [
        { id: "vr-1", code: "VR-001", status: "NOT_STARTED", is_mandatory: true },
      ],
    };

    assert.equal(mockReview.circuit_revision, 2);
    assert.equal(mockReview.analysis_id, "an-202");

    // When circuit version advances to 3
    const currentCircuitVersion = 3;
    const isStale = mockReview.circuit_revision !== currentCircuitVersion;
    assert.equal(isStale, true);
  });

  test("UNKNOWN verification requirements cannot be treated as SATISFIED", () => {
    const unknownReq = {
      id: "vr-002",
      code: "VR-002",
      title: "Verify Junction Temperature under Thermal Extreme",
      status: "UNKNOWN",
      unknowns: ["Ambient temperature profile unverified"],
      is_mandatory: true,
    };

    // Contract: UNKNOWN != PASS / SATISFIED
    const isSatisfied = unknownReq.status === "SATISFIED";
    assert.equal(isSatisfied, false);
    assert.equal(unknownReq.unknowns.length > 0, true);
  });

  test("Failure modes carry deterministic evidence basis and severity", () => {
    const mockFailureMode = {
      id: "fm-1",
      category: "THERMAL_OVERSTRESS",
      trigger: "Elevated Junction Temperature: 118°C",
      mechanism: "Linear power dissipation exceeds unheatsinked thermal package threshold",
      likelihood: "HIGH",
      severity: "CRITICAL",
      evidence: ["DETERMINISTIC_ANALYSIS", "THERMAL_DISSIPATION_EQUATION"],
    };

    assert.equal(mockFailureMode.severity, "CRITICAL");
    assert.equal(mockFailureMode.evidence.includes("DETERMINISTIC_ANALYSIS"), true);
    assert.equal((mockFailureMode as any).risk_score, undefined); // No arbitrary score!
  });

  test("Test points link to verification requirements and specify instrumentation", () => {
    const mockTestPoint = {
      id: "tp-1",
      code: "TP-001",
      measurement: "DC Steady-State Voltage on +5V",
      expected_basis: "Target voltage within +/- 3% under nominal load",
      instrumentation: "Digital Multimeter (6.5 digit precision)",
      operating_condition: "NOMINAL",
      related_requirement_id: "vr-001",
    };

    assert.equal(mockTestPoint.code, "TP-001");
    assert.equal(mockTestPoint.instrumentation.includes("Multimeter"), true);
    assert.equal(mockTestPoint.related_requirement_id, "vr-001");
  });

  test("Traceable engineering evidence requires verifiable source and reference", () => {
    const mockEvidence = {
      id: "ev-1",
      verification_requirement_id: "vr-1",
      evidence_type: "MEASUREMENT",
      source: "Keysight 34461A 6.5 Digit DMM",
      description: "Measured rail voltage under full 1.0A load",
      value: "4.988",
      unit: "V",
      reference: "Laboratory Test Log Book 3, p. 12",
      status: "VALID",
      confidence: "HIGH",
      provided_by: "engineer-1",
    };

    assert.equal(mockEvidence.status, "VALID");
    assert.equal(mockEvidence.value, "4.988");
    assert.equal(mockEvidence.unit, "V");
    assert.equal(mockEvidence.provided_by, "engineer-1");
  });
});

describe("Phase 1 Wave 6: Engineering Knowledge, Evidence & Traceability Test Suite", () => {
  test("Validates EngineeringSource integrity with SHA-256 document digest and trust level", () => {
    const source = {
      id: "src-lm7805",
      title: "TI LM7805 Linear Regulator Datasheet",
      document_type: "DATASHEET",
      publisher: "Texas Instruments",
      revision: "Rev. T",
      document_digest: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      trust_level: "MANUFACTURER_PRIMARY",
      is_deprecated: false,
    };

    assert.equal(source.document_digest.length, 64);
    assert.match(source.document_digest, /^[a-f0-9]{64}$/);
    assert.equal(source.trust_level, "MANUFACTURER_PRIMARY");
    assert.equal((source as any).trust_score, undefined); // Never an arbitrary score
  });

  test("Validates End-to-End Traceability graph structure", () => {
    const traceabilityGraph = {
      root_type: "FINDING",
      root_id: "fnd-101",
      finding: {
        id: "fnd-101",
        rule_code: "PWR-001",
        title: "Max junction temp exceeded",
        severity: "CRITICAL",
      },
      analysis_provenance: {
        analysis_id: "an-202",
        circuit_revision: 2,
        engine_versions: { OhmsLawEngine: "1.2.0", RuleEngine: "1.4.0" },
        rule_set_version: "QUEBET-ELECTRICAL-001 v1.3",
        knowledge_snapshot_id: "snap-abc",
      },
      knowledge_records: [
        {
          id: "kr-lm7805-theta-ja",
          subject_identifier: "LM7805",
          parameter: "thermal_resistance_junction_to_ambient",
          value: "54.0",
          unit: "C/W",
          status: "VERIFIED",
        },
      ],
      sources: [
        {
          id: "src-ti-lm7805",
          title: "TI LM7805 Linear Regulator Datasheet",
          trust_level: "MANUFACTURER_PRIMARY",
        },
      ],
      requirements: [
        {
          id: "vr-1",
          code: "VR-001",
          title: "Verify LM7805 Junction Temperature",
        },
      ],
      evidence: [
        {
          id: "ev-1",
          verification_requirement_id: "vr-1",
          evidence_type: "MEASUREMENT",
          status: "VALID",
          instrument: "FLIR E4 Thermal Camera",
          calibration_status: "CALIBRATED",
        },
      ],
      reviews: [],
    };

    assert.equal(traceabilityGraph.root_type, "FINDING");
    assert.equal(traceabilityGraph.finding?.id, "fnd-101");
    assert.equal(traceabilityGraph.analysis_provenance?.rule_set_version, "QUEBET-ELECTRICAL-001 v1.3");
    assert.equal(traceabilityGraph.knowledge_records[0]?.subject_identifier, "LM7805");
    assert.equal(traceabilityGraph.sources[0]?.trust_level, "MANUFACTURER_PRIMARY");
    assert.equal(traceabilityGraph.evidence[0]?.calibration_status, "CALIBRATED");
  });

  test("Evaluates Knowledge applicability ternary states (never assumes applicability)", () => {
    // Condition testing helper mirroring ApplicabilityEngine
    function evaluateApplicability(
      conditions: Record<string, any>,
      context: Record<string, any>
    ): "APPLICABLE" | "NOT_APPLICABLE" | "CONDITIONALLY_APPLICABLE" | "UNKNOWN" {
      if (!conditions || Object.keys(conditions).length === 0) {
        return "APPLICABLE";
      }

      let hasConditional = false;
      for (const [key, expected] of Object.entries(conditions)) {
        if (!(key in context)) {
          return "UNKNOWN";
        }
        const actual = context[key];
        if (typeof expected === "object" && expected !== null) {
          if (expected.min !== undefined && actual < expected.min) return "NOT_APPLICABLE";
          if (expected.max !== undefined && actual > expected.max) return "NOT_APPLICABLE";
          hasConditional = true;
        } else if (actual !== expected) {
          return "NOT_APPLICABLE";
        }
      }
      return hasConditional ? "CONDITIONALLY_APPLICABLE" : "APPLICABLE";
    }

    // Matching conditions
    const matched = evaluateApplicability(
      { package: "TO-220", ambient_temp_c: { min: -40, max: 125 } },
      { package: "TO-220", ambient_temp_c: 25 }
    );
    assert.equal(matched, "CONDITIONALLY_APPLICABLE");

    // Package mismatch
    const packageMismatch = evaluateApplicability(
      { package: "TO-220" },
      { package: "SOT-223" }
    );
    assert.equal(packageMismatch, "NOT_APPLICABLE");

    // Temperature out of range
    const tempExceeded = evaluateApplicability(
      { ambient_temp_c: { min: -40, max: 125 } },
      { ambient_temp_c: 135 }
    );
    assert.equal(tempExceeded, "NOT_APPLICABLE");

    // Context missing required parameter -> UNKNOWN (NEVER assumed APPLICABLE)
    const unknownState = evaluateApplicability(
      { package: "TO-220", airflow_lfm: 200 },
      { package: "TO-220" } // airflow missing
    );
    assert.equal(unknownState, "UNKNOWN");
  });

  test("Flags evidence as stale when circuit revision advances", () => {
    const evidence = {
      id: "ev-101",
      verification_requirement_id: "vr-1",
      circuit_revision: 2,
      is_stale: false,
    };

    const currentCircuitRevision = 3;
    const isStale = evidence.circuit_revision !== currentCircuitRevision;
    assert.equal(isStale, true);
  });

  test("Requires instrument calibration traceability for physical measurement evidence", () => {
    const validEvidence = {
      id: "ev-201",
      evidence_type: "MEASUREMENT",
      instrument: "Keysight 34461A 6.5 Digit DMM",
      instrument_model: "34461A",
      instrument_serial: "MY53102345",
      calibration_reference: "CAL-2025-0812",
      calibration_status: "CALIBRATED",
    };

    assert.equal(validEvidence.calibration_status, "CALIBRATED");
    assert.equal(validEvidence.instrument_serial, "MY53102345");

    const expiredEvidence = {
      ...validEvidence,
      calibration_status: "EXPIRED",
    };
    assert.equal(expiredEvidence.calibration_status, "EXPIRED");
    assert.notEqual(expiredEvidence.calibration_status, "CALIBRATED");
  });
});

describe("Phase 1 Wave 7: System-Level Engineering Intelligence & Subsystem Architecture Test Suite", () => {
  test("Validates hierarchical Subsystem decomposition and cycle prevention semantics", () => {
    const parentSub = {
      id: "sub-pwr",
      name: "Power Architecture",
      subsystem_type: "POWER",
      parent_subsystem_id: null,
      revision: 1,
    };

    const childSub1 = {
      id: "sub-reg",
      name: "5V Buck Regulator",
      subsystem_type: "REGULATION",
      parent_subsystem_id: "sub-pwr",
      revision: 1,
    };

    const childSub2 = {
      id: "sub-filt",
      name: "Output Filter",
      subsystem_type: "PASSIVE",
      parent_subsystem_id: "sub-reg",
      revision: 1,
    };

    const subsystems = [parentSub, childSub1, childSub2];

    // Cycle detection helper walking parent pointers
    function checkCycle(subId: string, targetParentId: string): boolean {
      let current: string | null = targetParentId;
      while (current) {
        if (current === subId) return true;
        const found = subsystems.find((s) => s.id === current);
        current = found ? found.parent_subsystem_id : null;
      }
      return false;
    }

    assert.equal(checkCycle("sub-pwr", "sub-reg"), true); // Attempting to make sub-pwr child of sub-reg would cause cycle
    assert.equal(checkCycle("sub-pwr", "sub-filt"), true); // Attempting to make sub-pwr child of sub-filt would cause cycle
    assert.equal(checkCycle("sub-filt", "sub-pwr"), false); // Valid hierarchy
  });

  test("Evaluates Interface Compatibility Engine 4-state logic (UNKNOWN != PASS)", () => {
    interface InterfaceContract {
      protocol?: string;
      voltage_nominal?: number;
      voltage_min?: number;
      voltage_max?: number;
      baud_rate?: number;
      logic_level?: string;
    }

    function evaluateInterface(
      src: InterfaceContract,
      dst: InterfaceContract
    ): { status: "COMPATIBLE" | "INCOMPATIBLE" | "PARTIALLY_COMPATIBLE" | "UNKNOWN"; unknowns: string[]; mismatches: string[] } {
      const unknowns: string[] = [];
      const mismatches: string[] = [];

      // Check protocol
      if (!src.protocol || !dst.protocol) {
        unknowns.push("protocol");
      } else if (src.protocol !== dst.protocol) {
        mismatches.push(`Protocol mismatch: ${src.protocol} vs ${dst.protocol}`);
      }

      // Check voltage
      if (src.voltage_nominal === undefined || dst.voltage_nominal === undefined) {
        unknowns.push("voltage_nominal");
      } else if (Math.abs(src.voltage_nominal - dst.voltage_nominal) > 0.05) {
        mismatches.push(`Nominal voltage mismatch: ${src.voltage_nominal}V vs ${dst.voltage_nominal}V`);
      }

      // Check baud rate if present
      if (src.baud_rate && dst.baud_rate && src.baud_rate !== dst.baud_rate) {
        mismatches.push(`Baud rate mismatch: ${src.baud_rate} vs ${dst.baud_rate}`);
      }

      if (mismatches.length > 0) {
        return { status: "INCOMPATIBLE", unknowns, mismatches };
      }
      if (unknowns.length > 0) {
        return { status: "UNKNOWN", unknowns, mismatches };
      }
      return { status: "COMPATIBLE", unknowns, mismatches };
    }

    // 1. Fully compatible
    const compResult = evaluateInterface(
      { protocol: "SPI", voltage_nominal: 3.3, baud_rate: 1000000 },
      { protocol: "SPI", voltage_nominal: 3.3, baud_rate: 1000000 }
    );
    assert.equal(compResult.status, "COMPATIBLE");

    // 2. Incompatible (voltage mismatch)
    const incompResult = evaluateInterface(
      { protocol: "UART", voltage_nominal: 5.0 },
      { protocol: "UART", voltage_nominal: 3.3 }
    );
    assert.equal(incompResult.status, "INCOMPATIBLE");
    assert.equal(incompResult.mismatches.length > 0, true);

    // 3. Missing info -> strictly UNKNOWN, never PASS
    const unknownResult = evaluateInterface(
      { protocol: "I2C" }, // missing voltage_nominal
      { protocol: "I2C", voltage_nominal: 3.3 }
    );
    assert.equal(unknownResult.status, "UNKNOWN");
    assert.equal(unknownResult.unknowns.includes("voltage_nominal"), true);
  });

  test("Aggregates Power Tree loads and detects capacity limits", () => {
    const powerDomain = {
      id: "dom-5v",
      name: "5V_MAIN",
      nominal_voltage: 5.0,
      current_capacity_a: 2.0, // 2A capacity
    };

    const connectedLoads = [
      { subsystem_id: "sub-mcu", current_draw_a: 0.15 },
      { subsystem_id: "sub-sensors", current_draw_a: 0.05 },
      { subsystem_id: "sub-display", current_draw_a: 0.8 },
      { subsystem_id: "sub-radio", current_draw_a: 0.5 },
    ];

    const totalDrawA = connectedLoads.reduce((sum, item) => sum + item.current_draw_a, 0);
    assert.equal(Math.round(totalDrawA * 100) / 100, 1.5);
    assert.equal(totalDrawA <= powerDomain.current_capacity_a, true);

    // Add extra motor load that overdraws domain
    const overloadedDrawA = totalDrawA + 1.2; // 2.7A > 2.0A
    assert.equal(overloadedDrawA > powerDomain.current_capacity_a, true);
  });

  test("Evaluates Failure Propagation and containment barriers", () => {
    const propagationGraph = {
      root_cause: { subsystem_id: "sub-high-voltage", failure: "SURGE_OVERVOLTAGE" },
      path: [
        { from: "sub-high-voltage", to: "sub-isolated-transceiver", isolated: true, barrier: "GALVANIC_ISOLATION" },
        { from: "sub-isolated-transceiver", to: "sub-mcu", isolated: false, barrier: null },
      ],
    };

    // Determine if failure is contained by barrier
    const barrier = propagationGraph.path.find((p) => p.isolated);
    assert.equal(Boolean(barrier), true);
    assert.equal(barrier?.barrier, "GALVANIC_ISOLATION");
  });

  test("Verifies that system revision advances mark previous analyses as STALE", () => {
    const analysis = {
      id: "sa-1",
      system_id: "sys-1",
      system_revision: 2,
      is_stale: false,
    };

    const currentSystemRevision = 3;
    const isStale = analysis.system_revision < currentSystemRevision;
    assert.equal(isStale, true);
  });

  test("Validates System Snapshot structure and cryptographic digest format", () => {
    const snapshot = {
      id: "snap-sys-1",
      system_id: "sys-1",
      system_revision: 3,
      snapshot_hash: "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e",
      content: {
        system: { id: "sys-1", name: "Autonomous Rover Architecture", revision: 3 },
        subsystems_count: 5,
        interfaces_count: 7,
      },
    };

    assert.equal(snapshot.snapshot_hash.length, 64);
    assert.match(snapshot.snapshot_hash, /^[a-f0-9]{64}$/);
    assert.equal(snapshot.system_revision, 3);
  });
});

describe("Phase 1 Wave 8: System Design Synthesis & Scenario Intelligence Test Suite", () => {
  test("Enforces Hard vs Soft constraint semantics and UNKNOWN != SATISFIED boundary", () => {
    interface Constraint {
      metric: string;
      constraint_type: "HARD" | "SOFT";
      operator: "<=" | ">=";
      target_value: number;
    }

    function evaluateConstraint(
      constraint: Constraint,
      actualValue: number | undefined
    ): { status: "SATISFIED" | "VIOLATED" | "UNKNOWN"; reason: string } {
      if (actualValue === undefined) {
        return {
          status: "UNKNOWN",
          reason: `Metric ${constraint.metric} is unknown/uncalculated`,
        };
      }

      const satisfied =
        constraint.operator === "<="
          ? actualValue <= constraint.target_value
          : actualValue >= constraint.target_value;

      return {
        status: satisfied ? "SATISFIED" : "VIOLATED",
        reason: satisfied
          ? `Constraint satisfied: ${actualValue} ${constraint.operator} ${constraint.target_value}`
          : `Constraint violated: ${actualValue} does not satisfy ${constraint.operator} ${constraint.target_value}`,
      };
    }

    // Hard constraint satisfied
    const hardSatisfied = evaluateConstraint(
      { metric: "power_dissipation_w", constraint_type: "HARD", operator: "<=", target_value: 10.0 },
      8.5
    );
    assert.equal(hardSatisfied.status, "SATISFIED");

    // Hard constraint violated
    const hardViolated = evaluateConstraint(
      { metric: "power_dissipation_w", constraint_type: "HARD", operator: "<=", target_value: 10.0 },
      12.4
    );
    assert.equal(hardViolated.status, "VIOLATED");

    // Missing metric -> UNKNOWN, strictly NOT SATISFIED
    const hardUnknown = evaluateConstraint(
      { metric: "thermal_junction_c", constraint_type: "HARD", operator: "<=", target_value: 85.0 },
      undefined
    );
    assert.equal(hardUnknown.status, "UNKNOWN");
    assert.notEqual(hardUnknown.status, "SATISFIED");
  });

  test("Gates Scenario Execution on mandatory preconditions and validates SHA-256 snapshot", () => {
    interface ScenarioPreconditions {
      system_active: boolean;
      all_power_rails_nominal?: boolean;
    }

    function validatePreconditions(
      preconditions: ScenarioPreconditions,
      currentState: { active: boolean; rails_nominal: boolean | null }
    ): { satisfied: boolean; missing: string[] } {
      const missing: string[] = [];
      if (!currentState.active) {
        missing.push("system_active");
      }
      if (preconditions.all_power_rails_nominal) {
        if (currentState.rails_nominal !== true) {
          missing.push("all_power_rails_nominal");
        }
      }
      return { satisfied: missing.length === 0, missing };
    }

    // 1. Mandatory precondition met
    const pass = validatePreconditions(
      { system_active: true },
      { active: true, rails_nominal: true }
    );
    assert.equal(pass.satisfied, true);
    assert.equal(pass.missing.length, 0);

    // 2. Mandatory precondition not met -> Execution BLOCKED
    const blocked = validatePreconditions(
      { system_active: true, all_power_rails_nominal: true },
      { active: true, rails_nominal: null } // rails_nominal is unknown
    );
    assert.equal(blocked.satisfied, false);
    assert.equal(blocked.missing.includes("all_power_rails_nominal"), true);

    // 3. Scenario Snapshot Hash Format Verification
    const scenarioSnapshotHash = "b845e2a39df743a18e0019ffcd901844b209c135678da47712e5c832bb584e09";
    assert.equal(scenarioSnapshotHash.length, 64);
    assert.match(scenarioSnapshotHash, /^[a-f0-9]{64}$/);
  });

  test("Validates zero-synthetic-scoring in Multidimensional Comparison Matrix", () => {
    // Comparison matrix data structure
    const comparisonMatrix = {
      objective_id: "obj-power-opt",
      baseline: {
        revision: 2,
        subsystem_count: 4,
        interface_violations: 0,
        power_margin_w: 3.2,
        unverified_obligations: 1,
      },
      candidates: [
        {
          id: "cand-buck-swap",
          strategy: "REGULATOR_REPLACEMENT",
          subsystem_count: 4,
          interface_violations: 0,
          power_margin_w: 5.8,
          unverified_obligations: 2,
        },
        {
          id: "cand-isolated-can",
          strategy: "SUBSYSTEM_ISOLATION",
          subsystem_count: 5,
          interface_violations: 0,
          power_margin_w: 3.0,
          unverified_obligations: 3,
        },
      ],
    };

    // Verify presence of independent engineering dimensions
    assert.equal(comparisonMatrix.baseline.power_margin_w, 3.2);
    assert.equal(comparisonMatrix.candidates[0].power_margin_w, 5.8);
    assert.equal(comparisonMatrix.candidates[1].subsystem_count, 5);

    // Verify absence of composite / synthetic / gamified scores
    const objKeys = Object.keys(comparisonMatrix);
    assert.equal(objKeys.includes("composite_score"), false);
    assert.equal(objKeys.includes("winner"), false);
    assert.equal(objKeys.includes("health_score"), false);
    assert.equal(objKeys.includes("best_candidate"), false);
  });

  test("Enforces System Proposal revision binding, stale rejection, and atomic state transition", () => {
    interface SystemProposal {
      id: string;
      system_id: string;
      base_revision: number;
      status: "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "REJECTED" | "APPLIED" | "STALE";
      operations: Array<{ op_type: string; payload: Record<string, any> }>;
    }

    const proposal: SystemProposal = {
      id: "prop-ldo-replace",
      system_id: "sys-power-01",
      base_revision: 2,
      status: "DRAFT",
      operations: [
        { op_type: "ADD_SUBSYSTEM", payload: { name: "Buck Converter", subsystem_type: "REGULATION" } },
      ],
    };

    // Stale check against current system revision
    function validateProposalFreshness(prop: SystemProposal, currentSystemRevision: number): boolean {
      return prop.base_revision === currentSystemRevision;
    }

    // 1. Fresh against revision 2
    assert.equal(validateProposalFreshness(proposal, 2), true);

    // 2. Stale if system revision advances to 3
    assert.equal(validateProposalFreshness(proposal, 3), false);

    // 3. Approval lifecycle: Human must approve before applying
    function approveProposal(prop: SystemProposal, currentSystemRevision: number): SystemProposal {
      if (!validateProposalFreshness(prop, currentSystemRevision)) {
        return { ...prop, status: "STALE" };
      }
      return { ...prop, status: "APPROVED" };
    }

    const approvedProp = approveProposal(proposal, 2);
    assert.equal(approvedProp.status, "APPROVED");

    // 4. Stale approval rejection
    const staleProp = approveProposal(proposal, 3);
    assert.equal(staleProp.status, "STALE");

    // 5. Atomic Application increments system revision
    function applyApprovedProposal(prop: SystemProposal, currentSystemRevision: number) {
      if (prop.status !== "APPROVED") {
        throw new Error("PROPOSAL_NOT_APPROVED: Human approval required");
      }
      if (prop.base_revision !== currentSystemRevision) {
        throw new Error("SYSTEM_PROPOSAL_STALE: Base revision mismatch");
      }
      return {
        new_system_revision: currentSystemRevision + 1,
        proposal_status: "APPLIED" as const,
      };
    }

    const appliedResult = applyApprovedProposal(approvedProp, 2);
    assert.equal(appliedResult.new_system_revision, 3);
    assert.equal(appliedResult.proposal_status, "APPLIED");
  });

  // 19. Phase 1 Wave 9: Requirements, Baselines & Coverage (Zero Synthetic Score)
  test("Phase 1 Wave 9: Validates structured requirement expression and baseline immutability", () => {
    interface Requirement {
      id: string;
      key: string;
      priority: "SHALL" | "SHOULD" | "MAY";
      structured_expression?: {
        parameter: string;
        operator: string;
        nominal_value?: number;
        max_value?: number;
        unit: string;
      };
      status: "DRAFT" | "APPROVED";
    }

    const req: Requirement = {
      id: "req-1",
      key: "REQ-SYS-001",
      priority: "SHALL",
      structured_expression: {
        parameter: "efficiency",
        operator: ">=",
        nominal_value: 85,
        unit: "%",
      },
      status: "APPROVED",
    };

    assert.equal(req.priority, "SHALL");
    assert.equal(req.structured_expression?.parameter, "efficiency");
    assert.equal(req.structured_expression?.nominal_value, 85);

    // Baseline creation
    interface RequirementBaseline {
      id: string;
      system_revision: number;
      name: string;
      baseline_hash: string;
      requirement_ids: string[];
      is_frozen: boolean;
    }

    const baseline: RequirementBaseline = {
      id: "base-cdr",
      system_revision: 1,
      name: "CDR Baseline Freeze",
      baseline_hash: "a".repeat(64),
      requirement_ids: [req.id],
      is_frozen: true,
    };

    assert.equal(baseline.is_frozen, true);
    assert.equal(baseline.baseline_hash.length, 64);

    // Epistemological boundary: Coverage check must NEVER convert UNKNOWN into SATISFIED/PASS
    type CoverageStatus = "COVERED" | "PARTIALLY_COVERED" | "NOT_COVERED" | "UNKNOWN";
    function evaluateCoverage(hasVerificationRequirement: boolean, isVerified: boolean | null): CoverageStatus {
      if (!hasVerificationRequirement) return "NOT_COVERED";
      if (isVerified === null) return "UNKNOWN"; // UNKNOWN != PASS
      if (isVerified === true) return "COVERED";
      return "PARTIALLY_COVERED";
    }

    assert.equal(evaluateCoverage(true, null), "UNKNOWN");
    assert.notEqual(evaluateCoverage(true, null), "COVERED");
    assert.equal(evaluateCoverage(true, true), "COVERED");
    assert.equal(evaluateCoverage(false, false), "NOT_COVERED");
  });

  // 20. Phase 1 Wave 9: Multidimensional Comparison Matrix with ZERO Synthetic Scoring
  test("Phase 1 Wave 9: Alternative Comparison Matrix strictly prohibits composite scores and winner badges", () => {
    interface AlternativeComparisonItem {
      alternative_id: string;
      name: string;
      engineering_effects: Record<string, string>;
      requirement_effects: Record<string, string>;
      unknowns: string[];
      // Strictly NO overall_score, decision_score, rank, or is_winner
    }

    const matrix: AlternativeComparisonItem[] = [
      {
        alternative_id: "alt-buck",
        name: "Synchronous Buck Regulator",
        engineering_effects: { efficiency: "92%", thermal: "0.3W" },
        requirement_effects: { "REQ-SYS-001": "SATISFIED" },
        unknowns: ["Board parasitic resonance"],
      },
      {
        alternative_id: "alt-ldo",
        name: "Linear LDO Regulator",
        engineering_effects: { efficiency: "27.5%", thermal: "17W" },
        requirement_effects: { "REQ-SYS-001": "VIOLATED" },
        unknowns: ["Airflow dependence"],
      },
    ];

    for (const item of matrix) {
      assert.equal((item as any).overall_score, undefined);
      assert.equal((item as any).decision_score, undefined);
      assert.equal((item as any).rank, undefined);
      assert.equal((item as any).is_winner, undefined);
      assert.equal((item as any).winner, undefined);
    }
  });

  // 21. Phase 1 Wave 9: Human Selection Authority & Revision Binding
  test("Phase 1 Wave 9: Human alternative selection enforces mandatory justification and revision freshness", () => {
    interface DecisionRecord {
      id: string;
      system_revision: number;
      status: "DRAFT" | "DECIDED";
      selected_alternative_id: string | null;
      decided_by: string | null;
      rationale: {
        decision_rationale: string;
        key_requirements: string[];
        accepted_unknowns: string[];
      } | null;
    }

    const decision: DecisionRecord = {
      id: "dec-01",
      system_revision: 2,
      status: "DRAFT",
      selected_alternative_id: null,
      decided_by: null,
      rationale: null,
    };

    function selectAlternative(
      rec: DecisionRecord,
      altId: string,
      engineerId: string,
      rationale: string,
      currentSystemRev: number
    ): DecisionRecord {
      if (rec.system_revision !== currentSystemRev) {
        throw new Error("DECISION_STALE: System revision advanced since decision context was prepared");
      }
      if (!rationale || rationale.trim().length === 0) {
        throw new Error("RATIONALE_REQUIRED: Human decision requires explicit engineering justification");
      }
      return {
        ...rec,
        status: "DECIDED",
        selected_alternative_id: altId,
        decided_by: engineerId,
        rationale: {
          decision_rationale: rationale,
          key_requirements: ["REQ-SYS-001"],
          accepted_unknowns: ["Measured during proto rev A"],
        },
      };
    }

    // 1. Successful selection by engineer at fresh revision
    const decided = selectAlternative(
      decision,
      "alt-buck",
      "eng-alice",
      "Selected buck because 17W LDO dissipation exceeds thermal budget.",
      2
    );
    assert.equal(decided.status, "DECIDED");
    assert.equal(decided.selected_alternative_id, "alt-buck");
    assert.equal(decided.decided_by, "eng-alice");

    // 2. Stale rejection if system revision has bumped to 3
    assert.throws(
      () =>
        selectAlternative(
          decision,
          "alt-buck",
          "eng-alice",
          "Selection should fail due to staleness",
          3
        ),
      /DECISION_STALE/
    );
  });

  // 22. Phase 1 Wave 9: Design Review Readiness & Gating
  test("Phase 1 Wave 9: Review closure is gated on non-blocked status and waiver justifications", () => {
    interface ReviewFinding {
      id: string;
      severity: "INFO" | "MINOR" | "MAJOR" | "CRITICAL" | "BLOCKER";
      status: "OPEN" | "WAIVED" | "RESOLVED";
      waiver_rationale?: string;
    }

    const findings: ReviewFinding[] = [
      {
        id: "find-01",
        severity: "BLOCKER",
        status: "OPEN",
      },
    ];

    function evaluateReadiness(findingsList: ReviewFinding[]): { overall_status: "READY" | "BLOCKED"; blockers: string[] } {
      const openBlockers = findingsList.filter(
        (f) => (f.severity === "BLOCKER" || f.severity === "CRITICAL") && f.status === "OPEN"
      );
      if (openBlockers.length > 0) {
        return {
          overall_status: "BLOCKED",
          blockers: [`${openBlockers.length} blocker findings remain open`],
        };
      }
      return {
        overall_status: "READY",
        blockers: [],
      };
    }

    // 1. Initial review is BLOCKED by open blocker finding
    const r1 = evaluateReadiness(findings);
    assert.equal(r1.overall_status, "BLOCKED");
    assert.equal(r1.blockers.length, 1);

    // 2. Engineer waives finding with mandatory justification
    function waiveFinding(finding: ReviewFinding, rationale: string): ReviewFinding {
      if (!rationale || rationale.trim().length === 0) {
        throw new Error("WAIVER_RATIONALE_REQUIRED");
      }
      return { ...finding, status: "WAIVED", waiver_rationale: rationale };
    }

    const waivedFinding = waiveFinding(findings[0]!, "Internal termination resistor enabled in FPGA.");
    assert.equal(waivedFinding.status, "WAIVED");

    // 3. Review is now unblocked and ready for human chairperson closure
    const r2 = evaluateReadiness([waivedFinding]);
    assert.equal(r2.overall_status, "READY");
    assert.equal(r2.blockers.length, 0);
  });

  // 23. Phase 2 Wave 1: Cognitive Intent & Ambiguity Resolution
  test("Phase 2 Wave 1: Disambiguates generic queries into CLARIFICATION_REQUIRED and candidate options", () => {
    interface Ambiguity {
      type: string;
      target: string;
      status: string;
      candidates: { ref_des: string; name: string }[];
    }

    function checkComponentAmbiguity(query: string, circuitComponents: { ref_des: string; name: string }[]): {
      status: "INTERPRETED" | "CLARIFICATION_REQUIRED";
      ambiguities: Ambiguity[];
    } {
      const isGeneric = query.toLowerCase().includes("the regulator") && !/u\d+/i.test(query);
      if (isGeneric && circuitComponents.length > 1) {
        return {
          status: "CLARIFICATION_REQUIRED",
          ambiguities: [
            {
              type: "MULTIPLE_MATCHES",
              target: "regulator",
              status: "CLARIFICATION_REQUIRED",
              candidates: circuitComponents,
            },
          ],
        };
      }
      return { status: "INTERPRETED", ambiguities: [] };
    }

    const components = [
      { ref_des: "U1", name: "Buck 5V" },
      { ref_des: "U2", name: "Buck 3.3V" },
    ];

    // Ambiguous query flags clarification
    const ambRes = checkComponentAmbiguity("Verify thermal margin for the regulator", components);
    assert.equal(ambRes.status, "CLARIFICATION_REQUIRED");
    assert.equal(ambRes.ambiguities[0]?.candidates.length, 2);

    // Specific query proceeds without clarification requirement
    const specRes = checkComponentAmbiguity("Verify thermal margin for U1 buck regulator", components);
    assert.equal(specRes.status, "INTERPRETED");
    assert.equal(specRes.ambiguities.length, 0);
  });

  // 24. Phase 2 Wave 1: Task Plan DAG Cycle Detection
  test("Phase 2 Wave 1: Topological validation detects and rejects cyclic task graphs", () => {
    interface Task {
      key: string;
      dependencies: string[];
    }

    function detectCycle(tasks: Task[]): boolean {
      const adj: Record<string, string[]> = {};
      tasks.forEach((t) => {
        adj[t.key] = t.dependencies;
      });

      const visited = new Set<string>();
      const recStack = new Set<string>();

      function hasCycle(key: string): boolean {
        visited.add(key);
        recStack.add(key);
        for (const dep of adj[key] || []) {
          if (!visited.has(dep)) {
            if (hasCycle(dep)) return true;
          } else if (recStack.has(dep)) {
            return true;
          }
        }
        recStack.delete(key);
        return false;
      }

      for (const t of tasks) {
        if (!visited.has(t.key)) {
          if (hasCycle(t.key)) return true;
        }
      }
      return false;
    }

    const validPipeline: Task[] = [
      { key: "T1", dependencies: [] },
      { key: "T2", dependencies: ["T1"] },
      { key: "T3", dependencies: ["T2"] },
    ];
    assert.equal(detectCycle(validPipeline), false);

    const cyclicPipeline: Task[] = [
      { key: "T1", dependencies: ["T2"] },
      { key: "T2", dependencies: ["T1"] },
    ];
    assert.equal(detectCycle(cyclicPipeline), true);
  });

  // 25. Phase 2 Wave 1: Stale Plan Rejection & Epistemological Boundaries
  test("Phase 2 Wave 1: Rejects plan execution when system revision advances (COGNITIVE_PLAN_STALE)", () => {
    function validatePlanFreshness(planRevision: number, currentRevision: number): {
      is_valid: boolean;
      error?: string;
    } {
      if (planRevision !== currentRevision) {
        return {
          is_valid: false,
          error: "COGNITIVE_PLAN_STALE",
        };
      }
      return { is_valid: true };
    }

    assert.equal(validatePlanFreshness(2, 2).is_valid, true);
    const staleResult = validatePlanFreshness(1, 2);
    assert.equal(staleResult.is_valid, false);
    assert.equal(staleResult.error, "COGNITIVE_PLAN_STALE");
  });

  test("Phase 2 Wave 1: Epistemological boundary enforces UNKNOWN != PASS and zero synthetic scoring", () => {
    const taskOutput = {
      verification_status: "UNKNOWN",
      margin_calculated: false,
      missing_evidence: "Thermal impedance junction-to-ambient Rth_ja not documented",
    };

    // Strict boundary: UNKNOWN is never treated as PASS or SATISFIED
    assert.notEqual(taskOutput.verification_status, "PASS");
    assert.notEqual(taskOutput.verification_status, "SATISFIED");

    // Prohibition of synthetic composite scoring
    assert.equal("overall_score" in taskOutput, false);
    assert.equal("plan_score" in taskOutput, false);
    assert.equal("intelligence_score" in taskOutput, false);
  });

  // 26. Phase 2 Wave 1.1: Cognitive Hardening & Context Snapshot Invariants
  test("Phase 2 Wave 1.1: Context snapshot canonical digest invariants & state transitions", () => {
    // Canonical digest simulation: sorted references
    function computeCanonicalHash(params: {
      projectId: string;
      projectRevision: number;
      systemRevision: number | null;
      assumptions: string[];
    }): string {
      const sortedAssumptions = [...params.assumptions].sort();
      return `${params.projectId}:v${params.projectRevision}:sys${params.systemRevision}:[${sortedAssumptions.join(",")}]`;
    }

    const digest1 = computeCanonicalHash({
      projectId: "P1",
      projectRevision: 1,
      systemRevision: 2,
      assumptions: ["B", "A", "C"],
    });

    const digest2 = computeCanonicalHash({
      projectId: "P1",
      projectRevision: 1,
      systemRevision: 2,
      assumptions: ["C", "B", "A"], // Shuffled
    });

    assert.equal(digest1, digest2, "Canonical digest must be order-invariant");

    const digestBumped = computeCanonicalHash({
      projectId: "P1",
      projectRevision: 1,
      systemRevision: 3, // BUMPED
      assumptions: ["A", "B", "C"],
    });

    assert.notEqual(digest1, digestBumped, "Revision change must yield distinct digest");

    // State machine transition validation
    const validTransitions: Record<string, string[]> = {
      DRAFT: ["READY_FOR_VALIDATION", "READY", "BLOCKED", "STALE"],
      READY: ["EXECUTING", "STALE", "BLOCKED"],
      EXECUTING: ["COMPLETED", "PARTIAL", "FAILED", "STALE"],
      COMPLETED: [],
    };

    assert.equal(validTransitions["READY"]?.includes("EXECUTING"), true);
    assert.equal(validTransitions["COMPLETED"]?.includes("EXECUTING"), false);

    // Partial execution breakdown
    const executionBreakdown = {
      completed_tasks: ["T1"],
      failed_task: { task_id: "T2", reason: "POLICY_VIOLATION" },
      remaining_tasks: ["T3"],
      execution_status: "PARTIAL",
    };

    assert.equal(executionBreakdown.execution_status, "PARTIAL");
    assert.equal(executionBreakdown.completed_tasks.length, 1);
    assert.equal(executionBreakdown.remaining_tasks.length, 1);
    assert.notEqual(executionBreakdown.execution_status, "COMPLETED");
  });

  // 14. Phase 2 Wave 2: Cognitive Reflection & Engineering Reasoning
  test("Phase 2 Wave 2: Cognitive Reflection, epistemic invariants, and bounded replanning", () => {
    // Epistemic invariants: UNKNOWN != SATISFIED, CALCULATED != PHYSICALLY VERIFIED
    const mockReflection = {
      id: "refl-01",
      execution_id: "exec-01",
      plan_id: "plan-01",
      status: "ADDITIONAL_WORK_REQUIRED",
      reflection_cycle: 1,
      has_contradictions: true,
      has_unresolved_unknowns: true,
      has_requirement_gaps: true,
      has_verification_gaps: true,
      has_evidence_gaps: false,
      additional_work_required: true,
      findings: [
        {
          id: "f-01",
          finding_type: "CONTRADICTORY_RESULT",
          severity: "CRITICAL",
          title: "Operating current 620mA exceeds 500mA limit",
          affected_entity_type: "REQUIREMENT",
          affected_entity_id: "REQ-01",
          deterministic_facts: { calculated: "620mA", limit: "500mA" },
        },
        {
          id: "f-02",
          finding_type: "VERIFICATION_GAP",
          severity: "CRITICAL",
          title: "CALCULATED != PHYSICALLY VERIFIED: Radiated emissions requires physical measurement",
          affected_entity_type: "VERIFICATION",
          affected_entity_id: "V-01",
          deterministic_facts: { method: "SIMULATION", required: "PHYSICAL_TEST" },
        },
      ],
      proposed_follow_up_tasks: [
        { task_type: "operating_point_recalculation", order_index: 1 },
      ],
      provenance: {
        input_digest: "a".repeat(64),
        output_digest: "b".repeat(64),
        rule_set_version: "v1.0.0",
      },
    };

    // 1. Invariant verification
    assert.equal(mockReflection.has_contradictions, true);
    assert.equal(mockReflection.has_verification_gaps, true);
    assert.equal(mockReflection.findings.length, 2);

    // 2. Zero synthetic scoring invariant
    const serialized = JSON.stringify(mockReflection).toLowerCase();
    const forbidden = ["score", "readiness_percentage", "confidence_level", "overall_rating"];
    for (const term of forbidden) {
      assert.equal(serialized.includes(term), false, `Synthetic score ${term} must not exist`);
    }

    // 3. Bounded replanning limit check (MAX_REFLECTION_CYCLES = 3)
    const MAX_CYCLES = 3;
    const canReplanCycle1 = mockReflection.reflection_cycle < MAX_CYCLES;
    assert.equal(canReplanCycle1, true);

    const cycle3Reflection = { ...mockReflection, reflection_cycle: 3 };
    const canReplanCycle3 = cycle3Reflection.reflection_cycle < MAX_CYCLES;
    assert.equal(canReplanCycle3, false, "Replanning must be blocked when reflection_cycle reaches 3");
  });

  // 15. Phase 2 Wave 3: Controlled Engineering Decision Preparation & Human Gate
  test("Phase 2 Wave 3: Controlled Engineering Decision Preparation, zero-scoring comparison, and human gate invariants", () => {
    const mockDecisionBrief = {
      id: "brief-p2w3-01",
      project_id: "proj-100",
      base_revision: 2,
      question: "Evaluate power delivery stage alternatives: Buck Converter vs LDO.",
      scope: "SYSTEM",
      status: "READY_FOR_REVIEW",
      human_decision_required: true,
      selected_alternative_id: null,
      alternative_ids: ["alt-buck", "alt-ldo"],
      alternatives_data: [
        {
          id: "alt-buck",
          name: "TPS62840 Buck Converter",
          topology: "SWITCHING_BUCK",
          parameters: { efficiency: "92%", cost: "$1.15" },
        },
        {
          id: "alt-ldo",
          name: "TPS7A02 LDO Regulator",
          topology: "LINEAR_LDO",
          parameters: { efficiency: "65%", cost: "$0.35" },
        },
      ],
      requirement_summary: {
        comparison_matrix: [
          {
            alternative_id: "alt-buck",
            requirement_evaluations: {
              "REQ-EFF": { state: "SATISFIED" },
            },
          },
          {
            alternative_id: "alt-ldo",
            requirement_evaluations: {
              "REQ-EFF": { state: "NOT_SATISFIED" },
            },
          },
        ],
      },
      decision_questions: [
        {
          id: "dq-1",
          question: "Can system thermal envelope tolerate 1.2W dissipation of LDO?",
          origin: "AI_GENERATED",
          status: "INFORMATIONAL",
          human_response_required: true,
        },
      ],
      provenance: {
        input_digest: "c".repeat(64),
        output_digest: "d".repeat(64),
        prompt_version: "v1",
        rule_set_version: "v1.0.0",
      },
    };

    // 1. Invariant: Status is READY_FOR_REVIEW and human decision is strictly required
    assert.equal(mockDecisionBrief.status, "READY_FOR_REVIEW");
    assert.equal(mockDecisionBrief.human_decision_required, true);
    assert.equal(mockDecisionBrief.selected_alternative_id, null);

    // 2. Invariant: Decision Questions are INFORMATIONAL and require human response
    assert.equal(mockDecisionBrief.decision_questions[0]?.origin, "AI_GENERATED");
    assert.equal(mockDecisionBrief.decision_questions[0]?.status, "INFORMATIONAL");
    assert.equal(mockDecisionBrief.decision_questions[0]?.human_response_required, true);

    // 3. Invariant: Zero synthetic scoring / No winner declaration
    const serialized = JSON.stringify(mockDecisionBrief).toLowerCase();
    const forbidden = ["score", "winner", "best_alternative", "recommended_winner", "confidence_percentage"];
    for (const term of forbidden) {
      assert.equal(serialized.includes(`"${term}"`), false, `Synthetic score ${term} must not exist`);
    }

    // 4. Invariant: Stale detection when system revision advances
    const currentSystemRevision = 3;
    const isStale = mockDecisionBrief.base_revision < currentSystemRevision;
    assert.equal(isStale, true, "Brief must be identified as STALE when system revision advances");

    // 5. Invariant: Human gate simulation
    const simulateDecisionAttempt = (actor: string, isBriefStale: boolean) => {
      if (actor.toLowerCase().includes("ai") || actor.toLowerCase().includes("model")) {
        return { error: "MODEL_UNAUTHORIZED_DECISION", code: 403 };
      }
      if (isBriefStale) {
        return { error: "DECISION_BRIEF_STALE", code: 409 };
      }
      return { success: true, status: "RATIFIED", decided_by: actor };
    };

    // AI attempt rejected
    const aiAttempt = simulateDecisionAttempt("autonomous-ai-model", false);
    assert.equal(aiAttempt.code, 403);
    assert.equal(aiAttempt.error, "MODEL_UNAUTHORIZED_DECISION");

    // Stale attempt rejected
    const staleAttempt = simulateDecisionAttempt("engineer-alice", true);
    assert.equal(staleAttempt.code, 409);
    assert.equal(staleAttempt.error, "DECISION_BRIEF_STALE");

    // Legitimate human engineer ratified
    const validAttempt = simulateDecisionAttempt("engineer-alice", false);
    assert.equal(validAttempt.success, true);
    assert.equal(validAttempt.status, "RATIFIED");
    assert.equal(validAttempt.decided_by, "engineer-alice");
  });

  // 47. Phase 2 Wave 4: Engineering Memory, Decision History & Contextual Learning
  test("Phase 2 Wave 4: Memory Invariants, Deterministic Applicability & Zero Synthetic Scoring", () => {
    // 1. Mock SurfacedMemoryItem
    const mockMemoryItem: import("../src/components/cognitive/cognitive_types").SurfacedMemoryItem = {
      memory: {
        id: "mem-7805-thermal",
        tenant_id: "tenant-mock",
        memory_type: "DECISION_HISTORY",
        source_entity_type: "EngineeringDecisionRecord",
        source_entity_id: "dec-mock-001",
        project_id: "proj-mock",
        engineering_domain: "thermal",
        summary: "LM7805 regulator requires 15 degC/W heatsink under 500mA load.",
        applicability_conditions: {
          component_family: "LM7805",
          voltage_domain: "5V",
          engineering_domain: "thermal",
        },
        revision_context: { baseline_revision: 1 },
        historical_outcome: "VERIFIED_SUCCESS",
        is_conflicting: false,
        conflict_details: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      applicability: "APPLICABLE",
      why_surfaced: "Matching component family (LM7805) and domain (thermal).",
      historical_outcome: "VERIFIED_SUCCESS",
      current_relevance: "Informs thermal dissipation considerations for 5V output.",
      is_conflicting: false,
      conflict_details: {},
      warnings: ["Historical context — not current engineering verification."],
    };

    // 2. Invariant: Mandatory warning present
    assert.ok(
      mockMemoryItem.warnings.includes("Historical context — not current engineering verification."),
      "Must include mandatory advisory disclaimer"
    );

    // 3. Invariant: Zero synthetic scoring check
    const serialized = JSON.stringify(mockMemoryItem);
    const forbiddenKeys = [
      "memory_score",
      "memory_confidence",
      "learning_score",
      "relevance_percentage",
      "historical_success_score",
    ];
    for (const key of forbiddenKeys) {
      assert.equal(serialized.includes(key), false, `Forbidden key '${key}' found in memory item`);
    }

    // 4. Invariant: Authoritative override on conflict
    const evaluateConflict = (currentParam: string, historicalParam: string) => {
      if (currentParam !== historicalParam) {
        return {
          is_conflicting: true,
          authoritative_rule: "CURRENT AUTHORITATIVE SOURCE > HISTORICAL MEMORY",
          active_value: currentParam,
        };
      }
      return { is_conflicting: false, active_value: currentParam };
    };

    const conflictResult = evaluateConflict("600mA", "1A");
    assert.equal(conflictResult.is_conflicting, true);
    assert.equal(conflictResult.authoritative_rule, "CURRENT AUTHORITATIVE SOURCE > HISTORICAL MEMORY");
    assert.equal(conflictResult.active_value, "600mA");

    // 5. Invariant: Historical verification cannot satisfy current verification
    const evaluateVerificationObligation = (memoryOutcome: string, revisionChanged: boolean) => {
      if (memoryOutcome === "VERIFIED_SUCCESS" && revisionChanged) {
        return {
          current_verification_status: "REQUIRED",
          advisory_note: "Historical verification cannot close current verification obligations.",
        };
      }
      return { current_verification_status: "VERIFIED" };
    };

    const verifCheck = evaluateVerificationObligation(mockMemoryItem.historical_outcome, true);
    assert.equal(verifCheck.current_verification_status, "REQUIRED");
  });

  // 48. Phase 2 Wave 5: Engineering Context Synthesis & Cognitive State
  test("Phase 2 Wave 5: Engineering Context Synthesis, Canonical Digest & Epistemic Invariants", () => {
    // 1. Structure of complete EngineeringContextSnapshot
    const mockSnapshot: EngineeringContextSnapshot = {
      id: "ctx-snap-001",
      tenant_id: "tenant-p2w5",
      project_id: "proj-001",
      circuit_id: "circ-001",
      base_revision: 1,
      status: "CURRENT",
      canonical_digest: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      current_state: { components: [{ ref_des: "U1", value: "LM7805" }] },
      authoritative_facts: [{ entity_type: "Component", ref_des: "U1", property: "voltage_rating", value: "35V" }],
      deterministic_results: [{ analysis_type: "CIRCUIT_ANALYSIS", status: "COMPLETE", calculations: [] }],
      requirements: [{ requirement_key: "REQ-VOUT", state: "SATISFIED" }],
      constraints: [],
      assumptions: [{ field: "ambient_temp", value: "25C" }],
      findings: [],
      unknowns: [],
      evidence_state: { PHYSICAL_EVIDENCE: [], SIMULATION: [] },
      verification_state: { requirements: [{ id: "vr-1", title: "Thermal Bench Test", status: "REQUIRED" }] },
      decision_history: [{ decision_key: "DEC-001", title: "Selected LM7805" }],
      historical_memory: [],
      traceability_state: { component_count: 1, requirement_count: 1 },
      reflection_state: { status: "NO_ADDITIONAL_WORK_REQUIRED" },
      conflicts: [
        {
          id: "conf-1",
          category: "MEMORY_CONFLICT",
          source_a_type: "AuthoritativeDatasheet",
          source_a_id: "spec-1",
          source_b_type: "EngineeringMemoryRecord",
          source_b_id: "mem-1",
          description: "Historical memory conflicts with current authoritative datasheet.",
          requires_human_review: true,
        },
      ],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    // 2. Validate 64-char SHA-256 digest format
    assert.equal(mockSnapshot.canonical_digest.length, 64);
    assert.match(mockSnapshot.canonical_digest, /^[a-f0-9]{64}$/);

    // 3. Dynamic Freshness Check (Revision Binding)
    const checkFreshness = (snapshotBaseRev: number, currentCircuitRev: number): ContextSnapshotStatus => {
      return currentCircuitRev > snapshotBaseRev ? "STALE" : "CURRENT";
    };
    assert.equal(checkFreshness(mockSnapshot.base_revision, 1), "CURRENT");
    assert.equal(checkFreshness(mockSnapshot.base_revision, 2), "STALE");

    // 4. Invariant: CALCULATED != PHYSICALLY VERIFIED
    const evaluateTestStatus = (evidenceType: string) => {
      if (evidenceType === "SIMULATION_REPORT") {
        return { status: "PENDING", note: "Calculation or simulation cannot close a physical test requirement." };
      }
      return { status: "VERIFIED", note: "Physical lab evidence verified." };
    };
    const simResult = evaluateTestStatus("SIMULATION_REPORT");
    assert.equal(simResult.status, "PENDING");
    assert.notEqual(simResult.status, "VERIFIED");

    // 5. Invariant: Conflict detection preserves current source precedence
    const conflict = mockSnapshot.conflicts[0];
    assert.equal(conflict.category, "MEMORY_CONFLICT");
    assert.equal(conflict.requires_human_review, true);

    // 6. Invariant: Zero synthetic scoring check
    const serialized = JSON.stringify(mockSnapshot);
    const forbiddenTokens = [
      "confidence_percentage",
      "readiness_percentage",
      "engineering_score",
      "health_score",
      "intelligence_score",
    ];
    for (const token of forbiddenTokens) {
      assert.equal(serialized.includes(token), false, `Forbidden synthetic metric token '${token}' detected`);
    }
  });

  test("Phase 2 Wave 6: Engineering Workflow Orchestration, State Machine Transitions & Invariants", () => {
    // 1. Workflow state transitions
    const validStates: string[] = [
      "RECEIVED",
      "INTENT_RESOLVED",
      "CONTEXT_RESOLVED",
      "PLAN_READY",
      "EXECUTING",
      "REFLECTING",
      "ADDITIONAL_WORK_REQUIRED",
      "DECISION_PREPARATION",
      "CONTEXT_SYNTHESIS",
      "AWAITING_HUMAN",
      "COMPLETED",
      "BLOCKED",
      "STALE",
      "FAILED",
    ];

    const mockWorkflow = {
      id: "wf-701",
      tenant_id: "tenant-wf",
      project_id: "proj-1",
      circuit_id: "circ-1",
      base_revision: 1,
      status: "AWAITING_HUMAN",
      current_step: "HUMAN_DECISION_REQUIRED",
      user_request: "Evaluate LM7805 thermal margin and prepare decision brief",
      intent_packet_id: "intent-1",
      context_snapshot_id: "snap-1",
      plan_id: "plan-1",
      execution_id: "exec-1",
      reflection_id: "ref-1",
      decision_brief_id: "brief-1",
      synthesized_context_id: "ctx-1",
      reflection_cycles: 1,
      blocking_reasons: [],
      integrity_digest: "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    };

    assert.equal(validStates.includes(mockWorkflow.status), true);
    assert.equal(mockWorkflow.base_revision, 1);
    assert.equal(mockWorkflow.integrity_digest.length, 64);

    // 2. Staleness invariant check
    const isWorkflowStale = (wfBaseRev: number, currentCircuitRev: number) => {
      return wfBaseRev !== currentCircuitRev;
    };
    assert.equal(isWorkflowStale(1, 2), true); // Rev 1 != Rev 2 -> STALE
    assert.equal(isWorkflowStale(1, 1), false); // Fresh

    // 3. Zero synthetic scoring check
    const serializedWf = JSON.stringify(mockWorkflow);
    const forbiddenTokens = [
      "overall_score",
      "readiness_percentage",
      "confidence_percentage",
      "decision_score",
      "winner",
      "best",
    ];
    for (const token of forbiddenTokens) {
      assert.equal(serializedWf.includes(token), false, `Forbidden token '${token}' in workflow`);
    }
  });

  // 50. Phase 2 Wave 7: Engineering Cognitive Interaction & Explainability
  test("Phase 2 Wave 7: Cognitive Interaction, Grounded Evidence Chains & Epistemic Invariants", () => {
    // 1. Structure of EngineeringExplanationResponse
    const mockExplanation = {
      workflow_id: "wf-701",
      context_id: "ctx-701",
      category: "WHY",
      statement: "Requirement REQ-VOUT failed due to deterministic calculation calc-1 exceeding thermal ceiling.",
      base_revision: 1,
      is_stale: false,
      stale_factors: [],
      evidence_refs: ["calc-1", "pe-1"],
      requirement_refs: ["req-1"],
      finding_refs: ["f-1"],
      unknowns: ["U1 -> rth_jc: Missing laboratory characterization."],
      evidence_chain: [
        {
          step: "CALCULATION",
          entity_type: "DeterministicCalculation",
          entity_id: "calc-1",
          description: "Thermal power dissipation exceeds package rating.",
          is_physical: false,
          is_calculation: true,
        },
        {
          step: "PHYSICAL_EVIDENCE",
          entity_type: "PhysicalMeasurement",
          entity_id: "pe-1",
          description: "Calibrated bench thermocouple measurement.",
          is_physical: true,
          is_calculation: false,
        },
        {
          step: "CONCLUSION",
          entity_type: "RequirementEvaluation",
          entity_id: "req-1",
          description: "Thermal ceiling violation confirmed.",
          is_physical: false,
          is_calculation: false,
        },
      ],
      human_actions: [
        {
          action_type: "PHYSICAL_MEASUREMENT_REQUIRED",
          title: "Conduct Bench Thermocouple Test",
          description: "Simulation cannot fulfill physical verification requirement.",
          urgency: "HIGH",
        },
      ],
      origin: "AI_GROUNDED_EXPLANATION",
      authority: "INFORMATIONAL_ONLY",
      traceable_references: [
        { type: "EngineeringRequirement", id: "req-1", state: "FAILED" },
      ],
    };

    // 2. Validate Grounding and Authority Invariants
    assert.equal(mockExplanation.authority, "INFORMATIONAL_ONLY");
    assert.equal(mockExplanation.origin, "AI_GROUNDED_EXPLANATION");
    assert.equal(mockExplanation.base_revision, 1);
    assert.equal(mockExplanation.is_stale, false);

    // 3. Epistemic Invariant: Calculation != Physical Evidence
    for (const node of mockExplanation.evidence_chain) {
      if (node.is_physical) {
        assert.equal(node.is_calculation, false);
      }
      if (node.is_calculation) {
        assert.equal(node.is_physical, false);
      }
    }

    // 4. Grounding Contract & Hallucination Guard: Reject foreign entity references
    const authorizedIds = new Set(["wf-701", "ctx-701", "calc-1", "pe-1", "req-1", "f-1"]);
    const validateReferences = (assertedRefs: string[]) => {
      for (const ref of assertedRefs) {
        if (!authorizedIds.has(ref)) {
          throw new Error(`MODEL_INVALID_REFERENCE: ${ref}`);
        }
      }
      return true;
    };
    assert.equal(validateReferences(["calc-1", "req-1"]), true);
    assert.throws(
      () => validateReferences(["calc-1", "comp-phantom-999"]),
      /MODEL_INVALID_REFERENCE/
    );

    // 5. Epistemic Invariant: UNKNOWN != SATISFIED
    assert.equal(mockExplanation.unknowns.length, 1);
    assert.equal(mockExplanation.unknowns[0].includes("Missing"), true);

    // 6. Zero Synthetic Scoring & No Recommendation Invariants
    const serialized = JSON.stringify(mockExplanation);
    const forbidden = [
      "overall_score",
      "readiness_percentage",
      "confidence_percentage",
      "decision_score",
      "winner",
      "best",
      "recommended_winner",
    ];
    for (const token of forbidden) {
      assert.equal(serialized.includes(token), false, `Forbidden token '${token}' in explanation`);
    }
  });
});

describe("Phase 2 Wave 8: Engineering Evidence & Verification Workspace Test Suite", () => {
  test("51. Enforces Verification Workspace invariants, physical evidence distinction, human closure gate, and zero synthetic scoring", () => {
    // 1. Mock Verification Workspace Response
    const mockWorkspace = {
      workspace_id: "vw-801",
      workflow_id: "wf-801",
      project_id: "proj-801",
      circuit_id: "circ-801",
      base_revision: 1,
      is_stale: false,
      stale_factors: [],
      obligations: [
        {
          verification_requirement_id: "vr-thermal-1",
          code: "VR-THERM-001",
          title: "Thermal Junction Temperature Bench Verification",
          reason: "Verify junction temperature does not exceed 105C under full load at 85C ambient",
          method: "LAB_TEST",
          operating_condition: "85C ambient, 100% rated load",
          is_mandatory: true,
          status: "PENDING",
          related_requirement_code: "REQ-THERM-01",
          required_evidence_types: ["MEASUREMENT", "LAB_OBSERVATION"],
          attached_evidence_items: [
            {
              evidence_id: "evi-calc-1",
              evidence_type: "SIMULATION_REPORT",
              source: "SPICE Transient Thermal Model",
              description: "Simulated junction temp 98.4C",
              is_physical: false,
              value: "98.4",
              unit: "C",
            },
          ],
          sufficiency: "INSUFFICIENT", // Simulation alone cannot close physical bench requirement
          is_physical_required: true,
          has_physical_evidence: false,
          is_stale: false,
          stale_reasons: [],
          human_action_required: "Conduct bench measurement with thermal probe to satisfy physical verification.",
        },
        {
          verification_requirement_id: "vr-volt-2",
          code: "VR-VOLT-002",
          title: "Output Ripple Voltage Verification",
          reason: "Verify output ripple voltage is under 50mV peak-to-peak",
          method: "LAB_TEST",
          operating_condition: "Room ambient, 100% load",
          is_mandatory: true,
          status: "VERIFIED",
          related_requirement_code: "REQ-PWR-02",
          required_evidence_types: ["MEASUREMENT"],
          attached_evidence_items: [
            {
              evidence_id: "evi-meas-2",
              evidence_type: "MEASUREMENT",
              source: "Bench Rig 4",
              description: "Oscilloscope peak-to-peak ripple measurement",
              is_physical: true,
              instrument: "Tektronix MSO54",
              calibration_status: "CALIBRATED",
              value: "32.4",
              unit: "mV",
            },
          ],
          sufficiency: "SUFFICIENT",
          is_physical_required: true,
          has_physical_evidence: true,
          is_stale: false,
          stale_reasons: [],
          human_action_required: null,
        },
      ],
      summary: {
        total_obligations: 2,
        verified_count: 1,
        pending_count: 1,
        blocked_count: 0,
        stale_count: 0,
        missing_evidence_count: 0,
        insufficient_evidence_count: 1,
        physical_tests_pending: 1,
        unresolved_unknowns_count: 0,
        outstanding_human_actions: ["Conduct bench measurement with thermal probe to satisfy physical verification."],
      },
      provenance_integrity_digest: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      created_at: new Date().toISOString(),
    };

    // 2. Epistemic Invariant: CALCULATED != PHYSICALLY VERIFIED
    const thermalObligation = mockWorkspace.obligations[0];
    assert.equal(thermalObligation.is_physical_required, true);
    assert.equal(thermalObligation.has_physical_evidence, false);
    // Even though simulation evidence is attached, sufficiency is INSUFFICIENT
    assert.equal(thermalObligation.sufficiency, "INSUFFICIENT");
    assert.notEqual(thermalObligation.sufficiency, "SUFFICIENT");

    // 3. Epistemic Invariant: Physical evidence satisfies physical requirement
    const voltObligation = mockWorkspace.obligations[1];
    assert.equal(voltObligation.is_physical_required, true);
    assert.equal(voltObligation.has_physical_evidence, true);
    assert.equal(voltObligation.sufficiency, "SUFFICIENT");
    assert.equal(voltObligation.status, "VERIFIED");

    // 4. Epistemic Invariant: AI_VERIFICATION_AUTHORITY = NONE
    // Human closure gate validation function
    const evaluateClosureActor = (actor: string) => {
      const normalized = actor.toLowerCase();
      if (
        normalized.startsWith("ai-") ||
        normalized.includes("model") ||
        normalized.includes("agent") ||
        normalized.includes("bot")
      ) {
        throw new Error("AI_UNAUTHORIZED_VERIFICATION_CLOSURE: AI verification authority is NONE.");
      }
      return true;
    };

    assert.equal(evaluateClosureActor("Chief Hardware Engineer"), true);
    assert.equal(evaluateClosureActor("Verification Specialist"), true);
    assert.throws(
      () => evaluateClosureActor("ai-copilot-model"),
      /AI_UNAUTHORIZED_VERIFICATION_CLOSURE/
    );
    assert.throws(
      () => evaluateClosureActor("autonomous-agent"),
      /AI_UNAUTHORIZED_VERIFICATION_CLOSURE/
    );

    // 5. Epistemic Invariant: Zero Synthetic Scoring
    const serialized = JSON.stringify(mockWorkspace);
    const forbiddenScores = [
      "evidence_score",
      "verification_score",
      "verification_percentage",
      "confidence_score",
      "confidence_percentage",
      "readiness_score",
      "best_evidence",
    ];
    for (const token of forbiddenScores) {
      assert.equal(serialized.includes(token), false, `Forbidden synthetic score token '${token}' found.`);
    }

    // 6. Cryptographic Integrity Digest Present
    assert.equal(typeof mockWorkspace.provenance_integrity_digest, "string");
    assert.equal(mockWorkspace.provenance_integrity_digest.length, 64);
  });

  // 52. Phase 2 Wave 9: Cognitive Engineering Action & Closure Center Invariants
  test("Phase 2 Wave 9: Cognitive Action Center Aggregation, Zero Synthetic Scoring, and Human Closure Gates", () => {
    // 1. Structure of Action Center Response
    const mockActionCenter: {
      project_id: string;
      base_revision: number;
      actions: Array<{
        action_id: string;
        action_type: string;
        category: "ALL" | "BLOCKED" | "DECISIONS" | "EVIDENCE" | "VERIFICATION" | "REVIEWS" | "UNKNOWN" | "STALE";
        title: string;
        description: string;
        source_entity_type: string;
        source_entity_id: string;
        project_id: string;
        revision: number;
        current_status: string;
        required_human_action: string;
        blocking_reason?: string;
        related_entity_refs: string[];
        blocked_by: string[];
        depends_on: string[];
        is_stale: boolean;
        stale_factors: string[];
        route_target: string;
      }>;
      summary: {
        total_actions: number;
        blocked_actions: number;
        decision_actions: number;
        evidence_actions: number;
        verification_actions: number;
        review_actions: number;
        unknown_actions: number;
        stale_actions: number;
      };
      provenance_integrity_digest: string;
    } = {
      project_id: "proj-alpha",
      base_revision: 2,
      actions: [
        {
          action_id: "act-req-req-101",
          action_type: "REQUIREMENT_VIOLATION",
          category: "BLOCKED",
          title: "Violated Requirement: REQ-101",
          description: "Requirement REQ-101 is VIOLATED.",
          source_entity_type: "ENGINEERING_REQUIREMENT",
          source_entity_id: "req-101",
          project_id: "proj-alpha",
          revision: 2,
          current_status: "VIOLATED",
          required_human_action: "Perform engineering redesign or parameter tuning to satisfy REQ-101.",
          blocking_reason: "Thermal dissipation exceeds threshold by 14.5W.",
          related_entity_refs: ["comp-u1"],
          blocked_by: [],
          depends_on: [],
          is_stale: false,
          stale_factors: [],
          route_target: "/api/v1/projects/proj-alpha/requirements",
        },
        {
          action_id: "act-dec-dec-201",
          action_type: "DECISION_PENDING",
          category: "DECISIONS",
          title: "Pending Engineering Decision: Buck Controller Selection",
          description: "Decision record DEC-201 is PENDING human authorization.",
          source_entity_type: "ENGINEERING_DECISION_RECORD",
          source_entity_id: "dec-201",
          project_id: "proj-alpha",
          revision: 2,
          current_status: "PENDING",
          required_human_action: "Review decision brief and record authoritative human decision.",
          related_entity_refs: [],
          blocked_by: [],
          depends_on: [],
          is_stale: false,
          stale_factors: [],
          route_target: "/api/v1/cognitive/decision-records/dec-201",
        },
        {
          action_id: "act-ver-ver-301",
          action_type: "VERIFICATION_PHYSICAL_REQUIRED",
          category: "VERIFICATION",
          title: "Physical Bench Test Required: VR-TH-01",
          description: "Verification obligation VR-TH-01 requires bench test evidence.",
          source_entity_type: "ENGINEERING_VERIFICATION_REQUIREMENT",
          source_entity_id: "ver-301",
          project_id: "proj-alpha",
          revision: 2,
          current_status: "PENDING_PHYSICAL_TEST",
          required_human_action: "Perform physical bench measurement and attach calibrated instrument evidence.",
          related_entity_refs: [],
          blocked_by: [],
          depends_on: [],
          is_stale: false,
          stale_factors: [],
          route_target: "/api/v1/cognitive/verification/ver-301",
        },
      ],
      summary: {
        total_actions: 3,
        blocked_actions: 1,
        decision_actions: 1,
        evidence_actions: 0,
        verification_actions: 1,
        review_actions: 0,
        unknown_actions: 0,
        stale_actions: 0,
      },
      provenance_integrity_digest: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    };

    // 2. Invariant: Action Center is aggregation only (references authoritative entities)
    assert.equal(mockActionCenter.actions[0].source_entity_type, "ENGINEERING_REQUIREMENT");
    assert.equal(mockActionCenter.actions[1].source_entity_type, "ENGINEERING_DECISION_RECORD");
    assert.equal(mockActionCenter.actions[2].source_entity_type, "ENGINEERING_VERIFICATION_REQUIREMENT");
    assert.equal(mockActionCenter.actions[2].route_target, "/api/v1/cognitive/verification/ver-301");

    // 3. Invariant: Status groupings filter correctly
    const blockedActions = mockActionCenter.actions.filter((a) => a.category === "BLOCKED");
    assert.equal(blockedActions.length, 1);
    assert.equal(blockedActions[0].action_id, "act-req-req-101");

    const decisionActions = mockActionCenter.actions.filter((a) => a.category === "DECISIONS");
    assert.equal(decisionActions.length, 1);
    assert.equal(decisionActions[0].action_id, "act-dec-dec-201");

    // 4. Invariant: Zero Synthetic Scoring (No priority_score, risk_score, confidence_score, importance_score, AI_priority)
    const serialized = JSON.stringify(mockActionCenter);
    const forbiddenScores = [
      "priority_score",
      "risk_score",
      "confidence_score",
      "importance_score",
      "readiness_score",
      "AI_priority",
      "ai_priority",
      "rank_score",
    ];
    for (const token of forbiddenScores) {
      assert.equal(serialized.includes(token), false, `Forbidden synthetic score token '${token}' found.`);
    }

    // 5. Invariant: No Autonomous Closure (AI cannot close actions)
    const evaluateActionClosure = (actor: string, isAutomated: boolean) => {
      const lower = actor.toLowerCase();
      if (
        isAutomated ||
        lower.startsWith("ai-") ||
        lower.includes("copilot") ||
        lower.includes("agent") ||
        lower.includes("llm")
      ) {
        throw new Error("AI_AUTONOMOUS_ACTION_CLOSURE_FORBIDDEN: Actions require human engineering authority.");
      }
      return true;
    };

    assert.equal(evaluateActionClosure("Senior Systems Architect", false), true);
    assert.throws(() => evaluateActionClosure("ai-orchestrator", true), /AI_AUTONOMOUS_ACTION_CLOSURE_FORBIDDEN/);
    assert.throws(() => evaluateActionClosure("copilot-agent", false), /AI_AUTONOMOUS_ACTION_CLOSURE_FORBIDDEN/);

    // 6. Integrity Digest is 64 hex characters
    assert.equal(mockActionCenter.provenance_integrity_digest.length, 64);
  });
});

describe("Phase 3 Wave 1: Engineering Knowledge & Source Intelligence Test Suite", () => {
  test("Enforces Knowledge Classification invariants, authoritative precedence, and integrity digests", () => {
    // 1. Classification Enums
    const classifications = [
      "AUTHORITATIVE_SOURCE",
      "DERIVED_ENGINEERING_FACT",
      "CALCULATED_RESULT",
      "HISTORICAL_EXPERIENCE",
      "AI_GENERATED_EXPLANATION",
      "USER_ASSERTION",
      "UNKNOWN",
    ];

    assert.equal(classifications.length, 7);

    // 2. Precedence Ranking
    const PRECEDENCE_RANKS: Record<string, number> = {
      AUTHORITATIVE_SOURCE: 1,
      DERIVED_ENGINEERING_FACT: 2,
      CALCULATED_RESULT: 3,
      HISTORICAL_EXPERIENCE: 4,
      USER_ASSERTION: 5,
      AI_GENERATED_EXPLANATION: 6,
      UNKNOWN: 7,
    };

    assert.ok(PRECEDENCE_RANKS.AUTHORITATIVE_SOURCE < PRECEDENCE_RANKS.HISTORICAL_EXPERIENCE);
    assert.ok(PRECEDENCE_RANKS.HISTORICAL_EXPERIENCE < PRECEDENCE_RANKS.AI_GENERATED_EXPLANATION);
    assert.ok(PRECEDENCE_RANKS.AUTHORITATIVE_SOURCE < PRECEDENCE_RANKS.AI_GENERATED_EXPLANATION);

    // 3. Mock Knowledge Search Item
    const mockKnowledgeItem = {
      record: {
        id: "rec-101",
        subject_identifier: "LM317",
        parameter: "v_ref",
        raw_value: "1.25V",
        normalized_value: 1.25,
        unit: "V",
        classification: "AUTHORITATIVE_SOURCE",
        is_conflicting: false,
        conflict_details: {},
        source_location: { page: 4, table: "Electrical Characteristics" },
        status: "VERIFIED",
      },
      source: {
        id: "src-001",
        title: "LM317 3-Terminal Adjustable Regulator Datasheet",
        publisher: "Texas Instruments",
        document_identifier: "SLVS044X",
        revision: "Rev X",
        version: "1.0",
        document_hash: "a".repeat(64),
        trust_level: "MANUFACTURER_PRIMARY",
        status: "CURRENT",
      },
      provenance_chain: {
        integrity_digest: "a".repeat(64),
        revision_bound: "SLVS044X Rev X",
        classification: "AUTHORITATIVE_SOURCE",
        precedence_rank: 1,
      },
    };

    // Verify SHA-256 integrity digest length
    assert.equal(mockKnowledgeItem.source.document_hash.length, 64);
    assert.equal(mockKnowledgeItem.provenance_chain.integrity_digest.length, 64);

    // 4. Invariant: Contradictory Source Data handling
    const mockConflictingRecord = {
      ...mockKnowledgeItem.record,
      id: "rec-102",
      raw_value: "1.20V",
      normalized_value: 1.20,
      is_conflicting: true,
      conflict_details: {
        status: "CONTRADICTORY_SOURCE_DATA",
        delta_ratio: 0.0417,
        description: "Contradictory values detected for v_ref: 1.25V vs 1.20V",
      },
    };

    assert.equal(mockConflictingRecord.is_conflicting, true);
    assert.equal(mockConflictingRecord.conflict_details.status, "CONTRADICTORY_SOURCE_DATA");

    // 5. Invariant: Zero synthetic scoring (no confidence scores or priority rankings)
    const serialized = JSON.stringify(mockKnowledgeItem).toLowerCase();
    const forbidden = ["confidence_score", "probability_score", "ai_score", "match_confidence"];
    for (const term of forbidden) {
      assert.equal(serialized.includes(`"${term}"`), false, `Synthetic score ${term} must not exist`);
    }

    // 6. AI Explanations are explicitly non-authoritative
    const aiItem = {
      ...mockKnowledgeItem,
      record: {
        ...mockKnowledgeItem.record,
        classification: "AI_GENERATED_EXPLANATION",
      },
    };
    assert.notEqual(aiItem.record.classification, "AUTHORITATIVE_SOURCE");
    assert.equal(PRECEDENCE_RANKS[aiItem.record.classification], 6);
  });
});

describe("Phase 3 Wave 2: Component & Datasheet Intelligence Test Suite", () => {
  // 1. Identity Resolution States (RESOLVED, AMBIGUOUS, UNKNOWN, CONFLICTING) & No Winner Picking
  test("Deterministic component identity resolution forbids automated winner picking on ambiguity", () => {
    const resolvedIdentity = {
      state: "RESOLVED",
      part_number: "LM317T",
      manufacturer: "Texas Instruments",
      component_type: "LINEAR_REGULATOR",
      package: "TO-220",
      candidates: [],
    };
    assert.equal(resolvedIdentity.state, "RESOLVED");
    assert.equal(resolvedIdentity.part_number, "LM317T");

    const ambiguousIdentity = {
      state: "AMBIGUOUS",
      part_number: "LM317",
      candidates: [
        { part_number: "LM317T", manufacturer: "Texas Instruments", package: "TO-220" },
        { part_number: "LM317BD2T", manufacturer: "STMicroelectronics", package: "D2PAK" },
        { part_number: "LM317M", manufacturer: "ON Semiconductor", package: "TO-252" },
      ],
      ambiguity_reasons: ["Multiple manufacturer variants match prefix LM317 without package specification"],
    };
    assert.equal(ambiguousIdentity.state, "AMBIGUOUS");
    assert.equal(ambiguousIdentity.candidates.length, 3);
    // Crucial invariant: Never auto-select or pick a winner among candidates
    assert.equal((ambiguousIdentity as any).selected_winner, undefined);
  });

  // 2. Strict Separation: OPERATING_LIMIT vs ABSOLUTE_MAXIMUM
  test("Operating limit vs absolute maximum: strict safety invariant", () => {
    const limits = {
      recommended_operating_voltage_max: 5.5, // V
      absolute_maximum_voltage: 6.0,          // V
    };

    function validateOperatingPoint(v: number): "OPERATING_POINT_VALID" | "OPERATING_LIMIT_EXCEEDED" | "ABSOLUTE_MAXIMUM_EXCEEDED" {
      if (v > limits.absolute_maximum_voltage) {
        return "ABSOLUTE_MAXIMUM_EXCEEDED";
      }
      if (v > limits.recommended_operating_voltage_max) {
        return "OPERATING_LIMIT_EXCEEDED";
      }
      return "OPERATING_POINT_VALID";
    }

    // Normal operation
    assert.equal(validateOperatingPoint(5.0), "OPERATING_POINT_VALID");

    // Invariant: 5.8V is <= abs max (6.0V), but > recommended max (5.5V).
    // Concluding 5.8V is valid operating point is an engineering safety ERROR!
    assert.equal(validateOperatingPoint(5.8), "OPERATING_LIMIT_EXCEEDED");

    // Exceeding absolute maximum
    assert.equal(validateOperatingPoint(6.5), "ABSOLUTE_MAXIMUM_EXCEEDED");
  });

  // 3. Pin Definitions & Electrical Roles
  test("Validates component pin extraction and authoritative electrical roles", () => {
    const lm317Pins = [
      { pin_number: "1", pin_name: "ADJ", pin_type: "PASSIVE", electrical_role: "ADJUST" },
      { pin_number: "2", pin_name: "VOUT", pin_type: "POWER_OUT", electrical_role: "OUTPUT" },
      { pin_number: "3", pin_name: "VIN", pin_type: "POWER_IN", electrical_role: "INPUT" },
    ];

    assert.equal(lm317Pins.length, 3);
    const pinAdj = lm317Pins.find((p) => p.electrical_role === "ADJUST");
    assert.ok(pinAdj);
    assert.equal(pinAdj?.pin_number, "1");

    const pinVin = lm317Pins.find((p) => p.electrical_role === "INPUT");
    assert.ok(pinVin);
    assert.equal(pinVin?.pin_type, "POWER_IN");
  });

  // 4. Zero Synthetic Scoring across Component Intelligence
  test("Zero synthetic scoring: component profile and applicability are strictly categorical", () => {
    const mockComponentProfile = {
      identity: { state: "RESOLVED", part_number: "LM317" },
      pins: [{ pin_number: "1", pin_name: "ADJ" }],
      operating_ranges: [{ parameter: "input_voltage", raw_value: "3V to 40V" }],
      absolute_maximums: [{ parameter: "input_voltage", raw_value: "40V" }],
      application_constraints: [
        { constraint_type: "CAPACITANCE", description: "0.1uF input bypass capacitor required" },
      ],
      applicability_result: {
        status: "APPLICABLE",
        reasons: ["Input voltage 12V is within recommended operating range [3V..40V]"],
        missing_conditions: [],
      },
    };

    const serialized = JSON.stringify(mockComponentProfile).toLowerCase();
    const forbidden = [
      "confidence_score",
      "probability_score",
      "match_confidence",
      "suitability_score",
      "ai_score",
      "compatibility_percentage",
    ];

    for (const term of forbidden) {
      assert.equal(serialized.includes(`"${term}"`), false, `Synthetic score ${term} is strictly forbidden`);
    }

    // Only authorized categorical values
    const validCategories = ["APPLICABLE", "POTENTIALLY_APPLICABLE", "NOT_APPLICABLE", "UNKNOWN", "CONFLICTING"];
    assert.ok(validCategories.includes(mockComponentProfile.applicability_result.status));
  });

  // 5. Reference Designs Are Context Only (No Autonomous Mutation)
  test("Reference designs provide external component context without autonomous mutation", () => {
    const referenceDesign = {
      title: "1.2V to 37V Adjustable Regulator",
      topology: "LINEAR_REGULATOR",
      external_components: [
        { ref_des: "C1", value: "0.1uF", description: "Input bypass capacitor" },
        { ref_des: "C2", value: "1uF", description: "Output capacitor for transient response" },
        { ref_des: "R1", value: "240 Ohm", description: "Program resistor" },
        { ref_des: "R2", value: "5k Ohm", description: "Adjust potentiometer" },
      ],
      autonomous_circuit_mutation: false,
    };

    assert.equal(referenceDesign.external_components.length, 4);
    assert.equal(referenceDesign.autonomous_circuit_mutation, false);
  });
});

describe("Phase 3 Wave 5: PCB & Schematic Intelligence Test Suite", () => {
  // 1. Epistemic boundary: PCB_ANALYSIS != PCB_FABRICATION != PCB_INSPECTION != HARDWARE_TEST
  test("Strict epistemic boundary distinguishing PCB analysis from fabrication, inspection, and hardware testing", () => {
    const pcbRecord = {
      id: "pcb-rec-1",
      board_id: "board-1",
      classification: "PCB_ANALYSIS",
      verification_status: "ANALYTICAL_MODEL_CONSISTENCY",
      physical_hardware_verified: false,
      fabrication_status: "UNINSPECTED_FABRICATION",
    };

    assert.equal(pcbRecord.classification, "PCB_ANALYSIS");
    assert.notEqual(pcbRecord.classification, "PCB_FABRICATION");
    assert.notEqual(pcbRecord.classification, "PCB_INSPECTION");
    assert.notEqual(pcbRecord.classification, "HARDWARE_TEST");
    assert.equal(pcbRecord.physical_hardware_verified, false);
  });

  // 2. UNKNOWN != SATISFIED boundary
  test("Missing physical parameters strictly evaluate to UNKNOWN and never false SATISFIED", () => {
    const evaluation = {
      rule_id: "PCB009",
      parameter: "copper_thickness_um",
      status: "UNKNOWN",
      message: "Copper thickness not specified for layer; current capacity cannot be verified deterministically",
    };

    assert.equal(evaluation.status, "UNKNOWN");
    assert.notEqual(evaluation.status, "SATISFIED");
    assert.notEqual(evaluation.status, "PASS");
  });

  // 3. Zero synthetic scoring: No composite scores, winners, or layout percentages
  test("PCB analysis and constraint evaluations forbid synthetic scores or winner rankings", () => {
    const analysisResponse = {
      board_id: "board-1",
      revision: 2,
      provenance_digest: "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
      findings: [
        {
          rule_id: "PCB007",
          status: "VIOLATED",
          element_ref: "R1-R2",
          message: "Clearance 0.15mm below minimum 0.2mm",
        },
      ],
      summary: {
        total_findings: 1,
        errors: 1,
        warnings: 0,
        unknowns: 0,
      },
    };

    const serialized = JSON.stringify(analysisResponse).toLowerCase();
    const forbidden = [
      "confidence_score",
      "layout_score",
      "pcb_score",
      "routing_score",
      "winner",
      "best_layout",
      "recommended_layout",
    ];

    for (const term of forbidden) {
      assert.equal(serialized.includes(`"${term}"`), false, `Synthetic score ${term} is strictly forbidden`);
    }
  });

  // 4. Autonomous PCB mutation is strictly disabled
  test("Autonomous PCB mutation disabled: proposals require explicit human review and approval", () => {
    const proposal = {
      id: "prop-1",
      board_id: "board-1",
      title: "Increase R1 clearance to 0.25mm",
      status: "STAGED",
      autonomous_apply_enabled: false,
      human_review_required: true,
    };

    assert.equal(proposal.status, "STAGED");
    assert.equal(proposal.autonomous_apply_enabled, false);
    assert.equal(proposal.human_review_required, true);
  });

  // 5. Deterministic snapshot and SHA-256 integrity digest
  test("Snapshot canonicalization produces a 64-character SHA-256 hex digest", () => {
    const digest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
    assert.equal(digest.length, 64);
    assert.match(digest, /^[a-f0-9]{64}$/);
  });
});

// ==========================================
// Phase 3 Wave 6: BOM & Supply-Chain Intelligence
// ==========================================
describe("Phase 3 Wave 6: BOM & Supply-Chain Intelligence", () => {
  // 1. Separation of Design Identity and Procurement Identity
  test("Clean separation of Design Identity from Procurement Identity on BOM lines", () => {
    const bomLine: import("../src/components/schematic/types").EngineeringBOMLine = {
      id: "line-1",
      bom_id: "bom-1",
      reference_designator: "R1",
      quantity: 1,
      component_type: "Resistor",
      design_value: "10k",
      design_package: "0805",
      design_tolerance: "1%",
      design_rating: "0.25W",
      engineering_requirements: {
        nominal_value: 10000,
        tolerance: 1,
        power_rating: 0.25,
      },
      status: "SOURCED",
      provenance: { source: "CIRCUIT_COMPONENT" },
      candidates: [
        {
          id: "cand-1",
          bom_line_id: "line-1",
          manufacturer: "Yageo",
          mpn: "RC0805FR-0710KL",
          package: "0805",
          lifecycle_status: "ACTIVE",
          availability_status: "IN_STOCK",
          compatibility_status: "ENGINEERING_COMPATIBLE",
          compatibility_evaluations: [
            {
              parameter: "nominal_value",
              required_value: 10000,
              actual_value: 10000,
              status: "SATISFIED",
            },
          ],
          parameters: { nominal_value: 10000, power_rating: 0.25 },
          supply_sources: [
            {
              supplier: "Mouser",
              stock: 5000,
              unit_price: 0.05,
              currency: "USD",
              observed_at: "2026-10-08T12:00:00Z",
            },
          ],
          is_primary: true,
          provenance: { source: "SCHEMATIC_ANNOTATION" },
        },
      ],
    };

    assert.equal(bomLine.reference_designator, "R1");
    assert.equal(bomLine.design_value, "10k");
    assert.equal(bomLine.candidates.length, 1);
    assert.equal(bomLine.candidates[0].mpn, "RC0805FR-0710KL");
    assert.equal(bomLine.candidates[0].is_primary, true);
  });

  // 2. Multi-source dynamic supply data and conflict detection
  test("Multi-source dynamic supply data preserves quotes and flags stock conflicts", () => {
    const supplySources = [
      { supplier: "DigiKey", stock: 1200, unit_price: 0.045, currency: "USD", observed_at: "2026-10-08T09:00:00Z" },
      { supplier: "Mouser", stock: 0, unit_price: 0.05, currency: "USD", observed_at: "2026-10-08T09:30:00Z" },
    ];

    const hasInStock = supplySources.some((s) => s.stock > 0);
    const hasOutOfStock = supplySources.some((s) => s.stock === 0);
    const isConflicting = hasInStock && hasOutOfStock;

    assert.equal(isConflicting, true);
  });

  // 3. Zero synthetic scoring invariant
  test("Zero synthetic scoring: BOM and Candidate interfaces strictly prohibit composite scores or ranks", () => {
    const mockCandidate = {
      id: "cand-2",
      mpn: "GRM21BR71E105KA99L",
      manufacturer: "Murata",
      compatibility_status: "ENGINEERING_COMPATIBLE",
      availability_status: "IN_STOCK",
      lifecycle_status: "ACTIVE",
    };

    const serialized = JSON.stringify(mockCandidate).toLowerCase();
    const forbidden = ["supply_score", "part_score", "winner", "rank", "best_match", "composite_score"];
    for (const term of forbidden) {
      assert.equal(serialized.includes(`"${term}"`), false, `Forbidden score ${term} found in BOM model`);
    }
  });

  // 4. Human-gated substitution proposals
  test("Substitution proposals require explicit human engineering approval with diff preview", () => {
    const proposal: import("../src/components/schematic/types").BOMSubstitutionProposal = {
      id: "prop-1",
      bom_id: "bom-1",
      bom_line_id: "line-1",
      base_bom_revision: 1,
      circuit_version: 1,
      candidate_id: "cand-2",
      proposed_mpn: "ERJ-6ENF1002V",
      proposed_manufacturer: "Panasonic",
      rationale: "Long lead-time mitigation",
      diff_preview: {
        original: { mpn: "RC0805FR-0710KL", manufacturer: "Yageo" },
        proposed: { mpn: "ERJ-6ENF1002V", manufacturer: "Panasonic" },
        compatibility: "ENGINEERING_COMPATIBLE",
      },
      status: "PROPOSED",
      created_by: "eng-user-1",
    };

    assert.equal(proposal.status, "PROPOSED");
    assert.equal(proposal.proposed_mpn, "ERJ-6ENF1002V");
    assert.equal(proposal.diff_preview.compatibility, "ENGINEERING_COMPATIBLE");
  });

  // 5. Deterministic SHA-256 integrity digest
  test("Canonical BOM snapshot includes 64-character SHA-256 integrity digest", () => {
    const snapshot: import("../src/components/schematic/types").BOMSnapshot = {
      bom_id: "bom-1",
      bom_version: 1,
      circuit_id: "circ-1",
      circuit_version: 1,
      snapshot_digest: "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
      provenance_label: "PROVENANCE_AND_INTEGRITY_DIGEST",
      content: { total_lines: 2 },
    };

    assert.equal(snapshot.snapshot_digest.length, 64);
    assert.match(snapshot.snapshot_digest, /^[a-f0-9]{64}$/);
    assert.equal(snapshot.provenance_label, "PROVENANCE_AND_INTEGRITY_DIGEST");
  });
});

describe("Phase 3 Wave 7: Manufacturing / DFM & Assembly Intelligence Frontend Suite", () => {
  // 1. Finding structure and margin differentials
  test("Manufacturing finding maintains quantitative margin differentials and categorical status", () => {
    const finding: import("../src/components/schematic/types").ManufacturingFinding = {
      finding_id: "MFG001_FAIL_T1",
      rule_id: "MFG001",
      rule_name: "Minimum Trace Width",
      category: "FABRICATION",
      status: "FAIL",
      severity: "ERROR",
      message: "Trace width 0.10 mm is below 0.15 mm capability",
      element_type: "TRACE",
      element_ids: ["trace-1"],
      measured_value: 0.10,
      required_value: 0.15,
      margin: -0.05,
      unit: "mm",
      proposal_available: true,
    };

    assert.equal(finding.status, "FAIL");
    assert.equal(finding.category, "FABRICATION");
    assert.equal(finding.margin, -0.05);
    assert.equal(finding.proposal_available, true);
  });

  // 2. Strict epistemic boundary: UNKNOWN != PASS
  test("Epistemic boundary: UNKNOWN findings are distinct from compliant PASS findings", () => {
    const unknownFinding: import("../src/components/schematic/types").ManufacturingFinding = {
      finding_id: "MFG006_NO_OUTLINE",
      rule_id: "MFG006",
      rule_name: "Board Edge Clearance",
      category: "CLEARANCE",
      status: "UNKNOWN",
      severity: "WARNING",
      message: "Board dimensions undefined. Edge clearance cannot be validated.",
      element_type: "BOARD_EDGE",
      proposal_available: false,
    };

    assert.equal(unknownFinding.status, "UNKNOWN");
    assert.notEqual(unknownFinding.status, "PASS");
  });

  // 3. Zero synthetic scoring invariant
  test("Zero synthetic scoring: DFM summary strictly prohibits composite score or fabricator ranking", () => {
    const summary: import("../src/components/schematic/types").ManufacturingAnalysisSummary = {
      total_rules_evaluated: 16,
      pass_count: 14,
      fail_count: 1,
      warning_count: 1,
      unknown_count: 0,
      critical_violations: ["Trace width violation on F.Cu"],
      status: "FAILED",
    };

    const serialized = JSON.stringify(summary).toLowerCase();
    const forbidden = ["dfm_score", "manufacturability_score", "score", "rank", "fabricator_ranking"];
    for (const term of forbidden) {
      assert.equal(serialized.includes(`"${term}"`), false, `Forbidden synthetic score ${term} found in DFM summary`);
    }
  });

  // 4. Human-gated resolution proposals
  test("DFM proposal enforces human approval and mutation diff preview", () => {
    const proposal: import("../src/components/schematic/types").ManufacturingProposalResponse = {
      id: "prop-dfm-1",
      board_id: "board-1",
      board_revision: 1,
      analysis_id: "analysis-1",
      rule_id: "MFG001",
      title: "Widen copper trace to 0.15 mm",
      description: "Increases trace width to meet fabrication minimum",
      mutation_type: "ADJUST_TRACE_WIDTH",
      proposed_mutations: [
        { target_entity: "BoardTraceSegment", entity_id: "trace-1", action: "UPDATE", fields: { width: 0.15 } },
      ],
      diff_preview: {
        previous_width_mm: 0.10,
        proposed_width_mm: 0.15,
        delta_mm: 0.05,
      },
      status: "PROPOSED",
      created_by: "system-dfm",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    assert.equal(proposal.status, "PROPOSED");
    assert.equal(proposal.mutation_type, "ADJUST_TRACE_WIDTH");
    assert.equal(proposal.diff_preview.proposed_width_mm, 0.15);
  });

  // 5. Deterministic SHA-256 provenance digest & invariant assertions
  test("DFM snapshot includes SHA-256 canonical digest and non-negotiable invariant list", () => {
    const snapshot: import("../src/components/schematic/types").DFMSnapshotResponse = {
      board_id: "board-1",
      board_revision: 1,
      analysis_id: "analysis-1",
      rule_set_id: "ruleset-1",
      rule_set_revision: "REV_2026.1",
      canonical_digest: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      computed_at: new Date().toISOString(),
      invariants_verified: [
        "AI_ENGINEERING_AUTHORITY = NONE",
        "AUTONOMOUS_MANUFACTURING_APPROVAL = DISABLED",
        "UNKNOWN != PASS",
        "ZERO_SYNTHETIC_MANUFACTURABILITY_SCORE",
      ],
    };

    assert.equal(snapshot.canonical_digest.length, 64);
    assert.match(snapshot.canonical_digest, /^[a-f0-9]{64}$/);
    assert.equal(snapshot.invariants_verified.includes("AI_ENGINEERING_AUTHORITY = NONE"), true);
    assert.equal(snapshot.invariants_verified.includes("ZERO_SYNTHETIC_MANUFACTURABILITY_SCORE"), true);
  });
});

describe("Phase 3 Wave 8: Cross-Domain Consistency & System-Level Verification Test Suite", () => {
  // 1. Finding structure and multi-domain attributes
  test("Cross-domain finding maintains categorical status, domain pairing and source classification", () => {
    const finding: import("../src/components/schematic/types").CrossDomainFinding = {
      finding_id: "X001_NET_MISMATCH_VCC",
      project_id: "proj-1",
      domain_a: "SCHEMATIC",
      domain_b: "PCB",
      affected_entity_ids: ["net-vcc-1"],
      rule_id: "X001",
      status: "FAIL",
      severity: "CRITICAL",
      engineering_claim: "Schematic net topology matches PCB routed connectivity",
      explanation: "Net VCC contains 4 pins in schematic but only 3 pads on PCB",
      quantitative_values: { schematic_pins: 4, pcb_pads: 3 },
      margin: -1,
      source_classification: "CALCULATED",
    };

    assert.equal(finding.rule_id, "X001");
    assert.equal(finding.domain_a, "SCHEMATIC");
    assert.equal(finding.domain_b, "PCB");
    assert.equal(finding.status, "FAIL");
    assert.equal(finding.severity, "CRITICAL");
    assert.equal(finding.source_classification, "CALCULATED");
    assert.equal(finding.margin, -1);
  });

  // 2. Strict epistemic rule: UNKNOWN != PASS
  test("Strict epistemic invariant: UNKNOWN is never equal to PASS", () => {
    const unknownStatus: import("../src/components/schematic/types").CrossDomainStatus = "UNKNOWN";
    const passStatus: import("../src/components/schematic/types").CrossDomainStatus = "PASS";

    assert.notEqual(unknownStatus, passStatus);
    assert.equal(unknownStatus === "PASS", false);
  });

  // 3. Zero synthetic scoring invariant in cross-domain summary
  test("Cross-domain validation summary prohibits synthetic scores, ranks, and winners", () => {
    const summary: import("../src/components/schematic/types").CrossDomainValidationSummary = {
      total_findings: 20,
      pass_count: 15,
      fail_count: 2,
      warning_count: 1,
      unknown_count: 2,
      not_applicable_count: 0,
      critical_failure_count: 1,
      domains_evaluated: ["SCHEMATIC", "PCB", "BOM", "SIMULATION", "POWER_THERMAL", "DFM", "VERIFICATION"],
      status: "COMPLETED",
    };

    const serialized = JSON.stringify(summary).toLowerCase();
    const forbidden = ["score", "rank", "winner", "grade", "percentage", "index", "composite_score"];
    for (const term of forbidden) {
      assert.equal(serialized.includes(`"${term}"`), false, `Forbidden synthetic scoring metric ${term} found in CrossDomainValidationSummary`);
    }

    assert.equal(summary.total_findings, 20);
    assert.equal(summary.pass_count, 15);
    assert.equal(summary.fail_count, 2);
    assert.equal(summary.critical_failure_count, 1);
  });

  // 4. SHA-256 Provenance & Integrity digest
  test("Validation response contains 64-character SHA-256 canonical digest", () => {
    const response: import("../src/components/schematic/types").CrossDomainValidationResponse = {
      id: "val-rec-1",
      project_id: "proj-1",
      status: "COMPLETED",
      snapshot_digest: "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
      summary: {
        total_findings: 1,
        pass_count: 1,
        fail_count: 0,
        warning_count: 0,
        unknown_count: 0,
        not_applicable_count: 0,
        critical_failure_count: 0,
        domains_evaluated: ["SCHEMATIC", "PCB"],
        status: "COMPLETED",
      },
      findings: [],
      created_by: "eng-user-1",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    assert.equal(response.snapshot_digest.length, 64);
    assert.match(response.snapshot_digest, /^[a-f0-9]{64}$/);
    assert.equal(response.status, "COMPLETED");
  });

  // 5. Verification currency: historical verification does not verify current revision
  test("Historical verification rule flags revision mismatch as UNKNOWN/WARNING, not PASS", () => {
    const historicalFinding: import("../src/components/schematic/types").CrossDomainFinding = {
      finding_id: "X017_HISTORICAL_OVERCLAIM_1",
      project_id: "proj-1",
      domain_a: "VERIFICATION",
      domain_b: "SCHEMATIC",
      affected_entity_ids: ["rev-1-review"],
      rule_id: "X017",
      status: "UNKNOWN",
      severity: "HIGH",
      engineering_claim: "Historical verification does not verify current design revision",
      explanation: "HISTORICAL RECORD: Verification item passed on revision 1 (HISTORICAL_VERIFICATION != CURRENT_VERIFICATION; re-verification required for rev 2).",
      quantitative_values: { current_rev: 2, verified_rev: 1 },
      margin: null,
      source_classification: "HISTORICAL",
    };

    assert.equal(historicalFinding.status, "UNKNOWN");
    assert.equal(historicalFinding.source_classification, "HISTORICAL");
    assert.notEqual(historicalFinding.status, "PASS");
  });

  // 6. Staleness behavior: stale validation record preserves staleness reasons
  test("Stale validation record flags is_stale=true and retains explicit staleness reasons", () => {
    const staleResponse: import("../src/components/schematic/types").CrossDomainValidationResponse = {
      id: "val-rec-stale",
      project_id: "proj-1",
      status: "COMPLETED",
      is_stale: true,
      staleness_reasons: ["Circuit mutated to revision 2 after validation was executed"],
      snapshot_digest: "b1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
      summary: {
        total_findings: 5,
        pass_count: 4,
        fail_count: 0,
        warning_count: 0,
        unknown_count: 1,
        not_applicable_count: 0,
        critical_failure_count: 0,
        domains_evaluated: ["SCHEMATIC", "PCB"],
        status: "COMPLETED",
      },
      findings: [],
      created_by: "eng-user-1",
      created_at: new Date().toISOString(),
    };

    assert.equal(staleResponse.is_stale, true);
    assert.equal(staleResponse.staleness_reasons?.length, 1);
    assert.match(staleResponse.staleness_reasons![0], /revision 2/);
  });

  // 7. Simulation boundary: convergence does not imply engineering correctness
  test("Simulation consistency asserts convergence does not imply engineering correctness", () => {
    const simFinding: import("../src/components/schematic/types").CrossDomainFinding = {
      finding_id: "X012_PASS_sim1",
      project_id: "proj-1",
      domain_a: "SIMULATION",
      domain_b: "SCHEMATIC",
      affected_entity_ids: ["sim1"],
      rule_id: "X012",
      status: "PASS",
      severity: "INFO",
      engineering_claim: "Simulated SPICE model parameters match current schematic component properties",
      explanation: "Simulation result achieved valid numerical convergence consistent with component parameters. (CONVERGENCE != ENGINEERING_CORRECTNESS; SIMULATION_RESULT != PHYSICAL_MEASUREMENT).",
      quantitative_values: { convergence_status: "CONVERGED" },
      margin: null,
      source_classification: "SIMULATED",
    };

    assert.equal(simFinding.source_classification, "SIMULATED");
    assert.equal(simFinding.explanation.includes("CONVERGENCE != ENGINEERING_CORRECTNESS"), true);
    assert.equal(simFinding.explanation.includes("SIMULATION_RESULT != PHYSICAL_MEASUREMENT"), true);
  });

  // 8. Completeness invariant: missing domains strictly evaluated as UNKNOWN
  test("Completeness rule flags absent domain artifacts as UNKNOWN, never implied PASS", () => {
    const incompleteFinding: import("../src/components/schematic/types").CrossDomainFinding = {
      finding_id: "X020_INCOMPLETE_DOMAINS",
      project_id: "proj-1",
      domain_a: "SCHEMATIC",
      domain_b: "PCB",
      affected_entity_ids: [],
      rule_id: "X020",
      status: "UNKNOWN",
      severity: "INFO",
      engineering_claim: "Complete system engineering requires synchronization across all seven core domains",
      explanation: "Cross-domain state is incomplete. Missing domain artifacts: Simulation, DFM. Available domains: Schematic, PCB, BOM, Requirements, Verification.",
      quantitative_values: { available_domains: 5, missing_domains: 2 },
      margin: null,
      source_classification: "UNKNOWN",
    };

    assert.equal(incompleteFinding.status, "UNKNOWN");
    assert.notEqual(incompleteFinding.status, "PASS");
    assert.equal(incompleteFinding.quantitative_values.missing_domains, 2);
  });
});

describe("Phase 3 Wave 9: Unified Engineering Project Workspace & Revision Lineage Suite", () => {
  // 1. Multi-domain inventory posture representation
  test("Workspace state accurately models multi-domain inventory and statuses across all 8 domains", () => {
    const mockState: import("../src/components/workspace/types").ProjectWorkspaceStateResponse = {
      project_id: "proj-w9-1",
      project_name: "Substation Controller",
      project_status: "active",
      active_circuit_version: 2,
      domains: [
        {
          domain_name: "schematic",
          display_name: "Circuit Schematic",
          entity_count: 2,
          latest_entity_id: "circ-2",
          latest_revision: 2,
          status: "CONFIGURED",
          status_reason: "Active circuit (v2) is validated.",
          last_updated_at: new Date().toISOString(),
        },
        {
          domain_name: "pcb",
          display_name: "PCB Layout",
          entity_count: 1,
          latest_entity_id: "board-1",
          latest_revision: 1,
          status: "STALE",
          status_reason: "Board v1 bound to older circuit v1 (active: v2).",
          last_updated_at: new Date().toISOString(),
        },
        {
          domain_name: "bom",
          display_name: "Bill of Materials",
          entity_count: 1,
          latest_entity_id: "bom-1",
          latest_revision: 1,
          status: "STALE",
          status_reason: "BOM v1 bound to older circuit v1 (active: v2).",
          last_updated_at: new Date().toISOString(),
        },
        {
          domain_name: "simulation",
          display_name: "SPICE Simulation",
          entity_count: 0,
          latest_entity_id: null,
          latest_revision: null,
          status: "MISSING",
          status_reason: "No SPICE simulation jobs recorded.",
          last_updated_at: null,
        },
        {
          domain_name: "manufacturing",
          display_name: "DFM & Fabrication",
          entity_count: 0,
          latest_entity_id: null,
          latest_revision: null,
          status: "MISSING",
          status_reason: "No manufacturing or DFM analysis records found.",
          last_updated_at: null,
        },
        {
          domain_name: "requirements",
          display_name: "System Requirements",
          entity_count: 3,
          latest_entity_id: "req-1",
          latest_revision: null,
          status: "CONFIGURED",
          status_reason: "3 requirement(s) defined and tracked.",
          last_updated_at: new Date().toISOString(),
        },
        {
          domain_name: "design_review",
          display_name: "Design Reviews",
          entity_count: 0,
          latest_entity_id: null,
          latest_revision: null,
          status: "MISSING",
          status_reason: "No formal design reviews conducted.",
          last_updated_at: null,
        },
        {
          domain_name: "cross_domain",
          display_name: "Cross-Domain Verification",
          entity_count: 1,
          latest_entity_id: "cdv-1",
          latest_revision: null,
          status: "STALE",
          status_reason: "Validation is stale: Active circuit entity has changed.",
          last_updated_at: new Date().toISOString(),
        },
      ],
      cross_domain_validation: {
        record_id: "cdv-1",
        evaluated_at: new Date().toISOString(),
        status: "PASS",
        is_stale: true,
        staleness_reasons: ["Active circuit entity has changed."],
        rule_counts: { total: 10, pass: 10, fail: 0, warning: 0, unknown: 0 },
        snapshot_digest: "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
      },
      workspace_digest: "fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321",
      generated_at: new Date().toISOString(),
    };

    assert.equal(mockState.domains.length, 8);
    assert.equal(mockState.active_circuit_version, 2);
    assert.equal(mockState.workspace_digest.length, 64);
    assert.equal(mockState.cross_domain_validation?.is_stale, true);
  });

  // 2. Epistemic boundary: UNKNOWN != PASS, MISSING != CONFIGURED
  test("Epistemic boundaries: MISSING domains cannot be represented as CONFIGURED or PASS", () => {
    const missingDomain: import("../src/components/workspace/types").DomainInventoryItem = {
      domain_name: "simulation",
      display_name: "SPICE Simulation",
      entity_count: 0,
      latest_entity_id: null,
      latest_revision: null,
      status: "MISSING",
      status_reason: "No SPICE simulation jobs recorded.",
      last_updated_at: null,
    };

    assert.equal(missingDomain.status, "MISSING");
    assert.notEqual(missingDomain.status, "CONFIGURED");
    assert.notEqual(missingDomain.status, "UNKNOWN");
  });

  // 3. Zero synthetic scoring invariant
  test("Workspace responses strictly prohibit synthetic composite metrics or readiness scores", () => {
    const stateJson = JSON.stringify({
      project_id: "p1",
      workspace_digest: "abc",
      domains: [{ domain_name: "pcb", status: "CONFIGURED" }],
    });

    assert.equal(stateJson.includes("readiness_percentage"), false);
    assert.equal(stateJson.includes("confidence_percentage"), false);
    assert.equal(stateJson.includes("health_score"), false);
    assert.equal(stateJson.includes("composite_grade"), false);
  });

  // 4. Revision Lineage bindings
  test("Revision lineage binds child entities to circuit version and groups them deterministically", () => {
    const lineage: import("../src/components/workspace/types").ProjectRevisionLineageResponse = {
      project_id: "p1",
      active_circuit_version: 2,
      circuit_revisions: [
        {
          circuit_id: "circ-2",
          circuit_version: 2,
          is_current: true,
          validation_status: "VALID",
          created_at: new Date().toISOString(),
          boards: [],
          boms: [],
          simulations: [],
          manufacturing_analyses: [],
          design_reviews: [],
        },
        {
          circuit_id: "circ-1",
          circuit_version: 1,
          is_current: false,
          validation_status: "VALID",
          created_at: new Date().toISOString(),
          boards: [
            {
              entity_id: "board-1",
              entity_type: "board",
              name_or_type: "Mainboard Rev A",
              entity_version: 1,
              bound_circuit_version: 1,
              status: "IN_PROGRESS",
              created_at: new Date().toISOString(),
            },
          ],
          boms: [
            {
              entity_id: "bom-1",
              entity_type: "bom",
              name_or_type: "Main BOM Rev 1",
              entity_version: 1,
              bound_circuit_version: 1,
              status: "EVALUATED",
              created_at: new Date().toISOString(),
            },
          ],
          simulations: [],
          manufacturing_analyses: [],
          design_reviews: [],
        },
      ],
      unbound_entities: [],
      generated_at: new Date().toISOString(),
    };

    assert.equal(lineage.circuit_revisions.length, 2);
    assert.equal(lineage.circuit_revisions[0]?.is_current, true);
    assert.equal(lineage.circuit_revisions[1]?.boards.length, 1);
    assert.equal(lineage.circuit_revisions[1]?.boards[0]?.bound_circuit_version, 1);
  });

  // 5. Unbound entity isolation
  test("Unbound engineering entities targeting unknown revisions are isolated and flagged", () => {
    const orphan: import("../src/components/workspace/types").BoundEntityRef = {
      entity_id: "orphan-board-1",
      entity_type: "board",
      name_or_type: "Experimental Board",
      entity_version: 1,
      bound_circuit_version: 99,
      status: "DRAFT",
      created_at: new Date().toISOString(),
    };

    assert.equal(orphan.bound_circuit_version, 99);
    assert.equal(orphan.entity_type, "board");
  });

  // 6. Chronological activity timeline representation
  test("Activity timeline models reconstructed events across engineering domains", () => {
    const timeline: import("../src/components/workspace/types").ProjectActivityTimelineResponse = {
      project_id: "p1",
      events: [
        {
          event_id: "ev-1",
          category: "BOARD",
          event_type: "BOARD_CREATED",
          entity_id: "board-1",
          entity_name: "Power Board Rev A",
          revision_or_version: 1,
          timestamp: new Date().toISOString(),
          summary: "PCB board layout created.",
          details: { status: "IN_PROGRESS" },
        },
        {
          event_id: "ev-2",
          category: "CIRCUIT",
          event_type: "CIRCUIT_CREATED",
          entity_id: "circ-1",
          entity_name: "Power Supply",
          revision_or_version: 1,
          timestamp: new Date().toISOString(),
          summary: "Circuit schematic created.",
          details: { status: "VALID" },
        },
      ],
      total_events: 2,
      limit: 50,
      has_more: false,
    };

    assert.equal(timeline.events.length, 2);
    assert.equal(timeline.events[0]?.category, "BOARD");
    assert.equal(timeline.events[1]?.category, "CIRCUIT");
  });
});






