# QUEBET AI — Phase 4D: External Audit Anchoring & Ledger Notarization Implementation Report

**Milestone:** Phase 4D  
**Repository:** `C:\workflow\quebet_ai`  
**Status:** COMPLETED & EVIDENCE-VERIFIED  
**Date:** October 16, 2026  
**Implementation Spec:** `docs/PHASE_4D_EXTERNAL_AUDIT_ANCHORING_DESIGN_REVIEW.md`  

---

## 1. Executive Summary

Phase 4D establishes an authoritative, cryptographically sound, independently verifiable external timestamp anchoring and notarization subsystem for QUEBET AI's internal engineering audit ledger.

Prior to Phase 4D, the audit ledger maintained an internal SHA-256 hash chain that provided internal tamper evidence within PostgreSQL. However, internal hash chains cannot independently prove when events occurred or prove immutability against database administrators, storage compromises, or timeline reconstruction.

Phase 4D bridges this integrity boundary by introducing:
1. **Deterministic Checkpoint Manifests:** Monotonic per-project sequence slices serialized via canonical JSON and hashed with SHA-256.
2. **10-Stage RFC 3161 / CMS Cryptographic Verification Engine:** Full DER parsing, message imprint pinning (SHA-256), 128-bit cryptographic nonces, CMS signed attributes verification, single-signer validation, Extended Key Usage (`id-kp-timeStamping`) enforcement, validity window checks at `genTime`, and X.509 certificate chain validation against explicit trusted root bundles.
3. **Authoritative Audit Anchor Service:** Row-level project locking during checkpoint derivation, out-of-transaction network dispatch, durable database persistence (`ON DELETE RESTRICT`), and deterministic idempotent retries.
4. **Independent WORM Retention Subsystem:** Transparent disclosure of out-of-band mirroring status without conflating internal database storage with independent immutability.
5. **Release Governance Integration:** Evaluation of external notarization evidence within release readiness checks, while strictly maintaining the invariant that notarization is NOT engineering approval.

---

## 2. Non-Negotiable Engineering Invariants

Phase 4D strictly enforces the following core system axioms across all database models, services, endpoints, and frontend components:

```text
AI ENGINEERING AUTHORITY = NONE
AI DECISION AUTHORITY = NONE
AUTONOMOUS MUTATION = DISABLED
AUTONOMOUS APPROVAL = DISABLED
AUTONOMOUS VERIFICATION = DISABLED
HISTORICAL MEMORY != ENGINEERING TRUTH
HISTORICAL VERIFICATION != CURRENT VERIFICATION
AUDIT CHAIN VALIDITY != EXTERNAL ANCHOR VALIDITY
TIMESTAMPED DIGEST != PROOF OF EVENT TRUTH
UNKNOWN != SATISFIED
```

- **Notarization != Engineering Approval:** A cryptographically verified timestamp proves only that a particular checkpoint manifest digest existed at or before the timestamp authority's certified time. It does NOT assert that the schematic is electrically correct, that DRC is clean, that requirements are satisfied, or that a human engineer approved the release.
- **Fail-Closed Standard:** If `TSA_CA_CERT_PATH` is not configured in production, or if any certificate in the TSA chain is untrusted, expired, lacks the timestamping EKU, or has a mismatched signature, verification strictly fails closed.
- **AI Agent Prohibition:** Any attempt by an AI agent role (`ai_agent`, `copilot`, `assistant`) to initiate an anchor request or notarize a ledger checkpoint is blocked with `HTTP 403 Forbidden`.

---

## 3. Architecture & Implemented Components

### 3.1. Database Schema & Alembic Migration

