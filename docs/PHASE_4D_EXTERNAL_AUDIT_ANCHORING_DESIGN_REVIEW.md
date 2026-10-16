# QUEBET AI — Phase 4D: External Audit Anchoring & Ledger Notarization Design Review

**Document Version:** 2.0.0  
**Status:** `PHASE_4D_DESIGN_READY_FOR_APPROVAL`  
**Target Repository:** `C:\workflow\quebet_ai`  
**Execution Timestamp:** 2026-10-16T17:45:00Z  
**Primary Reviewers:** Principal Security Architect, Cryptographic Systems Engineer, Audit & Compliance Lead  

---

## 1. Revised Threat Model

The QUEBET AI audit ledger maintains an internal, append-only, per-project SHA-256 hash chain of all authoritative engineering operations (`EngineeringAuditEvent`). While internal cryptographic hashing prevents undetected event tampering by regular application users, an internal database ledger alone cannot resist attacks by a privileged database administrator (DBA), compromised cloud database infrastructure, or undetected storage corruption.

External RFC 3161 timestamping anchors the internal audit chain to an independent, legally recognized, cryptographic time authority. However, external anchoring operates under strict security boundaries and does not solve all data-integrity challenges.

### 1.1 Threat Matrix & Mitigation Analysis

| Threat ID | Threat Vector | Attacker Capability | Mitigation in Phase 4D | Residual Risk / Limitation |
| :--- | :--- | :--- | :--- | :--- |
| **TH-01** | **Historical Event Rewriting** | Privileged DBA mutates an event payload and re-hashes downstream sequence hashes to restore internal chain consistency. | Checkpoint manifest contains `chain_head_hash` and `to_sequence`, bound to an external RFC 3161 token minted at time $T$. Re-hashed chain produces a mismatched head digest that contradicts the independently timestamped anchor. | External anchor detects tampering only when verification is executed; it cannot prevent the unauthorized database rewrite from occurring in the first place. |
| **TH-02** | **Checkpoint Deletion / Dropping** | Privileged DBA deletes anchor rows to conceal the historical anchor state. | Schema eliminates `ON DELETE CASCADE`. Verified anchors are mirrored to an independent append-only retention destination. Deletion of local records leaves the external mirror intact, proving local ledger truncation. | If independent retention is not configured, local row deletion cannot be detected by an isolated local reader inspecting only the local database. |
| **TH-03** | **Token Replay / Cross-Project Substitution** | Attacker takes a valid RFC 3161 token from Project A (or checkpoint $N$) and associates it with Project B (or checkpoint $N+1$). | `TSTInfo.messageImprint` is cryptographically bound to the SHA-256 digest of the canonical Checkpoint Manifest, which explicitly embeds `project_id`, `tenant_id`, `checkpoint_sequence`, `from_sequence`, `to_sequence`, and `chain_head_hash`. Substitution results in immediate imprint mismatch. | None. Imprint mismatch is mathematically guaranteed by preimage resistance of SHA-256. |
| **TH-04** | **Rogue / Compromised TSA** | A compromised or misconfigured TSA mints backdated or forged timestamp tokens. | Verification enforces an explicit, trusted CA bundle (`TSA_CA_CERT_PATH`), certificate validity dates, Extended Key Usage (`id-kp-timeStamping`), and TSA policy OIDs. | If the trusted root CA itself is compromised, forged timestamps could be validated until certificate revocation evidence (CRL/OCSP) is consulted. |
| **TH-05** | **Request Interception / Replay** | Attacker intercepts a timestamp request and returns an old token or replays a previous transaction. | Requests include a cryptographically unpredictable 128-bit nonce (`secrets.randbits(128)`). The returned token's `TSTInfo.nonce` must match the request nonce exactly. | None. 128-bit entropy renders nonce prediction computationally infeasible ($2^{-128}$). |
| **TH-06** | **Concurrent Checkpoint Creation** | Multiple concurrent workers or API calls attempt to anchor the same project audit chain simultaneously. | Row-level locking on `Project` (`with_for_update()`), coupled with database unique constraints on `(project_id, checkpoint_sequence)` and `(project_id, to_sequence)`. | None. Conflicting transactions fail fast or serialize deterministically. |
| **TH-07** | **Audit Append During In-Flight Anchor** | High-velocity engineering actions append events (seq $N+1$, $N+2$) while an anchor request for seq $1..N$ is in flight to the TSA. | Checkpoints define an immutable sequence range `[from_sequence, to_sequence]`. Subsequent appends create new events starting at $N+1$; they do not mutate or invalidate the in-flight checkpoint. | The newly appended events remain unanchored until the next checkpoint is requested. |
| **TH-08** | **Network Timeout / Transient TSA Outage** | TSA network request times out, drops connection, or rate-limits requests. | Network calls occur strictly outside database transactions. Checkpoints enter a recoverable `FAILED` state. Retries reuse the deterministic logical manifest without digest mutation. | Release gate RG-09 fails closed or marks anchor unverified if an anchor was required. |
| **TH-09** | **Algorithm Downgrade / Mismatched Hash** | Malicious actor or broken TSA returns a token using MD5 or SHA-1, or an ambiguous canonical serialization. | Digest algorithm is strictly pinned to SHA-256 (`2.16.840.1.101.3.4.2.1`). Any token containing an unapproved algorithm is rejected immediately. | None. Downgrade attacks are rejected at the ASN.1 validation boundary. |
| **TH-10** | **Long-Term Verification (LTV) / Certificate Expiry** | TSA certificate expires 3 years after the token was issued. Verification today succeeds, but fails in 5 years due to expired certificate. | The system archives the complete CMS `SignedData` containing the signer certificate and intermediate certificates. Verification evaluates certificate validity at `TSTInfo.genTime`, recording explicit verification timestamps and LTV status. | True long-term non-repudiation across decades requires periodic re-timestamping or external RFC 4998 Evidence Records if root CAs expire. |

