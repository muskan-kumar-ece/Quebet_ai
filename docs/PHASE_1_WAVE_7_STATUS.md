# QUEBET AI — Phase 1 Wave 7 System-Level Engineering Intelligence & Subsystem Architecture Report

## Executive Summary

Phase 1 Wave 7 establishes the **System-Level Engineering Intelligence and Subsystem Architecture Layer** for QUEBET AI.

Prior to Wave 7, QUEBET AI operated exclusively at the discrete circuit schematic level. Wave 7 elevates the platform to support complete multi-subsystem electronics engineering:
* Decomposing complex electronic products into hierarchical subsystems.
* Formally typing and validating subsystem boundary interfaces (Power, Ground, Analog, Digital, Clock, Data, Control, Communication, RF, Thermal).
* Constructing and validating deterministic Power Distribution Trees with aggregated current loads and voltage domain boundary checking.
* Modeling explicit subsystem dependencies and operating modes.
* Performing deterministic multi-hop failure propagation analysis with physical containment barrier detection (galvanic isolation, protection fuses, thermal cutoffs).
* Calculating architectural change impact and blast radius across dependent subsystems, interfaces, power rails, and verification requirements.
* Ensuring full auditability through revision-bound analysis, automatic staleness invalidation, and immutable cryptographic system snapshots.

Wave 7 strictly upholds QUEBET's foundational engineering tenets:
* **`UNKNOWN != PASS` / `UNKNOWN != COMPATIBLE`**: Omitted interface contracts, unspecified voltages, or unlinked circuits evaluate strictly to `UNKNOWN`, never to `PASS`, `COMPATIBLE`, or `SATISFIED`.
* **Zero Synthetic or Composite Scoring**: No arbitrary system health scores, composite risk indices, or speculative badges (`TOP`, `BEST`).
* **Deterministic Engine Authority**: All compatibility evaluations, current budget summations, containment proofs, and blast radiuses are computed by deterministic rules. AI copilot capabilities provide natural-language reasoning and intent interpretation without authority to declare systems safe or mutate persistent architecture.
* **Revision-Bound & Stale-Protected**: Any structural mutation to a subsystem, interface, power domain, or dependency increments the system revision and immediately flags existing analyses as `STALE`.
* **Multi-Tenant Isolation**: Rigorous tenant scoping across all system models and endpoints, rejecting cross-tenant IDOR access.

---

## 1. System Engineering Architecture

```text
EngineeringSystem (Revision, Status, Multi-Tenant Isolation)
  ├── EngineeringSubsystem (Hierarchical Tree, Type, Circuit Linkage)
  ├── EngineeringSystemInterface (Source -> Destination, Typed Contract, Compatibility)
  ├── EngineeringPowerDomain (Voltage Limits, Source Subsystem, Current Capacity)
  ├── EngineeringSystemDependency (Semantic Directed Edges)
  ├── EngineeringOperatingMode & ModeTransition (Subsystem Masking, Operating Conditions)
  ├── EngineeringSystemRequirement (System-Level Constraints, Wave 6 Traceability)
  ├── EngineeringSystemAnalysis (Inputs Digest, Pinned Engine Versions, Findings)
  └── EngineeringSystemSnapshot (Immutable SHA-256 State Archive)
```

---

## 2. Core Domain Data Models & Database Schemas

Introduced in Alembic migration `009_phase_1_wave_7_system.py` (`backend/app/models/db/system.py`):

1. **`EngineeringSystem` (`engineering_systems`)**
   - High-level system engineering container bound to `project_id` and `tenant_id`.
   - Fields: `name`, `description`, `revision` (monotonic counter), `status` (`DRAFT`, `ACTIVE`, `UNDER_REVIEW`, `VERIFICATION_REQUIRED`, `PARTIALLY_VERIFIED`, `VERIFIED`, `BLOCKED`, `STALE`, `ARCHIVED`), `created_by`, `metadata_`.

2. **`EngineeringSubsystem` (`engineering_subsystems`)**
   - Hierarchical decomposition node with self-referential `parent_subsystem_id` foreign key.
   - Types: `POWER`, `PROTECTION`, `REGULATION`, `PROCESSING`, `SENSING`, `COMMUNICATION`, `STORAGE`, `ACTUATION`, `USER_INTERFACE`, `CLOCK`, `ANALOG`, `DIGITAL`, `RF`, `SAFETY`, `OTHER`.
   - Cycle prevention: Validated on create and update by walking parent lineage.
   - Deletion protection: Rejects deletion if child subsystems, active interfaces, or dependencies reference it.
   - Circuit link: Optional `circuit_id` foreign key binding the subsystem abstraction to a physical schematic.

3. **`EngineeringSystemInterface` (`engineering_system_interfaces`)**
   - Directed communication or power link from `source_subsystem_id` to `destination_subsystem_id`.
   - Types: `POWER`, `GROUND`, `ANALOG_SIGNAL`, `DIGITAL_SIGNAL`, `CLOCK`, `DATA`, `CONTROL`, `COMMUNICATION`, `RF`, `MECHANICAL`, `THERMAL`, `OTHER`.
   - Contract JSON: `voltage_nominal`, `voltage_min`, `voltage_max`, `max_current_a`, `protocol`, `baud_rate`, `logic_level`, `galvanic_isolation`.

