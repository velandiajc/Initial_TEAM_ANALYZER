from dataclasses import replace

from app.services.pci_redaction_service import PCIRedactionService


class TranscriptRepository:

    def __init__(self):
        self.transcripts = {}
        self.pci_redaction_service = PCIRedactionService()

    def add(self, transcript):
        sanitized = replace(
            transcript,
            raw_text=self.pci_redaction_service.redact(transcript.raw_text),
        )
        self.transcripts[sanitized.call_id] = sanitized

    def get(self, call_id):
        return self.transcripts.get(call_id)