### 1.2 What RFC 3161 Alone Does NOT Mitigate

It is a non-negotiable architectural invariant that external timestamping **must never be conflated with engineering validity or authority**:

```text
AUDIT CHAIN VALIDITY != EXTERNAL ANCHOR VALIDITY
TIMESTAMPED DIGEST != PROOF OF EVENT TRUTH
AI ENGINEERING AUTHORITY = NONE
AI DECISION AUTHORITY = NONE
AUTONOMOUS MUTATION = DISABLED
AUTONOMOUS APPROVAL = DISABLED
AUTONOMOUS VERIFICATION = DISABLED
HISTORICAL MEMORY != ENGINEERING TRUTH
HISTORICAL VERIFICATION != CURRENT VERIFICATION
UNKNOWN != SATISFIED
```

1. **RFC 3161 proves temporal existence only**: A valid timestamp token proves solely that a specific byte sequence (the checkpoint manifest digest) existed at or before the time asserted by the TSA (`genTime`).
2. **RFC 3161 does NOT prove engineering truth or physical reality**: A timestamped event asserting that an overstressed resistor passed thermal testing does not make the resistor safe.
3. **RFC 3161 does NOT prove event authorship**: A timestamp proves *when* data existed, not *who* authored it. Human actor attribution relies on QUEBET AI's authoritative authentication and cryptographic session tokens.
4. **RFC 3161 does NOT confer engineering authority**: External anchoring never satisfies release gates, overrides design rule violations, or authorizes baseline creation.
5. **RFC 3161 does NOT prevent local data deletion**: If all database records and local backups are purged without an external mirror, the timestamp token cannot restore the lost data.

---

## 2. Complete Trust Boundaries

```
+---------------------------------------------------------------------------------------------------------+
|                                    QUEBET AI TRUST DOMAIN                                               |
|                                                                                                         |
|  +----------------------------------+                   +--------------------------------------------+  |
|  |   Authoritative Human Actor      |                   |          Authoritative Database            |  |
|  |  (ENGINEER / LEAD_ENGINEER)      |                   |        (Neon PostgreSQL / SQLite)          |  |
|  +-----------------+----------------+                   +---------------------+----------------------+  |
|                    | Requests Anchor                                          |                         |
|                    v                                                          v                         |
|  +-----------------+----------------------------------------------------------+----------------------+  |
|  |                              AuditAnchorService (Internal Orchestrator)                           |  |
|  |                                                                                                   |  |
|  |  1. Locks Project row (with_for_update)                                                           |  |
|  |  2. Reads verified audit events seq [from..to] & head hash                                        |  |
|  |  3. Constructs deterministic Checkpoint Manifest & SHA-256 Digest                                  |  |
|  |  4. Persists Checkpoint in PENDING state (commit)                                                 |  |
|  +-----------------+---------------------------------------------------------------------------------+  |
+--------------------|------------------------------------------------------------------------------------+
                     |
                     | Submits 32-byte SHA-256 MessageImprint + 128-bit Nonce
                     | (Content-Type: application/timestamp-query)
                     v
+---------------------------------------------------------------------------------------------------------+
|                                    EXTERNAL UNTRUSTED NETWORK                                           |
|                                                                                                         |
|  +---------------------------------------------------------------------------------------------------+  |
|  |                               RFC 3161 Time Stamping Authority (TSA)                             |  |
|  |  - External third-party trust boundary (e.g. DigiCert, Sectigo, FreeTSA, or Internal Vault TSA)   |  |
|  |  - Untrusted until signature, certificate chain, and message imprint are mathematically verified |  |
|  +---------------------------------------------------------------------------------------------------+  |
+--------------------|------------------------------------------------------------------------------------+
                     |
                     | Returns binary TimeStampResp (Content-Type: application/timestamp-reply)
                     v
+---------------------------------------------------------------------------------------------------------+
|                                    QUEBET AI TRUST DOMAIN                                               |
|                                                                                                         |
|  +-----------------+---------------------------------------------------------------------------------+  |
|  |                              RFC3161VerificationEngine (Fail-Closed)                              |  |
|  |                                                                                                   |  |
|  |  [ ] Parse ASN.1 TimeStampResp (Check status == 0)                                                |  |
|  |  [ ] Verify MessageImprint matches Checkpoint Digest exactly                                      |  |
|  |  [ ] Verify DigestAlgorithm == SHA-256                                                            |  |
|  |  [ ] Verify Nonce matches request nonce exactly                                                   |  |
|  |  [ ] Extract CMS SignedData & SignerInfo (Exactly 1 signer)                                       |  |
|  |  [ ] Validate CMS SignedAttributes (contentType, messageDigest, signingCertificateV2)             |  |
|  |  [ ] Verify Cryptographic Signature over SignedAttributes                                        |  |
|  |  [ ] Verify TSA Certificate has EKU 'id-kp-timeStamping'                                          |  |
|  |  [ ] Verify TSA Certificate validity period at TSTInfo.genTime                                    |  |
|  |  [ ] Validate Certificate Chain against mandatory TSA_CA_CERT_PATH                                |  |
|  |  [ ] Check TSA Policy OID constraints (if configured)                                             |  |
|  +-----------------+---------------------------------------------------------------------------------+  |
|                    | All 10 checks PASS                                                                 |
|                    v                                                                                    |
|  +-----------------+-----------------------------------+     +---------------------------------------+  |
|  |          Local Database Commit                      |     |     Independent External Mirror       |  |
|  |  - Status: ANCHORED                                 | --> |  - Immutable WORM Storage / S3 Lock   |  |
|  |  - Store: token_der, tsa_timestamp, token_hash      |     |  - Prevents undetectable local drops  |  |
|  +-----------------------------------------------------+     +---------------------------------------+  |
+---------------------------------------------------------------------------------------------------------+
```

