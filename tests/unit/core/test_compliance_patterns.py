"""
Unit tests for HIPAA PHI and Financial data pattern detection and redaction.

Tests cover the extended PII_PATTERNS in sanitizers.py and the
field-name heuristic detection in validators.py.
"""

import pytest

from elastro.core.ingest.sanitizers import (
    PII_PATTERNS,
    SENSITIVE_FIELD_NAMES,
    COMPLIANCE_PROFILES,
    SanitizationChain,
    _REDACT_TOKENS,
)


# ---------------------------------------------------------------------------
# HIPAA PHI pattern tests
# ---------------------------------------------------------------------------


class TestHIPAAPatterns:
    """Validate HIPAA Safe Harbor identifier detection."""

    def test_dob_mm_dd_yyyy_slash(self):
        assert PII_PATTERNS["dob"].search("DOB: 03/15/1985")

    def test_dob_mm_dd_yyyy_dash(self):
        assert PII_PATTERNS["dob"].search("born 12-25-2001 in NYC")

    def test_dob_rejects_invalid_month(self):
        assert not PII_PATTERNS["dob"].search("13/01/1990")

    def test_dob_rejects_invalid_day(self):
        assert not PII_PATTERNS["dob"].search("01/32/1990")

    def test_zip_code_5_digit(self):
        assert PII_PATTERNS["zip_code"].search("ZIP: 90210")

    def test_zip_code_9_digit(self):
        assert PII_PATTERNS["zip_code"].search("ZIP+4: 90210-1234")

    def test_url_http(self):
        assert PII_PATTERNS["url"].search("visit http://example.com/path")

    def test_url_https(self):
        assert PII_PATTERNS["url"].search("at https://secure.site.org/api/v1")

    def test_ipv6_full(self):
        assert PII_PATTERNS["ipv6"].search("addr: 2001:0db8:85a3:0000:0000:8a2e:0370:7334")

    def test_vin_valid_17_chars(self):
        assert PII_PATTERNS["vin"].search("VIN: 1HGBH41JXMN109186")

    def test_vin_rejects_invalid_chars(self):
        # VIN cannot contain I, O, or Q
        assert not PII_PATTERNS["vin"].search("VIN: 1HGBH41IXMN10918O")

    def test_dea_number(self):
        assert PII_PATTERNS["dea_number"].search("DEA# AB1234567")

    def test_npi_10_digit_starting_1(self):
        assert PII_PATTERNS["npi"].search("NPI: 1234567890")

    def test_npi_10_digit_starting_2(self):
        assert PII_PATTERNS["npi"].search("NPI: 2345678901")

    def test_npi_rejects_starting_3(self):
        # NPI must start with 1 or 2
        assert not PII_PATTERNS["npi"].fullmatch("3456789012")


# ---------------------------------------------------------------------------
# Financial pattern tests
# ---------------------------------------------------------------------------


class TestFinancialPatterns:
    """Validate PCI DSS / GLBA financial data detection."""

    def test_iban_german(self):
        assert PII_PATTERNS["iban"].search("IBAN: DE89370400440532013000")

    def test_iban_british(self):
        assert PII_PATTERNS["iban"].search("IBAN: GB29NWBK60161331926819")

    def test_swift_8_char(self):
        assert PII_PATTERNS["swift_bic"].search("SWIFT: DEUTDEFF")

    def test_swift_11_char(self):
        assert PII_PATTERNS["swift_bic"].search("BIC: DEUTDEFF500")

    def test_routing_number_9_digits(self):
        assert PII_PATTERNS["routing_number"].search("routing: 021000021")

    def test_tax_id_ein(self):
        assert PII_PATTERNS["tax_id_ein"].search("EIN: 12-3456789")

    def test_credit_card_visa(self):
        assert PII_PATTERNS["credit_card"].search("CC: 4111111111111111")

    def test_credit_card_with_spaces(self):
        assert PII_PATTERNS["credit_card"].search("CC: 4111 1111 1111 1111")


# ---------------------------------------------------------------------------
# Sensitive field-name heuristic tests
# ---------------------------------------------------------------------------


