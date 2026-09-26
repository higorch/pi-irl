"""Persistência: config.json + variáveis do arquivo .env."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.models.stream_config import StreamConfig

CONFIG_FILENAME = "config.json"
ENV_FILENAME = ".env"
ENV_EXAMPLE_FILENAME = ".env.example"

# Chaves do .env → campos do StreamConfig
_ENV_MAP: dict[str, str] = {
    "VPS_HOST": "vps_host",
    "SRT_PORT": "srt_port",
    "STREAM_ID": "stream_id",
    "BONDING_SERVER": "bonding_server",
    "BONDING_PORT": "bonding_port",
    "BONDING_UUID": "bonding_uuid",
}


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return project_root() / CONFIG_FILENAME


def env_path() -> Path:
    return project_root() / ENV_FILENAME


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    """Lê .env simples (KEY=VALUE). Não sobrescreve variáveis já no ambiente."""
    file_path = path or env_path()
    values: dict[str, str] = {}
    if not file_path.exists():
        return values

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return values

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        values[key] = value
        if key not in os.environ:
            os.environ[key] = value
    return values


def _apply_env(config: StreamConfig, env: dict[str, str]) -> StreamConfig:
    data = config.to_dict()
    for env_key, field in _ENV_MAP.items():
        raw = (env.get(env_key) or os.environ.get(env_key) or "").strip()
        if not raw:
            continue
        if field in ("srt_port", "bonding_port", "bitrate_kbps", "fps", "gop", "audio_channels", "sample_rate"):
            try:
                data[field] = int(raw)
            except ValueError:
                continue
        else:
            data[field] = raw
    return StreamConfig.from_dict(data)


def load_config() -> StreamConfig:
    """config.json (se existir) + overlay do .env / ambiente."""
    env = load_dotenv()
    config = StreamConfig()

    path = config_path()
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                config = StreamConfig.from_dict(data)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            config = StreamConfig()

    return _apply_env(config, env)


def save_config(config: StreamConfig) -> None:
    path = config_path()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config.to_dict(), handle, indent=2, ensure_ascii=False)
