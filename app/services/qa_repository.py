class QARepository:

    def __init__(self):
        self.results = {}

    def add(self, qa):
        self.results[qa.call_id] = qa

    def get(self, call_id):
        return self.results.get(call_id)
    
