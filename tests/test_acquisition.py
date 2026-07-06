from datetime import datetime, timedelta, timezone

from formula1_strategy_tool.acquisition.downloader import (
    parse_openf1_datetime,
    safe_name,
    session_is_complete,
)


def test_parse_openf1_datetime_handles_z_suffix():
    parsed = parse_openf1_datetime("2024-03-02T15:00:00Z")
    assert parsed == datetime(2024, 3, 2, 15, 0, tzinfo=timezone.utc)


def test_safe_name_normalizes_spaces_and_punctuation():
    assert safe_name("São Paulo - Race") == "s_o_paulo_-_race"


def test_session_is_complete_when_end_is_old_enough():
    ended = datetime.now(timezone.utc) - timedelta(hours=3)
    session = {"date_end": ended.isoformat().replace("+00:00", "Z")}
    assert session_is_complete(session) is True


def test_session_is_complete_when_end_is_recent():
    ended = datetime.now(timezone.utc) - timedelta(minutes=30)
    session = {"date_end": ended.isoformat().replace("+00:00", "Z")}
    assert session_is_complete(session) is False
