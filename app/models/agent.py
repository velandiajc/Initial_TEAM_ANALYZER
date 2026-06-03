from dataclasses import dataclass, field


@dataclass
class Agent:
    agent_id: str
    employee_id: str
    name: str
    email: str
    nice_name: str
    cxone_name: str
    status: str
    supervisor: str
    aliases: list[str] = field(default_factory=list)
    