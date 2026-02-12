"""Configuration management for Busy Bridge."""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml


@dataclass
class Config:
    """Busy Bridge configuration."""
    
    url: str = "http://localhost:8080"
    api_key: Optional[str] = None
    agent_id: str = "busy-bridge"
    timeout: int = 60
    model_settings: Dict[str, Any] = field(default_factory=dict)
    imported_from: Optional[str] = None
    imported_at: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            url=os.getenv("BUSY38_URL", "http://localhost:8080"),
            api_key=os.getenv("BUSY38_API_KEY"),
            agent_id=os.getenv("BUSY38_AGENT_ID", "busy-bridge"),
            timeout=int(os.getenv("BUSY38_TIMEOUT", "60")),
        )
    
    @classmethod
    def from_file(cls, path: Optional[Union[Path, str]] = None) -> "Config":
        """Load configuration from YAML file."""
        if path is None:
            path = Path.home() / ".config" / "busy-bridge" / "config.yaml"
        else:
            path = Path(path)
        
        if not path.exists():
            return cls.from_env()
        
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        
        # Environment variables override file config
        env_config = cls.from_env()
        
        return cls(
            url=data.get("url", env_config.url),
            api_key=data.get("api_key", env_config.api_key),
            agent_id=data.get("agent_id", env_config.agent_id),
            timeout=data.get("timeout", env_config.timeout),
            model_settings=data.get("model_settings", {}) or {},
            imported_from=data.get("imported_from"),
            imported_at=data.get("imported_at"),
        )
    
    @classmethod
    def load(cls) -> "Config":
        """Load configuration from all sources (file + env override)."""
        return cls.from_file()

    @staticmethod
    def default_path() -> Path:
        return Path.home() / ".config" / "busy-bridge" / "config.yaml"

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "url": self.url,
            "agent_id": self.agent_id,
            "timeout": self.timeout,
            "model_settings": self.model_settings or {},
        }
        if self.api_key:
            out["api_key"] = self.api_key
        if self.imported_from:
            out["imported_from"] = self.imported_from
        if self.imported_at:
            out["imported_at"] = self.imported_at
        return out

    def save(self, path: Optional[Union[Path, str]] = None) -> Path:
        save_path = Path(path) if path is not None else self.default_path()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.to_dict(), f, sort_keys=True)
        return save_path

    def apply_model_import(self, source: str, settings: Dict[str, Any]) -> None:
        if not settings:
            return
        self.model_settings.update(settings)
        self.imported_from = source
        self.imported_at = datetime.now(timezone.utc).isoformat()
