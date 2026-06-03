from dataclasses import dataclass

@dataclass
class Transcript:

    call_id: str

    raw_text: str

    customer_sentiment: str

    resolution_type: str

    topics: list
    