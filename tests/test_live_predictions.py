"""Tests that live predictions never silently fall back to a historical snapshot."""

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
    monkeypatch.delenv("INFERENCE_CSV_FALLBACK", raising=False)

    result = routes_mod._model_predictions()

    assert len(result) == 1
    assert result[0].driver_number == 4
    assert result[0].pit_within_5_laps == 0.72
    # The prediction was scored from the live buffer, not a CSV snapshot.
    assert result[0].lap_number == 25


def test_no_live_features_yields_no_prediction_and_no_csv_fallback(monkeypatch):
    monkeypatch.setattr(routes_mod, "features_from_live", lambda state: None)
    csv_calls: list[int] = []
    monkeypatch.setattr(
        routes_mod, "_csv_predictions", lambda: csv_calls.append(1) or []
    )
    monkeypatch.delenv("INFERENCE_CSV_FALLBACK", raising=False)

    result = routes_mod._model_predictions()

    assert result == []
    assert csv_calls == []


def test_predictions_endpoint_survives_inference_exception(monkeypatch):
    from fastapi.testclient import TestClient

    from formula1_strategy_tool.main import app

    def boom(state):
        raise RuntimeError("model failure")

    monkeypatch.setattr(routes_mod, "features_from_live", boom)
    monkeypatch.delenv("INFERENCE_CSV_FALLBACK", raising=False)

    response = TestClient(app).get("/api/predictions")
    assert response.status_code == 200
    assert response.json() == []


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
