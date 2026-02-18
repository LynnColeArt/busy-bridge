from typing import Any, Dict, List

import pytest

from busy_bridge.client import Busy38Client, Busy38Error
from busy_bridge.config import Config


def _make_client():
    return Busy38Client(Config(url="http://localhost:8080"))


def test_stream_mission_yields_updates_until_terminal(monkeypatch):
    mission_state_steps = [
        {"mission_id": "m1", "state": "pending"},
        {"mission_id": "m1", "state": "running"},
        {"mission_id": "m1", "state": "approved"},
    ]
    calls = []

    def fake_request(method: str, path: str, **kwargs: Dict[str, Any]):
        calls.append((method, path))
        if path == "/missions/m1":
            return mission_state_steps.pop(0)
        if path == "/missions/m1/notes":
            return {"notes": []}
        raise AssertionError(f"Unexpected request path: {path}")

    client = _make_client()
    monkeypatch.setattr(client, "_request", fake_request)
    monkeypatch.setattr("busy_bridge.client.time.sleep", lambda _: None)

    updates: List[Dict[str, Any]] = list(client.stream_mission("m1", poll_interval=0.0))
    assert [u["mission"]["state"] for u in updates] == ["pending", "running", "approved"]
    assert len(calls) == 6


def test_stream_mission_raises_when_poll_limit_reached(monkeypatch):
    def fake_request(method: str, path: str, **kwargs: Dict[str, Any]):
        if path == "/missions/m2":
            return {"mission_id": "m2", "state": "running"}
        if path == "/missions/m2/notes":
            return {"notes": []}
        raise AssertionError(f"Unexpected request path: {path}")

    client = _make_client()
    monkeypatch.setattr(client, "_request", fake_request)
    monkeypatch.setattr("busy_bridge.client.time.sleep", lambda _: None)

    with pytest.raises(Busy38Error, match="Mission stream timed out"):
        list(client.stream_mission("m2", poll_interval=0.0, max_polls=1))
