class CallRepository:

    def __init__(self):
        self.calls = {}

    def add(self, call):
        self.calls[call.call_id] = call

    def get(self, call_id):
        return self.calls.get(call_id)

    def get_by_agent(self, agent_id):

        return [
            c
            for c in self.calls.values()
            if c.agent_id == agent_id
        ]