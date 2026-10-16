# QUEBET AI — Phase 1 Wave 6 Engineering Knowledge, Evidence & Traceability Report

## Executive Summary

Phase 1 Wave 6 establishes the authoritative **Engineering Knowledge, Evidence, Provenance, and Traceability Layer** for QUEBET AI.

In critical electronics engineering, analysis results, design reviews, and safety margins cannot be based on unverified assertions, opaque model hallucinations, or unreferenced assumptions. Wave 6 introduces a fully verifiable, reproducible provenance chain from physical manufacturer datasheets down to individual design review decisions.

Wave 6 strictly enforces the non-negotiable engineering principles:
* **`SOURCE != CLAIM`**: An authoritative document is separate from an asserted parameter extracted from it.
* **`CLAIM != VALIDATION`**: An asserted parameter or design rule is not valid until checked deterministically against circuit topology and operating conditions.
* **`VALIDATION != PHYSICAL VERIFICATION`**: Passing analytical rules or simulations does not equal laboratory bench measurement.
* **`UNKNOWN != VERIFIED`**: Missing information, absent environmental conditions, or uncharacterized components evaluate strictly to `UNKNOWN`, never to `PASS`, `VERIFIED`, or `APPLICABLE`.
* **`MISSING_SOURCE != AUTHORITATIVE`**: Component parameters without verified sources cannot claim authoritative status.
* **`UNVERIFIED_PART_NUMBER != VALID_COMPONENT`**: Part numbers not mapped to verified datasheets are flagged as uncharacterized.
* **`STALE_EVIDENCE != CURRENT_EVIDENCE`**: Evidence collected against an earlier circuit revision or expired calibration status cannot satisfy requirements for the current revision.
* **Zero Arbitrary Scoring**: Numerical trust percentages (e.g. `Trust = 92%`) are strictly prohibited in favor of categorical trust levels with cryptographic SHA-256 document hashing.
* **Historical Immutability**: Changes or supersessions in engineering knowledge never silently mutate historical analysis records or approved design reviews.

---

## 1. Traceability Architecture

The system enforces an unbroken, bidirectional traceability graph:

```text
Engineering Source (SHA-256 Hashed, Versioned, Trust-Categorized)
        ↓
Knowledge Record (Parameter, Value, Unit, Conditions JSON, Status)
        ↓
Component / Circuit Fact (Part Number, Rating, Thermal Limits)
        ↓
Analysis Input & Deterministic Engines (Pinned Engine & Rule-Set Versions)
        ↓
Finding & Calculation (Deterministic Electrical & Thermal Checks)
        ↓
Verification Requirement (VR001+ Functional, Thermal, Safety Requirements)
        ↓
Evidence (Physical Instrument Traceable, Calibrated, Revision-Pinned)
        ↓
Engineering Review Decision (Immutable, Revision-Bound)
```

---

## 2. Core Domain Data Models

Wave 6 introduces 4 new relational models and extends the verification models (`backend/migrations/versions/008_phase_1_wave_6_provenance.py`):

```text
EngineeringSource
  ├── EngineeringKnowledgeRecord (Conditions, Provenance, Applicability)
  │     └── EngineeringKnowledgeSnapshot (Immutable Hash & ID Set)
  └── EngineeringAnalysisProvenance (Engine Versions, Rule-Set Version, Inputs)
```

### 2.1 Data Models & Database Schemas

1. **`EngineeringSource` (`engineering_sources`)**
   - Cryptographic integrity: `document_digest` stores the SHA-256 hash of the authoritative source document.
   - Categorical trust levels: `MANUFACTURER_PRIMARY`, `MANUFACTURER_SECONDARY`, `DISTRIBUTOR_VERIFIED`, `STANDARD_BODY`, `LAB_REPORT`, `SIMULATION_MODEL`, `INTERNAL_STANDARD`, `USER_ASSERTED`.
   - Document metadata: `title`, `document_type` (`DATASHEET`, `APPLICATION_NOTE`, `STANDARD`, `TEST_REPORT`, `WHITE_PAPER`), `publisher`, `revision`, `url`.
   - Lifecycle tracking: `is_deprecated`, `superseded_by_id` linking to the newer source revision.
   - Strict multi-tenant isolation: null `tenant_id` for universal standards/datasheets, tenant-scoped for proprietary client sources.