class TestSensitiveFieldNames:
    """Validate field-name heuristic registry for HIPAA/Financial."""

    @pytest.mark.parametrize(
        "field",
        [
            "mrn",
            "medical_record_number",
            "patient_id",
            "beneficiary_id",
            "health_plan_id",
            "device_serial",
            "serial_number",
            "license_number",
            "drivers_license",
            "bank_account",
            "account_number",
            "cvv",
            "security_code",
            "password",
            "api_key",
        ],
    )
    def test_sensitive_field_in_registry(self, field):
        assert field in SENSITIVE_FIELD_NAMES

    def test_regular_field_not_flagged(self):
        assert "first_name" not in SENSITIVE_FIELD_NAMES
        assert "status" not in SENSITIVE_FIELD_NAMES
        assert "description" not in SENSITIVE_FIELD_NAMES


# ---------------------------------------------------------------------------
# Compliance profile tests
# ---------------------------------------------------------------------------


class TestComplianceProfiles:
    """Validate compliance profile pattern subsets."""

    def test_hipaa_profile_includes_phi_patterns(self):
        hipaa = COMPLIANCE_PROFILES["hipaa"]
        assert "ssn" in hipaa
        assert "dob" in hipaa
        assert "npi" in hipaa
        assert "dea_number" in hipaa
        assert "zip_code" in hipaa

    def test_hipaa_profile_excludes_financial(self):
        hipaa = COMPLIANCE_PROFILES["hipaa"]
        assert "credit_card" not in hipaa
        assert "iban" not in hipaa

    def test_pci_profile_includes_financial(self):
        pci = COMPLIANCE_PROFILES["pci"]
        assert "credit_card" in pci
        assert "iban" in pci
        assert "swift_bic" in pci
        assert "routing_number" in pci

    def test_pci_profile_excludes_hipaa(self):
        pci = COMPLIANCE_PROFILES["pci"]
        assert "npi" not in pci
        assert "dob" not in pci

    def test_all_profile_covers_everything(self):
        all_prof = COMPLIANCE_PROFILES["all"]
        for key in PII_PATTERNS:
            assert key in all_prof


# ---------------------------------------------------------------------------
# SanitizationChain integration tests
# ---------------------------------------------------------------------------


class TestSanitizationChainCompliance:
    """Test the SanitizationChain with compliance profiles."""

    def test_hipaa_compliance_auto_enables_redaction(self):
        chain = SanitizationChain(compliance="hipaa")
        assert chain.redact_pii is True

    def test_hipaa_redacts_dob(self):
        chain = SanitizationChain(compliance="hipaa")
        keep, doc = chain.sanitize({"notes": "Patient DOB 03/15/1985"})
        assert keep is True
        assert "[REDACTED_DOB]" in doc["notes"]

    def test_hipaa_redacts_npi(self):
        # Use NPI starting with 2 to avoid collision with phone_us pattern
        chain = SanitizationChain(compliance="hipaa")
        keep, doc = chain.sanitize({"provider": "NPI 2345678901"})
        assert "[REDACTED_NPI]" in doc["provider"]

    def test_hipaa_does_not_redact_credit_card(self):
        chain = SanitizationChain(compliance="hipaa")
        keep, doc = chain.sanitize({"payment": "4111111111111111"})
        # HIPAA profile doesn't include credit_card, so value should be unchanged
        assert doc["payment"] == "4111111111111111"

    def test_pci_redacts_iban(self):
        chain = SanitizationChain(compliance="pci")
        keep, doc = chain.sanitize({"bank": "IBAN DE89370400440532013000"})
        assert "[REDACTED_IBAN]" in doc["bank"]

    def test_pci_redacts_swift(self):
        chain = SanitizationChain(compliance="pci")
        keep, doc = chain.sanitize({"swift": "Code DEUTDEFF500"})
        assert "[REDACTED_SWIFT]" in doc["swift"]

    def test_mask_sensitive_fields_masks_mrn(self):
        chain = SanitizationChain(mask_sensitive_fields=True)
        keep, doc = chain.sanitize({"mrn": "MR-12345", "name": "Alice"})
        assert doc["mrn"] == "******"
        assert doc["name"] == "Alice"

    def test_mask_sensitive_fields_masks_bank_account(self):
        chain = SanitizationChain(mask_sensitive_fields=True)
        keep, doc = chain.sanitize(
            {"bank_account": "123456789", "status": "active"}
        )
        assert doc["bank_account"] == "******"
        assert doc["status"] == "active"

    def test_all_redaction_tokens_have_patterns(self):
        """Every pattern key must have a corresponding redaction token."""
        for key in PII_PATTERNS:
            assert key in _REDACT_TOKENS, f"Missing redaction token for pattern '{key}'"
