from dataclasses import dataclass


@dataclass
class QAResult:
    call_id: str
    qa_score: float
    verification: bool
    empathy: bool
    ownership: bool
    upsell: bool
    notes: str
    