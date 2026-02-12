from pathlib import Path

from click.testing import CliRunner

from busy_bridge.cli import cli
from busy_bridge.config import Config
from busy_bridge.import_settings import (
    DetectionResult,
    detect_installed_system_configs,
    import_detection_to_squid_store,
)


def test_detect_installed_system_configs_openclaw(tmp_path, monkeypatch):
    root = tmp_path / "scan_root"
    cfg_path = root / ".config" / "openclaw" / "config.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        "llm:\n"
        "  provider: openai\n"
        "  model: gpt-4.1-mini\n"
        "  base_url: https://api.openai.com/v1\n"
        "  temperature: 0.2\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BUSY_BRIDGE_IMPORT_SCAN_DIRS", str(root))

    found = detect_installed_system_configs(source="openclaw")
    assert len(found) == 1
    hit = found[0]
    assert hit.system == "openclaw"
    assert hit.config_path == cfg_path.resolve()
    assert hit.model_settings["provider"] == "openai"
    assert hit.model_settings["model"] == "gpt-4.1-mini"


def test_cli_settings_import_writes_config(tmp_path, monkeypatch):
    root = tmp_path / "scan_root"
    detected = root / ".config" / "openclaw" / "config.yaml"
    detected.parent.mkdir(parents=True, exist_ok=True)
    detected.write_text(
        "inference:\n"
        "  provider: anthropic\n"
        "  model: claude-3-7-sonnet\n"
        "  temperature: 0.1\n",
        encoding="utf-8",
    )

    cfg_file = tmp_path / "bridge.yaml"
    cfg_file.write_text("url: http://localhost:8080\n", encoding="utf-8")

    monkeypatch.setenv("BUSY_BRIDGE_IMPORT_SCAN_DIRS", str(root))
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["--config", str(cfg_file), "settings", "import", "--source", "openclaw"],
    )
    assert res.exit_code == 0, res.output
    saved = Config.from_file(cfg_file)
    assert saved.model_settings["provider"] == "anthropic"
    assert saved.model_settings["model"] == "claude-3-7-sonnet"
    assert saved.imported_from == "openclaw"


def test_detect_opencode_env_secrets(tmp_path, monkeypatch):
    root = tmp_path / "scan_root"
    env_path = root / ".opencode" / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(
        "OPENAI_API_KEY=sk-test-1234567890abcdef\n"
        "ANTHROPIC_API_KEY=anthropic-abcdef1234567890\n"
        "AGENT_NAME=Kat the Engineer\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BUSY_BRIDGE_IMPORT_SCAN_DIRS", str(root))

    found = detect_installed_system_configs(source="opencode")
    assert len(found) == 1
    hit = found[0]
    assert hit.system == "opencode"
    assert hit.config_path == env_path.resolve()
    assert "openai_api_key" in hit.secrets
    assert "anthropic_api_key" in hit.secrets


def test_import_detection_to_squid_store_uses_keystore(monkeypatch, tmp_path):
    saved = []

    class FakeStore:
        # Intentionally not named db_path, to ensure bridge uses positional ctor.
        def __init__(self, path):
            self.db_path = path

        def save_password(self, **kwargs):
            saved.append(kwargs)

        def close(self):
            return None

    import busy_bridge.import_settings as mod

    monkeypatch.setattr(mod, "_resolve_keystore_class", lambda: FakeStore)

    detection = DetectionResult(
        system="openclaw",
        config_path=Path("/tmp/.openclaw/config.yaml"),
        model_settings={"provider": "openai", "model": "gpt-4o-mini"},
        agent_settings={"agent_name": "Kat"},
        secrets={"openai_api_key": "sk-abcdefghijklmnopqrstuvwxyz"},
    )
    out = import_detection_to_squid_store(
        detection,
        db_path=tmp_path / "keystore.duckdb",
        target_agent_id="busy-bridge",
        actor="busy-bridge",
    )
    assert out.success is True
    assert out.imported_secret_count == 1
    assert out.imported_settings_count == 1
    assert len(saved) == 2
    names = sorted(x.get("name") for x in saved)
    assert names == ["import.openclaw.openai_api_key", "import.openclaw.settings"]


def test_import_detection_to_squid_store_writes_settings_even_if_empty(monkeypatch, tmp_path):
    saved = []

    class FakeStore:
        def __init__(self, path):
            self.db_path = path

        def save_password(self, **kwargs):
            saved.append(kwargs)

        def close(self):
            return None

    import busy_bridge.import_settings as mod

    monkeypatch.setattr(mod, "_resolve_keystore_class", lambda: FakeStore)

    detection = DetectionResult(
        system="opencode",
        config_path=Path("/tmp/.opencode/.env"),
        model_settings={},
        agent_settings={},
        secrets={"openai_api_key": "sk-abcdefghijklmnopqrstuvwxyz"},
    )
    out = import_detection_to_squid_store(
        detection,
        db_path=tmp_path / "keystore.duckdb",
        target_agent_id="busy-bridge",
        actor="busy-bridge",
        import_settings=True,
        import_secrets=True,
    )
    assert out.success is True
    assert out.imported_secret_count == 1
    assert out.imported_settings_count == 1