4. **`EngineeringPowerDomain` (`engineering_power_domains`)**
   - Supply rail definition with `nominal_voltage`, `min_voltage`, `max_voltage`, `current_capacity_a`.
   - Linked to `source_subsystem_id` and optional `regulator_subsystem_id`.

5. **`EngineeringSystemDependency` (`engineering_system_dependencies`)**
   - Semantic dependency relationship from `source_subsystem_id` to `target_subsystem_id`.
   - Types: `POWER_DEPENDS_ON`, `SIGNAL_DEPENDS_ON`, `DATA_DEPENDS_ON`, `CONTROL_DEPENDS_ON`, `CLOCK_DEPENDS_ON`, `THERMALLY_DEPENDS_ON`, `COMMUNICATION_DEPENDS_ON`.

6. **`EngineeringOperatingMode` (`engineering_operating_modes`) & `EngineeringModeTransition` (`engineering_mode_transitions`)**
   - Encapsulates subsystem operational states: `active_subsystem_ids`, `inactive_subsystem_ids`, `expected_power_domain_ids`, `relevant_interface_ids`.
   - Mode transitions define allowable state changes with `trigger`, `conditions`, `required_subsystems`, and `forbidden_conditions`.

7. **`EngineeringSystemRequirement` (`engineering_system_requirements`)**
   - System-level engineering constraints with `code`, `title`, `description`, `requirement_type`, `source` (Wave 6 reference), `status` (`UNKNOWN`, `SUPPORTED`, `VIOLATED`, `PARTIALLY_SUPPORTED`, `VERIFICATION_REQUIRED`).

8. **`EngineeringSystemAnalysis` (`engineering_system_analyses`) & `EngineeringSystemFinding` (`engineering_system_findings`)**
   - Captures deterministic evaluation at a specific `system_revision`.
   - Audit integrity: `inputs_digest` (SHA-256 hash of all system elements), `engine_versions`, `rule_set_version`, `is_stale`.
   - Findings carry `severity` (`CRITICAL`, `WARNING`, `INFO`), deterministic `calculation`, `provenance`, and explicit `unknowns` array.

9. **`EngineeringSystemSnapshot` (`engineering_system_snapshots`)**
   - Immutable historical state snapshot containing full serialized graph and SHA-256 `snapshot_hash`.

---

## 3. Deterministic Engineering Engines

Located in `backend/app/services/ai/system/`:

### 3.1 Interface Compatibility Engine (`interface_compatibility_engine.py`)
- Evaluates contract matching between interconnected subsystems across 4 states: `COMPATIBLE`, `INCOMPATIBLE`, `PARTIALLY_COMPATIBLE`, `UNKNOWN`.
- Checks:
  - Voltage compatibility: Source vs destination allowable voltage windows.
  - Current limits: Source supply limit vs destination load requirement.
  - Protocol matching: E.g., `SPI`, `I2C`, `UART`, `CAN`, `USB`, `ETHERNET`.
  - Timing & Baud rate: Baud rates must match identically if specified.
  - Logic level: Compatibility between TTL, CMOS 3.3V, CMOS 5V, LVDS, etc.
- Incomplete contracts evaluate strictly to `UNKNOWN`, populating the `unknowns` array.

### 3.2 Power Tree Service (`power_tree_service.py`)
- Traverses the power distribution tree starting from power source subsystems through regulators to downstream consumers.
- Detects circular power loops and unpowered active subsystems.
- Aggregates downstream current loads per power domain and verifies margins against `current_capacity_a`.
- Flags over-capacity rails as `CRITICAL` findings.

### 3.3 Failure Propagation Engine (`failure_propagation_engine.py`)
- Simulates multi-hop fault propagation originating at a specified root cause subsystem.
- Traverses downstream dependencies and inbound interfaces to identify affected subsystems.
- Identifies physical containment barriers:
  - Galvanic isolation barriers in interface contracts stop signal-borne electrical surges.
  - Fuse protection and thermal cutoffs isolate power rail short circuits.
- Categorizes affected subsystems, severed interfaces, lost power domains, and functional loss without arbitrary risk scores.

### 3.4 System Change Impact Service (`system_change_impact_service.py`)
- Analyzes blast radius when a subsystem or interface is added, modified, or removed.
- Identifies directly and transitively affected subsystems, interfaces, power domains, and requirements.
- Marks prior analyses as `STALE` and increments the system revision.

### 3.5 System Analysis Service (`system_analysis_service.py`)
- Orchestrates compatibility checks, power tree aggregation, loop detection, and requirement verification into an authoritative `EngineeringSystemAnalysis`.

---

## 4. API Surface & REST Endpoints

