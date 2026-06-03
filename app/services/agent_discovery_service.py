import json
import unicodedata
from pathlib import Path


class AgentDiscoveryService:

    def __init__(self, master_file_path):
        self.master_file_path = Path(
            master_file_path
        )

    def _normalize_text(self, value):

        if value is None:
            return ""

        value = str(value).strip()

        value = unicodedata.normalize(
            "NFKD",
            value
        )

        value = "".join(
            char
            for char in value
            if not unicodedata.combining(char)
        )

        return value

    def _proper_name_from_last_first(
        self,
        name
    ):
        """
        Briceño, Analyn
        ->
        Analyn Briceño
        """

        name = str(name).strip()

        if "," not in name:
            return name

        last, first = [
            part.strip()
            for part in name.split(",", 1)
        ]

        return f"{first} {last}".strip()

    def _build_aliases(
        self,
        agent_name,
        agent_no
    ):

        proper_name = (
            self._proper_name_from_last_first(
                agent_name
            )
        )

        normalized_proper_name = (
            self._normalize_text(
                proper_name
            )
        )

        normalized_original_name = (
            self._normalize_text(
                agent_name
            )
        )

        aliases = {
            str(agent_name).strip(),
            proper_name,
            normalized_original_name,
            normalized_proper_name,
            str(agent_no).strip(),
        }

        return sorted(
            alias
            for alias in aliases
            if alias
        )

    def _load_master(self):

        if not self.master_file_path.exists():

            self.master_file_path.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            default_payload = {
                "metadata": {
                    "version": "1.0",
                    "last_updated": "",
                    "created_by": "TEAM_ANALYZER"
                },
                "agents": [],
                "teams": [],
                "supervisors": [],
                "brands": []
            }

            self.master_file_path.write_text(
                json.dumps(
                    default_payload,
                    indent=4,
                    ensure_ascii=False
                ),
                encoding="utf-8"
            )

        return json.loads(
            self.master_file_path.read_text(
                encoding="utf-8"
            )
        )

    def _save_master(
        self,
        payload
    ):

        self.master_file_path.write_text(
            json.dumps(
                payload,
                indent=4,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

    def discover_from_surveys(
        self,
        surveys
    ):

        payload = self._load_master()

        agents = payload.get(
            "agents",
            []
        )

        existing_ids = {
            str(
                agent.get(
                    "agent_id",
                    ""
                )
            ).strip()
            for agent in agents
        }

        created_count = 0
        updated_count = 0

        for survey in surveys:

            agent_no = str(
                survey.agent_id
            ).strip()

            agent_name = str(
                survey.agent_name
            ).strip()

            if (
                not agent_no
                and not agent_name
            ):
                continue

            proper_name = (
                self._proper_name_from_last_first(
                    agent_name
                )
            )

            aliases = self._build_aliases(
                agent_name,
                agent_no
            )

            if agent_no not in existing_ids:

                new_agent = {
                    "agent_id": agent_no,
                    "employee_id": agent_no,
                    "name": proper_name,
                    "email": "",
                    "nice_name": agent_name,
                    "cxone_name": proper_name,
                    "status": "Active",
                    "supervisor": "",
                    "aliases": aliases
                }

                agents.append(
                    new_agent
                )

                existing_ids.add(
                    agent_no
                )

                created_count += 1

            else:

                for agent in agents:

                    if (
                        str(
                            agent.get(
                                "agent_id",
                                ""
                            )
                        ).strip()
                        == agent_no
                    ):

                        current_aliases = set(
                            agent.get(
                                "aliases",
                                []
                            )
                        )

                        merged_aliases = sorted(
                            current_aliases.union(
                                aliases
                            )
                        )

                        agent[
                            "aliases"
                        ] = merged_aliases

                        updated_count += 1

                        break

        payload[
            "agents"
        ] = agents

        self._save_master(
            payload
        )

        return {
            "created": created_count,
            "updated": updated_count,
            "total_agents": len(
                agents
            )
        }