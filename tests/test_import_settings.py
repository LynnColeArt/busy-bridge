from pathlib import Path

from click.testing import CliRunner

from busy_bridge.cli import cli
from busy_bridge.config import Config
from busy_bridge.import_settings import detect_installed_system_configs


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

