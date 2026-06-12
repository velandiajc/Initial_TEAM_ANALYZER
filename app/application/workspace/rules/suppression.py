from app.services.pci_redaction_service import PCIRedactionService


class WorkspaceSuppressionRules:
    RESTRICTED_KEY_PARTS = {
        "cardholder",
        "comment",
        "content_reference",
        "customer_email",
        "customer_id",
        "customer_identifier",
        "customer_name",
        "customer_phone",
        "cvv",
        "leadership_note",
        "manager_note",
        "pan",
        "payload",
        "private_note",
        "recording",
        "raw",
        "transcript",
    }
    RESTRICTED_VALUE_MARKERS = (
        "call-recording:",
        "call_recording:",
        "customer-id:",
        "customer:",
        "customer_identifier:",
        "recording:",
        "transcript:",
        "private-note:",
        "private_note:",
        "leadership-note:",
        "leadership_note:",
        "manager-note:",
        "manager_note:",
    )

    def __init__(self):
        self.pci_service = PCIRedactionService()

    def suppress(self, value):
        reasons = set()
        sanitized = self._suppress(value, reasons)
        return sanitized, tuple(sorted(reasons))

    def filter_references(self, references):
        safe = []
        reasons = set()
        for reference in references:
            sanitized, item_reasons = self.suppress(str(reference))
            reasons.update(item_reasons)
            if sanitized != "[SUPPRESSED]":
                safe.append(sanitized)
        return tuple(dict.fromkeys(safe)), tuple(sorted(reasons))

    def _suppress(self, value, reasons):
        if isinstance(value, dict):
            sanitized = {}
            for key, item in value.items():
                normalized = str(key).strip().lower()
                if any(
                    part in normalized
                    for part in self.RESTRICTED_KEY_PARTS
                ):
                    reasons.add("RESTRICTED_FIELD")
                    continue
                sanitized[str(key)] = self._suppress(item, reasons)
            return sanitized
        if isinstance(value, (list, tuple, set)):
            return [
                self._suppress(item, reasons)
                for item in value
            ]
        if isinstance(value, str):
            normalized = value.strip().lower()
            if any(
                marker in normalized
                for marker in self.RESTRICTED_VALUE_MARKERS
            ):
                reasons.add("RESTRICTED_REFERENCE")
                return "[SUPPRESSED]"
            redacted = self.pci_service.redact(value)
            if redacted != value:
                reasons.add("PCI_REDACTED")
            return redacted
        return value