Mounted in `backend/app/api/v1/routes/systems.py`:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/systems` | List systems (filterable by `project_id`) |
| `POST` | `/api/v1/systems` | Create new engineering system |
| `GET` | `/api/v1/systems/{id}` | Get complete system graph |
| `POST` | `/api/v1/subsystems` | Create subsystem with cycle prevention |
| `DELETE` | `/api/v1/subsystems/{id}` | Delete subsystem with deletion protection |
| `POST` | `/api/v1/interfaces` | Create subsystem interface with typed contract |
| `POST` | `/api/v1/power-domains` | Create power domain rail |
| `POST` | `/api/v1/dependencies` | Create semantic dependency edge |
| `POST` | `/api/v1/modes` | Create operating mode |
| `POST` | `/api/v1/requirements` | Create system requirement |
| `POST` | `/api/v1/systems/{id}/analyze` | Run deterministic system analysis |
| `GET` | `/api/v1/systems/{id}/analysis/latest` | Retrieve latest analysis with stale indicator |
| `GET` | `/api/v1/systems/{id}/findings` | Retrieve system findings |
| `POST` | `/api/v1/systems/{id}/failure-analysis` | Run failure propagation simulation |
| `POST` | `/api/v1/systems/{id}/change-impact` | Calculate architectural blast radius |
| `GET` | `/api/v1/systems/{id}/traceability` | Fetch system traceability matrix |
| `POST` | `/api/v1/systems/{id}/snapshots` | Create immutable cryptographic snapshot |

---

## 5. Frontend System Architecture Workspace

Implemented across `frontend/src/components/system/` and integrated into the project page:

1. **`SystemCanvas.tsx`**:
   - Interactive SVG-based system architecture diagram with pan and zoom.
   - Deterministic column layout grouping subsystems by architectural layer (Power/Protection -> Regulation -> Processing -> Sensing/Actuation/Comms).
   - Colored directional interface bezier curves with typed arrows and protocol badges.
   - Visual highlighting of selected subsystems and interfaces.

2. **`PowerTreeView.tsx`**:
   - Dedicated power rail distribution view displaying voltage hierarchies.
   - Real-time current budget bars showing aggregated downstream draw vs domain capacity.
   - Overload warning indicators and regulator relationship tags.

3. **`SystemTree.tsx`**:
   - Left-column navigation panel with quick search filtering.
   - Accordion tabs for Subsystems (hierarchical tree), Interfaces, Power Rails, Operating Modes, and Requirements.
   - Quick badges indicating linked circuits, nominal voltages, and verification states.

4. **`SystemInspector.tsx`**:
   - Right-side properties, findings, and traceability inspector.
   - Inspects subsystem metadata, circuit linkage, bound interfaces, and power relationships.
   - Inspects interface contracts (voltages, current, protocol, baud rate, logic level, galvanic isolation) and reports compatibility evaluations.
   - Full findings viewer with expandable inputs, calculations, provenance, and unknowns.

5. **`FailurePropagationModal.tsx`**:
   - Interactive failure simulation dialog.
   - Allows selecting a root cause subsystem and failure mode.
   - Displays affected subsystems, severed interfaces, unpowered rails, and active containment barriers (galvanic isolation, fuses).

6. **`SystemWorkspace.tsx`**:
   - Top-level workspace orchestrator with revision tracking and validation status badges.
   - View mode switcher between Architecture Diagram and Power Tree.
   - Stale analysis alert banner prompting the engineer to re-analyze after architectural modifications.
   - Modal management for failure propagation simulation and snapshot generation.

7. **Project Workspace Mode Switcher (`frontend/src/app/(dashboard)/projects/[id]/page.tsx`)**:
   - Header toggle allowing seamless switching between **Circuit Schematic** and **System Architecture** views.

---

## 6. Verification Results

### 6.1 Backend Pytest Suite
Ran `python -m pytest backend/tests -v`:
* **76 passed in 31.76s** (including 6 comprehensive test suites in `test_phase1_wave7.py`).
* Coverage includes:
  - Subsystem hierarchy and cycle prevention.
  - Subsystem deletion protection against active children, interfaces, and dependencies.
  - Interface Compatibility Engine 4-state evaluation (`COMPATIBLE`, `INCOMPATIBLE`, `PARTIALLY_COMPATIBLE`, `UNKNOWN`).
  - Power tree current load aggregation and overload detection.
  - Multi-hop failure propagation and galvanic isolation containment.
  - Revision advancement, stale analysis invalidation, and blast radius calculation.
  - Strict tenant isolation and IDOR cross-tenant access rejection.

### 6.2 Frontend Unit Test Suite
Ran `npm --prefix frontend test`:
* **31 tests across 5 suites passed with 0 failures** (including Phase 1 Wave 7 tests).
* Verified:
  - Subsystem tree cycle detection.
  - Interface Compatibility ternary logic (`UNKNOWN != PASS`).
  - Power tree load budget verification.
  - Failure propagation containment barriers.
  - Revision stale invalidation.
  - Cryptographic snapshot SHA-256 format.

### 6.3 Next.js Production Builds
* `frontend`: Compiled and built successfully (`exit code 0`).
* `admin`: Compiled and built successfully (`exit code 0`).

---

## 7. Status Declaration

```text
PHASE_1_WAVE_7_STATUS: COMPLETE
```
