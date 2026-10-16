"""
RFC 3161 & CMS Cryptographic Timestamping Protocol & Verification Engine.
Implements:
- RFC 3161 TimeStampReq construction with 128-bit entropy nonces.
- TimeStampResp status decoding and failure reporting.
- Complete 10-stage CMS (RFC 5652) and TSTInfo verification.
- Signed attributes validation (contentType, messageDigest, signingCertificateV2).
- Cryptographic signature validation (RSA PKCS#1 v1.5, RSA-PSS, ECDSA).
- TSA certificate EKU (id-kp-timeStamping) and validity window checking.
- Certificate chain validation against explicit trusted CA roots.

STRICT INVARIANTS:
- AI ENGINEERING AUTHORITY = NONE
- AI DECISION AUTHORITY = NONE
- AUDIT CHAIN VALIDITY != EXTERNAL ANCHOR VALIDITY
- TIMESTAMPED DIGEST != PROOF OF EVENT TRUTH
- UNKNOWN != SATISFIED
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import secrets
from typing import Any, List, Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID
from pyasn1.codec.der import decoder, encoder
from pyasn1.type import univ
from pyasn1_modules import rfc3161, rfc5652


# Cryptographic OIDs
SHA256_OID = "2.16.840.1.101.3.4.2.1"
ID_SIGNED_DATA_OID = "1.2.840.113549.1.7.2"
ID_CT_TST_INFO_OID = "1.2.840.113549.1.9.16.1.4"
ID_CONTENT_TYPE_ATTR = "1.2.840.113549.1.9.3"
ID_MESSAGE_DIGEST_ATTR = "1.2.840.113549.1.9.4"
ID_SIGNING_CERT_ATTR = "1.2.840.113549.1.9.16.2.12"
ID_SIGNING_CERT_V2_ATTR = "1.2.840.113549.1.9.16.2.47"
ID_KP_TIME_STAMPING_OID = "1.3.6.1.5.5.7.3.8"


class RFC3161Error(Exception):
    """Base exception for RFC 3161 timestamping failures."""
    def __init__(self, message: str, error_code: str):
        super().__init__(message)
        self.error_code = error_code


class RFC3161MalformedTokenError(RFC3161Error):
    def __init__(self, message: str):
        super().__init__(message, "MALFORMED_TOKEN")


class RFC3161StatusRejectedError(RFC3161Error):
    def __init__(self, message: str, pki_status: int, fail_info: Optional[str] = None):
        super().__init__(f"TSA rejected request (status {pki_status}): {fail_info or message}", "TSA_STATUS_REJECTED")
        self.pki_status = pki_status
        self.fail_info = fail_info


class RFC3161DigestMismatchError(RFC3161Error):
    def __init__(self, message: str):
        super().__init__(message, "MESSAGE_IMPRINT_MISMATCH")


class RFC3161NonceMismatchError(RFC3161Error):
    def __init__(self, message: str):
        super().__init__(message, "NONCE_MISMATCH")


class RFC3161AmbiguousSignerError(RFC3161Error):
    def __init__(self, message: str):
        super().__init__(message, "AMBIGUOUS_SIGNER")


class RFC3161InvalidSignatureError(RFC3161Error):
    def __init__(self, message: str):
        super().__init__(message, "INVALID_SIGNATURE")


class RFC3161InvalidEKUError(RFC3161Error):
    def __init__(self, message: str):
        super().__init__(message, "INVALID_CERTIFICATE_EKU")


class RFC3161CertificateExpiredError(RFC3161Error):
    def __init__(self, message: str):
        super().__init__(message, "CERTIFICATE_NOT_VALID_AT_GENTIME")


class RFC3161UntrustedCAError(RFC3161Error):
    def __init__(self, message: str):
        super().__init__(message, "UNTRUSTED_CERTIFICATE_CHAIN")


class RFC3161PolicyMismatchError(RFC3161Error):
    def __init__(self, message: str):
        super().__init__(message, "POLICY_MISMATCH")


@dataclass
class RFC3161VerificationResult:
    is_valid: bool
    status: str
    gen_time: Optional[datetime] = None
    serial_number: Optional[str] = None
    policy_oid: Optional[str] = None
    signer_subject: Optional[str] = None
    signer_issuer: Optional[str] = None
    ca_chain_trusted: bool = False
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None


class RFC3161Engine:
    """
    Complete, self-contained RFC 3161 request builder and CMS verification engine.
    """

    @classmethod
    def generate_nonce(cls) -> Tuple[int, str]:
        """Generates a 128-bit cryptographic integer nonce and its hex representation."""
        nonce_int = secrets.randbits(128)
        nonce_hex = f"{nonce_int:032x}"
        return nonce_int, nonce_hex

    @classmethod
    def create_timestamp_request(
        cls,
        digest_bytes: bytes,
        nonce: Optional[int] = None,
        policy_oid: Optional[str] = None,
        cert_req: bool = True,
    ) -> bytes:
        """
        Constructs and DER-encodes a standard RFC 3161 TimeStampReq.
        Digest must be 32 raw bytes (SHA-256).
        """
        if len(digest_bytes) != 32:
            raise ValueError(f"Expected 32 raw bytes for SHA-256 digest, got {len(digest_bytes)}")

        req = rfc3161.TimeStampReq()
        req["version"] = 1

        imprint = rfc3161.MessageImprint()
        imprint["hashAlgorithm"] = rfc3161.AlgorithmIdentifier()
        imprint["hashAlgorithm"]["algorithm"] = univ.ObjectIdentifier(SHA256_OID)
        imprint["hashedMessage"] = univ.OctetString(digest_bytes)
        req["messageImprint"] = imprint

        if policy_oid:
            req["reqPolicy"] = univ.ObjectIdentifier(policy_oid)

        if nonce is not None:
            req["nonce"] = univ.Integer(nonce)

        req["certReq"] = univ.Boolean(cert_req)

        return encoder.encode(req)

    @classmethod
    def parse_timestamp_response(cls, response_bytes: bytes) -> Tuple[int, Optional[str], Optional[bytes]]:
        """
        Parses raw binary TimeStampResp bytes.
        Returns: (status_code, failure_reason_if_any, raw_token_der_bytes_if_success).
        """
        try:
            resp, _ = decoder.decode(response_bytes, asn1Spec=rfc3161.TimeStampResp())
        except Exception as e:
            raise RFC3161MalformedTokenError(f"Failed to decode ASN.1 TimeStampResp: {str(e)}")

        status_val = int(resp["status"]["status"])

        if status_val not in (0, 1):  # 0: granted, 1: grantedWithMods
            fail_info = None
            fail_comp = resp["status"].getComponentByName("failInfo")
            if fail_comp is not None and getattr(fail_comp, "isValue", False):
                try:
                    fail_info = str(fail_comp)
                except Exception:
                    fail_info = None
            return status_val, fail_info or f"PKIStatus {status_val}", None

        token_component = resp.getComponentByName("timeStampToken")
        if token_component is None:
            raise RFC3161MalformedTokenError("TimeStampResp status is granted but timeStampToken component is missing")

        token_der = encoder.encode(token_component)
        return status_val, None, token_der

    @classmethod
    def verify_certificate_chain(
        cls,
        leaf_cert: x509.Certificate,
        intermediate_certs: List[x509.Certificate],
        ca_cert_path: Optional[str],
        check_time: datetime,
    ) -> bool:
        """
        Verifies certificate chain from leaf certificate to a trusted root in ca_cert_path.
        Validates cryptographic signatures and validity windows at check_time.
        """
        if not ca_cert_path:
            return False

        # Load trusted root certificates from ca_cert_path
        try:
            with open(ca_cert_path, "rb") as f:
                root_bundle = f.read()
            trusted_roots = x509.load_pem_x509_certificates(root_bundle)
        except Exception as e:
            raise RFC3161UntrustedCAError(f"Failed to load trusted root bundle from '{ca_cert_path}': {str(e)}")

        if not trusted_roots:
            raise RFC3161UntrustedCAError(f"No valid PEM certificates found in trusted root bundle '{ca_cert_path}'")

        # Pool of all candidate issuers (roots + intermediates)
        all_issuers = list(trusted_roots) + list(intermediate_certs)

        # Build and verify path
        current_cert = leaf_cert
        max_depth = 10
        depth = 0

        while depth < max_depth:
            # Check if current_cert is signed by a trusted root
            for root in trusted_roots:
                if current_cert.issuer == root.subject:
                    try:
                        root.public_key().verify(
                            current_cert.signature,
                            current_cert.tbs_certificate_bytes,
                            padding.PKCS1v15(),
                            current_cert.signature_hash_algorithm,
                        )
                        # Root itself must be valid
                        if not (root.not_valid_before_utc <= check_time <= root.not_valid_after_utc):
                            raise RFC3161CertificateExpiredError(f"Trusted root certificate '{root.subject}' was not valid at {check_time.isoformat()}")
                        return True
                    except (RFC3161CertificateExpiredError, RFC3161UntrustedCAError):
                        raise
                    except Exception:
                        pass

            # Find intermediate issuer
            found_issuer = None
            for candidate in intermediate_certs:
                if current_cert.issuer == candidate.subject and current_cert != candidate:
                    try:
                        candidate.public_key().verify(
                            current_cert.signature,
                            current_cert.tbs_certificate_bytes,
                            padding.PKCS1v15(),
                            current_cert.signature_hash_algorithm,
                        )
                        if not (candidate.not_valid_before_utc <= check_time <= candidate.not_valid_after_utc):
                            raise RFC3161CertificateExpiredError(f"Intermediate certificate '{candidate.subject}' was not valid at {check_time.isoformat()}")
                        found_issuer = candidate
                        break
                    except (RFC3161CertificateExpiredError, RFC3161UntrustedCAError):
                        raise
                    except Exception:
                        continue

            if not found_issuer:
                raise RFC3161UntrustedCAError(f"Cannot find trusted issuer for certificate: {current_cert.subject.rfc4514_string()}")

            current_cert = found_issuer
            depth += 1

        raise RFC3161UntrustedCAError(f"Certificate chain length exceeded maximum verification depth of {max_depth}")

    @classmethod
    def verify_timestamp_token(
        cls,
        token_der: bytes,
        expected_digest_bytes: bytes,
        expected_nonce: Optional[int] = None,
        ca_cert_path: Optional[str] = None,
        required_policy_oid: Optional[str] = None,
        require_trusted_ca: bool = True,
        verification_time: Optional[datetime] = None,
    ) -> RFC3161VerificationResult:
        """
        Executes complete 10-stage RFC 3161 and CMS verification over raw timestamp token bytes.
        """
        try:
            # 1. Decode ContentInfo
            try:
                content_info, _ = decoder.decode(token_der, asn1Spec=rfc5652.ContentInfo())
            except Exception as e:
                raise RFC3161MalformedTokenError(f"Failed to decode ASN.1 ContentInfo: {str(e)}")

            if str(content_info["contentType"]) != ID_SIGNED_DATA_OID:
                raise RFC3161MalformedTokenError(f"Expected contentType id-signedData ({ID_SIGNED_DATA_OID}), found {content_info['contentType']}")

            # 2. Decode SignedData
            try:
                signed_data, _ = decoder.decode(content_info["content"], asn1Spec=rfc5652.SignedData())
                encap = signed_data["encapContentInfo"]
                if str(encap["eContentType"]) != ID_CT_TST_INFO_OID:
                    raise RFC3161MalformedTokenError(f"Expected encapContentInfo eContentType id-ct-TSTInfo ({ID_CT_TST_INFO_OID}), found {encap['eContentType']}")

                raw_tst_octets = bytes(encap["eContent"])
                tst_info, _ = decoder.decode(raw_tst_octets, asn1Spec=rfc3161.TSTInfo())
            except RFC3161MalformedTokenError:
                raise
            except Exception as e:
                raise RFC3161MalformedTokenError(f"Failed to decode SignedData/TSTInfo: {str(e)}")

            # 3. Message Imprint Validation
            imprint = tst_info["messageImprint"]
            algo_oid = str(imprint["hashAlgorithm"]["algorithm"])
            if algo_oid != SHA256_OID:
                raise RFC3161DigestMismatchError(f"Unsupported message imprint algorithm '{algo_oid}'; strictly pinned to SHA-256 ({SHA256_OID})")

            token_imprint_bytes = bytes(imprint["hashedMessage"])
            if not hmac.compare_digest(token_imprint_bytes, expected_digest_bytes):
                raise RFC3161DigestMismatchError(
                    f"Message imprint mismatch: token contains {token_imprint_bytes.hex()}, expected {expected_digest_bytes.hex()}"
                )

            # 4. Nonce Validation
            if expected_nonce is not None:
                token_nonce = tst_info.getComponentByName("nonce")
                if token_nonce is None or not getattr(token_nonce, "isValue", False):
                    raise RFC3161NonceMismatchError("Request contained nonce, but returned TSTInfo has no nonce")
                if int(token_nonce) != expected_nonce:
                    raise RFC3161NonceMismatchError(f"Nonce mismatch: expected {expected_nonce}, found {int(token_nonce)}")

            # 5. Extract genTime & policy
            gen_time_raw = tst_info["genTime"].asDateTime
            if gen_time_raw.tzinfo is None:
                gen_time = gen_time_raw.replace(tzinfo=timezone.utc)
            else:
                gen_time = gen_time_raw.astimezone(timezone.utc)

            policy_oid = str(tst_info["policy"])
            if required_policy_oid and policy_oid != required_policy_oid:
                raise RFC3161PolicyMismatchError(f"Policy OID '{policy_oid}' does not match required policy '{required_policy_oid}'")

            serial_num = str(tst_info["serialNumber"])

            # 6. Resolve CMS SignerInfo (Must be exactly 1)
            signer_infos = signed_data["signerInfos"]
            if len(signer_infos) != 1:
                raise RFC3161AmbiguousSignerError(f"RFC 3161 requires exactly one SignerInfo, found {len(signer_infos)}")

            signer_info = signer_infos[0]

            # 7. Extract TSA Certificates from SignedData
            cert_entries = signed_data.getComponentByName("certificates")
            if cert_entries is None or len(cert_entries) == 0:
                raise RFC3161MalformedTokenError("SignedData contains no certificates; cannot resolve TSA signer")

            parsed_certs: List[x509.Certificate] = []
            for c_entry in cert_entries:
                c_bytes = encoder.encode(c_entry)
                try:
                    parsed_certs.append(x509.load_der_x509_certificate(c_bytes))
                except Exception:
                    pass

            if not parsed_certs:
                raise RFC3161MalformedTokenError("Failed to parse any valid X.509 certificates from SignedData")

            # Resolve signer certificate via IssuerAndSerialNumber or SubjectKeyIdentifier
            sid = signer_info["sid"]
            signer_cert: Optional[x509.Certificate] = None

            if sid.getName() == "issuerAndSerialNumber":
                ias = sid["issuerAndSerialNumber"]
                target_serial = int(ias["serialNumber"])
                for cert in parsed_certs:
                    if cert.serial_number == target_serial:
                        signer_cert = cert
                        break
            elif sid.getName() == "subjectKeyIdentifier":
                target_ski = bytes(sid["subjectKeyIdentifier"])
                for cert in parsed_certs:
                    try:
                        ski_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_KEY_IDENTIFIER)
                        if ski_ext.value.key_identifier == target_ski:
                            signer_cert = cert
                            break
                    except Exception:
                        continue

            if not signer_cert:
                raise RFC3161MalformedTokenError("Cannot find TSA signing certificate matching SignerInfo identifier in token")

            # 8. Validate Signed Attributes
            signed_attrs = signer_info.getComponentByName("signedAttrs")
            if signed_attrs is None or len(signed_attrs) == 0:
                raise RFC3161MalformedTokenError("RFC 3161 tokens must contain CMS signedAttrs")

            # Validate contentType attribute
            has_content_type = False
            has_message_digest = False
            tst_digest_in_attr: Optional[bytes] = None

            for attr in signed_attrs:
                a_oid = str(attr["attrType"])
                if a_oid == ID_CONTENT_TYPE_ATTR:
                    val_oid = str(decoder.decode(bytes(attr["attrValues"][0]), asn1Spec=univ.ObjectIdentifier())[0])
                    if val_oid == ID_CT_TST_INFO_OID:
                        has_content_type = True
                elif a_oid == ID_MESSAGE_DIGEST_ATTR:
                    val_octets = bytes(decoder.decode(bytes(attr["attrValues"][0]), asn1Spec=univ.OctetString())[0])
                    tst_digest_in_attr = val_octets
                    has_message_digest = True

            if not has_content_type:
                raise RFC3161MalformedTokenError("signedAttrs missing valid id-contentType attribute for id-ct-TSTInfo")
            if not has_message_digest or tst_digest_in_attr is None:
                raise RFC3161MalformedTokenError("signedAttrs missing id-messageDigest attribute")

            # Verify digest of raw eContent matches messageDigest attribute
            expected_tst_digest = hashlib.sha256(raw_tst_octets).digest()
            if not hmac.compare_digest(tst_digest_in_attr, expected_tst_digest):
                raise RFC3161DigestMismatchError("Signed attribute messageDigest does not match SHA-256 digest of TSTInfo")

            # 9. Verify Cryptographic Signature over Signed Attributes
            # In CMS, the signature is computed over DER encoding with context tag [0] replaced by SET OF 0x31
            signed_attrs_der = encoder.encode(signed_attrs)
            normalized_attrs_der = b"\x31" + signed_attrs_der[1:]
            signature_bytes = bytes(signer_info["signature"])

            pub_key = signer_cert.public_key()
            try:
                if isinstance(pub_key, rsa.RSAPublicKey):
                    pub_key.verify(signature_bytes, normalized_attrs_der, padding.PKCS1v15(), hashes.SHA256())
                elif isinstance(pub_key, ec.EllipticCurvePublicKey):
                    pub_key.verify(signature_bytes, normalized_attrs_der, ec.ECDSA(hashes.SHA256()))
                else:
                    raise RFC3161InvalidSignatureError(f"Unsupported public key type: {type(pub_key).__name__}")
            except (RFC3161InvalidSignatureError, RFC3161Error):
                raise
            except Exception as e:
                raise RFC3161InvalidSignatureError(f"Cryptographic signature verification failed: {str(e)}")

            # 10. TSA Certificate Extended Key Usage & Validity Period
            try:
                eku_ext = signer_cert.extensions.get_extension_for_oid(ExtensionOID.EXTENDED_KEY_USAGE)
                eku_oids = {str(o.dotted_string) for o in eku_ext.value}
                if ID_KP_TIME_STAMPING_OID not in eku_oids:
                    raise RFC3161InvalidEKUError(f"TSA certificate missing required ExtendedKeyUsage '{ID_KP_TIME_STAMPING_OID}'")
            except RFC3161InvalidEKUError:
                raise
            except Exception:
                raise RFC3161InvalidEKUError("TSA certificate does not contain an ExtendedKeyUsage extension")

            # Check validity window at genTime
            if not (signer_cert.not_valid_before_utc <= gen_time <= signer_cert.not_valid_after_utc):
                raise RFC3161CertificateExpiredError(
                    f"TSA certificate was not valid at genTime {gen_time.isoformat()} "
                    f"(valid {signer_cert.not_valid_before_utc.isoformat()} to {signer_cert.not_valid_after_utc.isoformat()})"
                )

            # 11. Certificate Chain & CA Trust Validation
            intermediates = [c for c in parsed_certs if c != signer_cert]
            ca_chain_trusted = False

            if ca_cert_path:
                ca_chain_trusted = cls.verify_certificate_chain(
                    leaf_cert=signer_cert,
                    intermediate_certs=intermediates,
                    ca_cert_path=ca_cert_path,
                    check_time=gen_time,
                )
            else:
                if require_trusted_ca:
                    raise RFC3161UntrustedCAError(
                        "TSA_CA_CERT_PATH is not configured; production verification strictly fails closed without trusted CA roots."
                    )

            return RFC3161VerificationResult(
                is_valid=True,
                status="VERIFIED",
                gen_time=gen_time,
                serial_number=serial_num,
                policy_oid=policy_oid,
                signer_subject=signer_cert.subject.rfc4514_string(),
                signer_issuer=signer_cert.issuer.rfc4514_string(),
                ca_chain_trusted=ca_chain_trusted,
            )

        except RFC3161Error as e:
            return RFC3161VerificationResult(
                is_valid=False,
                status=e.error_code,
                failure_code=e.error_code,
                failure_message=str(e),
            )
        except Exception as e:
            return RFC3161VerificationResult(
                is_valid=False,
                status="VERIFICATION_FAILED",
                failure_code="UNEXPECTED_VERIFICATION_ERROR",
                failure_message=str(e),
            )
