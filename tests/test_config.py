from pathlib import Path

from busy_bridge.config import Config


def test_from_file_accepts_string_path(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "url: http://localhost:9999\nagent_id: test-agent\ntimeout: 12\n",
        encoding="utf-8",
    )
    cfg = Config.from_file(str(cfg_path))
    assert cfg.url == "http://localhost:9999"
    assert cfg.agent_id == "test-agent"
    assert cfg.timeout == 12


def test_save_roundtrip_model_settings(tmp_path):
    cfg = Config(
        url="http://localhost:8080",
        api_key=None,
        agent_id="busy-bridge",
        timeout=60,
        model_settings={"provider": "openai", "model": "gpt-4o-mini"},
        imported_from="openclaw",
        imported_at="2026-01-01T00:00:00+00:00",
    )
    out_path = cfg.save(tmp_path / "bridge.yaml")
    loaded = Config.from_file(out_path)
    assert loaded.model_settings["provider"] == "openai"
    assert loaded.model_settings["model"] == "gpt-4o-mini"
    assert loaded.imported_from == "openclaw"

