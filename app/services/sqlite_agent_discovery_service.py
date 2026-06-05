import unicodedata

import pandas as pd


class SQLiteAgentDiscoveryService:

    def __init__(self, agent_repository):
        self.agent_repository = agent_repository

    def _normalize_text(self, value):
        value = self._clean_value(value)

        if not value:
            return ""

        value = unicodedata.normalize("NFKD", value)
        value = "".join(
            char for char in value
            if not unicodedata.combining(char)
        )

        return value

    def _clean_value(self, value):
        if value is None:
            return ""

        try:
            if pd.isna(value):
                return ""
        except TypeError:
            pass

        text = str(value).strip()

        if text.lower() in {"nan", "none", "null"}:
            return ""

        if text.endswith(".0") and text[:-2].isdigit():
            return text[:-2]

        return text

    def _proper_name_from_last_first(self, name):
        name = self._clean_value(name)

        if "," not in name:
            return name

        last, first = [
            part.strip()
            for part in name.split(",", 1)
        ]

        return f"{first} {last}".strip()

    def _build_aliases(self, agent_name, agent_no):
        proper_name = self._proper_name_from_last_first(agent_name)

        aliases = {
            self._clean_value(agent_no),
            self._clean_value(agent_name),
            proper_name,
            self._normalize_text(agent_name),
            self._normalize_text(proper_name),
        }

        return sorted(
            alias for alias in aliases
            if alias
        )

    def discover_from_surveys(self, surveys):
        created = 0
        updated = 0

        for survey in surveys:
            agent_no = self._clean_value(survey.agent_id)
            agent_name = self._clean_value(survey.agent_name)

            if not agent_no and not agent_name:
                continue

            proper_name = self._proper_name_from_last_first(
                agent_name
            )

            existing_agent_id = (
                self.agent_repository.find_agent_id(agent_no)
                or self.agent_repository.find_agent_id(agent_name)
                or self.agent_repository.find_agent_id(proper_name)
            )

            canonical_agent_id = (
                existing_agent_id
                or agent_no
                or proper_name
                or agent_name
            )

            aliases = self._build_aliases(
                agent_name,
                canonical_agent_id
            )

            agent = {
                "agent_id": canonical_agent_id,
                "employee_id": agent_no,
                "name": proper_name,
                "email": "",
                "nice_name": agent_name,
                "cxone_name": proper_name,
                "status": "Active",
                "supervisor": "",
                "aliases": aliases,
            }

            self.agent_repository.upsert_agent(agent)

            if existing_agent_id:
                updated += 1
            else:
                created += 1

        return {
            "created": created,
            "updated": updated
        }
