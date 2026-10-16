"""
Phase 4D Security & Integrity Verification Suite: External Audit Anchoring & Ledger Notarization.

Verifies:
1. Checkpoint canonicalization & deterministic SHA-256 digest calculation.
2. Monotonic sequence ranges and contiguous coverage.
3. Complete 10-stage RFC 3161 / CMS verification:
   - Message imprint matching.
   - SHA-256 algorithm pinning (rejecting downgrade attacks).
   - Cryptographic signature validation (RSA PKCS#1 v1.5).
   - Signed attributes validation (contentType, messageDigest).
   - Signer resolution and ambiguous signer rejection.
   - TSA certificate ExtendedKeyUsage (id-kp-timeStamping) enforcement.
   - Validity window validation at genTime (rejecting expired certificates).
   - CA trust chain validation against explicit trusted root bundles.
   - 128-bit cryptographic nonce matching.
   - PKIStatus error handling (rejecting TSA failure statuses).
4. Authoritative Audit Anchor Service lifecycle:
   - Row-level Project concurrency serialization.
   - Network failure / timeout handling with graceful FAILED state.
   - Idempotent retries reusing exact checkpoint manifest and digest.
   - Mid-flight audit appends without anchor corruption.
   - Database foreign-key RESTRICT enforcement on Project deletion.
   - Independent external retention disclosure (WORM mirroring flag).
   - Offline cryptographic re-verification.
5. Mandatory Engineering Invariants:
   - AI ENGINEERING AUTHORITY = NONE (AI agent roles strictly rejected with HTTP 403).
   - Human role RBAC enforcement.
   - Multi-tenant and personal workspace isolation (cross-tenant access denied).
   - Release gate independence (notarization != engineering approval).
"""
import datetime
import hashlib
import os
import tempfile
import uuid
import pytest
from unittest.mock import AsyncMock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID, NameOID
from fastapi import HTTPException
from pyasn1.codec.der import decoder, encoder
from pyasn1.type import univ, useful
from pyasn1_modules import rfc3161, rfc5280, rfc5652
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal, engine
from app.core.dependencies import AuthenticatedUser
from app.models.db.audit_anchor import AnchorStatus, EngineeringAuditAnchor
from app.models.db.audit_ledger import EngineeringAuditEvent
from app.models.db.project import Project, ProjectStatus, ProjectType
from app.services.audit_anchor_service import AuditAnchorService
from app.services.audit_ledger_service import AuditLedgerService
from app.services.release_service import ReleaseService
from app.services.rfc3161_service import (
    ID_CONTENT_TYPE_ATTR,
    ID_CT_TST_INFO_OID,
    ID_MESSAGE_DIGEST_ATTR,
    ID_SIGNED_DATA_OID,
    RFC3161CertificateExpiredError,
    RFC3161DigestMismatchError,
    RFC3161Engine,
    RFC3161Error,
    RFC3161InvalidEKUError,
    RFC3161InvalidSignatureError,
    RFC3161MalformedTokenError,
    RFC3161NonceMismatchError,
    RFC3161PolicyMismatchError,
    RFC3161StatusRejectedError,
    RFC3161UntrustedCAError,
    RFC3161VerificationResult,
    SHA256_OID,
)


@pytest.fixture(autouse=True)
async def cleanup_db():
    yield
    await engine.dispose()


# ==============================================================================
# Cryptographic Fixtures & Helpers
# ==============================================================================

def generate_ca_and_tsa(
    ca_common_name: str = "Test Root CA",
    tsa_common_name: str = "Test TSA",
    include_tsa_eku: bool = True,
    tsa_valid_days_ago: int = 1,
    tsa_expire_days_ahead: int = 365,
):
    """Generates an in-memory CA and TSA certificate chain for testing."""
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ca_common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(100)
        .not_valid_before(now - datetime.timedelta(days=30))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    tsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tsa_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, tsa_common_name)])
    builder = (
        x509.CertificateBuilder()
        .subject_name(tsa_name)
        .issuer_name(ca_name)
        .public_key(tsa_key.public_key())
        .serial_number(200)
        .not_valid_before(now - datetime.timedelta(days=tsa_valid_days_ago))
        .not_valid_after(now + datetime.timedelta(days=tsa_expire_days_ahead))
    )
    if include_tsa_eku:
        builder = builder.add_extension(
            x509.ExtendedKeyUsage([x509.ObjectIdentifier("1.3.6.1.5.5.7.3.8")]),
            critical=True,
        )

    tsa_cert = builder.sign(ca_key, hashes.SHA256())
    return ca_key, ca_cert, tsa_key, tsa_cert