### 2.1 State Segregation Standard

To prevent misleading states, the system enforces a strict distinction between local ledger states and external anchor verification states:

```text
[LOCAL HASH-CHAIN VERIFIED]  !=  [TOKEN PARSED]
[TOKEN PARSED]               !=  [TOKEN CRYPTOGRAPHICALLY VERIFIED]
[TOKEN VERIFIED]             !=  [TSA CERTIFICATE TRUSTED]
[TSA CERTIFICATE TRUSTED]    !=  [POLICY ACCEPTED]
[POLICY ACCEPTED]            !=  [LOCAL CHECKPOINT MATCHED]
[LOCAL CHECKPOINT MATCHED]   !=  [INDEPENDENT RETENTION CONFIRMED]
```

Under no circumstances will a checkpoint be marked `ANCHORED` unless **all** stages succeed. If the TSA CA certificate bundle is missing, invalid, or expired in production, verification **fails closed** (`VERIFICATION_FAILED`), and the checkpoint is not recognized as an authoritative anchor.

---

## 3. Complete RFC 3161 & CMS Verification Specification

RFC 3161 defines a timestamp token as an encapsulated Cryptographic Message Syntax (CMS) `SignedData` object (RFC 5652). Verification cannot rely on high-level parser success alone; it must execute an explicit 10-stage verification protocol.

### 3.1 Stage-by-Stage Verification Pipeline

```mermaid
flowchart TD
    A["Raw Binary Response (application/timestamp-reply)"] --> B["Stage 1: ASN.1 DER Decoding & Status Check"]
    B -->|status == 0 (granted)| C["Stage 2: Token Structure & OID Validation"]
    B -->|status != 0| ERR1["REJECT: TSA Error (PKIFailureInfo)"]
    C -->|id-ct-TSTInfo present| D["Stage 3: Message Imprint & Algorithm Match"]
    C -->|invalid OID / malformed| ERR2["REJECT: Malformed Token"]
    D -->|Imprint == Checkpoint Digest & Algo == SHA-256| E["Stage 4: 128-bit Nonce Validation"]
    D -->|Imprint mismatch| ERR3["REJECT: Digest Mismatch"]
    E -->|Nonce matches request| F["Stage 5: CMS Signer Resolution (Exactly 1)"]
    E -->|Nonce mismatch| ERR4["REJECT: Replay Detected"]
    F -->|Unambiguous SignerInfo| G["Stage 6: CMS Signed Attributes Verification"]
    F -->|Zero or >1 signers| ERR5["REJECT: Ambiguous Signer"]
    G -->|SignedAttrs valid & hash matches TSTInfo DER| H["Stage 7: Cryptographic Signature Verification"]
    G -->|SignedAttrs tampered| ERR6["REJECT: Attribute Digest Mismatch"]
    H -->|RSA/ECDSA signature valid| I["Stage 8: TSA Certificate & EKU Validation"]
    H -->|Signature invalid| ERR7["REJECT: Invalid Signature"]
    I -->|EKU id-kp-timeStamping & valid at genTime| J["Stage 9: CA Chain Trust Validation"]
    I -->|Missing EKU or Expired| ERR8["REJECT: Untrusted Certificate"]
    J -->|Chain validates to TSA_CA_CERT_PATH| K["Stage 10: Policy & Algorithm Constraint Validation"]
    J -->|Untrusted Root / Broken Chain| ERR9["REJECT: Untrusted CA Root"]
    K -->|Policy accepted| PASS["RESULT: VERIFIED ANCHOR"]
    K -->|Policy rejected| ERR10["REJECT: Policy Constraint Violation"]
```