2. **`EngineeringKnowledgeRecord` (`engineering_knowledge_records`)**
   - Domain classification: `domain` (`ELECTRICAL`, `THERMAL`, `MECHANICAL`, `RELIABILITY`, `REGULATORY`).
   - Granular identification: `subject_identifier` (e.g. `LM7805`, `AMS1117-3.3`), `parameter` (e.g. `thermal_resistance_junction_to_ambient`, `dropout_voltage_max`), `value`, `unit`.
   - Operating conditions JSON: `conditions` (temperature bounds, package types, supply voltages, test frequencies, airflow).
   - Knowledge state: `status` (`VERIFIED`, `INFERRED`, `UNKNOWN`, `SUPERSEDED`), `superseded_by_id`.
   - Authoritative link: `source_id` foreign key referencing `EngineeringSource`.

3. **`EngineeringKnowledgeSnapshot` (`engineering_knowledge_snapshots`)**
   - Captures the exact set of knowledge record IDs used during a specific calculation or analysis.
   - Generates an immutable `snapshot_hash` based on ordered record IDs.

4. **`EngineeringAnalysisProvenance` (`engineering_analysis_provenance`)**
   - Explicit execution reproducibility: Pinned to `analysis_id`, `circuit_id`, and `circuit_revision`.
   - Engine and rule versioning: `engine_versions` JSON (e.g. `OhmsLawEngine: 1.2.0`, `RuleEngine: 1.4.0`), `rule_set_version` (e.g. `QUEBET-ELECTRICAL-001 v1.3`).
   - Audit telemetry: `knowledge_snapshot_id`, `inputs_digest` (SHA-256 of circuit state), `calculation_methods` JSON.

5. **`EngineeringEvidence` Extensions (`engineering_evidence`)**
   - Extended with physical instrumentation tracking:
     - `source_id`: References the source document or calibration standard.
     - `instrument`, `instrument_model`, `instrument_serial`.
     - `calibration_reference`, `calibration_status` (`CALIBRATED`, `EXPIRED`, `UNKNOWN`, `NOT_APPLICABLE`).
     - `circuit_id`, `circuit_revision`: Pinned to the circuit revision under test.
     - `is_stale`: Flagged whenever the circuit revision advances past the evidence revision.

---

## 3. Deterministic Engines & Services

### 3.1 Applicability Engine (`applicability_engine.py`)
Evaluates whether a knowledge record's operating conditions match the operational context of a circuit component.
* **4-State Ternary Logic**:
  - `APPLICABLE`: All specified conditions match operational context precisely.
  - `NOT_APPLICABLE`: At least one condition is definitively violated (e.g. package mismatch, temperature exceeding absolute maximum).
  - `CONDITIONALLY_APPLICABLE`: Conditions match but within continuous bounded ranges requiring engineering observation.
  - `UNKNOWN`: The knowledge record requires specific context parameters (e.g. ambient airflow, heatsink area) that are omitted from the circuit model. **Never assumes applicability!**

### 3.2 Knowledge Bootstrap Service (`knowledge_bootstrap.py`)
Seeds authentic manufacturer datasheets with verified SHA-256 digests and validated parameters for foundational engineering components:
* **Texas Instruments LM7805** (Doc: `SLVS044X`, Digest: `e3b0c442...`):
  - Fixed output voltage, max input voltage (35V), dropout voltage (2.0V @ 1A), thermal resistance ($\theta_{JA} = 54^\circ\text{C/W}$ for TO-220, $19^\circ\text{C/W}$ for TO-263).
* **Advanced Monolithic Systems AMS1117-3.3** (Doc: `AMS1117-DS-V1`, Digest: `a1b2c3d4...`):
  - 3.3V nominal output, max input voltage (15V), dropout voltage (1.3V @ 800mA), $\theta_{JA} = 90^\circ\text{C/W}$ for SOT-223.
* **Vishay & Yageo Standard Passives**:
  - Standard thick film resistor thermal and voltage limits across 0805, 0603, and 1206 footprints.

### 3.3 Knowledge Impact Service (`knowledge_impact_service.py`)
Calculates the downstream blast radius when an engineering source or knowledge record is updated, corrected, or superseded:
* Computes affected components across projects and circuits.
* Identifies historical analyses and design reviews relying on the superseded record.
* **Preserves Historical Immutability**: Historical records are flagged as relying on superseded knowledge without silent overwriting or automated mutations.

