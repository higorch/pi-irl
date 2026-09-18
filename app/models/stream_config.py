"""Modelo de configuração da transmissão e geração da URL SRT."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum


STREAM_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class StreamStatus(str, Enum):
    OFFLINE = "OFFLINE"
    STARTING = "STARTING"
    LIVE = "LIVE"
    STOPPING = "STOPPING"
    ERROR = "ERROR"

    @property
    def label_pt(self) -> str:
        labels = {
            StreamStatus.OFFLINE: "Offline",
            StreamStatus.STARTING: "Iniciando",
            StreamStatus.LIVE: "Ao vivo",
            StreamStatus.STOPPING: "Parando",
            StreamStatus.ERROR: "Erro",
        }
        return labels[self]


@dataclass
class StreamConfig:
    vps_host: str = ""
    srt_port: int = 8890
    stream_id: str = "irl"
    camera: str = ""
    resolution: str = "1280x720"
    fps: int = 24
    bitrate_kbps: int = 4000
    microphone: str = ""
    audio_channels: int = 1
    sample_rate: int = 48000
    gop: int = 48

    def build_srt_url(self) -> str:
        """Monta a URL SRT dinamicamente a partir de host, porta e stream id."""
        host = self.vps_host.strip()
        stream_id = self.stream_id.strip()
        return (
            f"srt://{host}:{self.srt_port}"
            f"?mode=caller&streamid=publish:{stream_id}"
        )

    def build_rtsp_url(self) -> str:
        """URL RTSP esperada no MediaMTX (apenas informativa)."""
        host = self.vps_host.strip()
        stream_id = self.stream_id.strip()
        return f"rtsp://{host}:8554/{stream_id}"

    def validate(self) -> list[str]:
        """Retorna lista de erros de validação (vazia se tudo ok)."""
        errors: list[str] = []

        if not self.vps_host.strip():
            errors.append("Informe o host URL/IP.")

        if self.srt_port < 1 or self.srt_port > 65535:
            errors.append("Porta SRT inválida.")

        stream_id = self.stream_id.strip()
        if not stream_id:
            errors.append("Informe o ID da transmissão.")
        elif not STREAM_ID_PATTERN.fullmatch(stream_id):
            errors.append(
                "ID da transmissão inválido. Use apenas letras, números, _ e -."
            )

        if not self.camera.strip():
            errors.append("Nenhuma câmera selecionada.")

        if not self.microphone.strip():
            errors.append("Nenhum microfone selecionado.")

        if not re.fullmatch(r"\d+x\d+", self.resolution.strip()):
            errors.append("Resolução inválida. Use o formato LARGURAxALTURA.")

        if self.fps < 1 or self.fps > 120:
            errors.append("FPS inválido.")

        if self.bitrate_kbps < 100:
            errors.append("Taxa de bits muito baixa.")

        if self.audio_channels not in (1, 2):
            errors.append("Canais de áudio devem ser 1 ou 2.")

        if self.gop < 1:
            errors.append("GOP inválido.")

        return errors

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> StreamConfig:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)
