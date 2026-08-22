"""Tests for the in-process replay runtime registry (multi-user isolation)."""

from formula1_strategy_tool.acquisition import replay as replay_mod
from formula1_strategy_tool.acquisition import replay_registry

_BASE64URL = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


def test_registry_creates_unique_opaque_ids(monkeypatch):
    started: list[int] = []
    monkeypatch.setattr(
        replay_mod.ReplayController,
        "start",
        lambda self, session_key, speed=10.0: started.append(session_key),
    )

    registry = replay_registry.ReplayRegistry()
    a = registry.create(100, speed=10)
    b = registry.create(200, speed=50)

    assert a.replay_id != b.replay_id
    assert len(a.replay_id) >= 32
    assert set(a.replay_id) <= _BASE64URL
    assert set(b.replay_id) <= _BASE64URL
    assert started == [100, 200]


def test_registry_get_returns_only_that_runtime(monkeypatch):
    monkeypatch.setattr(replay_mod.ReplayController, "start", lambda *a, **k: None)

    registry = replay_registry.ReplayRegistry()
    a = registry.create(100)
    b = registry.create(200)

    assert registry.get(a.replay_id).controller is a.controller
    assert registry.get(b.replay_id).controller is b.controller
    assert registry.get("unknown-id") is None


def test_registry_stop_removes_only_that_runtime(monkeypatch):
    stopped = []
    monkeypatch.setattr(replay_mod.ReplayController, "start", lambda *a, **k: None)
    monkeypatch.setattr(
        replay_mod.ReplayController, "stop", lambda self: stopped.append(self)
    )

    registry = replay_registry.ReplayRegistry()
    a = registry.create(100)
    b = registry.create(200)

    registry.stop(a.replay_id)

    assert registry.get(a.replay_id) is None
    assert registry.get(b.replay_id) is not None
    assert stopped == [a.controller]


def test_registry_cleanup_expired_reaps_only_abandoned(monkeypatch):
    stopped = []
    monkeypatch.setattr(replay_mod.ReplayController, "start", lambda *a, **k: None)
    monkeypatch.setattr(
        replay_mod.ReplayController, "stop", lambda self: stopped.append(self)
    )

    clock = {"now": 0.0}
    registry = replay_registry.ReplayRegistry(
        inactivity_ttl=100.0, now=lambda: clock["now"]
    )
    a = registry.create(100)
    b = registry.create(200)

    clock["now"] = 150.0
    registry.touch(b.replay_id)

    assert registry.cleanup_expired() == 1
    assert registry.get(a.replay_id) is None
    assert registry.get(b.replay_id) is not None
    assert stopped == [a.controller]
