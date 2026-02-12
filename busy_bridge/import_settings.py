"""Detection and import of settings from other agent systems."""

from __future__ import annotations

import json
import os
import re
import importlib.util
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

try:
    import tomllib
except Exception:  # pragma: no cover
    tomllib = None


SYSTEM_CONFIG_CANDIDATES: Dict[str, List[str]] = {
    "openclaw": [
        ".config/openclaw/config.yaml",
        ".config/openclaw/config.yml",
        ".config/openclaw/config.json",
        ".config/openclaw/.env",
        ".openclaw/config.yaml",
        ".openclaw/config.yml",
        ".openclaw/config.json",
        ".openclaw/.env",
    ],
    "opencode": [
        ".config/opencode/config.yaml",
        ".config/opencode/config.yml",
        ".config/opencode/config.json",
        ".config/opencode/config.toml",
        ".config/opencode/.env",
        ".opencode/config.yaml",
        ".opencode/config.yml",
        ".opencode/config.json",
        ".opencode/config.toml",
        ".opencode/.env",
    ],
    "codex": [
        ".config/codex/config.yaml",
        ".config/codex/config.yml",
        ".config/codex/config.json",
        ".config/codex/config.toml",
        ".config/codex/.env",
        ".codex/config.yaml",
        ".codex/config.yml",
        ".codex/config.json",
        ".codex/config.toml",
        ".codex/.env",
    ],
    "claude": [
        ".config/claude/config.yaml",
        ".config/claude/config.yml",
        ".config/claude/settings.json",
        ".config/claude/.env",
        ".claude/config.yaml",
        ".claude/config.yml",
        ".claude/settings.json",
        ".claude/.env",
    ],
    "blossom": [
        ".config/blossom/config.yaml",
        ".config/blossom/config.yml",
    ],
    "busy": [
        ".config/busy/config.yaml",
        ".config/busy/config.yml",
    ],
    "openwebui": [
        ".config/openwebui/config.json",
        ".config/openwebui/.env",
    ],
    "litellm": [
        ".config/litellm/config.yaml",
        ".config/litellm/config.yml",
        ".config/litellm/config.toml",
        ".config/litellm/.env",
    ],
}

SECRET_KEY_RE = re.compile(r"(api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password)", re.IGNORECASE)
PLACEHOLDER_SECRET_RE = re.compile(
    r"^(your[-_ ]?|example[-_ ]?|changeme|replaceme|test|dummy|placeholder)",
    re.IGNORECASE,
)


@dataclass
class DetectionResult:
    system: str
    config_path: Path
    model_settings: Dict[str, Any] = field(default_factory=dict)
    agent_settings: Dict[str, Any] = field(default_factory=dict)
    secrets: Dict[str, str] = field(default_factory=dict)


@dataclass
class SquidStoreImportResult:
    success: bool
    db_path: Optional[Path]
    source_system: str
    imported_secret_count: int = 0
    imported_settings_count: int = 0
    errors: List[str] = field(default_factory=list)


def _dedupe_paths(paths: Iterable[Path]) -> List[Path]:
    seen = set()
    out: List[Path] = []
    for p in paths:
        rp = p.expanduser().resolve()
        key = str(rp)
        if key in seen:
            continue
        seen.add(key)
        out.append(rp)
    return out


def _default_scan_roots() -> List[Path]:
    roots = [
        Path.home(),
        Path.home() / ".config",
        Path.cwd(),
    ]
    raw_extra = os.getenv("BUSY_BRIDGE_IMPORT_SCAN_DIRS", "").strip()
    if raw_extra:
        for part in raw_extra.split(","):
            part = part.strip()
            if part:
                roots.append(Path(part))
    return _dedupe_paths(roots)


