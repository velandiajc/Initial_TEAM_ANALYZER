import json
from pathlib import Path

from app.models.agent import Agent


class AgentRegistry:

    def __init__(self):
        self.by_agent_id = {}
        self.by_employee_id = {}
        self.by_email = {}
        self.by_name = {}
        self.by_nice_name = {}
        self.by_cxone_name = {}
        self.by_alias = {}

    def _normalize(self, value):
        return str(value).strip().lower()

    def add_agent(self, agent: Agent):

        self.by_agent_id[
            self._normalize(agent.agent_id)
        ] = agent

        self.by_employee_id[
            self._normalize(agent.employee_id)
        ] = agent

        self.by_email[
            self._normalize(agent.email)
        ] = agent

        self.by_name[
            self._normalize(agent.name)
        ] = agent

        self.by_nice_name[
            self._normalize(agent.nice_name)
        ] = agent

        self.by_cxone_name[
            self._normalize(agent.cxone_name)
        ] = agent

        for alias in agent.aliases:
            self.by_alias[
                self._normalize(alias)
            ] = agent

    def get_by_agent_id(self, value):
        return self.by_agent_id.get(
            self._normalize(value)
        )

    def get_by_employee_id(self, value):
        return self.by_employee_id.get(
            self._normalize(value)
        )

    def get_by_email(self, value):
        return self.by_email.get(
            self._normalize(value)
        )

    def get_by_name(self, value):
        return self.by_name.get(
            self._normalize(value)
        )

    def get_by_nice_name(self, value):
        return self.by_nice_name.get(
            self._normalize(value)
        )

    def get_by_cxone_name(self, value):
        return self.by_cxone_name.get(
            self._normalize(value)
        )

    def get_by_alias(self, value):
        return self.by_alias.get(
            self._normalize(value)
        )

    def find_agent(self, value):

        key = self._normalize(value)

        return (
            self.by_agent_id.get(key)
            or self.by_employee_id.get(key)
            or self.by_email.get(key)
            or self.by_name.get(key)
            or self.by_nice_name.get(key)
            or self.by_cxone_name.get(key)
            or self.by_alias.get(key)
        )

    def all_agents(self):
        return list(
            self.by_agent_id.values()
        )

    @classmethod
    def from_json(cls, path):

        registry = cls()

        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(
                f"Agent master file not found: {file_path}"
            )

        payload = json.loads(
            file_path.read_text(
                encoding="utf-8"
            )
        )

        agents = payload.get(
            "agents",
            []
        )

        for item in agents:

            agent = Agent(**item)

            registry.add_agent(agent)

        return registry