from app.services.pci_redaction_service import PCIRedactionService


def test_redacts_luhn_valid_pan_with_common_separators():
    service = PCIRedactionService()

    result = service.redact(
        "Cards 4111 1111 1111 1111 and 5555-5555-5555-4444."
    )

    assert result == "Cards [REDACTED PAN] and [REDACTED PAN]."
    assert service.is_persistence_safe(result)


def test_redacts_contextual_cvv_before_and_after_label():
    service = PCIRedactionService()

    result = service.redact(
        "CVV: 123 and 999 was the card security code."
    )

    assert "123" not in result
    assert "999" not in result
    assert result.count("[REDACTED CVV]") == 2


def test_redacts_pan_before_adjacent_cvv():
    service = PCIRedactionService()

    result = service.redact("4111 1111 1111 1111 cvv 123")

    assert result == "[REDACTED PAN] cvv [REDACTED CVV]"


def test_does_not_redact_invalid_pan_phone_or_standalone_short_number():
    service = PCIRedactionService()
    value = "Order 4111111111111112 phone 5551234567 extension 123."

    assert service.redact(value) == value
    assert not service.contains_pan(value)
    assert not service.contains_cvv(value)


def test_filename_redaction_handles_pan_after_dash_without_touching_uuid():
    service = PCIRedactionService()
    uuid = "60558441-3254-451b-8954-dc8cf015f654"

    assert service.redact_filename_component(
        "call-4111-1111-1111-1111"
    ) == "call-redacted-pan"
    assert service.redact(uuid) == uuid
    assert not service.contains_pan(uuid)