def _flatten_dict(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (data or {}).items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.update(_flatten_dict(v, key))
        else:
            out[key] = v
    return out


def _parse_env_text(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        key = k.strip()
        val = v.strip().strip("\"").strip("'")
        if key:
            out[key] = val
    return out


def _parse_config(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    name = path.name.lower()

    if name == ".env":
        return _parse_env_text(text)

    if suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {}

    if suffix == ".json":
        data = json.loads(text or "{}")
        return data if isinstance(data, dict) else {}

    if suffix == ".toml" and tomllib is not None:
        data = tomllib.loads(text)
        return data if isinstance(data, dict) else {}

    # Fallback for extensionless configs.
    for parser in ("yaml", "json", "toml"):
        try:
            if parser == "yaml":
                data = yaml.safe_load(text) or {}
            elif parser == "json":
                data = json.loads(text or "{}")
            else:
                if tomllib is None:
                    continue
                data = tomllib.loads(text)
            if isinstance(data, dict):
                return data
        except Exception:
            continue

    return {}


def _normalize_key_name(key: str) -> str:
    out = re.sub(r"[^A-Za-z0-9]+", "_", str(key)).strip("_").lower()
    return out[:120] if out else "value"


def _is_probable_secret(key: str, value: Any) -> bool:
    if not isinstance(value, str):
        return False
    raw = value.strip()
    if len(raw) < 10:
        return False
    if PLACEHOLDER_SECRET_RE.match(raw):
        return False
    return bool(SECRET_KEY_RE.search(key))


def _extract_model_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    flat = _flatten_dict(data)
    out: Dict[str, Any] = {}

    key_map = {
        "model": [
            "model",
            "default_model",
            "llm.model",
            "models.default",
            "inference.model",
        ],
        "provider": [
            "provider",
            "llm.provider",
            "inference.provider",
        ],
        "base_url": [
            "base_url",
            "api_base",
            "llm.base_url",
            "inference.base_url",
        ],
        "temperature": [
            "temperature",
            "llm.temperature",
            "inference.temperature",
        ],
        "max_tokens": [
            "max_tokens",
            "llm.max_tokens",
            "inference.max_tokens",
        ],
    }

    for out_key, candidates in key_map.items():
        for c in candidates:
            if c in flat and flat[c] not in (None, ""):
                out[out_key] = flat[c]
                break

    return out


def _extract_agent_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    flat = _flatten_dict(data)
    out: Dict[str, Any] = {}
    key_map = {
        "agent_name": ["agent_name", "agent.name", "name", "profile.name"],
        "agent_id": ["agent_id", "agent.id", "id", "profile.id"],
        "persona": ["persona", "agent.persona", "profile.persona"],
        "role": ["role", "agent.role", "profile.role"],
    }
    for out_key, candidates in key_map.items():
        for c in candidates:
            if c in flat and flat[c] not in (None, ""):
                out[out_key] = flat[c]
                break
    return out


def _extract_secrets(data: Dict[str, Any]) -> Dict[str, str]:
    flat = _flatten_dict(data)
    out: Dict[str, str] = {}
    for key, value in flat.items():
        if _is_probable_secret(key, value):
            out[_normalize_key_name(key)] = str(value).strip()
    return out


def detect_installed_system_configs(
    *,
    source: Optional[str] = None,
    roots: Optional[List[Path]] = None,
) -> List[DetectionResult]:
    scan_roots = roots or _default_scan_roots()
    systems = [source] if source else sorted(SYSTEM_CONFIG_CANDIDATES.keys())
    out: List[DetectionResult] = []

    for system in systems:
        if not system:
            continue
        candidates = SYSTEM_CONFIG_CANDIDATES.get(system, [])
        if not candidates:
            continue
        for root in scan_roots:
            for rel in candidates:
                cfg_path = root / rel
                if not cfg_path.exists() or not cfg_path.is_file():
                    continue
                try:
                    data = _parse_config(cfg_path)
                except Exception:
                    continue
                model_settings = _extract_model_settings(data)
                agent_settings = _extract_agent_settings(data)
                secrets = _extract_secrets(data)
                if not model_settings and not agent_settings and not secrets:
                    continue
                out.append(
                    DetectionResult(
                        system=system,
                        config_path=cfg_path.resolve(),
                        model_settings=model_settings,
                        agent_settings=agent_settings,
                        secrets=secrets,
                    )
                )
    return out


def _resolve_keystore_class() -> Optional[type[Any]]:
    # `key_store` is a common module name; we may already have a different library
    # installed that occupies it. For SquidKeys, we force-load the local repo
    # modules under the real `key_store.*` names temporarily so imports resolve.

    candidates: List[Path] = []
    raw = os.getenv("BUSY_BRIDGE_KEY_STORE_SRC", "").strip()
    if raw:
        candidates.append(Path(raw))

    candidates.extend(
        [
            Path("/home/lynn/projects/key-store/src"),
            Path.cwd().parent / "key-store" / "src",
            Path.cwd() / "key-store" / "src",
        ]
    )

    for base in candidates:
        src = base.expanduser().resolve()
        pkg_dir = src / "key_store"
        models_py = pkg_dir / "models.py"
        store_py = pkg_dir / "store.py"
        if not (models_py.exists() and store_py.exists()):
            continue

        saved: Dict[str, Any] = {}
        for k in list(sys.modules.keys()):
            if k == "key_store" or k.startswith("key_store."):
                saved[k] = sys.modules.get(k)
                del sys.modules[k]

        try:
            # Create an importable package shell for key_store.
            pkg = types.ModuleType("key_store")
            pkg.__path__ = [str(pkg_dir)]  # type: ignore[attr-defined]
            pkg.__package__ = "key_store"
            sys.modules["key_store"] = pkg

            # Load key_store.models
            spec_m = importlib.util.spec_from_file_location("key_store.models", str(models_py))
            if spec_m is None or spec_m.loader is None:
                continue
            mod_m = importlib.util.module_from_spec(spec_m)
            sys.modules["key_store.models"] = mod_m
            spec_m.loader.exec_module(mod_m)  # type: ignore[attr-defined]

            # Load key_store.store
            spec_s = importlib.util.spec_from_file_location("key_store.store", str(store_py))
            if spec_s is None or spec_s.loader is None:
                continue
            mod_s = importlib.util.module_from_spec(spec_s)
            sys.modules["key_store.store"] = mod_s
            spec_s.loader.exec_module(mod_s)  # type: ignore[attr-defined]

            ks = getattr(mod_s, "KeyStore", None)
            if ks is not None:
                return ks
        except Exception:
            continue
        finally:
            # Restore any previously-loaded key_store modules to avoid contaminating other imports.
            for k in list(sys.modules.keys()):
                if k == "key_store" or k.startswith("key_store."):
                    del sys.modules[k]
            for k, v in saved.items():
                if v is not None:
                    sys.modules[k] = v

    return None


def import_detection_to_squid_store(
    detection: DetectionResult,
    *,
    target_agent_id: str = "busy-bridge",
    actor: str = "busy-bridge",
    db_path: Optional[Path] = None,
    import_secrets: bool = True,
    import_settings: bool = True,
) -> SquidStoreImportResult:
    keystore_cls = _resolve_keystore_class()
    resolved_db = Path(db_path or os.getenv("SQUIDKEYS_DB_PATH", "./data/keystore.duckdb")).expanduser().resolve()

    if keystore_cls is None:
        return SquidStoreImportResult(
            success=False,
            db_path=resolved_db,
            source_system=detection.system,
            errors=[
                "key_store module not available. Install key-store (recommended: pip install -e ../key-store) and ensure duckdb+cryptography are installed."
            ],
        )

    imported_secret_count = 0
    imported_settings_count = 0
    errors: List[str] = []

    try:
        try:
            # Some distributions may not accept db_path as a keyword argument.
            store = keystore_cls(str(resolved_db))
        except TypeError:
            store = keystore_cls(db_path=str(resolved_db))
    except Exception as exc:
        return SquidStoreImportResult(
            success=False,
            db_path=resolved_db,
            source_system=detection.system,
            errors=[f"failed to initialize squid store: {exc}"],
        )

    try:
        if import_secrets:
            for name, value in sorted((detection.secrets or {}).items()):
                try:
                    store.save_password(
                        agent_id=target_agent_id,
                        name=f"import.{detection.system}.{name}",
                        password=str(value),
                        metadata={
                            "source_system": detection.system,
                            "source_path": str(detection.config_path),
                            "imported_by": actor,
                            "kind": "secret",
                        },
                        actor=actor,
                    )
                    imported_secret_count += 1
                except Exception as exc:
                    errors.append(f"secret {name}: {exc}")

        # Always store a settings payload record if requested, even if empty,
        # so the import event is discoverable/auditable.
        if import_settings:
            payload = {
                "source_system": detection.system,
                "source_path": str(detection.config_path),
                "model_settings": detection.model_settings,
                "agent_settings": detection.agent_settings,
            }
            try:
                store.save_password(
                    agent_id=target_agent_id,
                    name=f"import.{detection.system}.settings",
                    password=json.dumps(payload, ensure_ascii=True, sort_keys=True),
                    metadata={
                        "source_system": detection.system,
                        "source_path": str(detection.config_path),
                        "imported_by": actor,
                        "kind": "settings",
                    },
                    actor=actor,
                )
                imported_settings_count += 1
            except Exception as exc:
                errors.append(f"settings payload: {exc}")
    finally:
        try:
            store.close()
        except Exception:
            pass

    return SquidStoreImportResult(
        success=len(errors) == 0,
        db_path=resolved_db,
        source_system=detection.system,
        imported_secret_count=imported_secret_count,
        imported_settings_count=imported_settings_count,
        errors=errors,
    )
