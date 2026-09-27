"""Persistência: config.json + variáveis do arquivo .env."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
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

SUDO_PASSWORD_ENV = "PI_SUDO_PASSWORD"
# Segredos não vão para os.environ: senão FFmpeg e demais processos filhos os herdariam.
_SECRET_ENV_KEYS = frozenset({SUDO_PASSWORD_ENV})
_exported_secrets: dict[str, str] = {}


@dataclass(frozen=True)
class AppSettings:
    """Ajustes do app que não fazem parte do perfil de transmissão."""

    # Início automático no boot: tentativas de conectar câmera/mic USB (0 = sem limite)
    device_retry_attempts: int = 10
    device_retry_interval_s: int = 10


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return project_root() / CONFIG_FILENAME


def env_path() -> Path:
    return project_root() / ENV_FILENAME


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    """Lê .env simples (KEY=VALUE). Não sobrescreve variáveis já no ambiente."""
    for key in _SECRET_ENV_KEYS:
        if key in os.environ:
            _exported_secrets[key] = os.environ.pop(key)

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
        if key not in os.environ and key not in _SECRET_ENV_KEYS:
            os.environ[key] = value
    return values


def sudo_password() -> str:
    """Senha do sudo do Pi (PI_SUDO_PASSWORD no .env ou exportada). Vazio = sudo sem senha."""
    values = load_dotenv()
    return values.get(SUDO_PASSWORD_ENV) or _exported_secrets.get(SUDO_PASSWORD_ENV, "")


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


def _env_int(key: str, default: int, *, minimum: int) -> int:
    try:
        return max(minimum, int((os.environ.get(key) or "").strip()))
    except ValueError:
        return default


def load_app_settings() -> AppSettings:
    load_dotenv()
    defaults = AppSettings()
    return AppSettings(
        device_retry_attempts=_env_int(
            "DEVICE_RETRY_ATTEMPTS", defaults.device_retry_attempts, minimum=0
        ),
        device_retry_interval_s=_env_int(
            "DEVICE_RETRY_INTERVAL", defaults.device_retry_interval_s, minimum=2
        ),
    )


def save_config(config: StreamConfig) -> None:
    path = config_path()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config.to_dict(), handle, indent=2, ensure_ascii=False)
