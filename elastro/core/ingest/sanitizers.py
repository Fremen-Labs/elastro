"""
Client-side data sanitization pipeline for the Ingest Engine.

Provides a configurable chain of document transformations applied
**before** data reaches Elasticsearch:

- **PII Redaction** — regex-based detection and masking of emails,
  SSNs, phone numbers, credit cards, and IPv4 addresses.
- **HIPAA PHI Redaction** — extended patterns covering the 18 Safe
  Harbor identifiers: DOB, ZIP codes, NPI, DEA numbers, VINs,
  URLs, IPv6, and field-name heuristics for MRNs, beneficiary IDs,
  device serials, and biometric fields.
- **Financial Data Redaction** — PCI DSS / GLBA patterns for IBANs,
  SWIFT/BIC codes, ABA routing numbers, and Tax IDs (EIN).
- **Content Deduplication** — SHA-256 content hashing with an
  in-memory set for batch-level dedup.
- **Field Filtering** — allowlist / denylist field projection.
- **Value Masking** — pattern-matched field masking (e.g. passwords).
- **Trim & Normalize** — whitespace stripping and optional lowercasing.
"""

import hashlib
import json
import re
import unicodedata
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from elastro.core.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# PII patterns (compiled once, reused across documents)
# ---------------------------------------------------------------------------