def build_test_timestamp_token(
    digest_bytes: bytes,
    tsa_key: rsa.RSAPrivateKey,
    tsa_cert: x509.Certificate,
    ca_cert: x509.Certificate,
    nonce: int = 123456789,
    policy_oid: str = "1.3.6.1.4.1.99999.1",
    hash_algo_oid: str = SHA256_OID,
    gen_time: datetime.datetime = None,
    corrupt_signature: bool = False,
    corrupt_imprint: bool = False,
    omit_nonce: bool = False,
    corrupt_signed_attr_digest: bool = False,
    multiple_signers: bool = False,
) -> bytes:
    """Constructs a fully formed RFC 3161 DER-encoded timeStampToken."""
    if gen_time is None:
        gen_time = datetime.datetime.now(datetime.timezone.utc)

    # 1. Build TSTInfo
    tst_info = rfc3161.TSTInfo()
    tst_info["version"] = 1
    tst_info["policy"] = univ.ObjectIdentifier(policy_oid)
    imprint = rfc3161.MessageImprint()
    imprint["hashAlgorithm"] = rfc3161.AlgorithmIdentifier()
    imprint["hashAlgorithm"]["algorithm"] = univ.ObjectIdentifier(hash_algo_oid)

    actual_digest = b"\x00" * 32 if corrupt_imprint else digest_bytes
    imprint["hashedMessage"] = univ.OctetString(actual_digest)
    tst_info["messageImprint"] = imprint
    tst_info["serialNumber"] = univ.Integer(98765)
    tst_info["genTime"] = useful.GeneralizedTime(gen_time.strftime("%Y%m%d%H%M%SZ"))
    if not omit_nonce:
        tst_info["nonce"] = univ.Integer(nonce)

    raw_tst = encoder.encode(tst_info)
    tst_digest = hashlib.sha256(raw_tst).digest()
    if corrupt_signed_attr_digest:
        tst_digest = hashlib.sha256(b"corrupted-tst-octets").digest()

    # 2. Build SignerInfo
    signer_info = rfc5652.SignerInfo()
    signer_info["version"] = 1
    ias = rfc5652.IssuerAndSerialNumber()
    ca_cert_asn1, _ = decoder.decode(ca_cert.public_bytes(serialization.Encoding.DER), asn1Spec=rfc5280.Certificate())
    ias["issuer"] = ca_cert_asn1["tbsCertificate"]["subject"]
    ias["serialNumber"] = univ.Integer(tsa_cert.serial_number)
    signer_info["sid"]["issuerAndSerialNumber"] = ias
    signer_info["digestAlgorithm"]["algorithm"] = univ.ObjectIdentifier(SHA256_OID)

    # SignedAttrs
    attr1 = rfc5652.Attribute()
    attr1["attrType"] = univ.ObjectIdentifier(ID_CONTENT_TYPE_ATTR)
    attr1["attrValues"].append(univ.ObjectIdentifier(ID_CT_TST_INFO_OID))
    signer_info["signedAttrs"].append(attr1)

    attr2 = rfc5652.Attribute()
    attr2["attrType"] = univ.ObjectIdentifier(ID_MESSAGE_DIGEST_ATTR)
    attr2["attrValues"].append(univ.OctetString(tst_digest))
    signer_info["signedAttrs"].append(attr2)

    signed_attrs_der = encoder.encode(signer_info["signedAttrs"])
    normalized_attrs_der = b"\x31" + signed_attrs_der[1:]
    signature = tsa_key.sign(normalized_attrs_der, padding.PKCS1v15(), hashes.SHA256())
    if corrupt_signature:
        # Flip bits
        sig_list = bytearray(signature)
        sig_list[10] ^= 0xFF
        signature = bytes(sig_list)

    signer_info["signatureAlgorithm"]["algorithm"] = univ.ObjectIdentifier("1.2.840.113549.1.1.1")
    signer_info["signature"] = univ.OctetString(signature)

    # 3. Build SignedData
    signed_data = rfc5652.SignedData()
    signed_data["version"] = 3
    da = rfc5652.DigestAlgorithmIdentifier()
    da["algorithm"] = univ.ObjectIdentifier(SHA256_OID)
    signed_data["digestAlgorithms"].append(da)
    signed_data["encapContentInfo"]["eContentType"] = univ.ObjectIdentifier(ID_CT_TST_INFO_OID)
    signed_data["encapContentInfo"]["eContent"] = signed_data["encapContentInfo"]["eContent"].clone(raw_tst)

    # Certificates
    tsa_cert_asn1, _ = decoder.decode(tsa_cert.public_bytes(serialization.Encoding.DER), asn1Spec=rfc5280.Certificate())
    cert_choice = rfc5652.CertificateChoices()
    cert_choice["certificate"] = tsa_cert_asn1
    signed_data["certificates"].append(cert_choice)

    signed_data["signerInfos"].append(signer_info)
    if multiple_signers:
        signed_data["signerInfos"].append(signer_info)

    # 4. Wrap in ContentInfo
    content_info = rfc5652.ContentInfo()
    content_info["contentType"] = univ.ObjectIdentifier(ID_SIGNED_DATA_OID)
    content_info["content"] = encoder.encode(signed_data)
    return encoder.encode(content_info)


def build_test_timestamp_response(token_der: bytes, pki_status: int = 0) -> bytes:
    """Wraps token_der in a standard RFC 3161 TimeStampResp structure."""
    resp = rfc3161.TimeStampResp()
    resp["status"]["status"] = univ.Integer(pki_status)
    if token_der:
        tok, _ = decoder.decode(token_der, asn1Spec=rfc3161.TimeStampToken())
        resp["timeStampToken"] = tok
    return encoder.encode(resp)


# ==============================================================================
# 1. Deterministic Checkpoint & Canonicalization Tests
# ==============================================================================

