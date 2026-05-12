"""
Unit tests for the SanitizationChain.

Tests PII redaction, content deduplication, field filtering,
value masking, and text normalization.
"""

from elastro.core.ingest.sanitizers import SanitizationChain


class TestPIIRedaction:
    def test_email_redaction(self) -> None:
        chain = SanitizationChain(redact_pii=True)
        keep, doc = chain.sanitize({"note": "Contact alice@example.com"})
        assert keep is True
        assert "[REDACTED_EMAIL]" in doc["note"]
        assert "alice@example.com" not in doc["note"]

    def test_ssn_redaction(self) -> None:
        chain = SanitizationChain(redact_pii=True)
        _, doc = chain.sanitize({"data": "SSN: 123-45-6789"})
        assert "[REDACTED_SSN]" in doc["data"]
        assert "123-45-6789" not in doc["data"]

    def test_credit_card_redaction(self) -> None:
        chain = SanitizationChain(redact_pii=True)
        _, doc = chain.sanitize({"info": "Card: 4111 1111 1111 1111"})
        assert "[REDACTED_CC]" in doc["info"]

    def test_ipv4_redaction(self) -> None:
        chain = SanitizationChain(redact_pii=True)
        _, doc = chain.sanitize({"log": "Client IP: 192.168.1.100"})
        assert "[REDACTED_IP]" in doc["log"]

    def test_selective_pii_types(self) -> None:
        """Only redact specified PII types."""
        chain = SanitizationChain(redact_pii=True, pii_types=["email"])
        _, doc = chain.sanitize({"msg": "Email: a@b.com, SSN: 123-45-6789"})
        assert "[REDACTED_EMAIL]" in doc["msg"]
        assert "123-45-6789" in doc["msg"]  # SSN not redacted

    def test_non_string_values_untouched(self) -> None:
        chain = SanitizationChain(redact_pii=True)
        _, doc = chain.sanitize({"count": 42, "active": True})
        assert doc["count"] == 42
        assert doc["active"] is True

    def test_no_pii_no_change(self) -> None:
        chain = SanitizationChain(redact_pii=True)
        _, doc = chain.sanitize({"name": "Alice", "age": 30})
        assert doc["name"] == "Alice"


class TestDeduplication:
    def test_duplicate_skipped(self) -> None:
        chain = SanitizationChain(dedup=True)

        keep1, _ = chain.sanitize({"name": "Alice"})
        keep2, _ = chain.sanitize({"name": "Alice"})
        keep3, _ = chain.sanitize({"name": "Bob"})

        assert keep1 is True
        assert keep2 is False  # Duplicate
        assert keep3 is True

    def test_dedup_count(self) -> None:
        chain = SanitizationChain(dedup=True)
        chain.sanitize({"x": 1})
        chain.sanitize({"x": 1})
        chain.sanitize({"x": 1})
        assert chain.dedup_skipped == 2

    def test_reset_dedup(self) -> None:
        chain = SanitizationChain(dedup=True)
        chain.sanitize({"x": 1})
        chain.sanitize({"x": 1})
        assert chain.dedup_skipped == 1

        chain.reset_dedup()
        assert chain.dedup_skipped == 0

        keep, _ = chain.sanitize({"x": 1})
        assert keep is True  # No longer seen as duplicate

    def test_order_independent_hashing(self) -> None:
        """Documents with same fields in different order are deduped."""
        chain = SanitizationChain(dedup=True)
        keep1, _ = chain.sanitize({"a": 1, "b": 2})
        keep2, _ = chain.sanitize({"b": 2, "a": 1})
        assert keep1 is True
        assert keep2 is False


class TestFieldFiltering:
    def test_allowlist(self) -> None:
        chain = SanitizationChain(allow_fields=["name", "email"])
        _, doc = chain.sanitize(
            {"name": "Alice", "email": "a@b.com", "password": "secret"}
        )
        assert "name" in doc
        assert "email" in doc
        assert "password" not in doc

    def test_denylist(self) -> None:
        chain = SanitizationChain(deny_fields=["password", "secret"])
        _, doc = chain.sanitize({"name": "Alice", "password": "123", "secret": "xyz"})
        assert "name" in doc
        assert "password" not in doc
        assert "secret" not in doc

    def test_allowlist_and_denylist(self) -> None:
        """Allowlist is applied first, then denylist removes from the result."""
        chain = SanitizationChain(
            allow_fields=["a", "b", "c"],
            deny_fields=["c"],
        )
        _, doc = chain.sanitize({"a": 1, "b": 2, "c": 3, "d": 4})
        assert doc == {"a": 1, "b": 2}


class TestValueMasking:
    def test_mask_password(self) -> None:
        chain = SanitizationChain(mask_fields=["password"])
        _, doc = chain.sanitize({"name": "Alice", "password": "supersecret"})
        assert doc["password"] == "******"
        assert doc["name"] == "Alice"

    def test_mask_case_insensitive(self) -> None:
        chain = SanitizationChain(mask_fields=["TOKEN"])
        _, doc = chain.sanitize({"token": "abc123"})
        assert doc["token"] == "******"


class TestTrimAndNormalize:
    def test_trim_whitespace(self) -> None:
        chain = SanitizationChain(trim=True)
        _, doc = chain.sanitize({"name": "  Alice  ", "age": 30})
        assert doc["name"] == "Alice"

    def test_lowercase_fields(self) -> None:
        chain = SanitizationChain(lowercase_fields=["status"])
        _, doc = chain.sanitize({"status": "ACTIVE", "name": "Alice"})
        assert doc["status"] == "active"
        assert doc["name"] == "Alice"  # Unaffected

    def test_trim_disabled(self) -> None:
        chain = SanitizationChain(trim=False)
        _, doc = chain.sanitize({"name": "  Alice  "})
        assert doc["name"] == "  Alice  "


class TestChainComposition:
    def test_full_chain(self) -> None:
        """All steps compose correctly in order."""
        chain = SanitizationChain(
            redact_pii=True,
            dedup=True,
            deny_fields=["secret"],
            mask_fields=["password"],
            trim=True,
            lowercase_fields=["status"],
        )

        doc = {
            "name": "  Alice  ",
            "email": "Contact: alice@test.com",
            "status": "ACTIVE",
            "password": "s3cr3t",
            "secret": "should-be-removed",
        }

        keep, result = chain.sanitize(doc)
        assert keep is True
        assert "secret" not in result  # Deny-listed
        assert result["password"] == "******"  # Masked
        assert result["name"] == "Alice"  # Trimmed
        assert result["status"] == "active"  # Lowercased
        assert "[REDACTED_EMAIL]" in result["email"]  # PII redacted

    def test_does_not_mutate_original(self) -> None:
        chain = SanitizationChain(trim=True, mask_fields=["pw"])
        original = {"name": "  Bob  ", "pw": "pass"}
        _, _ = chain.sanitize(original)
        assert original["name"] == "  Bob  "  # Not mutated