PII_PATTERNS: Dict[str, re.Pattern[str]] = {
    # ── Core PII ─────────────────────────────────────────────────
    "email": re.compile(r"\b[\w.+-]+@[\w.-]+\.\w{2,}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone_us": re.compile(r"\b(?:\+1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    # ── HIPAA PHI Additions ──────────────────────────────────────
    "dob": re.compile(
        r"\b(?:0[1-9]|1[0-2])[/\-](?:0[1-9]|[12]\d|3[01])[/\-](?:19|20)\d{2}\b"
    ),
    "zip_code": re.compile(r"\b\d{5}(?:-\d{4})?\b"),
    "url": re.compile(r"https?://[^\s\"'<>]+"),
    "ipv6": re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b"),
    "vin": re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b"),
    "dea_number": re.compile(r"\b[A-Za-z]{2}\d{7}\b"),
    "npi": re.compile(r"\b[12]\d{9}\b"),
    # ── Financial Additions ──────────────────────────────────────
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    "swift_bic": re.compile(r"\b[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b"),
    "routing_number": re.compile(r"\b\d{9}\b"),
    "tax_id_ein": re.compile(r"\b\d{2}-\d{7}\b"),
}

# Default replacement tokens per PII type
_REDACT_TOKENS: Dict[str, str] = {
    # Core PII
    "email": "[REDACTED_EMAIL]",
    "ssn": "[REDACTED_SSN]",
    "phone_us": "[REDACTED_PHONE]",
    "credit_card": "[REDACTED_CC]",
    "ipv4": "[REDACTED_IP]",
    # HIPAA PHI
    "dob": "[REDACTED_DOB]",
    "zip_code": "[REDACTED_ZIP]",
    "url": "[REDACTED_URL]",
    "ipv6": "[REDACTED_IP]",
    "vin": "[REDACTED_VIN]",
    "dea_number": "[REDACTED_DEA]",
    "npi": "[REDACTED_NPI]",
    # Financial
    "iban": "[REDACTED_IBAN]",
    "swift_bic": "[REDACTED_SWIFT]",
    "routing_number": "[REDACTED_ROUTING]",
    "tax_id_ein": "[REDACTED_EIN]",
}

# ---------------------------------------------------------------------------
# Compliance profiles — curated subsets of PII patterns
# ---------------------------------------------------------------------------

COMPLIANCE_PROFILES: Dict[str, List[str]] = {
    "hipaa": [
        "email",
        "ssn",
        "npi",
        "dea_number",
        "phone_us",
        "ipv4",
        "ipv6",
        "dob",
        "zip_code",
        "url",
        "vin",
    ],
    "pci": [
        "credit_card",
        "iban",
        "swift_bic",
        "routing_number",
        "tax_id_ein",
    ],
    "financial": [
        "credit_card",
        "iban",
        "swift_bic",
        "routing_number",
        "tax_id_ein",
        "ssn",
    ],
    "all": list(PII_PATTERNS.keys()),
}

# ---------------------------------------------------------------------------
# HIPAA field-name heuristics — fields with no standard regex format
# ---------------------------------------------------------------------------

SENSITIVE_FIELD_NAMES: FrozenSet[str] = frozenset(
    {
        # HIPAA PHI — Medical identifiers
        "mrn",
        "medical_record",
        "medical_record_number",
        "medical_record_no",
        "patient_id",
        "patient_number",
        "beneficiary",
        "beneficiary_id",
        "health_plan_id",
        "health_plan_number",
        "member_id",
        "member_number",
        "subscriber_id",
        "group_number",
        # HIPAA PHI — Device & biometric
        "device_id",
        "device_serial",
        "serial_number",
        "biometric",
        "fingerprint",
        "voiceprint",
        "retina_scan",
        "face_id",
        # HIPAA PHI — License & certificate
        "license_number",
        "drivers_license",
        "dl_number",
        "certificate_number",
        "certificate_id",
        "license_plate",
        "plate_number",
        "vehicle_id",
        # Financial — Account identifiers
        "bank_account",
        "account_number",
        "acct_no",
        "acct_number",
        "routing",
        "routing_number",
        "aba_number",
        "cvv",
        "cvc",
        "security_code",
        "card_number",
        "pan",
        "expiry",
        "expiration_date",
        "pin",
        # General secrets
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "private_key",
    }
)


# ---------------------------------------------------------------------------
# Sanitization chain
# ---------------------------------------------------------------------------


class SanitizationChain:
    """Configurable, ordered chain of document sanitization steps.

    Each step is independently toggleable.  The chain is immutable after
    construction — create a new instance to change settings.

    Args:
        redact_pii: Replace detected PII with redaction tokens.
        pii_types: Which PII types to redact (default: all).
        compliance: Compliance profile name ('hipaa', 'pci', 'financial',
            'all').  Overrides ``pii_types`` when set.
        dedup: Enable content-hash deduplication.
        allow_fields: If set, only these fields pass through (allowlist).
        deny_fields: If set, these fields are removed (denylist).
        mask_fields: Field name patterns whose values are replaced with
            ``******`` (e.g. ``["password", "secret", "token"]``).
        mask_sensitive_fields: Automatically mask fields whose names match
            the ``SENSITIVE_FIELD_NAMES`` registry (HIPAA + Financial).
        trim: Strip leading/trailing whitespace from string values.
        normalize_unicode: Apply NFC unicode normalization.
        lowercase_fields: Field names whose values are lowercased.
    """

    def __init__(
        self,
        *,
        redact_pii: bool = False,
        pii_types: Optional[List[str]] = None,
        compliance: Optional[str] = None,
        dedup: bool = False,
        allow_fields: Optional[List[str]] = None,
        deny_fields: Optional[List[str]] = None,
        mask_fields: Optional[List[str]] = None,
        mask_sensitive_fields: bool = False,
        trim: bool = True,
        normalize_unicode: bool = False,
        lowercase_fields: Optional[List[str]] = None,
    ) -> None:
        self.redact_pii = redact_pii
        self.mask_sensitive_fields = mask_sensitive_fields

        # Resolve PII types from compliance profile or explicit list
        if compliance and compliance in COMPLIANCE_PROFILES:
            self.pii_types: List[str] = COMPLIANCE_PROFILES[compliance]
            self.compliance: Optional[str] = compliance
            # Auto-enable redaction when a compliance profile is set
            if not self.redact_pii:
                self.redact_pii = True
        else:
            self.pii_types = pii_types or list(PII_PATTERNS.keys())
            self.compliance = compliance

        self.dedup = dedup
        self.allow_fields: Optional[FrozenSet[str]] = (
            frozenset(allow_fields) if allow_fields else None
        )
        self.deny_fields: FrozenSet[str] = frozenset(deny_fields or [])

        # Merge explicit mask fields with sensitive field registry
        _mask = set(f.lower() for f in (mask_fields or []))
        if mask_sensitive_fields:
            _mask |= SENSITIVE_FIELD_NAMES
        self.mask_fields: FrozenSet[str] = frozenset(_mask)

        self.trim = trim
        self.normalize_unicode = normalize_unicode
        self.lowercase_fields: FrozenSet[str] = frozenset(lowercase_fields or [])

        # Dedup state — in-memory content hash set
        self._seen_hashes: Set[str] = set()
        self._dedup_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sanitize(self, doc: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Apply the full sanitization chain to a document.

        Returns:
            Tuple of ``(keep, sanitized_doc)``.  If ``keep`` is False the
            document should be skipped (e.g. duplicate).
        """
        result = doc.copy()

        # 1. Field filtering (allowlist / denylist)
        result = self._filter_fields(result)

        # 2. Value masking
        if self.mask_fields:
            result = self._mask_values(result)

        # 3. Trim & normalize strings
        if self.trim or self.normalize_unicode or self.lowercase_fields:
            result = self._normalize_strings(result)

        # 4. PII redaction
        if self.redact_pii:
            result = self._redact_pii(result)

        # 5. Deduplication (must be last — operates on final content)
        if self.dedup:
            if self._is_duplicate(result):
                return False, result

        return True, result

    @property
    def dedup_skipped(self) -> int:
        """Number of documents skipped by deduplication."""
        return self._dedup_count

    def reset_dedup(self) -> None:
        """Clear the dedup hash set (useful between batches / files)."""
        self._seen_hashes.clear()
        self._dedup_count = 0

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    def _filter_fields(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Apply allowlist / denylist field filtering."""
        if self.allow_fields is not None:
            doc = {k: v for k, v in doc.items() if k in self.allow_fields}
        if self.deny_fields:
            doc = {k: v for k, v in doc.items() if k not in self.deny_fields}
        return doc

    def _mask_values(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Replace values of sensitive-named fields with mask token."""
        for key in list(doc.keys()):
            if key.lower() in self.mask_fields:
                doc[key] = "******"
        return doc

    def _normalize_strings(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Trim, normalize unicode, and lowercase configured fields."""
        for key, value in list(doc.items()):
            if not isinstance(value, str):
                continue
            if self.trim:
                value = value.strip()
            if self.normalize_unicode:
                value = unicodedata.normalize("NFC", value)
            if key in self.lowercase_fields:
                value = value.lower()
            doc[key] = value
        return doc

    def _redact_pii(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Scan string values for PII patterns and replace with tokens."""
        for key, value in list(doc.items()):
            if not isinstance(value, str):
                continue
            for pii_name in self.pii_types:
                pattern = PII_PATTERNS.get(pii_name)
                if pattern is None:
                    continue
                token = _REDACT_TOKENS.get(pii_name, "[REDACTED]")
                value = pattern.sub(token, value)
            doc[key] = value
        return doc

    def _is_duplicate(self, doc: Dict[str, Any]) -> bool:
        """Check if document content has already been seen."""
        content_hash = hashlib.sha256(
            json.dumps(doc, sort_keys=True, default=str).encode()
        ).hexdigest()
        if content_hash in self._seen_hashes:
            self._dedup_count += 1
            return True
        self._seen_hashes.add(content_hash)
        return False
