# PCI Boundary Statement

## Policy

TEAM_ANALYZER does not store cardholder data. The platform is not a system of
record for payment card numbers, card verification values, magnetic-stripe
data, PINs, or payment authorization secrets.

Audio and operational source systems must suppress payment data before
delivery to TEAM_ANALYZER. Sprint 5.1 adds defense in depth for accidental
exposure; these controls do not expand TEAM_ANALYZER into the PCI cardholder
data environment.

## Enforced Controls

- Luhn-valid PAN candidates containing 13 to 19 digits are detected.
- PANs with spaces or hyphens are redacted before transcript and report writes.
- Contextual CVV, CVC, CID, card verification, and security-code values are
  replaced before persistence.
- Transcript, survey, workbook inventory, scorecard, risk report, and audit
  output paths use the shared redaction service.
- Every SQLite text column is protected by insert and update triggers backed by
  the shared detector. Unsanitized card data causes the transaction to fail.
- Audit metadata drops governed sensitive keys and redacts card data in
  otherwise permitted values.

Invalid Luhn candidates, ordinary telephone numbers, and standalone short
numbers without a card-security context are not treated as cardholder data.

## Operating Procedure

When a persistence attempt is rejected:

1. Do not bypass or disable the PCI trigger.
2. Remove the source artifact from the processing boundary.
3. Redact the source through the approved service or request a sanitized export.
4. Record the event without copying the sensitive value into logs or audit
   metadata.
5. Escalate confirmed cardholder-data exposure to Security and Compliance.

Raw recordings and source transcripts remain local operational inputs and are
excluded from version control. Retention, deletion, and access controls for
those source systems remain the responsibility of the approved operational
owner.
