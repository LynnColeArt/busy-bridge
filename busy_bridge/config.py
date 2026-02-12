"""Configuration management for Busy Bridge."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class Config:
    """Busy Bridge configuration."""
    
    url: str = "http://localhost:8080"
    api_key: Optional[str] = None
    agent_id: str = "busy-bridge"
    timeout: int = 60
    
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
    def from_file(cls, path: Optional[Path] = None) -> "Config":
        """Load configuration from YAML file."""
        if path is None:
            path = Path.home() / ".config" / "busy-bridge" / "config.yaml"
        
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
        )
    
    @classmethod
    def load(cls) -> "Config":
        """Load configuration from all sources (file + env override)."""
        return cls.from_file()