### 3.2 Detailed Technical Specifications for Each Stage

#### Stage 1: DER Decoding & Status Verification
- Decode binary response into `pyasn1_modules.rfc3161.TimeStampResp`.
- Extract `PKIStatusInfo.status`:
  * Value `0` (`granted`) or `1` (`grantedWithMods`): Proceed.
  * Any other value (e.g. `2` `rejection`, `3` `waiting`, `5` `revocationWarning`): Fail closed immediately. Extract `PKIFailureInfo` bitmask (e.g. `badAlg`, `badRequest`, `unacceptedPolicy`, `systemFailure`) and return explicit error code.

#### Stage 2: Token Structure & Encapsulated Content
- Extract `timeStampToken` (`pyasn1_modules.rfc5652.ContentInfo`).
- Validate `ContentInfo.contentType` equals `id-signedData` (`1.2.840.113549.1.7.2`).
- Decode `ContentInfo.content` as `SignedData` (RFC 5652).
- Validate `SignedData.encapContentInfo.eContentType` equals `id-ct-TSTInfo` (`1.2.840.113549.1.9.16.1.4`).
- Extract the raw octets of `SignedData.encapContentInfo.eContent` and decode as `TSTInfo`.

#### Stage 3: Message Imprint & Algorithm Verification
- Extract `TSTInfo.messageImprint`:
  * `hashAlgorithm.algorithm`: Must equal SHA-256 OID `2.16.840.1.101.3.4.2.1`. Any other OID (including SHA-1, MD5, SHA-512) is rejected.
  * `hashedMessage`: Extract raw octets (must be exactly 32 bytes).
  * Compute expected 32-byte SHA-256 digest of the canonical Checkpoint Manifest.
  * Constant-time comparison: `hmac.compare_digest(hashedMessage, expected_checkpoint_digest_bytes)`.
  * If comparison fails, raise `ImprintMismatchError`.

#### Stage 4: Nonce & Replay Verification
- Check if `TSTInfo.nonce` is present:
  * If a request nonce was transmitted, `TSTInfo.nonce` **MUST** be present.
  * Compare `int(TSTInfo.nonce)` with the request nonce integer.
  * If mismatched or absent, raise `NonceMismatchError`.

#### Stage 5: Signer Identification & Unambiguity
- Inspect `SignedData.signerInfos`:
  * RFC 3161 Section 2.4.2 explicitly mandates: **"There MUST be only one SignerInfo structure"**.
  * If `len(signerInfos) != 1`, fail closed (`AmbiguousSignerError`).
- Resolve the TSA certificate from `SignedData.certificates` matching `SignerInfo.sid`:
  * By `IssuerAndSerialNumber` (RFC 5652 Section 5.3).
  * Or by `SubjectKeyIdentifier`.
  * If no matching certificate is found in the token, fail closed (`SignerCertificateNotFoundError`).

#### Stage 6: Signed Attributes Verification (CMS Section 5.4)
- `SignerInfo.signedAttrs` **MUST** be present in RFC 3161 tokens:
  1. `id-contentType` (`1.2.840.113549.1.9.3`): Must match `id-ct-TSTInfo` (`1.2.840.113549.1.9.16.1.4`).
  2. `id-messageDigest` (`1.2.840.113549.1.9.4`):
     - Compute the digest of the raw DER-encoded `eContent` (`TSTInfo` octets) using `SignerInfo.digestAlgorithm`.
     - Validate that the computed digest matches the attribute's octet value exactly.
  3. `id-aa-signingCertificate` (`1.2.840.113549.1.9.16.2.12`) or `id-aa-signingCertificateV2` (`1.2.840.113549.1.9.16.2.47`):
     - Extract certificate hash from attribute.
     - Verify that the hash matches the SHA-256 digest of the TSA certificate identified in Stage 5. This prevents rogue certificate substitution.

#### Stage 7: Cryptographic Signature Verification
- In CMS, the digital signature is calculated over the **DER encoding of `signedAttrs` with the context-specific tag `[0]` replaced by a universal `SET OF` tag (`0x31`)**.
- Extract `SignerInfo.signature`.
- Load the TSA public key using `cryptography.x509`.
- Verify the signature over the canonical encoded signed attributes:
  * For RSA (`1.2.840.113549.1.1.1`): `padding.PKCS1v15()` with appropriate hash algorithm.
  * For RSA-PSS (`1.2.840.113549.1.1.10`): `padding.PSS(mgf=..., salt_length=...)`.
  * For ECDSA (`1.2.840.10045.2.1`): `ec.ECDSA(...)`.
- If the cryptographic verification fails, raise `InvalidSignatureError`.