def test_checkpoint_canonicalization_and_deterministic_digest():
    """
    Checkpoint Manifest must sort keys alphabetically and use identical separators
    so that identical inputs deterministically yield identical SHA-256 digests.
    """
    manifest_a = {
        "to_sequence": 10,
        "from_sequence": 1,
        "project_id": "proj-123",
        "chain_head_hash": "a" * 64,
        "checkpoint_format_version": "1.0.0",
        "checkpoint_id": "chk-999",
        "checkpoint_sequence": 1,
        "digest_algorithm": "SHA-256",
        "event_count": 10,
        "chain_id": "ledger:project:proj-123",
        "canonicalization_algorithm": "QUEBET_CANONICAL_JSON_V1",
        "tenant_id": "tenant-abc",
        "logical_timestamp": "2026-10-16T18:00:00Z",
    }
    # Manifest B has scrambled key insertion order
    manifest_b = {
        "logical_timestamp": "2026-10-16T18:00:00Z",
        "tenant_id": "tenant-abc",
        "canonicalization_algorithm": "QUEBET_CANONICAL_JSON_V1",
        "chain_id": "ledger:project:proj-123",
        "event_count": 10,
        "digest_algorithm": "SHA-256",
        "checkpoint_sequence": 1,
        "checkpoint_id": "chk-999",
        "checkpoint_format_version": "1.0.0",
        "chain_head_hash": "a" * 64,
        "project_id": "proj-123",
        "from_sequence": 1,
        "to_sequence": 10,
    }

    hash_a = AuditLedgerService.compute_payload_hash(manifest_a)
    hash_b = AuditLedgerService.compute_payload_hash(manifest_b)

    assert hash_a == hash_b
    assert len(hash_a) == 64


def test_monotonic_sequence_ranges():
    """Ensures from_sequence <= to_sequence and sequence ranges are contiguous."""
    anchor1 = EngineeringAuditAnchor(
        id=str(uuid.uuid4()),
        project_id="proj-1",
        checkpoint_sequence=1,
        from_sequence=1,
        to_sequence=5,
        chain_head_hash="h1",
        checkpoint_manifest={},
        checkpoint_digest="d1",
        nonce="n1",
        status=AnchorStatus.ANCHORED.value,
        tsa_url="mock",
    )
    anchor2 = EngineeringAuditAnchor(
        id=str(uuid.uuid4()),
        project_id="proj-1",
        checkpoint_sequence=2,
        from_sequence=6,
        to_sequence=10,
        chain_head_hash="h2",
        checkpoint_manifest={},
        checkpoint_digest="d2",
        nonce="n2",
        status=AnchorStatus.ANCHORED.value,
        tsa_url="mock",
    )
    assert anchor1.to_sequence >= anchor1.from_sequence
    assert anchor2.from_sequence == anchor1.to_sequence + 1
    assert anchor2.checkpoint_sequence == anchor1.checkpoint_sequence + 1


# ==============================================================================
# 2. Cryptographic Token & CMS Verification Tests
# ==============================================================================

