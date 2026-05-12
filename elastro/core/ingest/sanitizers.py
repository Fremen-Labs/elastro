"""
Client-side data sanitization pipeline for the Ingest Engine.

Provides a configurable chain of document transformations applied
**before** data reaches Elasticsearch:

- **PII Redaction** — regex-based detection and masking of emails,
  SSNs, phone numbers, credit cards, and IPv4 addresses.
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
    "email": re.compile(r"\b[\w.+-]+@[\w.-]+\.\w{2,}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone_us": re.compile(r"\b(?:\+1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

# Default replacement tokens per PII type
_REDACT_TOKENS: Dict[str, str] = {
    "email": "[REDACTED_EMAIL]",
    "ssn": "[REDACTED_SSN]",
    "phone_us": "[REDACTED_PHONE]",
    "credit_card": "[REDACTED_CC]",
    "ipv4": "[REDACTED_IP]",
}


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
        dedup: Enable content-hash deduplication.
        allow_fields: If set, only these fields pass through (allowlist).
        deny_fields: If set, these fields are removed (denylist).
        mask_fields: Field name patterns whose values are replaced with
            ``******`` (e.g. ``["password", "secret", "token"]``).
        trim: Strip leading/trailing whitespace from string values.
        normalize_unicode: Apply NFC unicode normalization.
        lowercase_fields: Field names whose values are lowercased.
    """

    def __init__(
        self,
        *,
        redact_pii: bool = False,
        pii_types: Optional[List[str]] = None,
        dedup: bool = False,
        allow_fields: Optional[List[str]] = None,
        deny_fields: Optional[List[str]] = None,
        mask_fields: Optional[List[str]] = None,
        trim: bool = True,
        normalize_unicode: bool = False,
        lowercase_fields: Optional[List[str]] = None,
    ) -> None:
        self.redact_pii = redact_pii
        self.pii_types: List[str] = pii_types or list(PII_PATTERNS.keys())
        self.dedup = dedup
        self.allow_fields: Optional[FrozenSet[str]] = (
            frozenset(allow_fields) if allow_fields else None
        )
        self.deny_fields: FrozenSet[str] = frozenset(deny_fields or [])
        self.mask_fields: FrozenSet[str] = frozenset(
            f.lower() for f in (mask_fields or [])
        )
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
