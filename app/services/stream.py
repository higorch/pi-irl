"""Orquestração da transmissão IRL (+ bonding opcional)."""

from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, Signal

from app.models.stream_config import StreamConfig, StreamStatus
from app.services import bonding as bonding_service
from app.services.ffmpeg import FFmpegService


class StreamService(QObject):
    """Coordena status, validação, bonding opcional e FFmpeg."""

    status_changed = Signal(str)
    log_line = Signal(str)
    validation_failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._status = StreamStatus.OFFLINE
        self._ffmpeg = FFmpegService(self)
        self._bonding = bonding_service.BondingManager(self)
        self._pending_config: StreamConfig | None = None
        self._user_stopping = False

        self._bonding.log_line.connect(self.log_line.emit)
        self._bonding.finished.connect(self._on_bonding_ready)
        self._ffmpeg.log_line.connect(self.log_line.emit)
        self._ffmpeg.started.connect(self._on_ffmpeg_started)
        self._ffmpeg.finished.connect(self._on_ffmpeg_finished)
        self._ffmpeg.error_occurred.connect(self._on_ffmpeg_error)

    @property
    def status(self) -> StreamStatus:
        return self._status

    @property
    def bonding_busy(self) -> bool:
        return self._bonding.busy

    @property
    def is_active(self) -> bool:
        return self._status in (
            StreamStatus.STARTING,
            StreamStatus.LIVE,
            StreamStatus.STOPPING,
        )

    def start(self, config: StreamConfig) -> bool:
        if self.is_active:
            self.validation_failed.emit("Já existe uma transmissão em andamento.")
            return False

        errors = config.validate()
        if not self._ffmpeg.ffmpeg_available():
            errors.append("FFmpeg não encontrado.")

        if errors:
            self.validation_failed.emit("\n".join(errors))
            return False

        if self._bonding.busy:
            self.validation_failed.emit(
                "Aguarde: o bonding ainda está sendo configurado em segundo plano."
            )
            return False

        self._user_stopping = False
        self._set_status(StreamStatus.STARTING)

        camera = config.camera.strip()
        mic = config.microphone.strip()
        channels = "estéreo" if config.audio_channels >= 2 else "mono"
        self.log_line.emit(
            f"Câmera: {camera} · Mic: {mic} ({channels}) · "
            f"{config.resolution}@{config.fps} · {config.bitrate_kbps} kbps"
        )

        if config.bonding_configured:
            self._pending_config = config
            self._bonding.prepare(
                config.bonding_server,
                config.bonding_port,
                config.bonding_uuid,
            )
        else:
            self.log_line.emit(
                "Bonding opcional não configurado — transmitindo sem agregação."
            )
            self._launch_ffmpeg(config)
        return True

    def stop(self) -> None:
        if self._pending_config is not None:
            self._pending_config = None
            self._set_status(StreamStatus.OFFLINE)
            self.log_line.emit(
                "Transmissão cancelada — o bonding termina de configurar em segundo plano."
            )
            return

        if not self.is_active and not self._ffmpeg.is_running():
            return

        self._user_stopping = True
        self._set_status(StreamStatus.STOPPING)
        self._ffmpeg.stop()

    def _on_bonding_ready(self, _ok: bool, message: str) -> None:
        self.log_line.emit(message)
        config, self._pending_config = self._pending_config, None
        if config is None or self._status != StreamStatus.STARTING:
            return
        self._launch_ffmpeg(config)

    def _launch_ffmpeg(self, config: StreamConfig) -> None:
        self.log_line.emit(
            f"Publicando SRT → {config.vps_host.strip()}:{config.srt_port} / "
            f"{config.stream_id.strip()}"
        )
        self._ffmpeg.start(config)

    def _set_status(self, status: StreamStatus) -> None:
        self._status = status
        self.status_changed.emit(status.value)

    def _on_ffmpeg_started(self) -> None:
        self._set_status(StreamStatus.LIVE)

    def _on_ffmpeg_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        if self._user_stopping:
            self._set_status(StreamStatus.OFFLINE)
            self.log_line.emit("Transmissão encerrada.")
            self._user_stopping = False
            return

        if exit_status == QProcess.ExitStatus.CrashExit or exit_code != 0:
            self._set_status(StreamStatus.ERROR)
            hint = ""
            if exit_code in (1, 251, 4294967041):
                hint = (
                    " Confira câmera/mic, canais ALSA e Host/SRT da VPS."
                )
            self.log_line.emit(
                f"Transmissão falhou (código {exit_code}).{hint}"
            )
        else:
            self._set_status(StreamStatus.OFFLINE)
            self.log_line.emit("Transmissão finalizada.")

    def _on_ffmpeg_error(self, message: str) -> None:
        self._set_status(StreamStatus.ERROR)
        self.log_line.emit(message)
