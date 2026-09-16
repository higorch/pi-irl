"""Persistência local da configuração em JSON."""

from __future__ import annotations

import json
from pathlib import Path

from app.models.stream_config import StreamConfig

CONFIG_FILENAME = "config.json"


def config_path() -> Path:
    """Caminho do arquivo de configuração ao lado do projeto."""
    return Path(__file__).resolve().parent.parent / CONFIG_FILENAME


def load_config() -> StreamConfig:
    path = config_path()
    if not path.exists():
        return StreamConfig()

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return StreamConfig()
        return StreamConfig.from_dict(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return StreamConfig()


def save_config(config: StreamConfig) -> None:
    path = config_path()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config.to_dict(), handle, indent=2, ensure_ascii=False)