#### Stage 8: TSA Certificate & Extended Key Usage
- Inspect the TSA certificate using `cryptography.x509`:
  1. **Extended Key Usage (EKU)**: Must contain `ExtendedKeyUsageOID.TIME_STAMPING` (`1.3.6.1.5.5.7.3.8`).
  2. **Validity Time Window**: Extract `TSTInfo.genTime` (normalized to UTC).
     - Must satisfy: `cert.not_valid_before_utc <= genTime <= cert.not_valid_after_utc`.
     - If `genTime` falls outside the validity window, raise `CertificateExpiredError`.

#### Stage 9: Certificate Chain & CA Trust Validation
- **Production Requirement:** In production (`ENVIRONMENT == "production"`), `TSA_CA_CERT_PATH` is **mandatory**.
- Build certificate path from TSA leaf certificate -> intermediate certificates (supplied in `SignedData.certificates`) -> trusted root CA specified in `TSA_CA_CERT_PATH`.
- Verify each certificate's signature along the path to the root.
- If no valid path to a trusted root in `TSA_CA_CERT_PATH` can be constructed, fail closed (`UntrustedCertificateChainError`).

#### Stage 10: Policy Constraints
- If `TSA_POLICY_OID` is configured in QUEBET AI settings, verify that `TSTInfo.policy` matches the configured policy OID. If mismatched, raise `PolicyRejectedError`.

---

## 4. Deterministic Checkpoint Identity & Canonicalization Rules

### 4.1 The Checkpoint Identity Problem

A naive implementation generates a manifest where `created_at` represents the instant the HTTP request is sent. If a network timeout occurs and the application retries 10 seconds later, `created_at` changes, causing the canonical JSON string to change, changing the SHA-256 digest, and producing a completely different logical checkpoint. This violates idempotency and makes retries non-deterministic.

### 4.2 Solution: Immutable Logical Checkpoint Manifest

A logical checkpoint is created **once** when the anchoring process is initiated. Its canonical manifest and digest are persisted in the database row in `PENDING` state and **remain completely immutable during all subsequent retries**.

#### Canonical Checkpoint Manifest Schema
```json
{
  "canonicalization_algorithm": "QUEBET_CANONICAL_JSON_V1",
  "chain_head_hash": "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e",
  "chain_id": "ledger:project:9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "checkpoint_format_version": "1.0.0",
  "checkpoint_id": "2b320562-172b-417a-8698-01f30ffb8a78",
  "checkpoint_sequence": 1,
  "digest_algorithm": "SHA-256",
  "event_count": 42,
  "from_sequence": 1,
  "logical_timestamp": "2026-10-16T17:40:00.000000Z",
  "project_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "tenant_id": "tenant-alpha",
  "to_sequence": 42
}
```

#### Field Specifications:
* `checkpoint_format_version`: Constant `"1.0.0"`.
* `canonicalization_algorithm`: Constant `"QUEBET_CANONICAL_JSON_V1"`.
* `checkpoint_id`: Unique UUIDv4 string generated at checkpoint initialization.
* `project_id`: Authoritative UUID string of the project.
* `tenant_id`: Authoritative UUID string of the tenant (or `null` for personal workspace).
* `chain_id`: Deterministic chain identifier `f"ledger:project:{project_id}"`.
* `checkpoint_sequence`: Strictly monotonic per-project checkpoint sequence (1, 2, 3...).
* `from_sequence`: Monotonic sequence number of the first event covered in this checkpoint.
* `to_sequence`: Monotonic sequence number of the final event covered in this checkpoint.
* `chain_head_hash`: Exact 64-character SHA-256 hex digest of the event at `to_sequence`.
* `event_count`: Integer count `to_sequence - from_sequence + 1`.
* `digest_algorithm`: Constant `"SHA-256"`.
* `logical_timestamp`: Fixed UTC timestamp recorded at checkpoint creation (`datetime.now(timezone.utc).isoformat()`).

