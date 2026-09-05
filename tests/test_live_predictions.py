"""Tests that live predictions are scored from live state only, for any session type."""

import asyncio

import pandas as pd

from formula1_strategy_tool.acquisition.live_state import LiveState
from formula1_strategy_tool.api import routes as routes_mod


def test_valid_live_features_return_live_predictions(monkeypatch):
    feat = pd.DataFrame({"driver_number": [4], "lap_number": [25]})
    monkeypatch.setattr(routes_mod, "features_from_live", lambda state: feat)
    monkeypatch.setattr(
        routes_mod,
        "predict_feature_rows",
        lambda latest, model_dir: [
            {
                "driver_number": 4,
                "lap_number": 25,
                "pit_within_3_laps": 0.55,
                "pit_within_5_laps": 0.72,
                "pit_within_7_laps": 0.84,
                "predicted_next_compound": "HARD",
                "predicted_pit_window_start": 26,
                "predicted_pit_window_end": 30,
                "compound_probabilities": None,
                "updated_at": "2026-06-14T18:34:10Z",
            }
        ],
    )

    result = routes_mod._model_predictions()

    assert len(result) == 1
    assert result[0].driver_number == 4
    assert result[0].pit_within_5_laps == 0.72
    # The prediction was scored from the live buffer, not a CSV snapshot.
    assert result[0].lap_number == 25


def test_no_live_features_yields_no_prediction(monkeypatch):
    monkeypatch.setattr(routes_mod, "features_from_live", lambda state: None)

    result = routes_mod._model_predictions()

    assert result == []
    # The historical CSV fallback was removed, so an empty live buffer can
    # never silently substitute historical predictions.
    assert not hasattr(routes_mod, "_csv_predictions")
    assert not hasattr(routes_mod, "_csv_fallback_enabled")


def test_predictions_endpoint_survives_inference_exception(monkeypatch):
    from fastapi.testclient import TestClient

    from formula1_strategy_tool.main import app

    def boom(state):
        raise RuntimeError("model failure")

    monkeypatch.setattr(routes_mod, "features_from_live", boom)

    response = TestClient(app).get("/api/predictions")
    assert response.status_code == 200
    assert response.json() == []


def test_qualifying_without_intervals_builds_features():
    """A Qualifying buffer with laps but no intervals still yields features."""
    state = LiveState()
    state.update(
        "v1/sessions",
        {
            "session_key": 1,
            "session_type": "Qualifying",
            "session_name": "Qualifying",
            "year": 2026,
        },
    )
    state.update(
        "v1/laps",
        {
            "meeting_key": 100,
            "session_key": 1,
            "driver_number": 4,
            "lap_number": 12,
            "date_start": "2026-07-26T13:00:00+00:00",
            "lap_duration": 90.0,
            "duration_sector_1": 30.0,
            "duration_sector_2": 30.0,
            "duration_sector_3": 30.0,
            "is_pit_out_lap": False,
        },
    )
    state.update(
        "v1/stints",
        {
            "meeting_key": 100,
            "session_key": 1,
            "driver_number": 4,
            "stint_number": 1,
            "lap_start": 1,
            "lap_end": None,
            "compound": "SOFT",
            "tyre_age_at_start": 0,
        },
    )
    state.update(
        "v1/position",
        {"driver_number": 4, "date": "2026-07-26T13:01:30+00:00", "position": 1},
    )

    feat = routes_mod.features_from_live(state)

    assert feat is not None
    assert not feat.empty
    # No interval stream means no interval features — never invented zeros.
    assert "gap_to_leader" not in feat.columns
    assert "interval_ahead" not in feat.columns


def test_non_race_session_reaches_inference(monkeypatch):
    """A Qualifying session with features still runs model inference."""
    state = LiveState()
    state.update(
        "v1/sessions",
        {
            "session_key": 1,
            "session_type": "Qualifying",
            "session_name": "Qualifying",
            "date_start": "2026-07-26T13:00:00+00:00",
            "date_end": "2026-07-26T15:00:00+00:00",
        },
    )
    state.update(
        "v1/laps", {"driver_number": 4, "lap_number": 12, "lap_duration": 90.0}
    )

    feat = pd.DataFrame({"driver_number": [4], "lap_number": [12]})
    monkeypatch.setattr(routes_mod, "features_from_live", lambda s: feat)

    captured: list[pd.DataFrame] = []
    monkeypatch.setattr(
        routes_mod,
        "predict_feature_rows",
        lambda latest, model_dir: captured.append(latest)
        or [
            {
                "driver_number": 4,
                "lap_number": 12,
                "pit_within_3_laps": 0.1,
                "pit_within_5_laps": 0.2,
                "pit_within_7_laps": 0.3,
                "predicted_next_compound": "SOFT",
                "predicted_pit_window_start": 13,
                "predicted_pit_window_end": 17,
                "compound_probabilities": None,
                "updated_at": "2026-06-14T18:34:10Z",
            }
        ],
    )

    result = routes_mod._predictions_from_state(state)

    assert len(captured) == 1
    assert list(captured[0]["driver_number"]) == [4]
    assert len(result) == 1
    assert result[0].driver_number == 4


def test_websocket_broadcaster_sends_driver_update_when_prediction_fails():
    from formula1_strategy_tool.api.websocket import Broadcaster, ConnectionManager

    state = LiveState()
    manager = ConnectionManager()

    class FakeWebSocket:
        def __init__(self):
            self.sent: list[dict] = []

        async def accept(self):
            pass

        async def send_json(self, message):
            self.sent.append(message)

        async def close(self):
            pass

    def raising_prediction_source():
        raise RuntimeError("inference failed")

    broadcaster = Broadcaster(
        manager, state=state, prediction_source=raising_prediction_source
    )
    ws = FakeWebSocket()
    manager.active.add(ws)

    state.update(
        "v1/drivers",
        {
            "driver_number": 4,
            "full_name": "Lando Norris",
            "name_acronym": "NOR",
            "team_name": "McLaren",
            "team_colour": "FF8000",
        },
    )
    state.update(
        "v1/laps",
        {"driver_number": 4, "lap_number": 25, "lap_duration": 75.0},
    )

    asyncio.run(broadcaster.flush())

    types = {message["type"] for message in ws.sent}
    assert "driver_update" in types
    assert "prediction_update" not in types
