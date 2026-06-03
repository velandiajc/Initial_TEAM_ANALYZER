class TranscriptRepository:

    def __init__(self):
        self.transcripts = {}

    def add(self, transcript):
        self.transcripts[transcript.call_id] = transcript

    def get(self, call_id):
        return self.transcripts.get(call_id)
    