- **Migration:** `backend/migrations/versions/028_phase_4d_external_audit_anchors.py` (Revises: `027_phase_3_wave_10c_release_gates_and_baselines`). Forward-only, deterministic transactional DDL.
- **Model:** `EngineeringAuditAnchor` (`backend/app/models/db/audit_anchor.py`).
  - `project_id`: Foreign key referencing `projects.id` with `ondelete="RESTRICT"`. Projects with anchored audit records cannot be deleted.
  - `tenant_id`: Strict enterprise tenant scoping.
  - `checkpoint_sequence`: Strictly monotonic per-project checkpoint number.
  - `from_sequence`, `to_sequence`: Contiguous sequence coverage of underlying audit events.
  - `checkpoint_manifest`: Canonical JSON logical checkpoint dictionary.
  - `checkpoint_digest`: 64-character SHA-256 hex digest of the canonical manifest (Unique constraint `uq_anchor_checkpoint_digest`).
  - `nonce`: 128-bit cryptographic random nonce hex string.
  - `status`: Lifecycle state (`PENDING`, `ANCHORED`, `FAILED`, `VERIFICATION_FAILED`).
  - `token_der`: Complete binary DER timestamp token for offline verification.
  - `token_hash`: SHA-256 digest of `token_der`.
  - `mirrored_to_external_store`: Boolean flag indicating out-of-band immutable storage.
  - `Unique Constraints`:
    - `(project_id, checkpoint_sequence)`
    - `(project_id, to_sequence)`
    - `checkpoint_digest`

### 3.2. Cryptographic Engine (`backend/app/services/rfc3161_service.py`)

Implements full, standard-compliant RFC 3161 and RFC 5652 CMS parsing and verification:
1. **Request Construction:** `RFC3161Engine.create_timestamp_request()` builds DER-encoded `TimeStampReq` with pinned SHA-256 algorithm OID (`2.16.840.1.101.3.4.2.1`), raw 32-byte digest, 128-bit entropy nonce, and optional TSA policy OID.
2. **Response Decoding:** `RFC3161Engine.parse_timestamp_response()` decodes `TimeStampResp`, inspecting PKIStatus (granting only status 0 and 1) and extracting `timeStampToken`.
3. **10-Stage CMS Verification (`RFC3161Engine.verify_timestamp_token`):**
   - Stage 1: Decode `ContentInfo` and verify `contentType == id-signedData`.
   - Stage 2: Decode `SignedData` and verify `encapContentInfo.eContentType == id-ct-TSTInfo`.
   - Stage 3: Decode `TSTInfo` and verify `messageImprint.hashAlgorithm == SHA256_OID` and `messageImprint.hashedMessage == expected_digest`.
   - Stage 4: Verify request nonce matches `TSTInfo.nonce` (rejects missing or mismatched nonces).
   - Stage 5: Extract `genTime` and policy OID (verifying against configured policy if required).
   - Stage 6: Verify exactly one CMS `SignerInfo` exists (rejects ambiguous multiple signers).
   - Stage 7: Extract TSA certificates from `SignedData` and resolve leaf signing certificate via `issuerAndSerialNumber` or `subjectKeyIdentifier`.
   - Stage 8: Validate CMS `signedAttrs`, ensuring presence of `id-contentType` and `id-messageDigest`, and verifying that `id-messageDigest` matches the SHA-256 hash of raw `eContent`.
   - Stage 9: Cryptographically verify the signature over normalized signed attributes (`b"\x31" + signed_attrs_der[1:]`) using the signer's public key (RSA PKCS#1 v1.5, RSA-PSS, or ECDSA).
   - Stage 10: Validate TSA certificate Extended Key Usage (strictly enforcing `id-kp-timeStamping` `1.3.6.1.5.5.7.3.8`), confirm validity window at `genTime`, and verify certificate chain to trusted root CA bundle in `TSA_CA_CERT_PATH`.

### 3.3. Authoritative Audit Anchor Service (`backend/app/services/audit_anchor_service.py`)

