from dataclasses import dataclass

@dataclass
class Call:

    call_id: str
    agent_id: str

    audio_file: str
    transcript_file: str

    duration: int

    call_date: str

    brand: str
    