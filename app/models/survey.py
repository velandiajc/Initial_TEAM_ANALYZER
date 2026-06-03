from dataclasses import dataclass


@dataclass
class Survey:
    contact_id: str
    agent_id: str
    agent_name: str
    score: float
    comment: str
    survey_date: str
    brand: str
    media_type: str
    top_reason: str
    disposition: str
    