import math
from decimal import Decimal, InvalidOperation

import pandas as pd


class SurveyNormalizer:
    UNKNOWN = "unknown"
    CALL = "call"
    CHAT = "chat"

    def __init__(self, dataframe):
        self.dataframe = dataframe
        self.source_columns = self._build_source_columns(dataframe.columns)
        self.survey_type = self.detect_survey_type()

    def _normalize_column_name(self, column_name):
        return " ".join(str(column_name).strip().lower().split())

    def _build_source_columns(self, columns):
        return {
            self._normalize_column_name(column): column
            for column in columns
        }

    def _has_column(self, column_name):
        return self._normalize_column_name(column_name) in self.source_columns

    def detect_survey_type(self):
        has_chat_id = self._has_column("chat id")
        has_csat = self._has_column("CSAT")
        has_afn = self._has_column("afn")

        if has_chat_id or (has_csat and has_afn):
            return self.CHAT

        has_contact_id = self._has_column("contactid")
        has_osat = self._has_column("OSAT")
        has_agent_name = self._has_column("agentname")

        if has_contact_id or (has_osat and has_agent_name):
            return self.CALL

        return self.UNKNOWN

    def _source_column(self, column_name):
        return self.source_columns.get(
            self._normalize_column_name(column_name)
        )

    def _clean_value(self, value):
        if value is None:
            return ""

        try:
            if pd.isna(value):
                return ""
        except TypeError:
            pass

        if isinstance(value, float) and math.isfinite(value) and value.is_integer():
            return str(int(value))

        if isinstance(value, Decimal):
            try:
                if value == value.to_integral_value():
                    return str(value.to_integral_value())
            except InvalidOperation:
                pass

        text = str(value).strip()

        if text.lower() in {"nan", "none", "null"}:
            return ""

        if text.endswith(".0"):
            integer_part = text[:-2]

            if integer_part.isdigit():
                return integer_part

        return text

    def _get(self, row, *column_names, default=""):
        for column_name in column_names:
            source_column = self._source_column(column_name)

            if source_column is None:
                continue

            value = self._clean_value(row.get(source_column))

            if value:
                return value

        return default

    def _score(self, row, *column_names):
        value = self._get(row, *column_names)

        if not value:
            return 0.0

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _normalize_call_row(self, row):
        return {
            "contact_id": self._get(row, "contactid"),
            "agent_id": self._get(row, "agentno"),
            "agent_name": self._get(row, "agentname"),
            "score": self._score(row, "OSAT", "CSAT"),
            "comment": self._get(
                row,
                "OSAT Score Comment",
                "CSAT Score Comment",
                "Improve Experience Comment"
            ),
            "survey_date": self._get(row, "Date of Survey"),
            "brand": self._get(row, "brand"),
            "media_type": self._get(
                row,
                "media_type_name",
                default="Phone Call"
            ),
            "top_reason": self._get(row, "Top Reason Call"),
            "disposition": self._get(row, "disposition_name"),
            "survey_type": self.CALL,
            "channel": "Phone Call",
        }

    def _normalize_chat_row(self, row):
        return {
            "contact_id": self._get(row, "chat id"),
            "agent_id": self._get(row, "ano", "icano"),
            "agent_name": self._get(row, "afn"),
            "score": self._score(row, "CSAT"),
            "comment": self._get(
                row,
                "CSAT Score Comment",
                "Improve Experience Comment"
            ),
            "survey_date": self._get(row, "Date of Survey"),
            "brand": self._get(row, "brand"),
            "media_type": self._get(
                row,
                "media_type_name",
                default="Chat"
            ),
            "top_reason": self._get(row, "Top Reason Call"),
            "disposition": self._get(
                row,
                "disposition_name",
                default=""
            ),
            "survey_type": self.CHAT,
            "channel": "Chat",
        }

    def _normalize_unknown_row(self, row):
        return {
            "contact_id": self._get(row, "contactid", "chat id", "Response ID"),
            "agent_id": self._get(row, "agentno", "ano", "icano"),
            "agent_name": self._get(row, "agentname", "afn"),
            "score": self._score(row, "OSAT", "CSAT"),
            "comment": self._get(
                row,
                "OSAT Score Comment",
                "CSAT Score Comment",
                "Improve Experience Comment"
            ),
            "survey_date": self._get(row, "Date of Survey"),
            "brand": self._get(row, "brand"),
            "media_type": self._get(row, "media_type_name"),
            "top_reason": self._get(row, "Top Reason Call"),
            "disposition": self._get(row, "disposition_name"),
            "survey_type": self.UNKNOWN,
            "channel": self.UNKNOWN,
        }

    def normalize(self):
        records = self.dataframe.to_dict(orient="records")

        if self.survey_type == self.CHAT:
            return [
                self._normalize_chat_row(record)
                for record in records
            ]

        if self.survey_type == self.CALL:
            return [
                self._normalize_call_row(record)
                for record in records
            ]

        return [
            self._normalize_unknown_row(record)
            for record in records
        ]
