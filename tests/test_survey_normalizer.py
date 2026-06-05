import math

import pandas as pd

from app.services.survey_normalizer import SurveyNormalizer


def normalize_one(row):
    normalizer = SurveyNormalizer(pd.DataFrame([row]))
    return normalizer.survey_type, normalizer.normalize()[0]


def test_call_survey_row_normalizes_correctly():
    survey_type, row = normalize_one({
        "Date of Survey": "2026-06-01",
        "contactid": "CALL-123",
        "brand": "Brand A",
        "media_type_name": "Voice",
        "agentname": "Agent One",
        "agentno": "A001",
        "OSAT": 9,
        "OSAT Score Comment": "Great help",
        "Top Reason Call": "Shipping",
        "disposition_name": "Resolved",
    })

    assert survey_type == "call"
    assert row["contact_id"] == "CALL-123"
    assert row["agent_id"] == "A001"
    assert row["agent_name"] == "Agent One"
    assert row["score"] == 9.0
    assert row["comment"] == "Great help"
    assert row["survey_date"] == "2026-06-01"
    assert row["brand"] == "Brand A"
    assert row["media_type"] == "Voice"
    assert row["top_reason"] == "Shipping"
    assert row["disposition"] == "Resolved"


def test_chat_survey_row_normalizes_correctly():
    survey_type, row = normalize_one({
        "Date of Survey": "2026-06-02",
        "brand": "Brand B",
        "afn": "Chat Agent",
        "chat id": "CHAT-123",
        "ano": "C001",
        "CSAT": 8,
        "CSAT Score Comment": "Fast chat",
        "Top Reason Call": "Returns",
    })

    assert survey_type == "chat"
    assert row["contact_id"] == "CHAT-123"
    assert row["agent_id"] == "C001"
    assert row["agent_name"] == "Chat Agent"
    assert row["score"] == 8.0
    assert row["comment"] == "Fast chat"
    assert row["survey_date"] == "2026-06-02"
    assert row["brand"] == "Brand B"
    assert row["media_type"] == "Chat"
    assert row["top_reason"] == "Returns"
    assert row["disposition"] == ""


def test_missing_optional_columns_do_not_crash():
    survey_type, row = normalize_one({
        "contactid": "CALL-456",
        "agentname": "Agent Two",
        "agentno": "A002",
        "OSAT": 7,
    })

    assert survey_type == "call"
    assert row["contact_id"] == "CALL-456"
    assert row["media_type"] == "Phone Call"
    assert row["comment"] == ""
    assert row["disposition"] == ""


def test_nan_comments_become_empty_strings():
    _, row = normalize_one({
        "contactid": "CALL-789",
        "agentname": "Agent Three",
        "agentno": "A003",
        "OSAT": 10,
        "OSAT Score Comment": math.nan,
    })

    assert row["comment"] == ""


def test_chat_comment_fallback_uses_improve_experience_comment():
    _, row = normalize_one({
        "chat id": "CHAT-456",
        "afn": "Chat Agent",
        "ano": "C002",
        "CSAT": 6,
        "CSAT Score Comment": "",
        "Improve Experience Comment": "Needed clearer next steps",
    })

    assert row["comment"] == "Needed clearer next steps"


def test_call_score_uses_osat_before_csat():
    _, row = normalize_one({
        "contactid": "CALL-987",
        "agentname": "Agent Four",
        "agentno": "A004",
        "OSAT": 9,
        "CSAT": 3,
    })

    assert row["score"] == 9.0


def test_chat_score_uses_csat():
    _, row = normalize_one({
        "chat id": "CHAT-789",
        "afn": "Chat Agent",
        "ano": "C003",
        "CSAT": 5,
    })

    assert row["score"] == 5.0


def test_numeric_ids_become_clean_strings():
    _, row = normalize_one({
        "chat id": 12345.0,
        "afn": "Chat Agent",
        "ano": 7001.0,
        "CSAT": 9,
    })

    assert row["contact_id"] == "12345"
    assert row["agent_id"] == "7001"
