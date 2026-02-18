from click.testing import CliRunner

from busy_bridge.cli import cli
from busy_bridge.client import Busy38Client


def test_mission_start_follow_runs_stream(monkeypatch, tmp_path):
    cfg_file = tmp_path / "bridge.yaml"
    cfg_file.write_text("url: http://localhost:8080\n", encoding="utf-8")

    monkeypatch.setattr(
        Busy38Client,
        "start_mission",
        lambda self, *_, **__: {"mission_id": "m1"},
    )
    monkeypatch.setattr(
        Busy38Client,
        "stream_mission",
        lambda self, mission_id: iter(
            [
                {
                    "mission": {"mission_id": "m1", "state": "running"},
                    "notes": [],
                },
                {
                    "mission": {"mission_id": "m1", "state": "approved"},
                    "notes": [],
                },
            ]
        ),
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["--config", str(cfg_file), "mission", "start", "build docs", "--follow"])
    assert result.exit_code == 0
    assert "Mission started: m1" in result.output
    assert "Mission state: running" in result.output
    assert "Mission state: approved" in result.output