- **Concurrency Serialization:** Acquires row-level `FOR UPDATE` lock on `Project` during checkpoint manifest derivation, preventing concurrent workers from creating overlapping sequence ranges.
- **Out-of-Transaction Network Dispatch:** Database lock is released and network call to external TSA occurs outside the transaction to prevent database connection exhaustion.
- **Idempotent Retries:** If an anchor request fails (e.g. network timeout), the checkpoint row is persisted in `FAILED` state. Retrying reuses the exact same checkpoint manifest, sequence range, and digest.
- **Offline Re-verification (`verify_anchor`):** Complete local re-verification using stored `token_der` and CA bundle, along with database verification of contiguous sequence coverage and chain-head hash alignment.

### 3.4. Independent External Retention Service (`backend/app/services/audit_retention_service.py`)

- Manages optional mirroring of verified anchors to out-of-band immutable destinations (e.g., S3 Object Lock in Compliance Mode).
- Transparently discloses when external retention is unconfigured (`mirrored_to_external_store = False`).
- Strictly avoids claiming local PostgreSQL storage as independent immutability.

### 3.5. REST API Endpoints (`backend/app/api/v1/routes/audit.py`)

- `POST /api/v1/audit/projects/{project_id}/anchor`: Request RFC 3161 external timestamp notarization. Strictly restricted to human engineers.
- `GET /api/v1/audit/projects/{project_id}/anchors`: Retrieve chronological anchors with tenant isolation.
- `GET /api/v1/audit/projects/{project_id}/anchors/{anchor_id}`: Retrieve detailed anchor metadata and token hash.
- `POST /api/v1/audit/projects/{project_id}/anchors/{anchor_id}/verify`: Execute full cryptographic and ledger re-verification.

### 3.6. Frontend Governance Integration (`frontend/src/components/schematic/ReleaseGovernanceTab.tsx`)

- Displays external timestamp notarization status, TSA timestamp, serial number, and verification badge.
- Displays out-of-band WORM retention status with explicit limitation disclosures.

---

## 4. Verification & Test Evidence

### 4.1. Unit & Security Integration Test Suite

