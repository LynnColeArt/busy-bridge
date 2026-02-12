"""Detection and import of model settings from other agent systems."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

try:
    import tomllib
except Exception:  # pragma: no cover
    tomllib = None


SYSTEM_CONFIG_CANDIDATES: Dict[str, List[str]] = {
    # OpenClaw variants
    "openclaw": [
        ".config/openclaw/config.yaml",
        ".config/openclaw/config.yml",
        ".openclaw/config.yaml",
        ".openclaw/config.yml",
    ],
    # Busy/bridge-adjacent systems we may want to bootstrap from
    "blossom": [
        ".config/blossom/config.yaml",
        ".config/blossom/config.yml",
    ],
    "busy": [
        ".config/busy/config.yaml",
        ".config/busy/config.yml",
    ],
    # Generic LLM proxy tools
    "openwebui": [
        ".config/openwebui/config.json",
    ],
    "litellm": [
        ".config/litellm/config.yaml",
        ".config/litellm/config.yml",
    ],
}


@dataclass
class DetectionResult:
    system: str
    config_path: Path
    model_settings: Dict[str, Any]


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


def _parse_config(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {}
    if suffix == ".json":
        data = json.loads(text or "{}")
        return data if isinstance(data, dict) else {}
    if suffix == ".toml" and tomllib is not None:
        data = tomllib.loads(text)
        return data if isinstance(data, dict) else {}
    return {}


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
                if not model_settings:
                    continue
                out.append(
                    DetectionResult(
                        system=system,
                        config_path=cfg_path,
                        model_settings=model_settings,
                    )
                )
    return out