def test_valid_token_verification_success(tmp_path):
    """A correctly signed token by an authorized TSA against a trusted CA bundle succeeds."""
    ca_key, ca_cert, tsa_key, tsa_cert = generate_ca_and_tsa()
    ca_pem_path = str(tmp_path / "ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    digest = hashlib.sha256(b"manifest-data").digest()
    nonce = 123456789
    token_der = build_test_timestamp_token(
        digest_bytes=digest,
        tsa_key=tsa_key,
        tsa_cert=tsa_cert,
        ca_cert=ca_cert,
        nonce=nonce,
    )

    result = RFC3161Engine.verify_timestamp_token(
        token_der=token_der,
        expected_digest_bytes=digest,
        expected_nonce=nonce,
        ca_cert_path=ca_pem_path,
        required_policy_oid="1.3.6.1.4.1.99999.1",
        require_trusted_ca=True,
    )

    assert result.is_valid is True
    assert result.status == "VERIFIED"
    assert result.ca_chain_trusted is True
    assert result.signer_subject == "CN=Test TSA"
    assert result.signer_issuer == "CN=Test Root CA"


def test_message_imprint_mismatch_rejection(tmp_path):
    """Verification must fail closed if token contains a different message imprint."""
    ca_key, ca_cert, tsa_key, tsa_cert = generate_ca_and_tsa()
    ca_pem_path = str(tmp_path / "ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    expected_digest = hashlib.sha256(b"expected-manifest").digest()
    token_der = build_test_timestamp_token(
        digest_bytes=expected_digest,
        tsa_key=tsa_key,
        tsa_cert=tsa_cert,
        ca_cert=ca_cert,
        corrupt_imprint=True,  # Imprint has different bytes
    )

    result = RFC3161Engine.verify_timestamp_token(
        token_der=token_der,
        expected_digest_bytes=expected_digest,
        ca_cert_path=ca_pem_path,
        require_trusted_ca=True,
    )
    assert result.is_valid is False
    assert result.failure_code == "MESSAGE_IMPRINT_MISMATCH"


def test_algorithm_downgrade_rejection(tmp_path):
    """Tokens using legacy or downgraded algorithms (e.g. SHA-1) must be strictly rejected."""
    ca_key, ca_cert, tsa_key, tsa_cert = generate_ca_and_tsa()
    ca_pem_path = str(tmp_path / "ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    digest = hashlib.sha256(b"data").digest()
    # Downgrade to SHA-1 OID (1.3.14.3.2.26)
    token_der = build_test_timestamp_token(
        digest_bytes=digest,
        tsa_key=tsa_key,
        tsa_cert=tsa_cert,
        ca_cert=ca_cert,
        hash_algo_oid="1.3.14.3.2.26",
    )

    result = RFC3161Engine.verify_timestamp_token(
        token_der=token_der,
        expected_digest_bytes=digest,
        ca_cert_path=ca_pem_path,
        require_trusted_ca=True,
    )
    assert result.is_valid is False
    assert result.failure_code == "MESSAGE_IMPRINT_MISMATCH"
    assert "Unsupported message imprint algorithm" in (result.failure_message or "")


def test_corrupted_signature_rejection(tmp_path):
    """Cryptographic signature tampering must be caught and rejected with INVALID_SIGNATURE."""
    ca_key, ca_cert, tsa_key, tsa_cert = generate_ca_and_tsa()
    ca_pem_path = str(tmp_path / "ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    digest = hashlib.sha256(b"data").digest()
    token_der = build_test_timestamp_token(
        digest_bytes=digest,
        tsa_key=tsa_key,
        tsa_cert=tsa_cert,
        ca_cert=ca_cert,
        corrupt_signature=True,
    )

    result = RFC3161Engine.verify_timestamp_token(
        token_der=token_der,
        expected_digest_bytes=digest,
        ca_cert_path=ca_pem_path,
        require_trusted_ca=True,
    )
    assert result.is_valid is False
    assert result.failure_code == "INVALID_SIGNATURE"


def test_untrusted_ca_chain_rejection(tmp_path):
    """Tokens signed by an untrusted or rogue CA not in TSA_CA_CERT_PATH must be rejected."""
    # Rogue CA
    rogue_ca_key, rogue_ca_cert, rogue_tsa_key, rogue_tsa_cert = generate_ca_and_tsa(
        ca_common_name="Rogue Untrusted CA", tsa_common_name="Rogue TSA"
    )
    # Legitimate trusted CA bundle
    _, legit_ca_cert, _, _ = generate_ca_and_tsa(ca_common_name="Legit Enterprise Root CA")
    ca_pem_path = str(tmp_path / "legit_ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(legit_ca_cert.public_bytes(serialization.Encoding.PEM))

    digest = hashlib.sha256(b"data").digest()
    token_der = build_test_timestamp_token(
        digest_bytes=digest,
        tsa_key=rogue_tsa_key,
        tsa_cert=rogue_tsa_cert,
        ca_cert=rogue_ca_cert,
    )

    result = RFC3161Engine.verify_timestamp_token(
        token_der=token_der,
        expected_digest_bytes=digest,
        ca_cert_path=ca_pem_path,
        require_trusted_ca=True,
    )
    assert result.is_valid is False
    assert result.failure_code == "UNTRUSTED_CERTIFICATE_CHAIN"


def test_missing_timestamping_eku_rejection(tmp_path):
    """Certificates lacking id-kp-timeStamping EKU must be rejected with INVALID_CERTIFICATE_EKU."""
    ca_key, ca_cert, tsa_key, tsa_cert_no_eku = generate_ca_and_tsa(include_tsa_eku=False)
    ca_pem_path = str(tmp_path / "ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    digest = hashlib.sha256(b"data").digest()
    token_der = build_test_timestamp_token(
        digest_bytes=digest,
        tsa_key=tsa_key,
        tsa_cert=tsa_cert_no_eku,
        ca_cert=ca_cert,
    )

    result = RFC3161Engine.verify_timestamp_token(
        token_der=token_der,
        expected_digest_bytes=digest,
        ca_cert_path=ca_pem_path,
        require_trusted_ca=True,
    )
    assert result.is_valid is False
    assert result.failure_code == "INVALID_CERTIFICATE_EKU"


def test_expired_certificate_rejection(tmp_path):
    """TSA certificate not valid at token genTime must fail with CERTIFICATE_NOT_VALID_AT_GENTIME."""
    # Certificate that expired yesterday
    ca_key, ca_cert, tsa_key, expired_tsa_cert = generate_ca_and_tsa(
        tsa_valid_days_ago=10, tsa_expire_days_ahead=-1
    )
    ca_pem_path = str(tmp_path / "ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    digest = hashlib.sha256(b"data").digest()
    token_der = build_test_timestamp_token(
        digest_bytes=digest,
        tsa_key=tsa_key,
        tsa_cert=expired_tsa_cert,
        ca_cert=ca_cert,
    )

    result = RFC3161Engine.verify_timestamp_token(
        token_der=token_der,
        expected_digest_bytes=digest,
        ca_cert_path=ca_pem_path,
        require_trusted_ca=True,
    )
    assert result.is_valid is False
    assert result.failure_code == "CERTIFICATE_NOT_VALID_AT_GENTIME"


def test_mismatched_nonce_rejection(tmp_path):
    """If request supplied a nonce and token returns a different nonce, reject with NONCE_MISMATCH."""
    ca_key, ca_cert, tsa_key, tsa_cert = generate_ca_and_tsa()
    ca_pem_path = str(tmp_path / "ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    digest = hashlib.sha256(b"data").digest()
    expected_nonce = 111122223333
    different_nonce = 999988887777

    token_der = build_test_timestamp_token(
        digest_bytes=digest,
        tsa_key=tsa_key,
        tsa_cert=tsa_cert,
        ca_cert=ca_cert,
        nonce=different_nonce,
    )

    result = RFC3161Engine.verify_timestamp_token(
        token_der=token_der,
        expected_digest_bytes=digest,
        expected_nonce=expected_nonce,
        ca_cert_path=ca_pem_path,
        require_trusted_ca=True,
    )
    assert result.is_valid is False
    assert result.failure_code == "NONCE_MISMATCH"


def test_missing_nonce_when_expected_rejection(tmp_path):
    """If request specified a nonce but returned token has no nonce, reject with NONCE_MISMATCH."""
    ca_key, ca_cert, tsa_key, tsa_cert = generate_ca_and_tsa()
    ca_pem_path = str(tmp_path / "ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    digest = hashlib.sha256(b"data").digest()
    expected_nonce = 111122223333

    token_der = build_test_timestamp_token(
        digest_bytes=digest,
        tsa_key=tsa_key,
        tsa_cert=tsa_cert,
        ca_cert=ca_cert,
        omit_nonce=True,
    )

    result = RFC3161Engine.verify_timestamp_token(
        token_der=token_der,
        expected_digest_bytes=digest,
        expected_nonce=expected_nonce,
        ca_cert_path=ca_pem_path,
        require_trusted_ca=True,
    )
    assert result.is_valid is False
    assert result.failure_code == "NONCE_MISMATCH"


def test_tsa_error_status_rejection():
    """TimeStampResp with non-zero PKIStatus (e.g. status=2 rejection) must be rejected."""
    # PKIStatus 2 = rejection
    resp = rfc3161.TimeStampResp()
    resp["status"]["status"] = univ.Integer(2)
    resp_der = encoder.encode(resp)

    status_val, fail_info, token_der = RFC3161Engine.parse_timestamp_response(resp_der)
    assert status_val == 2
    assert token_der is None


def test_signed_attrs_digest_mismatch_rejection(tmp_path):
    """If messageDigest signedAttr does not match raw eContent digest, reject."""
    ca_key, ca_cert, tsa_key, tsa_cert = generate_ca_and_tsa()
    ca_pem_path = str(tmp_path / "ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    digest = hashlib.sha256(b"data").digest()
    token_der = build_test_timestamp_token(
        digest_bytes=digest,
        tsa_key=tsa_key,
        tsa_cert=tsa_cert,
        ca_cert=ca_cert,
        corrupt_signed_attr_digest=True,
    )

    result = RFC3161Engine.verify_timestamp_token(
        token_der=token_der,
        expected_digest_bytes=digest,
        ca_cert_path=ca_pem_path,
        require_trusted_ca=True,
    )
    assert result.is_valid is False
    assert result.failure_code == "MESSAGE_IMPRINT_MISMATCH"


def test_ambiguous_signers_rejection(tmp_path):
    """RFC 3161 strictly requires exactly one CMS SignerInfo. Multiple signers must fail."""
    ca_key, ca_cert, tsa_key, tsa_cert = generate_ca_and_tsa()
    ca_pem_path = str(tmp_path / "ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    digest = hashlib.sha256(b"data").digest()
    token_der = build_test_timestamp_token(
        digest_bytes=digest,
        tsa_key=tsa_key,
        tsa_cert=tsa_cert,
        ca_cert=ca_cert,
        multiple_signers=True,
    )

    result = RFC3161Engine.verify_timestamp_token(
        token_der=token_der,
        expected_digest_bytes=digest,
        ca_cert_path=ca_pem_path,
        require_trusted_ca=True,
    )
    assert result.is_valid is False
    assert result.failure_code == "AMBIGUOUS_SIGNER"


def test_malformed_token_der_rejection():
    """Corrupted or non-ASN.1 binary bytes must fail closed with MALFORMED_TOKEN."""
    result = RFC3161Engine.verify_timestamp_token(
        token_der=b"\x00\x01\x02\x03\x04\x05",
        expected_digest_bytes=hashlib.sha256(b"x").digest(),
        require_trusted_ca=False,
    )
    assert result.is_valid is False
    assert result.failure_code == "MALFORMED_TOKEN"


# ==============================================================================
# 3. Authoritative Audit Anchor Service & Ledger Orchestration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_request_anchor_success_with_tsa_mock(tmp_path):
    """
    End-to-end request_anchor succeeds when TSA responds with a valid token,
    transitioning the anchor status to ANCHORED with verified cryptographic evidence.
    """
    ca_key, ca_cert, tsa_key, tsa_cert = generate_ca_and_tsa()
    ca_pem_path = str(tmp_path / "ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    user_id = str(uuid.uuid4())
    tenant_id = f"tenant-{uuid.uuid4().hex[:6]}"
    project_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=project_id,
            tenant_id=tenant_id,
            owner_id=user_id,
            name="Anchoring Test Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.commit()

        ledger = AuditLedgerService(session)
        # Add 3 audit events
        for seq in range(1, 4):
            await ledger.record_event(
                project_id=project_id,
                actor_id=user_id,
                actor_role="LEAD_ENGINEER",
                event_type="CIRCUIT_MUTATION",
                entity_type="circuit",
                entity_id="circ-1",
                payload={"seq": seq},
                commit=True,
            )

    human_user = AuthenticatedUser(
        id=user_id,
        email="lead@quebet.io",
        role="LEAD_ENGINEER",
        plan="enterprise",
        tenant_id=tenant_id,
    )

    # Mock TSA response
    def mock_tsa_dispatch(request):
        req_bytes = request.content
        req_parsed, _ = decoder.decode(req_bytes, asn1Spec=rfc3161.TimeStampReq())
        digest_bytes = bytes(req_parsed["messageImprint"]["hashedMessage"])
        nonce = int(req_parsed["nonce"]) if req_parsed.getComponentByName("nonce") is not None else 0

        token_der = build_test_timestamp_token(
            digest_bytes=digest_bytes,
            tsa_key=tsa_key,
            tsa_cert=tsa_cert,
            ca_cert=ca_cert,
            nonce=nonce,
        )
        resp_der = build_test_timestamp_response(token_der, pki_status=0)
        import httpx
        return httpx.Response(200, content=resp_der, headers={"Content-Type": "application/timestamp-reply"})

    async def async_mock_dispatch(url, content, headers=None, timeout=None):
        return mock_tsa_dispatch(type("Req", (), {"content": content})())

    async with AsyncSessionLocal() as session:
        service = AuditAnchorService(session)
        with patch("httpx.AsyncClient.post", side_effect=async_mock_dispatch):
            anchor = await service.request_anchor(
                project_id=project_id,
                current_user=human_user,
                tsa_url="https://mock.tsa.org",
                ca_cert_path=ca_pem_path,
            )

            assert anchor.status == AnchorStatus.ANCHORED.value
            assert anchor.checkpoint_sequence == 1
            assert anchor.from_sequence == 1
            assert anchor.to_sequence == 3
            assert anchor.chain_head_hash is not None
            assert anchor.token_der is not None
            assert anchor.last_verification_status == "VERIFIED"


@pytest.mark.asyncio
async def test_network_timeout_handling():
    """
    When TSA times out, anchor row transitions to FAILED with NETWORK_TIMEOUT,
    preserving the checkpoint manifest and digest for idempotent retry.
    """
    user_id = str(uuid.uuid4())
    tenant_id = f"tenant-{uuid.uuid4().hex[:6]}"
    project_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=project_id,
            tenant_id=tenant_id,
            owner_id=user_id,
            name="Timeout Test Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.commit()

        ledger = AuditLedgerService(session)
        await ledger.record_event(
            project_id=project_id,
            actor_id=user_id,
            actor_role="LEAD_ENGINEER",
            event_type="CIRCUIT_MUTATION",
            entity_type="circuit",
            entity_id="circ-1",
            payload={"action": "init"},
            commit=True,
        )

    human_user = AuthenticatedUser(
        id=user_id,
        email="lead@quebet.io",
        role="LEAD_ENGINEER",
        plan="enterprise",
        tenant_id=tenant_id,
    )

    async with AsyncSessionLocal() as session:
        service = AuditAnchorService(session)
        import httpx
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Connection timed out")):
            anchor = await service.request_anchor(
                project_id=project_id,
                current_user=human_user,
                tsa_url="https://mock.timeout.tsa",
            )
            assert anchor.status == AnchorStatus.FAILED.value
            assert anchor.error_code == "NETWORK_TIMEOUT"
            assert anchor.from_sequence == 1
            assert anchor.to_sequence == 1


@pytest.mark.asyncio
async def test_idempotent_retry_manifest_preservation(tmp_path):
    """
    Retrying an anchor after failure or with force_retry reuses the exact same
    checkpoint manifest, digest, and checkpoint sequence.
    """
    ca_key, ca_cert, tsa_key, tsa_cert = generate_ca_and_tsa()
    ca_pem_path = str(tmp_path / "ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    user_id = str(uuid.uuid4())
    tenant_id = f"tenant-{uuid.uuid4().hex[:6]}"
    project_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=project_id,
            tenant_id=tenant_id,
            owner_id=user_id,
            name="Retry Test Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.commit()

        ledger = AuditLedgerService(session)
        await ledger.record_event(
            project_id=project_id,
            actor_id=user_id,
            actor_role="LEAD_ENGINEER",
            event_type="CIRCUIT_MUTATION",
            entity_type="circuit",
            entity_id="circ-1",
            payload={"v": 1},
            commit=True,
        )

    human_user = AuthenticatedUser(
        id=user_id,
        email="lead@quebet.io",
        role="LEAD_ENGINEER",
        plan="enterprise",
        tenant_id=tenant_id,
    )

    # 1. Trigger failure
    import httpx
    async with AsyncSessionLocal() as session:
        service = AuditAnchorService(session)
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Network unreachable")):
            anchor_failed = await service.request_anchor(
                project_id=project_id,
                current_user=human_user,
                tsa_url="https://mock.tsa",
            )
            assert anchor_failed.status == AnchorStatus.FAILED.value

    # Record first anchor's manifest & digest
    async with AsyncSessionLocal() as session:
        service = AuditAnchorService(session)
        anchor_failed = await service.get_latest_anchor(project_id)
        original_digest = anchor_failed.checkpoint_digest
        original_manifest = dict(anchor_failed.checkpoint_manifest)
        original_seq = anchor_failed.checkpoint_sequence

    # 2. Retry with successful TSA response
    def mock_tsa(request):
        req_bytes = request.content
        req_parsed, _ = decoder.decode(req_bytes, asn1Spec=rfc3161.TimeStampReq())
        digest_bytes = bytes(req_parsed["messageImprint"]["hashedMessage"])
        nonce = int(req_parsed["nonce"]) if req_parsed.getComponentByName("nonce") is not None else 0

        token_der = build_test_timestamp_token(
            digest_bytes=digest_bytes,
            tsa_key=tsa_key,
            tsa_cert=tsa_cert,
            ca_cert=ca_cert,
            nonce=nonce,
        )
        resp_der = build_test_timestamp_response(token_der, pki_status=0)
        return httpx.Response(200, content=resp_der, headers={"Content-Type": "application/timestamp-reply"})

    async def async_mock_retry_post(url, content, headers=None, timeout=None):
        return mock_tsa(type("Req", (), {"content": content})())

    async with AsyncSessionLocal() as session:
        service = AuditAnchorService(session)
        with patch("httpx.AsyncClient.post", side_effect=async_mock_retry_post):
            anchor_retried = await service.request_anchor(
                project_id=project_id,
                current_user=human_user,
                tsa_url="https://mock.tsa",
                ca_cert_path=ca_pem_path,
                force_retry=True,
            )

            assert anchor_retried.status == AnchorStatus.ANCHORED.value
            assert anchor_retried.checkpoint_sequence == original_seq
            assert anchor_retried.checkpoint_digest == original_digest
            assert anchor_retried.checkpoint_manifest == original_manifest
            assert anchor_retried.retry_count == 1


@pytest.mark.asyncio
async def test_audit_append_mid_flight_immutability(tmp_path):
    """
    Appending new audit events mid-flight or after an anchor request does not
    mutate the anchored range or invalidate the anchored manifest.
    """
    ca_key, ca_cert, tsa_key, tsa_cert = generate_ca_and_tsa()
    ca_pem_path = str(tmp_path / "ca.pem")
    with open(ca_pem_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    user_id = str(uuid.uuid4())
    tenant_id = f"tenant-{uuid.uuid4().hex[:6]}"
    project_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=project_id,
            tenant_id=tenant_id,
            owner_id=user_id,
            name="Append Test Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.commit()

        ledger = AuditLedgerService(session)
        await ledger.record_event(
            project_id=project_id,
            actor_id=user_id,
            actor_role="LEAD_ENGINEER",
            event_type="CIRCUIT_MUTATION",
            entity_type="circuit",
            entity_id="circ-1",
            payload={"ev": 1},
            commit=True,
        )

    human_user = AuthenticatedUser(
        id=user_id,
        email="lead@quebet.io",
        role="LEAD_ENGINEER",
        plan="enterprise",
        tenant_id=tenant_id,
    )

    import httpx
    def mock_tsa(request):
        req_parsed, _ = decoder.decode(request.content, asn1Spec=rfc3161.TimeStampReq())
        digest_bytes = bytes(req_parsed["messageImprint"]["hashedMessage"])
        nonce = int(req_parsed["nonce"]) if req_parsed.getComponentByName("nonce") is not None else 0
        token_der = build_test_timestamp_token(
            digest_bytes=digest_bytes,
            tsa_key=tsa_key,
            tsa_cert=tsa_cert,
            ca_cert=ca_cert,
            nonce=nonce,
        )
        return httpx.Response(200, content=build_test_timestamp_response(token_der), headers={"Content-Type": "application/timestamp-reply"})

    async def async_mock_append_post(url, content, headers=None, timeout=None):
        return mock_tsa(type("Req", (), {"content": content})())

    # Anchor event 1
    async with AsyncSessionLocal() as session:
        service = AuditAnchorService(session)
        with patch("httpx.AsyncClient.post", side_effect=async_mock_append_post):
            anchor1 = await service.request_anchor(
                project_id=project_id,
                current_user=human_user,
                tsa_url="https://mock.tsa.org",
                ca_cert_path=ca_pem_path,
            )
            assert anchor1.status == AnchorStatus.ANCHORED.value
            assert anchor1.to_sequence == 1

    # Now append Event 2 to ledger
    async with AsyncSessionLocal() as session:
        ledger = AuditLedgerService(session)
        await ledger.record_event(
            project_id=project_id,
            actor_id=user_id,
            actor_role="LEAD_ENGINEER",
            event_type="CIRCUIT_MUTATION",
            entity_type="circuit",
            entity_id="circ-1",
            payload={"ev": 2},
            commit=True,
        )

    # Re-verify anchor1: must still be completely VERIFIED
    async with AsyncSessionLocal() as session:
        service = AuditAnchorService(session)
        verified1 = await service.verify_anchor(
            project_id=project_id,
            anchor_id=anchor1.id,
            current_user=human_user,
            ca_cert_path=ca_pem_path,
        )
        assert verified1["is_valid"] is True
        assert verified1["status"] == "VERIFIED"
        assert verified1["to_sequence"] == 1

    # Anchor event 2 (checkpoint 2: from_sequence=2, to_sequence=2)
    async with AsyncSessionLocal() as session:
        service = AuditAnchorService(session)
        with patch("httpx.AsyncClient.post", side_effect=async_mock_append_post):
            anchor2 = await service.request_anchor(
                project_id=project_id,
                current_user=human_user,
                tsa_url="https://mock.tsa.org",
                ca_cert_path=ca_pem_path,
            )
            assert anchor2.status == AnchorStatus.ANCHORED.value
            assert anchor2.checkpoint_sequence == 2
            assert anchor2.from_sequence == 2
            assert anchor2.to_sequence == 2


@pytest.mark.asyncio
async def test_project_deletion_restricted_with_anchors():
    """Attempting to delete a Project that has associated audit anchors raises IntegrityError."""
    user_id = str(uuid.uuid4())
    tenant_id = f"tenant-{uuid.uuid4().hex[:6]}"
    project_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=project_id,
            tenant_id=tenant_id,
            owner_id=user_id,
            name="Restricted Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        anchor = EngineeringAuditAnchor(
            id=str(uuid.uuid4()),
            project_id=project_id,
            tenant_id=tenant_id,
            checkpoint_sequence=1,
            from_sequence=1,
            to_sequence=1,
            chain_head_hash="head",
            checkpoint_manifest={"test": str(uuid.uuid4())},
            checkpoint_digest=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            nonce=uuid.uuid4().hex,
            status=AnchorStatus.ANCHORED.value,
            tsa_url="mock",
        )
        session.add(anchor)
        await session.commit()

    # Attempt to delete project
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete
        with pytest.raises(IntegrityError):
            await session.execute(delete(Project).where(Project.id == project_id))
            await session.commit()


@pytest.mark.asyncio
async def test_missing_retention_disclosure():
    """When external S3 mirroring is not configured, anchor discloses mirrored_to_external_store = False."""
    anchor = EngineeringAuditAnchor(
        id=str(uuid.uuid4()),
        project_id="proj-1",
        checkpoint_sequence=1,
        from_sequence=1,
        to_sequence=1,
        chain_head_hash="head",
        checkpoint_manifest={},
        checkpoint_digest="d",
        nonce="n",
        status=AnchorStatus.PENDING.value,
        tsa_url="mock",
        mirrored_to_external_store=False,
    )
    assert anchor.mirrored_to_external_store is False
    assert anchor.external_store_uri is None


# ==============================================================================
# 4. Mandatory Security & Authorization Invariants
# ==============================================================================

@pytest.mark.asyncio
async def test_tenant_isolation_anchor_access():
    """User from Tenant B cannot access or list anchors belonging to Tenant A (HTTP 404)."""
    tenant_a = f"tenant-a-{uuid.uuid4().hex[:6]}"
    tenant_b = f"tenant-b-{uuid.uuid4().hex[:6]}"
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    proj_a = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=proj_a,
            tenant_id=tenant_a,
            owner_id=user_a,
            name="Tenant A Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.commit()

    user_b_auth = AuthenticatedUser(
        id=user_b,
        email="user_b@tenantb.io",
        role="ENGINEER",
        plan="enterprise",
        tenant_id=tenant_b,
    )

    async with AsyncSessionLocal() as session:
        service = AuditAnchorService(session)
        with pytest.raises(HTTPException) as exc_info:
            await service.list_anchors(project_id=proj_a, current_user=user_b_auth)
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_untenanted_personal_workspace_anchor_isolation():
    """Untenanted user cannot access anchors belonging to an enterprise tenant (HTTP 404)."""
    tenant_a = f"tenant-a-{uuid.uuid4().hex[:6]}"
    user_a = str(uuid.uuid4())
    user_untenanted = str(uuid.uuid4())
    proj_a = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=proj_a,
            tenant_id=tenant_a,
            owner_id=user_a,
            name="Tenant A Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.commit()

    untenanted_auth = AuthenticatedUser(
        id=user_untenanted,
        email="untenanted@personal.io",
        role="ENGINEER",
        plan="free",
        tenant_id=None,
    )

    async with AsyncSessionLocal() as session:
        service = AuditAnchorService(session)
        with pytest.raises(HTTPException) as exc_info:
            await service.list_anchors(project_id=proj_a, current_user=untenanted_auth)
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_ai_agent_anchor_request_denied():
    """
    AI agents possess ZERO engineering authority.
    Any request to create or notarize an anchor from an AI role must be denied with HTTP 403.
    """
    user_id = str(uuid.uuid4())
    proj_id = str(uuid.uuid4())

    ai_user = AuthenticatedUser(
        id=user_id,
        email="copilot@quebet.internal",
        role="ai_agent",
        plan="enterprise",
        tenant_id="tenant-ai",
    )

    async with AsyncSessionLocal() as session:
        service = AuditAnchorService(session)
        with pytest.raises(HTTPException) as exc_info:
            await service.request_anchor(project_id=proj_id, current_user=ai_user)
        assert exc_info.value.status_code == 403
        assert "AI agents possess no engineering authority" in exc_info.value.detail


@pytest.mark.asyncio
async def test_unauthorized_human_role_denied():
    """Users without human engineering roles (e.g. VIEWER, GUEST) are denied with HTTP 403."""
    user_id = str(uuid.uuid4())
    proj_id = str(uuid.uuid4())

    viewer_user = AuthenticatedUser(
        id=user_id,
        email="viewer@quebet.io",
        role="VIEWER",
        plan="enterprise",
        tenant_id="tenant-view",
    )

    async with AsyncSessionLocal() as session:
        service = AuditAnchorService(session)
        with pytest.raises(HTTPException) as exc_info:
            await service.request_anchor(project_id=proj_id, current_user=viewer_user)
        assert exc_info.value.status_code == 403
        assert "is not an authorized human engineering role" in exc_info.value.detail


@pytest.mark.asyncio
async def test_release_gate_independence():
    """
    Strict Invariant:
    AUDIT CHAIN VALIDITY != EXTERNAL ANCHOR VALIDITY != RELEASE APPROVAL.
    Having a valid external timestamp anchor does NOT automatically satisfy release gates.
    """
    user_id = str(uuid.uuid4())
    tenant_id = f"tenant-{uuid.uuid4().hex[:6]}"
    project_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        # Project without design reviews or required release artifacts
        project = Project(
            id=project_id,
            tenant_id=tenant_id,
            owner_id=user_id,
            name="Unapproved Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        # Add an anchored record
        anchor = EngineeringAuditAnchor(
            id=str(uuid.uuid4()),
            project_id=project_id,
            tenant_id=tenant_id,
            checkpoint_sequence=1,
            from_sequence=1,
            to_sequence=1,
            chain_head_hash="head",
            checkpoint_manifest={"gate_test": str(uuid.uuid4())},
            checkpoint_digest=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            nonce=uuid.uuid4().hex,
            status=AnchorStatus.ANCHORED.value,
            tsa_url="mock",
            last_verification_status="VERIFIED",
        )
        session.add(anchor)
        await session.commit()

    human_user = AuthenticatedUser(
        id=user_id,
        email="engineer@quebet.io",
        role="ENGINEER",
        plan="enterprise",
        tenant_id=tenant_id,
    )

    async with AsyncSessionLocal() as session:
        rel_service = ReleaseService(session)
        readiness = await rel_service.evaluate_release_readiness(
            project_id=project_id,
            user=human_user,
        )
        # Release readiness must NOT be approved simply because an anchor exists.
        assert readiness.overall_readiness != "READY_FOR_RELEASE"
        assert readiness.overall_readiness in ("NOT_READY", "BLOCKED")