A dedicated test suite was implemented in [`backend/tests/unit/test_security_phase4d.py`](file:///c:/workflow/quebet_ai/backend/tests/unit/test_security_phase4d.py), covering 26 distinct scenarios:

| # | Test Identifier | Verification Focus | Status |
|---|---|---|---|
| 1 | `test_checkpoint_canonicalization_and_deterministic_digest` | Key sorting & identical SHA-256 digest | **PASS** |
| 2 | `test_monotonic_sequence_ranges` | Contiguous, strictly monotonic ranges | **PASS** |
| 3 | `test_valid_token_verification_success` | Full 10-stage CMS/TSTInfo verification | **PASS** |
| 4 | `test_message_imprint_mismatch_rejection` | Imprint mismatch rejected (`MESSAGE_IMPRINT_MISMATCH`) | **PASS** |
| 5 | `test_algorithm_downgrade_rejection` | Legacy algorithms rejected (SHA-1 downgrade attack) | **PASS** |
| 6 | `test_corrupted_signature_rejection` | Signature bit-flip rejected (`INVALID_SIGNATURE`) | **PASS** |
| 7 | `test_untrusted_ca_chain_rejection` | Rogue CA certificate rejected (`UNTRUSTED_CERTIFICATE_CHAIN`) | **PASS** |
| 8 | `test_missing_timestamping_eku_rejection` | Certificate lacking timestamping EKU rejected | **PASS** |
| 9 | `test_expired_certificate_rejection` | Certificate expired at `genTime` rejected | **PASS** |
| 10 | `test_mismatched_nonce_rejection` | Nonce mismatch rejected (`NONCE_MISMATCH`) | **PASS** |
| 11 | `test_missing_nonce_when_expected_rejection` | Missing nonce rejected when expected | **PASS** |
| 12 | `test_tsa_error_status_rejection` | PKIStatus=2 rejection handled cleanly | **PASS** |
| 13 | `test_signed_attrs_digest_mismatch_rejection` | Attribute digest mismatch rejected | **PASS** |
| 14 | `test_ambiguous_signers_rejection` | Multiple signers rejected (`AMBIGUOUS_SIGNER`) | **PASS** |
| 15 | `test_malformed_token_der_rejection` | Invalid ASN.1 bytes fail closed (`MALFORMED_TOKEN`) | **PASS** |
| 16 | `test_request_anchor_success_with_tsa_mock` | End-to-end service anchor creation & verification | **PASS** |
| 17 | `test_network_timeout_handling` | Network timeout transitions to `FAILED` with `NETWORK_TIMEOUT` | **PASS** |
| 18 | `test_idempotent_retry_manifest_preservation` | Retry reuses identical manifest, digest, and sequence | **PASS** |
| 19 | `test_audit_append_mid_flight_immutability` | Subsequent ledger appends do not corrupt anchor range | **PASS** |
| 20 | `test_project_deletion_restricted_with_anchors` | `ON DELETE RESTRICT` raises `IntegrityError` | **PASS** |
| 21 | `test_missing_retention_disclosure` | Transparent disclosure when external S3 unconfigured | **PASS** |
| 22 | `test_tenant_isolation_anchor_access` | Tenant B cannot read Tenant A anchors (HTTP 404) | **PASS** |
| 23 | `test_untenanted_personal_workspace_anchor_isolation` | Untenanted user cannot read tenant anchors (HTTP 404) | **PASS** |
| 24 | `test_ai_agent_anchor_request_denied` | AI roles strictly rejected (HTTP 403) | **PASS** |
| 25 | `test_unauthorized_human_role_denied` | Unauthorized roles (VIEWER) rejected (HTTP 403) | **PASS** |
| 26 | `test_release_gate_independence` | Anchor does NOT automatically pass release gates | **PASS** |

### 4.2. Pytest Execution Output

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\workflow\quebet_ai\backend
configfile: pyproject.toml
plugins: anyio-4.13.0, langsmith-0.8.3, asyncio-0.26.0, django-4.12.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 26 items

tests\unit\test_security_phase4d.py ..........................           [100%]

============================= 26 passed in 35.88s =============================
```

### 4.3. Full Security Regression Suite Output

To verify zero regressions against Phase 4A, 4B, and 4C hardening, the entire security suite was executed:

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\workflow\quebet_ai\backend
configfile: pyproject.toml
plugins: anyio-4.13.0, langsmith-0.8.3, asyncio-0.26.0, django-4.12.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 34 items

tests\unit\test_security_phase4c.py ................                     [ 47%]
tests\unit\test_security_phase4b.py ..........                           [ 76%]
tests\unit\test_security.py ........                                     [100%]

======================== 34 passed in 74.01s (0:01:14) ========================
```

Total active security tests passing: **60 of 60**.

---

## 5. Explicit Limitations & Threat Model Disclosures

1. **Local Database Truncation:** While PostgreSQL foreign key constraints enforce `ON DELETE RESTRICT`, a compromised superuser or direct database administrator can still delete rows directly in PostgreSQL. Independent tamper resistance requires external WORM mirroring (`TSA_MIRROR_S3_BUCKET`).
2. **TSA Trust Dependency:** The integrity of the timestamp depends entirely on the security of the configured TSA and the integrity of the trusted root certificate bundle in `TSA_CA_CERT_PATH`.
3. **No Semantic Verification:** A timestamp guarantees only that the checkpoint manifest existed at the certified time; it provides no evidence that the engineering contents are defect-free.

---

## 6. Milestone Conclusion

Phase 4D is formally **COMPLETE** and verified against all criteria established in `docs/PHASE_4D_EXTERNAL_AUDIT_ANCHORING_DESIGN_REVIEW.md`.

Next Milestone: **Phase 4E — End-to-End Penetration, Concurrency & Governance Verification**.