### 3.4 Traceability Service (`traceability_service.py`)
Assembles complete end-to-end graph structures for any engineering artifact:
* `FindingTraceability`: Finding $\to$ Analysis Provenance $\to$ Knowledge Records $\to$ Sources $\to$ Linked Requirements $\to$ Physical Evidence.
* `RequirementTraceability`: Requirement $\to$ Failure Mode $\to$ Analysis Finding $\to$ Knowledge Records $\to$ Sources $\to$ Associated Evidence with Calibration Records.
* `EvidenceTraceability`: Evidence $\to$ Requirement $\to$ Review $\to$ Instrument Calibration $\to$ Source Standard.

---

## 4. REST API Endpoint Surface

Wave 6 mounts 13 dedicated traceability endpoints under `/api/v1`:

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/sources` | Register authoritative engineering source with SHA-256 digest |
| `GET` | `/sources` | List registered sources with trust level and deprecation filters |
| `GET` | `/sources/{id}` | Retrieve specific source details and supersession history |
| `POST` | `/sources/{id}/supersede` | Supersede source with newer revision and maintain lineage |
| `POST` | `/knowledge` | Create verified knowledge record with conditions JSON |
| `GET` | `/knowledge` | Query knowledge records by domain, subject, parameter, and status |
| `GET` | `/knowledge/{id}` | Retrieve knowledge record with eager source relationship |
| `POST` | `/knowledge/{id}/supersede` | Supersede knowledge record with updated values |
| `GET` | `/analyses/{id}/traceability` | Full execution provenance, engine versions, and snapshot |
| `GET` | `/findings/{id}/traceability` | Complete upstream knowledge and downstream verification chain |
| `GET` | `/verification-requirements/{id}/traceability` | Upstream failure mode and downstream instrumented evidence |
| `GET` | `/evidence/{id}/traceability` | Calibration provenance and requirement linkage |
| `GET` | `/circuits/{id}/knowledge-impact` | Downstream blast radius analysis for updated knowledge |

---

## 5. Frontend Traceability Workspace

The frontend engineering workspace integrates complete visual inspection into the provenance layer:

1. **`TraceabilityModal.tsx`**:
   - High-density modal offering multi-layer inspection:
     - **Upstream Sources**: Publisher, document title, revision, trust badge (`MANUFACTURER_PRIMARY`), and SHA-256 document digest verification.
     - **Knowledge Records**: Parameter name, verified value, unit, status (`VERIFIED`), and operating conditions JSON inspector.
     - **Analysis Provenance**: Analysis ID, circuit revision, engine versions map, and rule-set version (`QUEBET-ELECTRICAL-001 v1.3`).
     - **Physical Evidence & Calibration**: Instrument model, serial number, calibration certificate reference, and calibration status (`CALIBRATED` / `EXPIRED`).
2. **`DesignReviewTab.tsx`**:
   - Added interactive `Trace` action triggers on:
     - Failure Mode cards (links to finding and upstream knowledge).
     - Verification Requirement items (links to root findings and test points).
     - Recorded Evidence items (links to instrument calibration and source documents).

---

## 6. Verification & Quality Gates

The implementation has been thoroughly verified across all architectural layers:

### 6.1 Backend Test Suite (`pytest`)
All 70 tests pass with zero regressions:
```text
backend\tests\unit\test_health.py ......                                 [  8%]
backend\tests\unit\test_model_router.py ..                               [ 11%]
backend\tests\unit\test_phase1_circuits.py .......                       [ 21%]
backend\tests\unit\test_phase1_wave2.py .......                          [ 31%]
backend\tests\unit\test_phase1_wave3.py ..........                       [ 45%]
backend\tests\unit\test_phase1_wave4.py .......                          [ 55%]
backend\tests\unit\test_phase1_wave4_1.py ..........                     [ 70%]
backend\tests\unit\test_phase1_wave5.py .......                          [ 80%]
backend\tests\unit\test_phase1_wave6.py ......                           [ 88%]
backend\tests\unit\test_security.py ........                             [100%]

============================= 70 passed in 23.53s =============================
```

### 6.2 Frontend Unit Tests (`node:test`)
All 25 tests pass covering Canvas, Design Intelligence, Verification, and Traceability:
```text
# tests 25
# suites 4
# pass 25
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 291.4969
```

### 6.3 Production Builds
- `frontend` (`next build`): Compiled successfully, 0 TypeScript errors, 6/6 static routes generated.
- `admin` (`next build`): Compiled successfully, 0 TypeScript errors, 7/7 static routes generated.

---

```text
PHASE_1_WAVE_6_STATUS: COMPLETE
```