#### Canonicalization Rules:
1. Manifest dictionary is normalized via [`AuditLedgerService.canonical_json_value()`](file:///c:/workflow/quebet_ai/backend/app/services/audit_ledger_service.py#L57).
2. Serialized with [`AuditLedgerService.serialize_canonical_payload()`](file:///c:/workflow/quebet_ai/backend/app/services/audit_ledger_service.py#L102):
   - Alphabetical key sorting.
   - Compact separators: `","` (comma) and `":"` (colon) with zero whitespace.
   - UTF-8 encoding without ASCII escaping (`ensure_ascii=False`).
3. SHA-256 hex digest is computed over the resulting byte stream (`checkpoint_digest`).
4. The 32 raw bytes (`bytes.fromhex(checkpoint_digest)`) form the exact `MessageImprint` submitted to RFC 3161.

---

## 5. Nonce & Replay Protection

To prevent replay attacks and token substitution:
1. **Entropy**: The request nonce is generated using `secrets.randbits(128)`, providing 128 bits of cryptographic entropy.
2. **ASN.1 Encoding**: Encoded as an unsigned ASN.1 `INTEGER` in `TimeStampReq.nonce` (RFC 3161 Section 2.4.1).
3. **Database Retention**: Stored as a 32-character hexadecimal string in `engineering_audit_anchors.nonce`.
4. **Validation**: During verification, the integer in `TSTInfo.nonce` must equal the stored nonce integer exactly. If a token from a previous checkpoint or another project is presented, it will fail both the 128-bit nonce validation and the message imprint match.

---

## 6. Database Schema & Independent Retention Strategy

### 6.1 Database Schema (`engineering_audit_anchors`)

```python
class EngineeringAuditAnchor(Base, UUIDMixin):
    """
    Durable record of an external RFC 3161 cryptographic timestamp anchor
    binding a specific sequence range of an engineering audit ledger.
    """
    __tablename__ = "engineering_audit_anchors"

    # Multi-tenant and project scoping (RESTRICT deletion; preserve audit trail)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    # Monotonic checkpoint counter per project
    checkpoint_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Covered audit ledger sequence range
    from_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    to_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chain_head_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Immutable Checkpoint Manifest & Digest
    checkpoint_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    checkpoint_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # 128-bit Cryptographic Nonce (hex string)
    nonce: Mapped[str] = mapped_column(String(32), nullable=False)

    # Lifecycle State: PENDING, ANCHORED, FAILED, VERIFICATION_FAILED
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True, nullable=False)

    # TSA Authority & Metadata
    tsa_url: Mapped[str] = mapped_column(String(255), nullable=False)
    tsa_policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tsa_serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tsa_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Raw Verified RFC 3161 Token
    token_der: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Operational Diagnostic Fields
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Independent Retention Mirror Metadata
    mirrored_to_external_store: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    external_store_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    anchored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verification_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Unique Constraints
    __table_args__ = (
        UniqueConstraint("project_id", "checkpoint_sequence", name="uq_anchor_project_sequence"),
        UniqueConstraint("project_id", "to_sequence", name="uq_anchor_project_to_seq"),
    )
```

### 6.2 Elimination of `ON DELETE CASCADE` & Project Deletion Policy

In the initial design, `project_id` used `ON DELETE CASCADE`. This introduced a fatal vulnerability: deleting a project would silently erase all external audit anchors from the database.

**Revised Policy:**
1. Foreign key constraint changed to `ON DELETE RESTRICT`. A project with existing audit events or anchors **cannot be deleted via hard SQL delete**.
2. Deleting a project is strictly implemented via soft deletion (`projects.deleted_at = NOW()`).
3. Historical audit events (`engineering_audit_events`) and audit anchors (`engineering_audit_anchors`) remain permanently preserved and immutable for regulatory audit compliance.

### 6.3 Independent External Retention Strategy

If all anchor rows reside solely within the production Neon PostgreSQL database, a rogue cloud DBA could drop the `engineering_audit_anchors` table, destroying all local evidence of the timestamps.

To mitigate this, QUEBET AI defines an **Independent Retention Protocol**:

```
+---------------------------+       +------------------------------------+
|  AuditAnchorService       | ----> |  Neon PostgreSQL                   |
|  (Local Database Commit)  |       |  (engineering_audit_anchors table) |
+-------------+-------------+       +------------------------------------+
              |
              | Mirrored asynchronously post-verification
              v
+------------------------------------------------------------------------+
|                     INDEPENDENT RETENTION STORE                         |
|                                                                        |
| Option A: AWS S3 / Cloud Storage Object Lock (WORM Compliance Mode)     |
|   - Path: s3://quebet-audit-anchors/{tenant_id}/{project_id}/{seq}.json |
|   - Content: Canonical Manifest + Base64 DER Token + TSA Cert Chain    |
|   - Retain: 7-10 years immutable; cannot be deleted even by root DBA    |
|                                                                        |
| Option B: Public Transparency Log (Sigstore Rekor / Custom Notary)     |
|   - Log entry binds Checkpoint Digest + TSA Token                      |
|   - Returns Signed Entry Timestamp (SET) & Inclusion Proof             |
+------------------------------------------------------------------------+
```

#### Evaluation of Approaches:
1. **Immutable WORM Object Storage (Recommended for Enterprise)**:
   - *Mechanism*: Store checkpoint package (`manifest.json` + `token.der`) in S3 with Object Lock enabled in Compliance Mode.
   - *Trust Assumptions*: AWS/GCP infrastructure IAM boundary separate from Neon DB credentials.
   - *Operational Cost*: Minimal (pennies per gigabyte/year).
   - *Failure Mode*: If S3 is unreachable, local anchor succeeds with `mirrored_to_external_store = False`, queued for background retry.
2. **Phase 4D Baseline Deployment & Explicit Limitation**:
   - In standard development and baseline enterprise deployments where external S3 Object Lock is not yet provisioned, the database table stores the primary record.
   - **Explicit Limitation**: Without an independently administered external store, the system guarantees *tamper-evidence* (history modification is detected) but *cannot prevent a rogue DBA from deleting local records entirely*. This limitation is explicitly documented in Section 9.

---

## 7. Retry, Concurrency & Failure Semantics

### 7.1 Detailed Anchor Lifecycle State Machine

```
                   +---------------------+
                   |    NOT_REQUESTED    |
                   +----------+----------+
                              |
                              | Human Engineer invokes POST /anchor
                              v
                   +---------------------+
                   |       PENDING       | <------------------------------------+
                   +----------+----------+                                      |
                              |                                                 |
            +-----------------+-----------------+                               |
            |                                   |                               |
            | HTTP Timeout / Network Error       | TSA Response Received         | Retries reuse
            v                                   v                               | identical
     +-------------+                 +---------------------+                    | manifest &
     |   FAILED    |                 |  10-Stage Verify    |                    | digest
     +------+------+                 +----------+----------+                    |
            |                                   |                               |
            | Retry invoked                     | Verification fails            |
            +-----------------------------------|-------------------------------+
                                                |
                                                +---------> +---------------------+
                                                |           | VERIFICATION_FAILED |
                                                |           +---------------------+
                                                v
                                   Verification succeeds
                                                |
                                                v
                                         +--------------+
                                         |   ANCHORED   |
                                         +-------+------+
                                                 |
                                                 | Periodic or On-Demand Re-verify
                                                 v
                                         +--------------+
                                         | RE-VERIFIED  |
                                         +--------------+
```

### 7.2 Concurrency & Race-Condition Controls

1. **Transaction Isolation**:
   - `AuditAnchorService.request_anchor(project_id)` initiates an explicit database transaction.
   - Acquires an exclusive row lock on `Project`: `SELECT * FROM projects WHERE id = :id FOR UPDATE`.
   - Inspects the latest event in `engineering_audit_events`. Let this be sequence $M$.
   - Inspects the latest anchor in `engineering_audit_anchors`.
     * If latest anchor has `to_sequence == M` and `status == ANCHORED`, the current head is already anchored; returns existing anchor.
     * If latest anchor has `to_sequence == M` and `status == PENDING`, an anchor request is currently in flight; returns pending status.
2. **Range Derivation**:
   - `from_sequence = (latest_anchor.to_sequence + 1) if latest_anchor else 1`.
   - `to_sequence = M`.
   - If $M < \text{from\_sequence}$, no new events exist to anchor.
3. **Database Commit Before Network Call**:
   - Generates `checkpoint_manifest`, computes `checkpoint_digest`, generates 128-bit `nonce`.
   - Inserts `EngineeringAuditAnchor` row with `status = "PENDING"`.
   - **Commits transaction**. The lock on `Project` is released, preventing long-running database transaction stalls during the external HTTP network call.
4. **External Network Call**:
   - Executes HTTP POST to configured `TSA_SERVER_URL` with a strict 10-second timeout.
5. **Post-Response Transaction**:
   - Executes the 10-stage RFC 3161/CMS verification engine.
   - If verification succeeds: updates row to `status = "ANCHORED"`, records `token_der`, `tsa_timestamp`, `token_hash`, and commits.
   - If TSA returns an error or network times out: updates row to `status = "FAILED"`, records `error_code` and `error_message`, and commits.
   - If verification fails cryptographically: updates row to `status = "VERIFICATION_FAILED"`, records detailed failure reason, and commits.

### 7.3 Mid-Flight Audit Appends

If an engineer updates a schematic or adds a net while the TSA request is in flight:
- New events are appended to `engineering_audit_events` at sequences $M+1, M+2$.
- The in-flight anchor specifically covers $1..M$ and binds `chain_head_hash` at sequence $M$.
- When the TSA response arrives, it perfectly validates the range $1..M$.
- The next anchor request will simply compute `from_sequence = M + 1` and `to_sequence = M + 2`. The audit ledger maintains a continuous, non-overlapping series of anchored checkpoints ($1..M$, $M+1..N$, etc.).

---

## 8. Comprehensive Testing Strategy

A dedicated adversarial test suite (`backend/tests/unit/test_security_phase4d.py`) will be implemented using deterministic in-memory cryptographic test fixtures. Tests must run without depending on public internet access or external third-party TSAs.

### 8.1 Required Adversarial Test Matrix

| Test ID | Test Target | Verification Condition | Expected Result |
| :--- | :--- | :--- | :---: |
| **TEST-01** | Checkpoint Canonicalization | Same manifest serialized 100 times produces identical byte stream and SHA-256 digest. | Exact digest match |
| **TEST-02** | Monotonic Scope & Coverage | Checkpoint $K+1$ strictly begins at $\text{to\_sequence}_K + 1$ with zero gaps or overlaps. | Contiguous range verified |
| **TEST-03** | End-to-End Valid Token | Generate valid RFC 3161 token using in-memory test CA and TSA signing key. | `ANCHORED` status verified |
| **TEST-04** | Message Imprint Mismatch | Modify 1 byte of the checkpoint manifest after token generation. | Rejected: `ImprintMismatchError` |
| **TEST-05** | Wrong Digest Algorithm | Submit token specifying SHA-1 OID instead of SHA-256. | Rejected: `UnsupportedAlgorithmError` |
| **TEST-06** | Invalid Cryptographic Signature | Corrupt 1 byte of the CMS signature octets. | Rejected: `InvalidSignatureError` |
| **TEST-07** | Untrusted Certificate Chain | Sign token with a valid CA not present in `TSA_CA_CERT_PATH`. | Rejected: `UntrustedCertificateChainError` |
| **TEST-08** | Invalid EKU Usage | Sign token with certificate missing `id-kp-timeStamping` (e.g. Server Auth only). | Rejected: `InvalidEKUError` |
| **TEST-09** | Expired TSA Certificate | Set `genTime` outside certificate validity window (`not_valid_after`). | Rejected: `CertificateExpiredError` |
| **TEST-10** | Nonce Mismatch & Replay | Return token containing nonce different from request nonce. | Rejected: `NonceMismatchError` |
| **TEST-11** | TSA Error Response Status | Return `TimeStampResp` with `status = 2` (`rejection`) and `badAlg` failure info. | Rejected: `TSARequestRejectedError` |
| **TEST-12** | Network Timeout Handling | Simulate HTTP connection timeout / connection reset. | Checkpoint state = `FAILED` |
| **TEST-13** | Idempotent Retry Semantics | Retry a `FAILED` checkpoint; verify it reuses the exact same manifest and digest. | Digest unchanged; status -> `ANCHORED` |
| **TEST-14** | Concurrent Checkpoint Race | Launch 5 concurrent anchor tasks against same project. | Exactly 1 succeeds; 4 serialize or detect in-flight |
| **TEST-15** | Mid-Flight Audit Append | Append events seq 11..12 while seq 1..10 is pending; verify seq 1..10 anchors cleanly. | Range 1..10 verified |
| **TEST-16** | Out-of-Order Anchor Rejection | Attempt to anchor sequence $15..20$ before $1..14$ is anchored. | Rejected: Sequence discontinuity |
| **TEST-17** | Deletion Protection | Attempt hard delete on Project with active anchors; verify `ON DELETE RESTRICT`. | IntegrityError raised; hard delete blocked |
| **TEST-18** | Tenant Isolation Enforcement | Untenanted user or Tenant B attempts to view/verify Tenant A's anchors. | HTTP 404 Fail Closed |
| **TEST-19** | Missing Trust Config Fail-Closed | Set `ENVIRONMENT=production` and `TSA_CA_CERT_PATH=None`; attempt verification. | Fails closed with configuration error |
| **TEST-20** | Offline Re-Verification | Re-verify previously stored token without network connectivity using stored trust material. | Re-verification succeeds |

---

## 9. Explicit Limitations

To maintain uncompromising engineering integrity, the following limitations are explicitly declared:

1. **RFC 3161 proves temporal existence, not engineering validity**: A valid timestamp does not certify that circuit calculations are correct, that DFM rules are satisfied, or that hardware was physically verified.
2. **Local DBA Deletion Limitation**: Without an independently administered, out-of-band WORM storage mirror (e.g., S3 Object Lock in compliance mode), an attacker with root database access who drops the entire database will destroy local evidence of the anchors. External anchoring makes local history rewriting *tamper-evident*, but cannot prevent local destruction unless the external mirror is provisioned.
3. **Long-Term Validation (LTV) Boundary**: The initial Phase 4D implementation verifies certificates against configured roots and `genTime`. True long-term non-repudiation over multiple decades (CAdES-A / RFC 4998) requires recurring re-timestamping before CA certificates expire.
4. **No Automated Release Authority**: External anchoring is purely an evidence verification mechanism. It does not automatically grant release approvals or override release gates (`AI ENGINEERING AUTHORITY = NONE`).

---

## 10. Implementation Dependencies & Deployment Requirements

### 10.1 Software Dependencies
- Python 3.11+
- `cryptography >= 46.0.0` (Already installed: 46.0.5)
- `pyasn1 >= 0.6.0` (Already installed)
- `pyasn1-modules >= 0.4.0` (Already installed; provides `rfc3161` and `rfc5652`)
- `httpx >= 0.28.0` (Already installed: 0.28.1)
- `SQLAlchemy >= 2.0.0` & `asyncpg`

### 10.2 Configuration Settings (`backend/app/core/config.py`)
```python
# RFC 3161 External Timestamping Configuration
TSA_SERVER_URL: Optional[str] = None          # URL of external or internal RFC 3161 TSA
TSA_CA_CERT_PATH: Optional[str] = None        # Path to PEM-encoded trusted CA certificate bundle
TSA_TIMEOUT_SECONDS: float = 10.0             # Strict HTTP request timeout
TSA_POLICY_OID: Optional[str] = None          # Optional explicit TSA policy OID
TSA_REQUIRE_CERT_REQ: bool = True             # Request TSA to include signing certificate
TSA_MIRROR_S3_BUCKET: Optional[str] = None    # Optional independent WORM object storage bucket
```

---

## 11. Approval Gate Declaration

**Proposed Milestone Status:** `PHASE_4D_DESIGN_READY_FOR_APPROVAL`

This design addresses every item required by the Phase 4D Design Review. Production code and database migrations have not been altered. The design is submitted for authoritative confirmation before implementation commences.
